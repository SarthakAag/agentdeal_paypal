
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from .auth import current_user, deal_side, require_user
from .db import conn, expire_reviews, negotiation_view
from .rules import utility
from .schemas import Limits

router = APIRouter(tags=["views"])

NOT_SIM = "(n.source IS NULL OR n.source != 'simulated')"


@router.get("/config")
def config():
    return {
        "engine": os.getenv("AGENTDEAL_ENGINE", "heuristic"),
        "demo": os.getenv("DEMO_MODE") == "1",
        "inr_per_usd": float(os.getenv("INR_PER_USD", "88")),
    }


@router.get("/health")
def health():
    return {"status": "healthy"}


@router.get("/results")
def results():
    # Resolve the project root from this file instead of relying on
    # Render's current working directory.
    project_root = Path(__file__).resolve().parents[2]
    p = project_root / "results" / "versions.json"

    if not p.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Results file not found: {p}",
        )

    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Invalid results JSON file",
        )


def _reliability() -> dict:
    """On-time delivery per listing, from real (non-simulated) deals. The latest outcome of each deal counts."""
    out: dict = {}

    with conn() as c:
        rows = c.execute(
            f"""SELECT n.listing_id AS lid, o.outcome AS outcome, COUNT(*) AS c
                FROM outcomes o JOIN negotiations n ON n.id = o.negotiation_id
                WHERE o.id = (
                    SELECT MAX(id) FROM outcomes WHERE negotiation_id = n.id
                ) AND {NOT_SIM}
                GROUP BY n.listing_id, o.outcome"""
        ).fetchall()

    for r in rows:
        d = out.setdefault(r["lid"], {"deals": 0, "on_time": 0})
        d["deals"] += r["c"]

        if r["outcome"] == "delivered_on_time":
            d["on_time"] += r["c"]

    for d in out.values():
        d["rate"] = round(d["on_time"] / d["deals"], 3) if d["deals"] else None

    return out


@router.get("/listings")
def list_listings(request: Request):
    """Public view: a seller's private limits are never returned."""
    me = current_user(request)
    me_email = me["email"] if me else None

    with conn() as c:
        rows = c.execute(
            """SELECT l.id, l.product, l.ask_price, l.created, l.owner_email,
                      su.name AS seller_name,
                      (SELECT COUNT(*) FROM negotiations n
                       WHERE n.listing_id = l.id) AS negotiations
               FROM listings l
               LEFT JOIN users su ON su.email = l.owner_email
               WHERE COALESCE(l.active, 1) = 1
                 AND l.owner_email IS NOT NULL
                 AND l.id NOT IN (
                     SELECT listing_id FROM negotiations
                     WHERE source = 'simulated'
                 )
               ORDER BY l.id DESC"""
        ).fetchall()

    rel = _reliability()

    return [
        {
            "id": r["id"],
            "product": r["product"],
            "ask_price": r["ask_price"],
            "created": r["created"],
            "negotiations": r["negotiations"],
            "seller_name": r["seller_name"],
            "mine": bool(me_email and r["owner_email"].lower() == me_email),
            "reliability": rel.get(r["id"]),
        }
        for r in rows
    ]


@router.get("/listings/mine")
def my_listings(request: Request):
    """A seller's own listings, including their private limits (visible only to them)."""
    u = require_user(request, "seller")

    with conn() as c:
        rows = c.execute(
            """SELECT l.id, l.product, l.ask_price, l.min_price,
                      l.fastest_days, l.ideal_days, l.created,
                      COALESCE(l.active, 1) AS active,
                      (SELECT COUNT(*) FROM negotiations n
                       WHERE n.listing_id = l.id) AS negotiations,
                      (SELECT COUNT(*) FROM negotiations n
                       WHERE n.listing_id = l.id AND n.status = 'paid') AS paid
               FROM listings l
               WHERE l.owner_email = ?
               ORDER BY l.id DESC""",
            (u["email"],),
        ).fetchall()

    return [dict(r) for r in rows]


@router.get("/listings/{lid}")
def get_listing(lid: int, request: Request):
    me = current_user(request)

    with conn() as c:
        r = c.execute(
            """SELECT l.id, l.product, l.ask_price, l.created,
                      l.owner_email, COALESCE(l.active, 1) AS active,
                      su.name AS seller_name
               FROM listings l
               LEFT JOIN users su ON su.email = l.owner_email
               WHERE l.id = ?""",
            (lid,),
        ).fetchone()

    if not r:
        raise HTTPException(404, "Listing not found")

    return {
        "id": r["id"],
        "product": r["product"],
        "ask_price": r["ask_price"],
        "created": r["created"],
        "active": bool(r["active"]),
        "seller_name": r["seller_name"],
        "mine": bool(
            me and r["owner_email"] and r["owner_email"].lower() == me["email"]
        ),
        "reliability": _reliability().get(lid),
    }


