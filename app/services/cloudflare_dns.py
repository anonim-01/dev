from __future__ import annotations

"""Cloudflare DNS helper utilities."""

from typing import Iterable, List

import requests

from ..config import CloudflareConfig
from .cloudflare_ssl import (
    API_BASE_URL,
    REQUEST_TIMEOUT,
    CloudflareError,
    build_headers,
    format_errors,
    require_zone_id,
)


def _request(method: str, path: str, *, params: dict | None = None, json: dict | None = None) -> dict:
    response = requests.request(
        method,
        f"{API_BASE_URL}{path}",
        headers=build_headers(),
        params=params,
        json=json,
        timeout=REQUEST_TIMEOUT,
    )
    data = response.json()
    if not response.ok or not data.get("success"):
        raise CloudflareError(format_errors(data))
    return data


def _find_dns_record(zone_id: str, host: str) -> dict | None:
    data = _request(
        "GET",
        f"/zones/{zone_id}/dns_records",
        params={"type": "A", "name": host, "page": 1, "per_page": 1},
    )
    result = data.get("result") or []
    return result[0] if result else None


def _determine_hosts(hosts: Iterable[str] | None) -> List[str]:
    if hosts is None:
        hosts = CloudflareConfig.ssl_hosts
    cleaned: list[str] = []
    for host in hosts:
        value = (host or "").strip()
        if not value:
            continue
        cleaned.append(value.lower())
    # Remove duplicates while preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for host in cleaned:
        if host in seen:
            continue
        seen.add(host)
        deduped.append(host)
    return deduped


def sync_a_records(ip_address: str, hosts: Iterable[str] | None = None, proxied: bool | None = None) -> list[dict]:
    if not ip_address:
        raise CloudflareError("Geçerli bir IP adresi bulunamadı.")
    zone_id = require_zone_id()
    resolved_hosts = _determine_hosts(hosts)
    if not resolved_hosts:
        raise CloudflareError("Güncellenecek Cloudflare DNS host listesi bulunamadı.")

    ttl = 120
    default_proxied = CloudflareConfig.auth_email or CloudflareConfig.api_token
    # proxied param None ise Cloudflare hesabınızın proxy'sini kullanmak için True'ya çekiyoruz.
    proxied_value = proxied if proxied is not None else True if default_proxied else False

    results: list[dict] = []
    for host in resolved_hosts:
        payload = {
            "type": "A",
            "name": host,
            "content": ip_address,
            "ttl": ttl,
            "proxied": proxied_value,
        }
        existing = _find_dns_record(zone_id, host)
        if existing:
            record_id = existing.get("id")
            _request("PUT", f"/zones/{zone_id}/dns_records/{record_id}", json=payload)
            results.append({"host": host, "action": "updated"})
        else:
            _request("POST", f"/zones/{zone_id}/dns_records", json=payload)
            results.append({"host": host, "action": "created"})
    return results


__all__ = ["sync_a_records"]
