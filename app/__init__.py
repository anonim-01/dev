from __future__ import annotations

from flask import Flask

from .config import AppConfig, STATIC_DIR
from .ip_blocker import check_ip_blocked
from .routes.admin import admin_bp
from .routes.binlookup import binlookup_bp
from .routes.commands import commands_bp
from .routes.public import public_bp
from .services.settings import get_settings as get_app_settings


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/assets", template_folder="../templates")
    app.config["SECRET_KEY"] = AppConfig.secret_key

    # IP engelleme middleware'ini ekle
    app.before_request(check_ip_blocked)

    app.register_blueprint(public_bp)
    app.register_blueprint(commands_bp)
    app.register_blueprint(binlookup_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_app_settings():  # pragma: no cover - template helper
        return {"app_settings": get_app_settings()}

    return app
