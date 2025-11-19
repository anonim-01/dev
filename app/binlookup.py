from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests

BIN_SERVICE_URL = "https://lookup.binlist.net/{bin}"
HEADERS = {"User-Agent": "pyhton-edevlet/1.0", "Accept-Version": "3"}

# Bank logo mapping (you can expand this with actual bank logos)
BANK_LOGOS = {
    "akbank": "🏦",  # Replace with actual logo URLs if available
    "garanti": "🏦",
    "is bankasi": "🏦",
    "halkbank": "🏦",
    "vakifbank": "🏦",
    "ziraat": "🏦",
    "yapi kredi": "🏦",
    "denizbank": "🏦",
    "ing": "🏦",
    "teb": "🏦",
    "hsbc": "🏦",
    "anadolubank": "🏦",
    "fibabanka": "🏦",
    "kuveytturk": "🏦",
    "alternatifbank": "🏦",
    "burgan": "🏦",
    "rabobank": "🏦",
    "sekerbank": "🏦",
    "turkish bank": "🏦",
    "icbc turkey": "🏦",
}


@lru_cache(maxsize=256)
def lookup_bank(bin_prefix: str | None) -> dict[str, Any]:
    if not bin_prefix or len(bin_prefix) < 6:
        return {}

    try:
        response = requests.get(BIN_SERVICE_URL.format(bin=bin_prefix), headers=HEADERS, timeout=5)
        if response.status_code == 200:
            data = response.json()  # type: ignore[return-value]
            # Add logo information
            if data.get("bank", {}).get("name"):
                bank_name_lower = data["bank"]["name"].lower()
                for bank_key, logo in BANK_LOGOS.items():
                    if bank_key in bank_name_lower:
                        data["bank"]["logo"] = logo
                        break
                else:
                    data["bank"]["logo"] = "🏦"  # Default logo
            return data
    except requests.RequestException:
        pass
    return {}
