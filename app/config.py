from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = (BASE_DIR / "static").resolve()
ADMIN_STATIC_DIR = (STATIC_DIR / "admin").resolve()
BAN_REDIRECT_URL = "turkiye.gov.tr"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "on", "yes"}


class AppConfig:
    secret_key: str = os.getenv("FLASK_SECRET_KEY", "edevlet-dev-secret")
    database_url: str | None = os.getenv("DATABASE_URL")

    _database_path_raw = os.getenv("DATABASE_PATH")
    if _database_path_raw:
        database_path: Path = Path(_database_path_raw).expanduser().resolve()
    else:
        database_path = (BASE_DIR / "db.sqlite3").resolve()

    frontend_encryption_enabled: bool = _env_flag("FRONTEND_ENCRYPTION_ENABLED", True)


class CloudflareConfig:
    account_id: str | None = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token: str | None = os.getenv("CLOUDFLARE_API_TOKEN")
    auth_email: str | None = os.getenv("CLOUDFLARE_AUTH_EMAIL")
    auth_key: str | None = os.getenv("CLOUDFLARE_AUTH_KEY")
    zone_id: str | None = os.getenv("CLOUDFLARE_ZONE_ID")
    ssl_hosts: list[str] = [
        host.strip()
        for host in (os.getenv("CLOUDFLARE_SSL_HOSTS") or "").split(",")
        if host and host.strip()
    ]

__all__ = [
    "AppConfig",
    "BASE_DIR",
    "STATIC_DIR",
    "ADMIN_STATIC_DIR",
    "BAN_REDIRECT_URL",
    "_env_flag",
    "CloudflareConfig",
]
