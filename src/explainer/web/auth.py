"""In-app authentication for the Study Lamp web UI.

A single shared password gates the whole site. Passwords are hashed with
scrypt; the login session is a short hmac-signed, timestamped cookie. No
server-side session store, so it stays compatible with the single-process,
in-memory-job deployment.
"""
import asyncio
import base64
import binascii
import hashlib
import hmac
import os
import time
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 64 * 1024 * 1024


def _scrypt(plaintext: str, salt: bytes) -> bytes:
    return hashlib.scrypt(plaintext.encode("utf-8"), salt=salt, n=_SCRYPT_N,
                          r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN,
                          maxmem=_SCRYPT_MAXMEM)


def hash_password(plaintext: str) -> str:
    """Return a self-describing "<b64salt>$<b64dk>" string for the password."""
    salt = os.urandom(16)
    dk = _scrypt(plaintext, salt)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(plaintext: str, stored: str) -> bool:
    """Constant-time check of a password against a stored hash. False if malformed."""
    try:
        salt_b64, dk_b64 = stored.split("$", 1)
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(dk_b64, validate=True)
    except (ValueError, binascii.Error):
        return False
    if not salt or not expected:
        return False
    return hmac.compare_digest(_scrypt(plaintext, salt), expected)


class SessionCodec:
    """Mints and validates hmac-signed, timestamped session cookies."""

    def __init__(self, secret_key: str, max_age_days: int = 30) -> None:
        self._key = secret_key.encode("utf-8")
        self._max_age = max_age_days * 86400

    def _sign(self, msg: str) -> str:
        return hmac.new(self._key, msg.encode("utf-8"), hashlib.sha256).hexdigest()

    def issue(self, now: float | None = None) -> str:
        ts = str(int(time.time() if now is None else now))
        return f"{ts}.{self._sign(ts)}"

    def read(self, cookie: str, now: float | None = None) -> bool:
        if not cookie or "." not in cookie:
            return False
        ts, sig = cookie.rsplit(".", 1)
        if not hmac.compare_digest(sig, self._sign(ts)):
            return False
        try:
            issued = int(ts)
        except ValueError:
            return False
        current = int(time.time() if now is None else now)
        return 0 <= current - issued <= self._max_age


COOKIE_NAME = "studylamp_session"
_PUBLIC_PREFIXES = ("/static",)
_PUBLIC_PATHS = ("/login", "/logout")
_FAILED_LOGIN_DELAY = 0.25  # seconds; blunts rapid password guessing


def install_auth(app, config) -> bool:
    """Wire the single-password gate onto the app. No-op (returns False) unless
    both a password hash and a secret key are configured."""
    if not (config.auth_password_hash and config.auth_secret_key):
        return False

    codec = SessionCodec(config.auth_secret_key, config.auth_session_days)
    login_html = (Path(__file__).parent / "static" / "login.html").read_text(encoding="utf-8")

    @app.middleware("http")
    async def _gate(request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS or path.startswith(_PUBLIC_PREFIXES):
            return await call_next(request)
        if codec.read(request.cookies.get(COOKIE_NAME, "")):
            return await call_next(request)
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Authentication required."}, status_code=401)
        return RedirectResponse("/login", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_page() -> str:
        return login_html

    @app.post("/login")
    async def login_submit(request: Request):
        form = await request.form()
        if verify_password(form.get("password", ""), config.auth_password_hash):
            resp = RedirectResponse("/", status_code=303)
            resp.set_cookie(COOKIE_NAME, codec.issue(), httponly=True,
                            samesite="lax", secure=config.auth_cookie_secure,
                            max_age=config.auth_session_days * 86400)
            return resp
        await asyncio.sleep(_FAILED_LOGIN_DELAY)
        return RedirectResponse("/login?error=1", status_code=303)

    @app.post("/logout")
    def logout():
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(COOKIE_NAME)
        return resp

    return True
