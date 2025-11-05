from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = Field(..., description="PostgreSQL connection string")
    mlflow_tracking_uri: str = Field(default="http://localhost:5001")
    model_registry_name: str = Field(default="alertiq-lgbm")
    severity_threshold: float = Field(default=0.5)


def get_settings() -> Settings:
    return Settings()
