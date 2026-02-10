from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    api_name: str = 'bwe-embedding-server'
    api_version: str = '0.1.0'
    api_host: str = '0.0.0.0'
    api_port: int = 8090
    app_env: str = 'development'

    model_path: str = 'nomic-ai/nomic-embed-multimodal-3b'
    model_device: str = 'cuda'

    model_config = SettingsConfigDict(
        env_file = '.env',
        env_file_encoding = 'utf-8',
        case_sensitive = False,
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()