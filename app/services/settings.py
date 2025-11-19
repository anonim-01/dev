from __future__ import annotations

"""Application-level settings stored in the database."""

import os
from typing import Dict

from ..database import execute, fetch_all

DEFAULT_SETTINGS: Dict[str, str] = {
    "site_name": "Sanex Group",
    "local_ip": "127.0.0.1",
    "public_ip": os.getenv("SERVER_PUBLIC_IP", ""),
    "ssl_hosts": "sanexgroup.com",
}


def get_settings() -> Dict[str, str]:
    rows = fetch_all("SELECT key, value FROM app_settings")
    data = {row["key"]: row["value"] for row in rows}
    merged = DEFAULT_SETTINGS.copy()
    merged.update({k: v for k, v in data.items() if v is not None})
    return merged


def update_settings(updates: Dict[str, str]) -> None:
    sql = (
        "INSERT INTO app_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
    )
    for key, value in updates.items():
        execute(sql, (key, value))


def get_setting(key: str, default: str | None = None) -> str | None:
    settings = get_settings()
    return settings.get(key, default)


__all__ = ["get_settings", "update_settings", "get_setting", "DEFAULT_SETTINGS"]
