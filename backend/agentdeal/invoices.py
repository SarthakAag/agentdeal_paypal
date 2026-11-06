import os
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import paypal_client as pp
from .db import conn
from .payments import _get, _log

router = APIRouter(tags=["invoices"])

INVOICEABLE = {"approved", "payment_pending", "funds_held", "paid"}


class InvoiceIn(BaseModel):
    buyer_email: Optional[str] = None
    send: bool = True


def _summary(nid: int) -> dict:
    row = _get(nid)
    return {
        "negotiation_id": nid,
        "invoice_id": row["invoice_id"],
        "invoice_number": row["invoice_number"],
        "invoice_status": row["invoice_status"],
        "invoice_url": row["invoice_url"],
        "amount_usd": row["amount_usd"],
    }


@router.post("/negotiations/{nid}/invoice")
def create_deal_invoice(nid: int, body: Optional[InvoiceIn] = None):
    """Turns the approved deal into a formal PayPal invoice."""
    body = body or InvoiceIn()
    row = _get(nid)
    if row["status"] not in INVOICEABLE:
        raise HTTPException(409, f"Negotiation is '{row['status']}'; both sides must approve first")
    if row["invoice_id"]:
        return _summary(nid)   # idempotent: one invoice per deal

    buyer_email = body.buyer_email or os.getenv("DEFAULT_BUYER_EMAIL")
    if not buyer_email:
        raise HTTPException(422, "Provide buyer_email or set DEFAULT_BUYER_EMAIL in .env")

    inr, days = row["agreed_price"], row["agreed_days"]
    usd = row["amount_usd"] or pp.inr_to_usd(inr)
    today = date.today()
    delivery_by = today + timedelta(days=days)
    rate = os.getenv("INR_PER_USD", "88")

    term = (
        f"Agreed through AI-assisted negotiation (deal #{nid}, {row['rounds']} rounds, "
        f"{row['engine']} agents) and approved by both parties. "
        f"Agreed price: ₹{inr:,.2f} (charged as ${usd:.2f} USD at {rate} INR per USD). "
        f"Delivery within {days} days, by {delivery_by.isoformat()}."
    )
    note = "Funds are authorized up front and captured when the seller confirms delivery."

    try:
        inv = pp.create_invoice(
            amount_usd=usd, product=row["product"],
            item_description=f"Delivery in {days} days (by {delivery_by.isoformat()}). Agreed price ₹{inr:,.2f}.",
            buyer_email=buyer_email, note=note, term=term,
            invoice_date=today.isoformat(), due_date=(today + timedelta(days=7)).isoformat(),
        )
        status, url = "DRAFT", None
        if body.send:
            url = pp.send_invoice(inv["invoice_id"])["recipient_view_url"]
            status = "SENT"
    except pp.PayPalError as e:
        raise HTTPException(502, str(e))

    with conn() as c:
        c.execute(
            "UPDATE negotiations SET invoice_id=?, invoice_number=?, invoice_status=?, invoice_url=?, amount_usd=? WHERE id=?",
            (inv["invoice_id"], inv["invoice_number"], status, url, usd, nid),
        )
    _log(nid, "INVOICE_" + status, {**inv, "url": url})
    return _summary(nid)


@router.get("/negotiations/{nid}/invoice")
def get_deal_invoice(nid: int):
    """Returns the stored invoice and refreshes its status from PayPal."""
    row = _get(nid)
    if not row["invoice_id"]:
        raise HTTPException(404, "No invoice for this negotiation yet")
    try:
        live = pp.get_invoice(row["invoice_id"])
    except pp.PayPalError as e:
        raise HTTPException(502, str(e))
    with conn() as c:
        c.execute("UPDATE negotiations SET invoice_status=? WHERE id=?", (live["status"], nid))
    return _summary(nid)