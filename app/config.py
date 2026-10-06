import os
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    wc_store_url: str
    wc_consumer_key: str
    wc_consumer_secret: str

    # Pagination limits
    max_per_page: int = 100
    default_per_page: int = 20

    # HTTP timeouts in seconds
    connect_timeout: float = 5.0
    read_timeout: float = 30.0

    # Retry config
    max_retries: int = 3
    retry_backoff_base: float = 1.0  # seconds; delay = base * 2^attempt

    @field_validator("wc_store_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
