from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    api_name: str = Field(default="bwe-embedding-server", alias="API_NAME")
    api_version: str = Field(default="0.1.0", alias="API_VERSION")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8090, alias="API_PORT")
    app_env: str = Field(default="development", alias="APP_ENV")

    model_path: str = Field(default="nomic-ai/nomic-embed-multimodal-3b", alias="MODEL_PATH")
    model_device: str = Field(default="cuda", alias="MODEL_DEVICE")

    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding = "utf-8",
        case_sensitive = False,
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()