from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://autoclip:autoclip@postgres:5432/autoclip"
    redis_url: str = "redis://redis:6379/0"

    data_dir: Path = Path("/data")
    output_dir: Path = Path("/outputs")
    brandkit_dir: Path = Path("/app/brandkit")

    whisper_model: str = "small"
    whisper_compute_type: str = "int8"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    default_clip_count: int = 4
    min_clip_seconds: int = 20
    max_clip_seconds: int = 90

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def work_dir(self) -> Path:
        return self.data_dir / "work"


settings = Settings()
