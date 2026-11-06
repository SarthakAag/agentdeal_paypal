import json
import os
import sqlite3
from pathlib import Path

DB_PATH = Path("data/agentdeal.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product TEXT NOT NULL,
    ask_price REAL NOT NULL,
    min_price REAL NOT NULL,
    fastest_days INTEGER NOT NULL,
    ideal_days INTEGER NOT NULL,
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS negotiations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    engine TEXT NOT NULL,
    buyer_json TEXT NOT NULL,
    seller_json TEXT NOT NULL,
    status TEXT NOT NULL,
    agreed_price REAL,
    agreed_days INTEGER,
    rounds INTEGER,
    violations INTEGER DEFAULT 0,
    transcript_json TEXT,
    buyer_approved INTEGER DEFAULT 0,
    seller_approved INTEGER DEFAULT 0,
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS payment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negotiation_id INTEGER,
    event_type TEXT NOT NULL,
    verified INTEGER DEFAULT 0,
    payload_json TEXT,
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negotiation_id INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    detail_json TEXT,
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negotiation_id INTEGER NOT NULL,
    actor TEXT,
    action TEXT NOT NULL,
    detail TEXT,
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    negotiation_id INTEGER,
    text TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Added after the first version; applied to existing databases automatically.
NEW_COLUMNS = {
    "paypal_order_id": "TEXT",
    "paypal_auth_id": "TEXT",
    "paypal_capture_id": "TEXT",
    "amount_usd": "REAL",
    "approve_url": "TEXT",
    "invoice_id": "TEXT",
    "invoice_number": "TEXT",
    "invoice_url": "TEXT",
    "invoice_status": "TEXT",
    "deliver_by": "TEXT",
    "paypal_refund_id": "TEXT",
    "source": "TEXT",
    "narration_json": "TEXT",
    "buyer_email": "TEXT",
    "proposal_price": "REAL",
    "proposal_days": "INTEGER",
    "review_by": "TEXT",
}

LISTING_COLUMNS = {
    "owner_email": "TEXT",
    "active": "INTEGER DEFAULT 1",
}

HIDDEN = ("buyer_email", "owner_email", "paypal_order_id", "paypal_auth_id", "paypal_capture_id",
          "paypal_refund_id", "invoice_id", "invoice_number", "invoice_url", "invoice_status")


def conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)
        have = {r["name"] for r in c.execute("PRAGMA table_info(negotiations)")}
        for name, typ in NEW_COLUMNS.items():
            if name not in have:
                c.execute(f"ALTER TABLE negotiations ADD COLUMN {name} {typ}")
        have = {r["name"] for r in c.execute("PRAGMA table_info(listings)")}
        for name, typ in LISTING_COLUMNS.items():
            if name not in have:
                c.execute(f"ALTER TABLE listings ADD COLUMN {name} {typ}")


# ---------------------------------------------------------------- notifications

