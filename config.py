from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment configuration.

    Note there are no per-account Gmail credentials here — each user's
    Gmail address and app password are registered at runtime and stored
    (encrypted) in the database. This file only holds server-wide config.
    """

    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database URL
    DATABASE_URL: str = "sqlite:///./gmail_mcp.db"

    # Fernet key used to encrypt/decrypt every user's stored app password.
    ENCRYPTION_KEY: str

    # Background IMAP polling (applies across every registered account)
    INBOX_POLL_INTERVAL_SECONDS: int = 60
    ENABLE_BACKGROUND_POLLING: bool = True

    # Gmail SMTP/IMAP endpoints (fixed — identical for every user's account)
    GMAIL_SMTP_HOST: str = "smtp.gmail.com"
    GMAIL_SMTP_PORT: int = 587
    GMAIL_IMAP_HOST: str = "imap.gmail.com"
    GMAIL_IMAP_PORT: int = 993

    # Configuration for loading from .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Instantiate settings instance
settings = Settings()
