
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .auth import deal_side
from .db import conn

router = APIRouter(tags=["messages"])


def init_messages_table():
    """Create the chat table without modifying existing tables."""
    with conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS deal_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                negotiation_id INTEGER NOT NULL,
                sender_email TEXT NOT NULL,
                sender_side TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_deal_messages
            ON deal_messages (negotiation_id, id)
        """)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.get("/negotiations/{nid}/messages")
def get_messages(nid: int, request: Request):
    side, row = deal_side(request, nid)

    with conn() as c:
        messages = c.execute(
            """
            SELECT id, sender_email, sender_side, body, created_at
            FROM deal_messages
            WHERE negotiation_id = ?
            ORDER BY id ASC
            LIMIT 500
            """,
            (nid,),
        ).fetchall()

    return {
        "negotiation_id": nid,
        "my_side": side,
        "items": [dict(m) for m in messages],
    }


@router.post("/negotiations/{nid}/messages", status_code=201)
def send_message(nid: int, body: MessageIn, request: Request):
    side, row = deal_side(request, nid)

    message = body.body.strip()
    if not message:
        raise HTTPException(422, "Message cannot be empty")

    if len(message) > 2000:
        raise HTTPException(422, "Message is too long")

    with conn() as c:
        cur = c.execute(
            """
            INSERT INTO deal_messages
                (negotiation_id, sender_email, sender_side, body)
            VALUES (?, ?, ?, ?)
            """,
            (nid, request.session["email"].lower(), side, message),
        )

        saved = c.execute(
            """
            SELECT id, sender_email, sender_side, body, created_at
            FROM deal_messages
            WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()

    return {"message": dict(saved)}
