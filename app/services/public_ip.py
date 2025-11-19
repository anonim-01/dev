from __future__ import annotations

"""Utilities for discovering the current server's public IP address."""

from typing import Iterable

import requests

IP_ENDPOINTS: Iterable[tuple[str, str | None]] = (
    ("https://api.ipify.org?format=json", "ip"),
    ("https://ifconfig.co/json", "ip"),
    ("https://checkip.amazonaws.com", None),
    ("https://ipv4.icanhazip.com", None),
)

REQUEST_TIMEOUT = 5


def fetch_public_ip() -> str:
    last_error: Exception | None = None
    for url, field in IP_ENDPOINTS:
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            if field:
                data = response.json()
                value = (data or {}).get(field)
                if value:
                    return str(value).strip()
            else:
                return response.text.strip()
        except Exception as exc:  # pragma: no cover - relies on network
            last_error = exc
            continue
    raise RuntimeError(f"Public IP alınamadı: {last_error}")


__all__ = ["fetch_public_ip"]
