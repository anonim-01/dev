from __future__ import annotations

"""Helpers for managing domain/subdomain alias mappings."""

import re
import secrets
import string
import uuid
from typing import Dict, List

from ..database import execute, fetch_all, fetch_one
from .settings import get_settings, update_settings

_SUBDOMAIN_SANITIZER = re.compile(r"[^a-z0-9-]")
_SCHEME_PREFIX = re.compile(r"^https?://", re.IGNORECASE)
_RANDOM_ALPHABET = string.ascii_lowercase + string.digits


def _normalize_domain(value: str) -> str:
    cleaned = (value or "").strip().lower()
    cleaned = _SCHEME_PREFIX.sub("", cleaned)
    if "/" in cleaned:
        cleaned = cleaned.split("/", 1)[0]
    return cleaned


def _normalize_subdomain(value: str | None) -> str:
    cleaned = (value or "").strip().lower().replace(" ", "-")
    return _SUBDOMAIN_SANITIZER.sub("", cleaned)


def _join_host(subdomain: str, base_domain: str) -> str:
    subdomain = subdomain.strip()
    if not subdomain:
        return base_domain
    return f"{subdomain}.{base_domain}" if base_domain else subdomain


def _host_to_url(host: str) -> str:
    return f"https://{host}" if host else ""


def _decorate_alias_row(row: Dict[str, str] | None) -> Dict[str, str]:
    if not row:
        return {}
    base = row.get("base_domain", "")
    real_sub = row.get("subdomain", "") or ""
    masked = row.get("masked_subdomain", "")
    target_host = _join_host(real_sub, base)
    masked_host = _join_host(masked, base)
    row["target_host"] = target_host
    row["masked_host"] = masked_host
    row["target_url"] = _host_to_url(target_host)
    row["masked_url"] = _host_to_url(masked_host)
    return row


def generate_masked_subdomain(length: int = 24) -> str:
    return "".join(secrets.choice(_RANDOM_ALPHABET) for _ in range(max(8, length)))


def _masked_exists(base_domain: str, masked_subdomain: str) -> bool:
    row = fetch_one(
        "SELECT 1 FROM domain_aliases WHERE base_domain=? AND masked_subdomain=? LIMIT 1",
        (base_domain, masked_subdomain),
    )
    return row is not None


def _sync_ssl_hosts(hosts: List[str]) -> None:
    normalized_hosts = [host.strip().lower() for host in hosts if host]
    if not normalized_hosts:
        return
    settings = get_settings()
    current_hosts = {
        item.strip().lower()
        for item in (settings.get("ssl_hosts") or "").split(",")
        if item and item.strip()
    }
    changed = False
    for host in normalized_hosts:
        if host not in current_hosts:
            current_hosts.add(host)
            changed = True
    if changed:
        update_settings({"ssl_hosts": ", ".join(sorted(current_hosts))})


def create_alias(base_domain: str, subdomain: str, masked_subdomain: str | None = None) -> Dict[str, str]:
    base = _normalize_domain(base_domain)
    if not base:
        raise ValueError("Geçerli bir ana domain girin (ör. sanexgroup.com).")
    real_subdomain = _normalize_subdomain(subdomain)
    masked = _normalize_subdomain(masked_subdomain) if masked_subdomain else ""
    if not masked:
        masked = generate_masked_subdomain()
    if _masked_exists(base, masked):
        attempts = 0
        while _masked_exists(base, masked) and attempts < 5:
            masked = generate_masked_subdomain()
            attempts += 1
        if _masked_exists(base, masked):
            raise ValueError("Benzersiz bir maskelenmiş subdomain üretilemedi. Lütfen tekrar deneyin.")
    alias_id = uuid.uuid4().hex
    execute(
        "INSERT INTO domain_aliases (id, base_domain, subdomain, masked_subdomain) VALUES (?, ?, ?, ?)",
        (alias_id, base, real_subdomain, masked),
    )
    _sync_ssl_hosts([
        _join_host(real_subdomain, base),
        _join_host(masked, base),
    ])
    alias = fetch_one(
        "SELECT id, base_domain, subdomain, masked_subdomain, created_at FROM domain_aliases WHERE id=?",
        (alias_id,),
    )
    return _decorate_alias_row(alias)


def list_aliases() -> List[Dict[str, str]]:
    rows = fetch_all(
        "SELECT id, base_domain, subdomain, masked_subdomain, created_at FROM domain_aliases ORDER BY created_at DESC"
    )
    return [_decorate_alias_row(row) for row in rows]


def delete_alias(alias_id: str) -> None:
    execute("DELETE FROM domain_aliases WHERE id=?", (alias_id,))


__all__ = [
    "create_alias",
    "delete_alias",
    "generate_masked_subdomain",
    "list_aliases",
]
