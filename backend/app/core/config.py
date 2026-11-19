from typing import List, Union
from pydantic import field_validator
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_PATH: str = str(Path(__file__).parent.parent.parent / "chatmeet.db")
    MEDIA_DIR: str = str(Path(__file__).parent.parent.parent / "media")
    LLM_MODEL_PATH: str = "Qwen2.5-1.5B-Instruct.Q8_0.gguf"
    WHISPER_MODEL: str = "base"
    MAX_UPLOAD_MB: int = 100


    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]
    @field_validator("CORS_ORIGINS", mode="before", check_fields=False)
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000"]
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
