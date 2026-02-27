import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel


class Settings(BaseModel):
    KIS_APP_KEY: str
    KIS_APP_SECRET: str
    KIS_ACCOUNT_NO: str
    KIS_ENV: Literal["mock", "live"]

    @classmethod
    def from_env(cls) -> "Settings":
        return cls.model_validate(
            {
                "KIS_APP_KEY": os.getenv("KIS_APP_KEY"),
                "KIS_APP_SECRET": os.getenv("KIS_APP_SECRET"),
                "KIS_ACCOUNT_NO": os.getenv("KIS_ACCOUNT_NO"),
                "KIS_ENV": os.getenv("KIS_ENV"),
            }
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
