from __future__ import annotations
from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # DB
    db_host: str
    db_port: int = 3306
    db_name: str
    db_user: str
    db_password: str

    # REDIS
    redis_host: str
    redis_port: int = 6379

    # APP
    node_id: str = "unknown"
    debug: bool = False

    @computed_field
    @property
    def database_url(self) -> str:
        return(
            f"mysql+aiomysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"
    model_config = {"extra": "ignore"}

@lru_cache
def get_settings() -> Settings:
    return Settings()