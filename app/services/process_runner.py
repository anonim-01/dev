from __future__ import annotations

"""Utility helpers to run shell commands and capture output for audit logging."""

import shlex
import subprocess
from typing import Iterable, List, Sequence


def _normalize_command(command: Sequence[str] | str) -> List[str]:
    if isinstance(command, (list, tuple)):
        return [str(part) for part in command]
    return shlex.split(command)


def run_command(command: Sequence[str] | str, timeout: int = 120) -> dict:
    args = _normalize_command(command)
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": " ".join(shlex.quote(part) for part in args),
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


__all__ = ["run_command"]