# action -> who is told and what. "other" means the side that did not perform the action.
_RULES = {
    "deal_reached": [("seller", "{p}: a buyer's agent reached terms with yours. Review and approve the deal.")],
    "review_requested": [
        ("seller", "{p}: the agents could not close. The buyer's final offer needs your decision."),
        ("buyer", "{p}: the agents could not close, so your final offer was sent to the seller to decide."),
    ],
    "review_accepted": [("buyer", "{p}: the seller accepted your final offer. Approve the deal to continue.")],
    "review_declined": [("buyer", "{p}: the seller declined your final offer. No deal.")],
    "review_expired": [
        ("buyer", "{p}: the seller did not answer in time. No deal."),
        ("seller", "{p}: the review window closed with no answer. No deal."),
    ],
    "no_deal": [("buyer", "{p}: no deal. The offers were too far apart.")],
    "approved": [("other", "{p}: the {actor} approved the deal.")],
    "declined": [("other", "{p}: the {actor} declined the deal.")],
    "both_approved": [
        ("buyer", "{p}: both sides approved. You can pay now."),
        ("seller", "{p}: both sides approved. Waiting for the buyer to pay."),
    ],
    "payment_started": [("seller", "{p}: the buyer started the PayPal payment.")],
    "payment_cancelled": [("buyer", "{p}: the payment was cancelled at PayPal. You can try again.")],
    "funds_held": [
        ("seller", "{p}: the buyer's money is on hold ({detail}). Confirm delivery to get paid."),
        ("buyer", "{p}: your payment is on hold until delivery ({detail})."),
    ],
    "delivered": [
        ("buyer", "{p}: delivery confirmed and payment captured."),
        ("seller", "{p}: delivery confirmed and you were paid."),
    ],
    "voided": [
        ("buyer", "{p}: the held funds were released to you."),
        ("seller", "{p}: the buyer's held funds were released."),
    ],
    "refunded": [
        ("buyer", "{p}: the payment was refunded to you."),
        ("seller", "{p}: the payment was refunded to the buyer."),
    ],
    "status_paid": [
        ("buyer", "{p}: PayPal confirmed the payment."),
        ("seller", "{p}: PayPal confirmed the payment."),
    ],
    "status_voided": [
        ("buyer", "{p}: PayPal confirmed the held funds were released."),
        ("seller", "{p}: PayPal confirmed the held funds were released."),
    ],
    "status_refunded": [
        ("buyer", "{p}: PayPal confirmed the refund."),
        ("seller", "{p}: PayPal confirmed the refund."),
    ],
}


def notify(email, nid, text) -> None:
    if not email:
        return
    with conn() as c:
        c.execute("INSERT INTO notifications (user_email, negotiation_id, text) VALUES (?,?,?)",
                  (email.lower(), nid, text))


def _notify_from_audit(nid: int, actor: str, action: str, detail) -> None:
    rules = _RULES.get(action)
    if not rules:
        return
    with conn() as c:
        r = c.execute(
            "SELECT n.buyer_email, l.owner_email, l.product FROM negotiations n "
            "JOIN listings l ON l.id = n.listing_id WHERE n.id=?", (nid,)).fetchone()
    if not r:
        return
    emails = {"buyer": r["buyer_email"], "seller": r["owner_email"]}
    for who, text in rules:
        if who == "other":
            if actor not in emails:
                continue
            who = "seller" if actor == "buyer" else "buyer"
        notify(emails.get(who), nid, text.format(p=r["product"], actor=actor, detail=detail or ""))


def audit(nid: int, actor: str, action: str, detail: str | None = None) -> None:
    """History of a deal, and the source of notifications. Call it after any open `with conn()` block
    has finished, otherwise SQLite reports the database as locked."""
    with conn() as c:
        c.execute("INSERT INTO audit (negotiation_id, actor, action, detail) VALUES (?,?,?,?)",
                  (nid, actor, action, detail))
    _notify_from_audit(nid, actor, action, detail)


def expire_reviews() -> None:
    """A seller review nobody answered in time ends as 'no deal', and both sides are told."""
    with conn() as c:
        ids = [r["id"] for r in c.execute(
            "SELECT id FROM negotiations WHERE status='seller_review' AND review_by IS NOT NULL "
            "AND review_by < datetime('now')")]
        for i in ids:
            c.execute("UPDATE negotiations SET status='no_deal' WHERE id=? AND status='seller_review'", (i,))
    for i in ids:
        audit(i, "system", "review_expired")


def review_minutes() -> int:
    return int(float(os.getenv("REVIEW_HOURS", "24")) * 60)


def negotiation_view(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["transcript"] = json.loads(d.pop("transcript_json") or "[]")
    d["buyer"] = json.loads(d.pop("buyer_json"))
    d["seller"] = json.loads(d.pop("seller_json"))
    d["narration"] = json.loads(d.pop("narration_json", None) or "{}")
    for k in HIDDEN:
        d.pop(k, None)
    return d