from __future__ import annotations

"""Cloudflare SSL certificate helpers."""

from dataclasses import dataclass
from typing import Iterable, List, Sequence

import requests

from ..config import CloudflareConfig
from .settings import get_settings

API_BASE_URL = "https://api.cloudflare.com/client/v4"
REQUEST_TIMEOUT = 15


class CloudflareError(RuntimeError):
    """Raised when Cloudflare API returns an error."""


@dataclass
class CertificatePack:
    id: str
    type: str
    status: str
    hosts: Sequence[str]
    certificates: Sequence[dict]
    created_on: str | None = None
    expires_on: str | None = None

    @classmethod
    def from_api(cls, payload: dict) -> "CertificatePack":
        certificates = payload.get("certificates") or []
        primary = certificates[0] if certificates else {}
        return cls(
            id=payload.get("id", ""),
            type=payload.get("type", ""),
            status=payload.get("status", ""),
            hosts=payload.get("hosts") or [],
            certificates=certificates,
            created_on=payload.get("created_on"),
            expires_on=primary.get("expires_on"),
        )


def format_errors(data: dict) -> str:
    errors = data.get("errors") or []
    if not errors:
        return "Cloudflare API isteği başarısız oldu."
    return ", ".join(f"{err.get('code')}: {err.get('message')}" for err in errors)


def build_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    auth_email = CloudflareConfig.auth_email
    auth_key = CloudflareConfig.auth_key
    bearer = CloudflareConfig.api_token

    if auth_email and auth_key:
        headers.update({"X-Auth-Email": auth_email, "X-Auth-Key": auth_key})
        return headers

    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
        return headers

    raise CloudflareError("Cloudflare API bilgileri eksik (.env dosyanızı kontrol edin).")


def require_zone_id() -> str:
    zone_id = CloudflareConfig.zone_id
    if not zone_id:
        raise CloudflareError("CLOUDFLARE_ZONE_ID tanımlı değil.")
    return zone_id


def fetch_certificate_packs() -> List[CertificatePack]:
    """Return the current SSL certificate packs for the configured zone."""

    zone_id = require_zone_id()
    response = requests.get(
        f"{API_BASE_URL}/zones/{zone_id}/ssl/certificate_packs",
        headers=build_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    data = response.json()
    if not response.ok or not data.get("success"):
        raise CloudflareError(format_errors(data))
    return [CertificatePack.from_api(item) for item in data.get("result", [])]


def _default_host_list() -> list[str]:
    settings = get_settings()
    hosts_str = settings.get("ssl_hosts", "")
    return [host.strip() for host in hosts_str.split(",") if host.strip()]


def order_advanced_certificate(hosts: Iterable[str] | None = None, validity_days: int = 90) -> dict:
    """Create a new advanced certificate pack for the provided hosts.

    Args:
        hosts: Optional iterable of hostnames. Falls back to CLOUDFLARE_SSL_HOSTS.
        validity_days: Desired validity period. Cloudflare currently supports 30/90.
    """

    resolved_hosts = hosts if hosts else _default_host_list() or CloudflareConfig.ssl_hosts
    host_list = [host.strip() for host in resolved_hosts if host and host.strip()]
    if not host_list:
        raise CloudflareError("Cloudflare SSL host list boş olamaz.")

    zone_id = require_zone_id()
    payload = {
        "type": "advanced",
        "hosts": host_list,
        "validation_method": "txt",
        "validity_days": validity_days,
    }
    response = requests.post(
        f"{API_BASE_URL}/zones/{zone_id}/ssl/certificate_packs",
        json=payload,
        headers=build_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    data = response.json()
    if not response.ok or not data.get("success"):
        raise CloudflareError(format_errors(data))
    return data.get("result", {})


def configured_host_list() -> list[str]:
    hosts = _default_host_list()
    return hosts if hosts else CloudflareConfig.ssl_hosts


__all__ = [
    "CertificatePack",
    "CloudflareError",
    "fetch_certificate_packs",
    "order_advanced_certificate",
    "API_BASE_URL",
    "REQUEST_TIMEOUT",
    "build_headers",
    "require_zone_id",
    "format_errors",
    "configured_host_list",
]