def _my_rows(
    email: str,
    listing_id: Optional[int] = None,
    limit: int = 500,
) -> list:
    # Process expired seller reviews before returning negotiation data.
    expire_reviews()

    sql = f"""SELECT n.id, n.listing_id, l.product, n.engine, n.status,
                     n.agreed_price, n.agreed_days, n.rounds, n.created,
                     n.buyer_email, l.owner_email,
                     n.buyer_approved, n.seller_approved,
                     bu.name AS buyer_name, su.name AS seller_name,
                     (SELECT outcome FROM outcomes o
                      WHERE o.negotiation_id = n.id
                      ORDER BY o.id DESC LIMIT 1) AS outcome
              FROM negotiations n
              JOIN listings l ON l.id = n.listing_id
              LEFT JOIN users bu ON bu.email = n.buyer_email
              LEFT JOIN users su ON su.email = l.owner_email
              WHERE {NOT_SIM}
                AND (n.buyer_email = ? OR l.owner_email = ?)"""

    params: list = [email, email]

    if listing_id is not None:
        sql += " AND n.listing_id = ?"
        params.append(listing_id)

    sql += " ORDER BY n.id DESC LIMIT ?"
    params.append(limit)

    with conn() as c:
        rows = c.execute(sql, params).fetchall()

    out = []

    for r in rows:
        side = "buyer" if (r["buyer_email"] or "").lower() == email else "seller"

        out.append(
            {
                "id": r["id"],
                "listing_id": r["listing_id"],
                "product": r["product"],
                "engine": r["engine"],
                "status": r["status"],
                "agreed_price": r["agreed_price"],
                "agreed_days": r["agreed_days"],
                "rounds": r["rounds"],
                "created": r["created"],
                "side": side,
                "buyer_approved": bool(r["buyer_approved"]),
                "seller_approved": bool(r["seller_approved"]),
                "counterparty": (
                    r["seller_name"] if side == "buyer" else r["buyer_name"]
                ),
                "outcome": r["outcome"],
            }
        )

    return out


@router.get("/negotiations")
def list_negotiations(
    request: Request,
    listing_id: Optional[int] = None,
    limit: int = Query(200, le=500),
):
    """Only the signed-in user's own deals, as buyer or as seller."""
    u = require_user(request)
    return _my_rows(u["email"], listing_id, limit)


@router.get("/account/summary")
def account_summary(request: Request):
    u = require_user(request)
    deals = _my_rows(u["email"])

    by: dict = {}
    paid = refunded = 0.0

    for d in deals:
        by[d["status"]] = by.get(d["status"], 0) + 1

        if d["status"] == "paid":
            paid += d["agreed_price"] or 0
        elif d["status"] == "refunded":
            refunded += d["agreed_price"] or 0

    out = {
        "user": u,
        "deals": len(deals),
        "by_status": by,
        "paid_inr": round(paid, 2),
        "refunded_inr": round(refunded, 2),
        "delivery": None,
    }

    if u["role"] == "seller":
        with_outcome = [d for d in deals if d["outcome"]]
        out["delivery"] = {
            "deals": len(with_outcome),
            "on_time": sum(
                1 for d in with_outcome
                if d["outcome"] == "delivered_on_time"
            ),
        }

    return out


def _no_deal_reason(transcript: list) -> Optional[str]:
    """Generic explanation built only from the public offers, so no private limit is revealed."""
    offers = [t for t in transcript if t.get("action") == "offer"]
    b = [t for t in offers if t["role"] == "buyer"]
    s = [t for t in offers if t["role"] == "seller"]

    if not b or not s:
        return None

    gap = round(s[-1]["price"] - b[-1]["price"], 2)

    if gap > 0:
        return (
            f"After {max(len(b), len(s))} rounds the final offers "
            f"were still ₹{gap:,.0f} apart on price."
        )

    return "The prices met, but the delivery terms did not line up before the rounds ran out."


