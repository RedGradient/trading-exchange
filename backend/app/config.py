from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    environment: str = "local"
    log_level: str = "INFO"

    jwt_secret_key: SecretStr | None = Field(default=None, min_length=32)
    jwt_access_token_minutes: int = Field(default=15, gt=0)
    jwt_refresh_token_days: int = Field(default=7, gt=0)
    auth_cookie_secure: bool = False
    ws_allowed_origins: list[str] = ["http://localhost:8000", "http://localhost:5173"]

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

    trades_queue_url: str = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/exchange-local-trades"
    trades_settled_topic_arn: str = (
        "arn:aws:sns:us-east-1:000000000000:exchange-local-trades-settled"
    )
    ws_fanout_queue_url: str = "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/exchange-local-ws-fanout"

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
