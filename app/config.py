from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Floristería Yada API"
    debug: bool = False
    api_prefix: str = "/api"

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "yada"
    mysql_password: str = "yada"
    mysql_database: str = "yada_shop"

    jwt_secret: str = "change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    admin_email: str = "admin@yadacr.com"
    admin_password: str = "YadaAdmin123!"
    admin_full_name: str = "Administrador Yada"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Floristería Yada <info@yadacr.com>"
    smtp_use_tls: bool = True
    order_notify_email: str = "info@yadacr.com"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
