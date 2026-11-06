
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from . import paypal_client as pp  # noqa: F401 (loads .env)
from .db import conn, expire_reviews

router = APIRouter(tags=["auth"])

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_fails: dict = {}  # email -> (failed attempts, time of the first one)


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(
        pw.encode(),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(
            pw.encode(),
            salt=bytes.fromhex(salt),
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        )
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


_DUMMY = hash_password("not-a-real-password")


def create_user(name: str, email: str, password: str, role: str) -> dict:
    email = email.strip().lower()

    try:
        with conn() as c:
            if c.execute(
                "SELECT 1 FROM users WHERE email=?", (email,)
            ).fetchone():
                raise ValueError(
                    "An account with this email already exists"
                )

            c.execute(
                "INSERT INTO users (email, name, role, password_hash) "
                "VALUES (?,?,?,?)",
                (email, name.strip(), role, hash_password(password)),
            )

    except sqlite3.IntegrityError:
        raise ValueError(
            "An account with this email already exists"
        )

    return {
        "email": email,
        "name": name.strip(),
        "role": role,
    }


def current_user(request: Request):
    email = request.session.get("email")

    if not email:
        return None

    with conn() as c:
        r = c.execute(
            "SELECT email, name, role FROM users WHERE email=?",
            (email,),
        ).fetchone()

    return dict(r) if r else None


def require_user(request: Request, role: str | None = None) -> dict:
    u = current_user(request)

    if not u:
        raise HTTPException(401, "Please sign in")

    if role and u["role"] != role:
        raise HTTPException(
            403,
            f"This needs a {role} account",
        )

    return u


def require_party(request: Request, party_email, side: str) -> dict:
    u = require_user(request)

    if not party_email or u["email"] != party_email.lower():
        raise HTTPException(
            403,
            f"Only the {side} on this deal can do this",
        )

    return u


def deal_side(request: Request, nid: int):
    """
    Return (side, row) for the signed-in user on this deal.
    People who are not part of it get a 404.
    """
    u = require_user(request)

    # Process expired seller reviews before retrieving the deal.
    expire_reviews()

    with conn() as c:
        row = c.execute(
            "SELECT n.*, l.product, l.owner_email FROM negotiations n "
            "JOIN listings l ON l.id = n.listing_id WHERE n.id=?",
            (nid,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "Negotiation not found")

    if row["buyer_email"] and u["email"] == row["buyer_email"].lower():
        return "buyer", row

    if row["owner_email"] and u["email"] == row["owner_email"].lower():
        return "seller", row

    raise HTTPException(404, "Negotiation not found")


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: str = Field(max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern="^(buyer|seller)$")


class LoginIn(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(max_length=128)


def _locked(email: str) -> bool:
    n, t = _fails.get(email, (0, 0.0))

    if n >= 5 and time.time() - t < 300:
        return True

    if n >= 5:
        _fails.pop(email, None)

    return False


@router.post("/auth/register")
def register(body: RegisterIn, request: Request):
    if not EMAIL.match(body.email.strip()):
        raise HTTPException(
            422,
            "Enter a valid email address",
        )

    try:
        user = create_user(
            body.name,
            body.email,
            body.password,
            body.role,
        )
    except ValueError as e:
        raise HTTPException(409, str(e))

    request.session.clear()
    request.session["email"] = user["email"]

    return {"user": user}


@router.post("/auth/login")
def login(body: LoginIn, request: Request):
    email = body.email.strip().lower()

    if _locked(email):
        raise HTTPException(
            429,
            "Too many wrong attempts. Try again in a few minutes.",
        )

    with conn() as c:
        r = c.execute(
            "SELECT email, name, role, password_hash "
            "FROM users WHERE email=?",
            (email,),
        ).fetchone()

    ok = (
        verify_password(
            body.password,
            r["password_hash"] if r else _DUMMY,
        )
        and r is not None
    )

    if not ok:
        n, t = _fails.get(email, (0, time.time()))
        _fails[email] = (n + 1, t)

        raise HTTPException(
            401,
            "Wrong email or password",
        )

    _fails.pop(email, None)

    request.session.clear()
    request.session["email"] = r["email"]

    return {
        "user": {
            "email": r["email"],
            "name": r["name"],
            "role": r["role"],
        }
    }


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request):
    return {"user": current_user(request)}


# ----------------------------------------------------------------
# Sign in with PayPal
# ----------------------------------------------------------------

def _front() -> str:
    return os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173",
    )


def _web_base() -> str:
    return (
        "https://www.sandbox.paypal.com"
        if "sandbox" in os.environ["PAYPAL_BASE_URL"]
        else "https://www.paypal.com"
    )


@router.get("/auth/paypal/login")
def paypal_login(request: Request, role: str = "buyer"):
    if role not in ("buyer", "seller"):
        role = "buyer"

    state = secrets.token_urlsafe(16)

    request.session["oauth_state"] = state
    request.session["login_role"] = role

    q = urlencode({
        "flowEntry": "static",
        "client_id": os.environ["PAYPAL_CLIENT_ID"],
        "response_type": "code",
        "scope": "openid email",
        "redirect_uri": (
            os.getenv(
                "PUBLIC_BASE_URL",
                "http://localhost:8000",
            )
            + "/api/auth/callback"
        ),
        "state": state,
    })

    return RedirectResponse(
        f"{_web_base()}/connect?{q}",
        status_code=303,
    )


@router.get("/auth/callback")
def paypal_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
):
    expected = request.session.pop("oauth_state", None)

    fail = RedirectResponse(
        f"{_front()}/login?error=failed",
        status_code=303,
    )

    if error or not code or not expected or state != expected:
        return fail

    try:
        tok = httpx.post(
            os.environ["PAYPAL_BASE_URL"] + "/v1/oauth2/token",
            auth=(
                os.environ["PAYPAL_CLIENT_ID"],
                os.environ["PAYPAL_CLIENT_SECRET"],
            ),
            data={
                "grant_type": "authorization_code",
                "code": code,
            },
            timeout=30,
        )

        tok.raise_for_status()

        info = httpx.get(
            os.environ["PAYPAL_BASE_URL"]
            + "/v1/identity/openidconnect/userinfo?schema=openid",
            headers={
                "Authorization": f"Bearer {tok.json()['access_token']}"
            },
            timeout=30,
        )

        info.raise_for_status()
        d = info.json()

    except (httpx.HTTPError, KeyError, ValueError):
        return fail

    email = (
        d.get("email")
        or next(
            (
                e.get("value")
                for e in d.get("emails", [])
                if e.get("primary")
            ),
            "",
        )
        or ""
    ).lower()

    if not email:
        return RedirectResponse(
            f"{_front()}/login?error=noemail",
            status_code=303,
        )

    with conn() as c:
        r = c.execute(
            "SELECT email FROM users WHERE email=?",
            (email,),
        ).fetchone()

    if not r:
        # First sign-in: create account with selected role.
        role = request.session.get("login_role", "buyer")

        create_user(
            d.get("name") or email.split("@")[0],
            email,
            secrets.token_urlsafe(24),
            role,
        )

    request.session.pop("login_role", None)
    request.session["email"] = email

    return RedirectResponse(
        f"{_front()}/",
        status_code=303,
    )
