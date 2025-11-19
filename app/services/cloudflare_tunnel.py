from __future__ import annotations

"""Helpers to manage cloudflared connector commands and logs."""

from pathlib import Path
from typing import Iterable, List

from ..config import BASE_DIR
from ..database import execute, fetch_all
from .process_runner import run_command

SCRIPTS_DIR = BASE_DIR / "scripts"
CONNECTOR_SCRIPT = SCRIPTS_DIR / "setup_cloudflared_connector.sh"


def _store_log(command: str, stdout: str, stderr: str, status: str) -> None:
    execute(
        "INSERT INTO cloudflared_logs (command, stdout, stderr, status) VALUES (?, ?, ?, ?)",
        (command, stdout, stderr, status),
    )


def _run_and_log(command: Iterable[str] | str) -> dict:
    result = run_command(command)
    status = "success" if result["returncode"] == 0 else "error"
    _store_log(result["command"], result["stdout"], result["stderr"], status)
    return result


def install_connector(token: str) -> dict:
    if not token:
        raise ValueError("Cloudflare tunnel token boş olamaz.")
    if not CONNECTOR_SCRIPT.exists():
        raise RuntimeError(f"Connector script bulunamadı: {CONNECTOR_SCRIPT}")
    command = ["bash", str(CONNECTOR_SCRIPT), token]
    return _run_and_log(command)


def run_status_checks() -> List[dict]:
    commands = [
        ["cloudflared", "--version"],
        ["ps", "-eo", "pid,cmd", "|", "grep", "cloudflared"],
    ]
    results: List[dict] = []
    for cmd in commands:
        if "|" in cmd:
            combined = " ".join(cmd)
            result = _run_and_log(["/bin/sh", "-c", combined])
        else:
            result = _run_and_log(cmd)
        results.append(result)
    return results


def run_custom_command(raw_command: str) -> dict:
    if not raw_command.strip():
        raise ValueError("Komut boş olamaz.")
    return _run_and_log(["/bin/sh", "-c", raw_command])


def get_recent_logs(limit: int = 50) -> List[dict]:
    return fetch_all(
        "SELECT id, command, stdout, stderr, status, created_at FROM cloudflared_logs ORDER BY id DESC LIMIT ?",
        (limit,),
    )


__all__ = [
    "install_connector",
    "run_status_checks",
    "run_custom_command",
    "get_recent_logs",
]
