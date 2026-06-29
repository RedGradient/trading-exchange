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

    postgres_db: str = "exchange"
    postgres_user: str = "exchange_user"
    postgres_password: str = "exchange_pass"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    database_url: str = (
        "postgresql+psycopg://exchange_user:exchange_pass@postgres:5432/exchange"
    )

    # AWS / LocalStack
    aws_region: str = "us-east-1"
    aws_endpoint_url: str = "http://localstack:4566"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def postgres_sync_dsn(self) -> str:
        """Sync DSN for Alembic migrations (psycopg2)."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        

settings = Settings()
