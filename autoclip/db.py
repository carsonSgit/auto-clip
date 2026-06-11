from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from autoclip.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    from autoclip import models  # noqa: F401  (register tables)

    Base.metadata.create_all(engine)
