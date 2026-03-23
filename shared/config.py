from __future__ import annotations
from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings

class Settings(BaseSettings): # LEGGE I VALORI DALLE VARIABILI D'AMBIENTE CHE SONO STATE DEFINITE NEL .YML
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

    @computed_field  # CAMPO CALCOLATO INTERNAMENTE, NON LETTO DALL'AMBIENTE
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

    model_config = {"extra": "ignore"} # IGNORA VARIABILI D'AMBIENTE AGGIUNTIVE TROVATE NEL .YML

@lru_cache # SERVE PER NON RILEGGERE L'AMBIENTE OGNI VOLTA
def get_settings() -> Settings:
    return Settings() # E' L'AMBIENTE CHE PASSA A LEI I VALORI INIETTATI DAL DOCKER, NON LO FACCIO IO A MANO