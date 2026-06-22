from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    environment: str = "local"
    log_level: str = "INFO"

    # Database
    database_url: str = (
        "postgresql+psycopg://exchange_user:exchange_pass@postgres:5432/exchange"
    )

    # AWS / LocalStack
    aws_region: str = "us-east-1"
    aws_endpoint_url: str = "http://localstack:4566"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"


_settings: Settings | None = None
def get_settings():
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
