import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from autoclip.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


# Pipeline stage order; a job's status is either one of these, "complete", or "failed".
STAGES = [
    "queued",
    "ingesting",
    "transcribing",
    "detecting_scenes",
    "selecting_highlights",
    "rendering",
    "finalizing",
]


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    source_filename: Mapped[str] = mapped_column(String(512))
    context_text: Mapped[str] = mapped_column(Text, default="")
    clip_count: Mapped[int] = mapped_column(Integer, default=4)
    min_clip_seconds: Mapped[int] = mapped_column(Integer, default=20)
    max_clip_seconds: Mapped[int] = mapped_column(Integer, default=90)

    status: Mapped[str] = mapped_column(String(32), default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    selector_used: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "llm" | "heuristic"

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    clips: Mapped[list["Clip"]] = relationship(back_populates="job", order_by="Clip.index")


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    index: Mapped[int] = mapped_column(Integer)
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    title: Mapped[str] = mapped_column(String(256), default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | rendered | failed

    job: Mapped[Job] = relationship(back_populates="clips")
