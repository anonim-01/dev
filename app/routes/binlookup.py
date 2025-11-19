from __future__ import annotations

import requests
from flask import Blueprint, request

binlookup_bp = Blueprint("binlookup", __name__)


@binlookup_bp.route("/bin-lookup", methods=["GET"])
def bin_lookup():
    """
    PHP'deki play.php dosyasının işlevini gören endpoint.
    BIN numarasını alır ve banka bilgilerini döndürür.
    """
    bin_code = request.args.get("bin", "").strip()
    if not bin_code or len(bin_code) != 6:
        return {"error": "Geçersiz BIN kodu"}, 400

    try:
        # lookup.binlist.net API'sini kullan
        response = requests.get(
            f"https://lookup.binlist.net/{bin_code}",
            headers={"User-Agent": "MyAgent/1.0"},
            timeout=5
        )
        response.raise_for_status()
        data = response.json()

        # Banka bilgilerini çıkar
        bank_info = data.get("bank", {})
        bank_name = bank_info.get("name", "")

        return {
            "type": data.get("type", ""),
            "brand": data.get("brand", ""),
            "bank_name": bank_name
        }
    except Exception as e:
        return {"error": f"BIN sorgulama hatası: {str(e)}"}, 500
