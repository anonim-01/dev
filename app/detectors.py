from __future__ import annotations

from user_agents import parse


def detect_device(user_agent: str | None) -> str:
    ua = parse(user_agent or "")
    if ua.is_mobile:
        return "Mobil"
    if ua.is_tablet:
        return "Tablet"
    if ua.is_pc:
        return "Masaüstü"
    return "Bilinmiyor"


def detect_browser(user_agent: str | None) -> str:
    ua = parse(user_agent or "")
    browser = ua.browser.family or "Bilinmiyor"
    version = ua.browser.version_string or ""
    return browser if not version else f"{browser} {version}"
