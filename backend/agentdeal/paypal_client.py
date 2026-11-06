import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_token = {"value": None, "expires": 0.0}


class PayPalError(Exception):
    pass


def _base() -> str:
    return os.environ["PAYPAL_BASE_URL"]


def inr_to_usd(inr: float) -> float:
    return round(inr / float(os.getenv("INR_PER_USD", "88")), 2)


def _access_token() -> str:
    if _token["value"] and time.time() < _token["expires"] - 60:
        return _token["value"]
    r = httpx.post(
        _base() + "/v1/oauth2/token",
        auth=(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"]),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    if r.status_code != 200:
        raise PayPalError(f"OAuth failed: {r.status_code}")
    d = r.json()
    _token["value"] = d["access_token"]
    _token["expires"] = time.time() + d.get("expires_in", 300)
    return _token["value"]


def _call(method: str, path: str, body=None, request_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json"}
    if request_id:
        headers["PayPal-Request-Id"] = request_id   # makes retries idempotent
    r = httpx.request(method, _base() + path, json=body, headers=headers, timeout=30)
    if r.status_code >= 400:
        raise PayPalError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
    return r.json() if r.text else {}


# ---------------------------------------------------------------- Orders

def create_order(amount_usd: float, description: str, reference_id: str,
                 return_url: str, cancel_url: str, request_id: str) -> dict:
    """AUTHORIZE intent: funds are held, not captured, until delivery is confirmed."""
    body = {
        "intent": "AUTHORIZE",
        "purchase_units": [{
            "reference_id": reference_id,
            "description": description[:127],
            "amount": {"currency_code": "USD", "value": f"{amount_usd:.2f}"},
        }],
        "payment_source": {"paypal": {"experience_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
        }}},
    }
    order = _call("POST", "/v2/checkout/orders", body, request_id)
    link = next((l["href"] for l in order.get("links", []) if l["rel"] in ("payer-action", "approve")), None)
    return {"order_id": order["id"], "approve_url": link, "status": order["status"]}


def authorize_order(order_id: str) -> dict:
    d = _call("POST", f"/v2/checkout/orders/{order_id}/authorize", {}, f"auth-{order_id}")
    auth = d["purchase_units"][0]["payments"]["authorizations"][0]
    return {"authorization_id": auth["id"], "status": auth["status"]}


def capture_authorization(auth_id: str, request_id: str) -> dict:
    d = _call("POST", f"/v2/payments/authorizations/{auth_id}/capture", {"final_capture": True}, request_id)
    return {"capture_id": d["id"], "status": d["status"]}


def void_authorization(auth_id: str, request_id: str) -> dict:
    """Releases held funds back to the buyer. PayPal usually answers with an empty body."""
    _call("POST", f"/v2/payments/authorizations/{auth_id}/void", None, request_id)
    return {"authorization_id": auth_id, "status": "VOIDED"}


def refund_capture(capture_id: str, request_id: str, note: str) -> dict:
    """Full refund of a captured payment (no amount in the body means refund everything)."""
    d = _call("POST", f"/v2/payments/captures/{capture_id}/refund",
              {"note_to_payer": note[:255]}, request_id)
    return {"refund_id": d["id"], "status": d.get("status")}


# ---------------------------------------------------------------- Invoicing (needs the Invoicing scope)

def create_invoice(amount_usd: float, product: str, item_description: str, buyer_email: str,
                   note: str, term: str, invoice_date: str, due_date: str) -> dict:
    """Creates a DRAFT invoice. It is not visible to the buyer until send_invoice()."""
    number = _call("POST", "/v2/invoicing/generate-next-invoice-number")["invoice_number"]
    body = {
        "detail": {
            "invoice_number": number,
            "invoice_date": invoice_date,
            "currency_code": "USD",
            "note": note[:4000],
            "term": term[:4000],
            "payment_term": {"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": due_date},
        },
        "primary_recipients": [{"billing_info": {"email_address": buyer_email}}],
        "items": [{
            "name": product[:200],
            "description": item_description[:1000],
            "quantity": "1",
            "unit_amount": {"currency_code": "USD", "value": f"{amount_usd:.2f}"},
        }],
        "configuration": {"allow_tip": False, "tax_inclusive": False},
    }
    if os.getenv("INVOICER_EMAIL"):
        body["invoicer"] = {"email_address": os.environ["INVOICER_EMAIL"]}
    d = _call("POST", "/v2/invoicing/invoices", body)
    return {"invoice_id": d["href"].rstrip("/").rsplit("/", 1)[-1], "invoice_number": number}


def send_invoice(invoice_id: str) -> dict:
    d = _call("POST", f"/v2/invoicing/invoices/{invoice_id}/send",
              {"send_to_recipient": True, "send_to_invoicer": False})
    return {"recipient_view_url": d.get("href")}


def get_invoice(invoice_id: str) -> dict:
    d = _call("GET", f"/v2/invoicing/invoices/{invoice_id}")
    return {"status": d.get("status"), "invoice_number": d.get("detail", {}).get("invoice_number")}


# ---------------------------------------------------------------- Webhooks

def verify_webhook(headers: dict, event: dict, webhook_id: str) -> bool:
    body = {
        "auth_algo": headers.get("paypal-auth-algo"),
        "cert_url": headers.get("paypal-cert-url"),
        "transmission_id": headers.get("paypal-transmission-id"),
        "transmission_sig": headers.get("paypal-transmission-sig"),
        "transmission_time": headers.get("paypal-transmission-time"),
        "webhook_id": webhook_id,
        "webhook_event": event,
    }
    try:
        return _call("POST", "/v1/notifications/verify-webhook-signature", body).get("verification_status") == "SUCCESS"
    except PayPalError:
        return False