from typing import List, Union
from pydantic import field_validator
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_PATH: str = str(Path(__file__).parent.parent.parent / "chatmeet.db")
    MEDIA_DIR: str = str(Path(__file__).parent.parent.parent / "media")
    LLM_MODEL_PATH: str = "Qwen2.5-1.5B-Instruct.Q8_0.gguf"
    LLM_SERVER_URL: str = "http://127.0.0.1:8080"
    LLM_TIMEOUT_SECONDS: int = 300
    LLM_MAX_TOKENS: int = 800
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"
    WORKER_POLL_INTERVAL: float = 2.0
    ENABLE_BACKGROUND_WORKER: bool = True
    MAX_UPLOAD_MB: int = 2000
    BOT_INGEST_TOKEN: str = "change-me"
    BOT_DISCONNECT_TIMEOUT_SECONDS: int = 600
    NO_SPEECH_PROB_THRESHOLD: float = 0.6
    AVG_LOGPROB_THRESHOLD: float = -1.0


    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