@router.get("/negotiations/{nid}")
def get_negotiation(nid: int, request: Request):
    """Only the buyer or the seller of this deal can open it, and each only receives their own private limits."""
    side, row = deal_side(request, nid)

    with conn() as c:
        audit_rows = c.execute(
            """SELECT actor, action, detail, created
               FROM audit
               WHERE negotiation_id = ?
               ORDER BY id""",
            (nid,),
        ).fetchall()

        pp_rows = c.execute(
            """SELECT event_type, created
               FROM payment_events
               WHERE negotiation_id = ? AND verified = 1
               ORDER BY id""",
            (nid,),
        ).fetchall()

        outcome = c.execute(
            """SELECT outcome FROM outcomes
               WHERE negotiation_id = ?
               ORDER BY id DESC LIMIT 1""",
            (nid,),
        ).fetchone()

        names = c.execute(
            """SELECT bu.name AS b, su.name AS s
               FROM negotiations n
               JOIN listings l ON l.id = n.listing_id
               LEFT JOIN users bu ON bu.email = n.buyer_email
               LEFT JOIN users su ON su.email = l.owner_email
               WHERE n.id = ?""",
            (nid,),
        ).fetchone()

    d = negotiation_view(row)
    d.pop("seller" if side == "buyer" else "buyer", None)

    if side != "buyer":
        d.pop("approve_url", None)

    for t in d["transcript"]:
        t["violation"] = bool(t.get("violation"))
        t["natural"] = d["narration"].get(str(t["turn"]))

    history = [
        {
            "who": r["actor"],
            "what": r["action"],
            "detail": r["detail"],
            "at": r["created"],
        }
        for r in audit_rows
    ]

    history += [
        {
            "who": "paypal",
            "what": r["event_type"],
            "detail": None,
            "at": r["created"],
        }
        for r in pp_rows
    ]

    history.sort(key=lambda h: h["at"])

    d["history"] = history
    d["outcome"] = outcome["outcome"] if outcome else None
    d["my_side"] = side
    d["counterparty"] = (
        (names["s"] if side == "buyer" else names["b"]) if names else None
    )

    # "What you gave up": uses only the viewer's own limits.
    d["summary"] = None
    mine = d.get(side)

    if mine and d["agreed_price"] is not None:
        L = Limits(**mine)
        p = d["agreed_price"]
        days = d["agreed_days"]
        is_buyer = side == "buyer"

        price_cushion = (
            L.price_limit - p if is_buyer else p - L.price_limit
        )
        days_cushion = (
            L.delivery_limit - days if is_buyer else days - L.delivery_limit
        )

        d["summary"] = {
            "score": utility(L, p, days),
            "price_given_up": round(
                (p - L.ideal_price) if is_buyer else (L.ideal_price - p),
                2,
            ),
            "days_given_up": (
                days - L.ideal_delivery
                if is_buyer
                else L.ideal_delivery - days
            ),
            "price_cushion": round(price_cushion, 2),
            "days_cushion": days_cushion,
            "near_limit": (
                price_cushion <= 0.05 * L.price_limit
                or days_cushion <= 0
            ),
        }

    d["no_deal_reason"] = (
        _no_deal_reason(d["transcript"])
        if d["status"] == "no_deal"
        else None
    )

    return d


@router.get("/activity")
def activity(request: Request, limit: int = 30):
    """Outcome counts and the PayPal event log for the signed-in user's own deals."""
    u = require_user(request)
    deals = _my_rows(u["email"])
    ids = [d["id"] for d in deals]

    counts: dict = {}

    for d in deals:
        if d["outcome"]:
            counts[d["outcome"]] = counts.get(d["outcome"], 0) + 1

    events = []

    with conn() as c:
        if ids:
            marks = ",".join("?" * len(ids))
            events = c.execute(
                f"""SELECT id, negotiation_id, event_type, verified, created
                    FROM payment_events
                    WHERE negotiation_id IN ({marks})
                    ORDER BY id DESC LIMIT ?""",
                [*ids, limit],
            ).fetchall()

        sim = c.execute(
            "SELECT COUNT(*) AS n FROM negotiations WHERE source = 'simulated'"
        ).fetchone()["n"]

    return {
        "counts": counts,
        "events": [dict(e) for e in events],
        "simulated_deals": sim,
    }


@router.post("/demo/expire/{nid}")
def demo_expire(nid: int, request: Request):
    """Demo only (DEMO_MODE=1): moves the delivery deadline into the past so the void flow can be shown."""
    if os.getenv("DEMO_MODE") != "1":
        raise HTTPException(404, "Not found")

    deal_side(request, nid)

    with conn() as c:
        cur = c.execute(
            """UPDATE negotiations
               SET deliver_by = '2000-01-01'
               WHERE id = ? AND status = 'funds_held'""",
            (nid,),
        )

    if cur.rowcount == 0:
        raise HTTPException(409, "Only deals with held funds can be expired")

    return {"ok": True}
