from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from flask import Response, make_response, render_template, url_for
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class EncryptedMarkup:
    ciphertext: str
    iv: str
    key: str
    mime: str = "text/html; charset=utf-8"


def _to_base64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("utf-8")


def _random_bytes(size: int) -> bytes:
    return os.urandom(size)


def encrypt_markup(markup: str) -> EncryptedMarkup:
    aes_key = _random_bytes(32)
    iv = _random_bytes(12)
    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(iv, markup.encode("utf-8"), None)
    return EncryptedMarkup(
        ciphertext=_to_base64(ciphertext),
        iv=_to_base64(iv),
        key=_to_base64(aes_key),
    )


def build_encrypted_response(markup: str) -> Response:
    payload = encrypt_markup(markup)
    shell = render_template(
        "_encrypted_wrapper.html",
        payload=payload,
        decryptor_url=url_for("static", filename="js/decryptor.js"),
    )
    response = make_response(shell)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["X-Content-Encrypted"] = "AES-256-GCM"
    return response


__all__ = ["EncryptedMarkup", "encrypt_markup", "build_encrypted_response"]
