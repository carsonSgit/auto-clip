from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://autoclip:autoclip@postgres:5432/autoclip"
    redis_url: str = "redis://redis:6379/0"

    data_dir: Path = Path("/data")
    output_dir: Path = Path("/outputs")
    brandkit_dir: Path = Path("/app/brandkit")

    whisper_model: str = "small"
    whisper_compute_type: str = "int8"

    # Wrapped in SecretStr so the key never leaks into logs or repr().
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-4-6"

    render_parallelism: int = 2  # concurrent ffmpeg renders; ffmpeg is itself multithreaded

    # Reject uploads larger than this (defense against disk exhaustion).
    max_upload_mb: int = 1024
    upload_free_space_reserve_mb: int = 1536

    default_clip_count: int = 4
    min_clip_seconds: int = 20
    max_clip_seconds: int = 90

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def work_dir(self) -> Path:
        return self.data_dir / "work"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def upload_free_space_reserve_bytes(self) -> int:
        return self.upload_free_space_reserve_mb * 1024 * 1024

    @property
    def anthropic_enabled(self) -> bool:
        return bool(self.anthropic_api_key.get_secret_value())


settings = Settings()
