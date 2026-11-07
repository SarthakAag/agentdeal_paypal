
import json
import os
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from . import paypal_client as pp
from .auth import require_party, is_demo_account
from .db import audit, conn

router = APIRouter(tags=["payments"])


# --------------------------------------------------
# Request models
# --------------------------------------------------

class VoidIn(BaseModel):
    reason: str = Field(
        default="seller_missed_deadline",
        pattern="^(seller_missed_deadline|buyer_cancelled|mutual_cancel)$",
    )
    force: bool = False


class RefundIn(BaseModel):
    reason: str = Field(
        default="buyer_requested",
        max_length=200,
    )


# --------------------------------------------------
# URL configuration
# --------------------------------------------------

def _base_url() -> str:
    return os.getenv(
        "PUBLIC_BASE_URL",
        "http://localhost:8000",
    ).rstrip("/")


def _front_url() -> str:
    return os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173",
    ).rstrip("/")


# --------------------------------------------------
# Database helpers
# --------------------------------------------------

def _get(nid: int):
    with conn() as c:
        row = c.execute(
            "SELECT n.*, l.product, l.owner_email "
            "FROM negotiations n "
            "JOIN listings l ON l.id = n.listing_id "
            "WHERE n.id=?",
            (nid,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "Negotiation not found")

    return row


def _log(nid, event_type, payload, verified=False):
    with conn() as c:
        c.execute(
            """
            INSERT INTO payment_events
            (negotiation_id, event_type, verified, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                nid,
                event_type,
                int(verified),
                json.dumps(payload),
            ),
        )


def _outcome(nid, outcome, detail=None):
    """Outcome labels are the training signal for the learning loop."""
    with conn() as c:
        c.execute(
            """
            INSERT INTO outcomes
            (negotiation_id, outcome, detail_json)
            VALUES (?, ?, ?)
            """,
            (
                nid,
                outcome,
                json.dumps(detail or {}),
            ),
        )


def _has_outcome(nid: int, outcome: str) -> bool:
    with conn() as c:
        return c.execute(
            """
            SELECT 1 FROM outcomes
            WHERE negotiation_id=? AND outcome=?
            """,
            (nid, outcome),
        ).fetchone() is not None


def _state(nid: int) -> dict:
    """Small response for write endpoints. Never includes private limits."""
    with conn() as c:
        r = c.execute(
            """
            SELECT id, status, agreed_price, agreed_days, deliver_by
            FROM negotiations
            WHERE id=?
            """,
            (nid,),
        ).fetchone()

    return dict(r)


def _require_real_buyer(request: Request, buyer_email: str):
    """
    Verify that the signed-in user is the buyer.
    Shared demo accounts cannot initiate PayPal payments.
    """
    user = require_party(request, buyer_email, "buyer")

    if is_demo_account(user["email"]):
        raise HTTPException(
            403,
            "PayPal payments are disabled for shared demo accounts. "
            "Use a personal account to test PayPal Sandbox payments.",
        )

    return user


def _require_real_seller(request: Request, seller_email: str):
    """
    Verify that the signed-in user is the seller.
    Shared demo accounts cannot perform PayPal refunds.
    """
    user = require_party(request, seller_email, "seller")

    if is_demo_account(user["email"]):
        raise HTTPException(
            403,
            "PayPal refunds are disabled for shared demo accounts.",
        )

    return user


# --------------------------------------------------
# Create PayPal order
# --------------------------------------------------

@router.post("/negotiations/{nid}/pay")
def pay(nid: int, request: Request):
    """
    Create a PayPal order that authorizes funds.
    Only the buyer can pay, after both sides approve.
    Shared demo accounts cannot initiate payments.
    """

    row = _get(nid)

    _require_real_buyer(request, row["buyer_email"])

    if row["status"] != "approved":
        raise HTTPException(
            409,
            f"Negotiation is '{row['status']}'; "
            "both sides must approve first",
        )

    usd = pp.inr_to_usd(row["agreed_price"])

    try:
        order = pp.create_order(
            amount_usd=usd,
            description=f"AgentDeal #{nid}: {row['product']}",
            reference_id=f"deal-{nid}",
            return_url=f"{_base_url()}/api/payments/return",
            cancel_url=f"{_base_url()}/api/payments/cancel?nid={nid}",
            request_id=f"agentdeal-order-{nid}",
        )

    except pp.PayPalError as e:
        raise HTTPException(502, str(e))

    with conn() as c:
        c.execute(
            """
            UPDATE negotiations
            SET status='payment_pending',
                paypal_order_id=?,
                amount_usd=?,
                approve_url=?
            WHERE id=?
            """,
            (
                order["order_id"],
                usd,
                order["approve_url"],
                nid,
            ),
        )

    _log(nid, "ORDER_CREATED", order)

    audit(
        nid,
        "buyer",
        "payment_started",
        f"${usd:.2f}",
    )

    return {
        "negotiation_id": nid,
        "amount_inr": row["agreed_price"],
        "amount_usd": usd,
        "approve_url": order["approve_url"],
    }


# --------------------------------------------------
# PayPal return and cancellation
# --------------------------------------------------

@router.get("/payments/return")
def payment_return(token: str):
    """
    PayPal redirects the buyer here after approval.
    Authorize funds and start the delivery clock.
    """

    with conn() as c:
        row = c.execute(
            """
            SELECT id, status, agreed_days
            FROM negotiations
            WHERE paypal_order_id=?
            """,
            (token,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "Unknown order")

    nid = row["id"]

    if row["status"] == "payment_pending":
        deliver_by = (
            date.today() + timedelta(days=row["agreed_days"])
        ).isoformat()

        try:
            auth = pp.authorize_order(token)

        except pp.PayPalError as e:
            raise HTTPException(502, str(e))

        with conn() as c:
            c.execute(
                """
                UPDATE negotiations
                SET status='funds_held',
                    paypal_auth_id=?,
                    deliver_by=?
                WHERE id=?
                """,
                (
                    auth["authorization_id"],
                    deliver_by,
                    nid,
                ),
            )

        _log(
            nid,
            "FUNDS_AUTHORIZED",
            {
                **auth,
                "deliver_by": deliver_by,
            },
        )

        audit(
            nid,
            "system",
            "funds_held",
            f"deliver by {deliver_by}",
        )

    return RedirectResponse(
        f"{_front_url()}/deals/{nid}?paypal=held",
        status_code=303,
    )


@router.get("/payments/cancel")
def payment_cancel(nid: int):
    _log(nid, "BUYER_CANCELLED", {})

    audit(
        nid,
        "buyer",
        "payment_cancelled",
    )

    return RedirectResponse(
        f"{_front_url()}/deals/{nid}?paypal=cancelled",
        status_code=303,
    )


# --------------------------------------------------
# Seller delivery and capture
# --------------------------------------------------

@router.post("/negotiations/{nid}/deliver")
def deliver(nid: int, request: Request):
    """
    Seller confirms delivery.
    Captures the previously authorized PayPal funds.
    """

    row = _get(nid)

    _require_real_seller(request, row["owner_email"])

    if row["status"] != "funds_held":
        raise HTTPException(
            409,
            f"Negotiation is '{row['status']}'; "
            "funds must be held first",
        )

    late = (
        bool(row["deliver_by"])
        and date.today() > date.fromisoformat(row["deliver_by"])
    )

    try:
        cap = pp.capture_authorization(
            row["paypal_auth_id"],
            f"agentdeal-capture-{nid}",
        )

    except pp.PayPalError as e:
        raise HTTPException(502, str(e))

    with conn() as c:
        c.execute(
            """
            UPDATE negotiations
            SET status='paid', paypal_capture_id=?
            WHERE id=?
            """,
            (
                cap["capture_id"],
                nid,
            ),
        )

    _log(nid, "PAYMENT_CAPTURED", cap)

    if not _has_outcome(nid, "delivered_late") and not _has_outcome(
        nid, "delivered_on_time"
    ):
        _outcome(
            nid,
            "delivered_late" if late else "delivered_on_time",
            {
                "deliver_by": row["deliver_by"],
            },
        )

    audit(
        nid,
        "seller",
        "delivered",
        "late" if late else "on time",
    )

    return _state(nid)


# --------------------------------------------------
# Void authorization
# --------------------------------------------------

def _void_deal(
    nid: int,
    row,
    reason: str,
    actor: str,
    forced: bool = False,
) -> dict:

    try:
        res = pp.void_authorization(
            row["paypal_auth_id"],
            f"agentdeal-void-{nid}",
        )

    except pp.PayPalError as e:
        raise HTTPException(502, str(e))

    with conn() as c:
        c.execute(
            "UPDATE negotiations SET status='voided' WHERE id=?",
            (nid,),
        )

    _log(
        nid,
        "FUNDS_VOIDED",
        {
            **res,
            "reason": reason,
            "forced": forced,
        },
    )

    if not _has_outcome(nid, "voided"):
        _outcome(
            nid,
            "voided",
            {
                "reason": reason,
                "forced": forced,
                "deliver_by": row["deliver_by"],
            },
        )

    audit(
        nid,
        actor,
        "voided",
        reason.replace("_", " "),
    )

    return _state(nid)


@router.post("/negotiations/{nid}/void")
def void(
    nid: int,
    request: Request,
    body: Optional[VoidIn] = None,
):
    """Buyer releases held funds after a valid cancellation or deadline."""

    body = body or VoidIn()

    row = _get(nid)

    _require_real_buyer(request, row["buyer_email"])

    if row["status"] != "funds_held":
        raise HTTPException(
            409,
            f"Negotiation is '{row['status']}'; "
            "only held funds can be voided",
        )

    if body.reason == "seller_missed_deadline" and not body.force:
        if (
            not row["deliver_by"]
            or date.today() <= date.fromisoformat(row["deliver_by"])
        ):
            raise HTTPException(
                409,
                f"Deadline {row['deliver_by']} has not passed yet",
            )

    return _void_deal(
        nid,
        row,
        body.reason,
        "buyer",
        forced=body.force,
    )


# --------------------------------------------------
# Automatic deadline sweep
# --------------------------------------------------

@router.post("/deadlines/sweep")
def sweep():
    """
    Buyer-protection agent:
    voids held payments whose delivery deadline has passed.
    """

    today = date.today().isoformat()

    with conn() as c:
        ids = [
            r["id"]
            for r in c.execute(
                """
                SELECT id
                FROM negotiations
                WHERE status='funds_held'
                  AND deliver_by IS NOT NULL
                  AND deliver_by < ?
                """,
                (today,),
            )
        ]

    results = []

    for nid in ids:
        try:
            _void_deal(
                nid,
                _get(nid),
                "seller_missed_deadline",
                "system",
            )

            results.append({
                "negotiation_id": nid,
                "result": "voided",
            })

        except HTTPException as e:
            results.append({
                "negotiation_id": nid,
                "result": "error",
                "detail": e.detail,
            })

    return {
        "checked": len(ids),
        "results": results,
    }


# --------------------------------------------------
# Refund captured payment
# --------------------------------------------------

@router.post("/negotiations/{nid}/refund")
def refund(
    nid: int,
    request: Request,
    body: Optional[RefundIn] = None,
):
    """Seller refunds a captured payment in full."""

    body = body or RefundIn()

    row = _get(nid)

    _require_real_seller(request, row["owner_email"])

    if row["status"] != "paid":
        raise HTTPException(
            409,
            f"Negotiation is '{row['status']}'; "
            "only paid deals can be refunded",
        )

    try:
        ref = pp.refund_capture(
            row["paypal_capture_id"],
            f"agentdeal-refund-{nid}",
            body.reason,
        )

    except pp.PayPalError as e:
        raise HTTPException(502, str(e))

    with conn() as c:
        c.execute(
            """
            UPDATE negotiations
            SET status='refunded', paypal_refund_id=?
            WHERE id=?
            """,
            (
                ref["refund_id"],
                nid,
            ),
        )

    _log(
        nid,
        "PAYMENT_REFUNDED",
        {
            **ref,
            "reason": body.reason,
        },
    )

    if not _has_outcome(nid, "refunded"):
        _outcome(
            nid,
            "refunded",
            {
                "reason": body.reason,
            },
        )

    audit(
        nid,
        "seller",
        "refunded",
        body.reason,
    )

    return _state(nid)


# --------------------------------------------------
# PayPal webhook matching
# --------------------------------------------------

def _find_deal(resource: dict):
    """
    Match PayPal events to deals using their order,
    authorization, capture or refund identifiers.
    """

    ids = set()

    rel = resource.get(
        "supplementary_data", {}
    ).get("related_ids", {})

    for key in (
        "order_id",
        "authorization_id",
        "capture_id",
    ):
        if rel.get(key):
            ids.add(rel[key])

    if resource.get("id"):
        ids.add(resource["id"])

    for link in resource.get("links", []):
        if link.get("rel") == "up" and link.get("href"):
            ids.add(
                link["href"].rstrip("/").rsplit("/", 1)[-1]
            )

    with conn() as c:
        for identifier in ids:
            row = c.execute(
                """
                SELECT id, status
                FROM negotiations
                WHERE paypal_order_id=?
                   OR paypal_auth_id=?
                   OR paypal_capture_id=?
                   OR paypal_refund_id=?
                """,
                (
                    identifier,
                    identifier,
                    identifier,
                    identifier,
                ),
            ).fetchone()

            if row:
                return row

    return None


# --------------------------------------------------
# PayPal webhook
# --------------------------------------------------

@router.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    """
    Only signature-verified PayPal events may
    change a deal's payment status.
    """

    event = await request.json()

    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID")

    verified = (
        bool(webhook_id)
        and pp.verify_webhook(
            {
                k.lower(): v
                for k, v in request.headers.items()
            },
            event,
            webhook_id,
        )
    )

    etype = event.get("event_type", "UNKNOWN")
    resource = event.get("resource", {})

    row = _find_deal(resource)
    nid = row["id"] if row else None

    _log(
        nid,
        etype,
        event,
        verified,
    )

    changed = None

    if verified and row:
        status = row["status"]

        with conn() as c:
            if (
                etype == "PAYMENT.CAPTURE.COMPLETED"
                and status in (
                    "approved",
                    "payment_pending",
                    "funds_held",
                )
            ):
                c.execute(
                    """
                    UPDATE negotiations
                    SET status='paid', paypal_capture_id=?
                    WHERE id=?
                    """,
                    (
                        resource.get("id"),
                        nid,
                    ),
                )

                changed = "paid"

            elif (
                etype == "PAYMENT.AUTHORIZATION.VOIDED"
                and status == "funds_held"
            ):
                c.execute(
                    """
                    UPDATE negotiations
                    SET status='voided'
                    WHERE id=?
                    """,
                    (nid,),
                )

                changed = "voided"

            elif (
                etype == "PAYMENT.CAPTURE.REFUNDED"
                and status == "paid"
            ):
                c.execute(
                    """
                    UPDATE negotiations
                    SET status='refunded', paypal_refund_id=?
                    WHERE id=?
                    """,
                    (
                        resource.get("id"),
                        nid,
                    ),
                )

                changed = "refunded"

        if (
            changed in ("voided", "refunded")
            and not _has_outcome(nid, changed)
        ):
            _outcome(
                nid,
                changed,
                {"source": "webhook"},
            )

        if changed:
            audit(
                nid,
                "paypal",
                f"status_{changed}",
                "set from a verified webhook",
            )

    return {
        "received": True,
        "verified": verified,
        "status_changed": changed,
    }


# --------------------------------------------------
# Payment event debugging
# --------------------------------------------------

@router.get("/payment-events")
def payment_events(limit: int = 50):
    """
    Debug listing of PayPal events.
    Only available when DEMO_MODE=1.
    """

    if os.getenv("DEMO_MODE") != "1":
        raise HTTPException(404, "Not found")

    limit = max(1, min(limit, 200))

    with conn() as c:
        rows = c.execute(
            """
            SELECT id, negotiation_id, event_type,
                   verified, created
            FROM payment_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(r) for r in rows]
