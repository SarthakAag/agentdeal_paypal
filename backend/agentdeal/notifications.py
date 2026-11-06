from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .auth import require_user
from .db import conn

router = APIRouter(tags=["notifications"])


class MarkReadIn(BaseModel):
    ids: Optional[list[int]] = None


@router.get("/notifications")
def get_notifications(request: Request, limit: int = 50):
    user = require_user(request)
    email = user["email"].lower()
    limit = max(1, min(limit, 200))

    with conn() as c:
        rows = c.execute(
            """
            SELECT id, negotiation_id, text, is_read, created
            FROM notifications
            WHERE user_email = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (email, limit),
        ).fetchall()

        unread = c.execute(
            """
            SELECT COUNT(*) AS total
            FROM notifications
            WHERE user_email = ? AND is_read = 0
            """,
            (email,),
        ).fetchone()["total"]

    items = []
    for row in rows:
        item = dict(row)
        item["is_read"] = bool(item["is_read"])
        # Keep compatibility with frontend components that use n.read.
        item["read"] = item["is_read"]
        items.append(item)

    return {
        "items": items,
        "unread": unread,
    }


@router.post("/notifications/read")
def mark_notifications_read(
    request: Request,
    body: MarkReadIn = MarkReadIn(),
):
    user = require_user(request)
    email = user["email"].lower()

    with conn() as c:
        if body.ids:
            ids = list(set(body.ids))
            placeholders = ",".join("?" for _ in ids)

            result = c.execute(
                f"""
                UPDATE notifications
                SET is_read = 1
                WHERE user_email = ?
                  AND id IN ({placeholders})
                """,
                [email, *ids],
            )
        else:
            result = c.execute(
                """
                UPDATE notifications
                SET is_read = 1
                WHERE user_email = ? AND is_read = 0
                """,
                (email,),
            )

    return {"ok": True, "updated": result.rowcount}