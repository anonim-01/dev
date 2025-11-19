#!/usr/bin/env python3
"""Fetch current public IP, persist it to .env, update app settings, and sync Cloudflare DNS."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.cloudflare_dns import CloudflareError, sync_a_records  # noqa: E402
from app.services.public_ip import fetch_public_ip  # noqa: E402
from app.services.settings import update_settings as update_app_settings  # noqa: E402

ENV_KEY = "SERVER_PUBLIC_IP"


def parse_hosts(raw_hosts: str | None) -> List[str]:
    if not raw_hosts:
        return []
    hosts = [item.strip() for item in raw_hosts.split(",")]
    return [host for host in hosts if host]


def update_env_file(env_path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()
    key_prefix = f"{key}="
    updated = False
    for idx, line in enumerate(lines):
        if line.startswith(key_prefix):
            lines[idx] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(BASE_DIR / ".env"), help=".env dosyasının yolu")
    parser.add_argument(
        "--hosts",
        default=None,
        help="Virgülle ayrılmış host listesi (varsayılan CLOUDFLARE_DNS_HOSTS veya CLOUDFLARE_SSL_HOSTS).",
    )
    parser.add_argument(
        "--skip-cloudflare",
        action="store_true",
        help="Cloudflare DNS kayıtlarını güncelleme.",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file)
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Yine de .env dosyası yoksa load_dotenv çalışmadığı için ortam değişkenlerinde mevcut değer olmayacak.
        pass

    ip_address = fetch_public_ip()
    update_env_file(env_path, ENV_KEY, ip_address)
    update_app_settings({"public_ip": ip_address})

    if args.skip_cloudflare:
        print(f"Public IP güncellendi: {ip_address} (Cloudflare atlandı)")
        return

    hosts_raw = args.hosts or os.getenv("CLOUDFLARE_DNS_HOSTS") or os.getenv("CLOUDFLARE_SSL_HOSTS")
    hosts = parse_hosts(hosts_raw)
    if not hosts:
        print("Cloudflare host listesi boş, DNS güncellemesi atlandı.")
        return
    try:
        sync_results = sync_a_records(ip_address, hosts)
    except CloudflareError as exc:
        print(f"Cloudflare DNS güncellenemedi: {exc}")
        raise SystemExit(1) from exc
    host_summary = ", ".join(f"{item['host']} ({item['action']})" for item in sync_results)
    print(f"Public IP {ip_address} olarak güncellendi ve Cloudflare DNS senkronize edildi: {host_summary}")


if __name__ == "__main__":
    main()
