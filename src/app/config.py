from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = 'development'
    api_host: str = '0.0.0.0'
    api_port: int = 8000

    app_name: str = 'bwe'
    debug: bool = False
    log_level: str = 'INFO'

    llama_host: str = '0.0.0.0'
    llama_port: int = 8080

    embedding_host: str = '0.0.0.0'
    embedding_port: int = 8090

    neo4j_uri: str = 'bolt://localhost:7687'
    neo4j_user: str
    neo4j_pwd: str
    neo4j_database: str

    model_config = SettingsConfigDict(
        env_file = '.env',
        env_file_encoding = 'utf-8',
        case_sensitive = False,
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()

