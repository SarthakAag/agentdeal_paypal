
import json
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .assist_prompts import (
    derive_mandate,
    extract_json,
    fmt_days,
    fmt_inr,
    move_style,
    narrator_messages,
    parser_messages,
)
from .auth import deal_side, require_user
from .db import conn
from .engine import get_engine

router = APIRouter(tags=["assist"])

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def available() -> bool:
    adapters = all(
        (Path("models") / f"{r}_lora" / "adapter_config.json").exists()
        for r in ("parser", "narrator")
    )
    return os.getenv("AGENTDEAL_ASSIST") == "local" and adapters


def numbers_ok(
    text: str,
    price: Optional[float],
    days: Optional[int],
) -> bool:
    """A rewritten message may contain only the original price and delivery days, nothing else numeric."""
    vals = [float(n.replace(",", "")) for n in NUM.findall(text)]

    if price is None or days is None:
        return not vals

    price_hit = day_hit = False

    for v in vals:
        if abs(v - price) <= 0.5:
            price_hit = True
        elif v == days:
            day_hit = True
        else:
            return False

    return price_hit and day_hit


@router.get("/assist/status")
def status():
    return {"available": available()}


class MandateTextIn(BaseModel):
    text: str = Field(min_length=3, max_length=500)
    ask_price: Optional[float] = None


@router.post("/assist/mandate")
def parse_mandate(body: MandateTextIn, request: Request):
    require_user(request, "buyer")

    if not available():
        raise HTTPException(503, "AI assist is not configured")

    try:
        raw = get_engine().generate(
            "parser",
            parser_messages(body.text, body.ask_price),
        )
    except Exception as e:
        raise HTTPException(
            502, f"Model error: {e.__class__.__name__}"
        )

    d = extract_json(raw)

    if not isinstance(d, dict):
        raise HTTPException(
            502,
            "The model reply could not be read. Please fill the form by hand.",
        )

    fields, missing = derive_mandate(d, body.ask_price)

    return {"fields": fields, "missing": missing, "note": ""}


@router.post("/negotiations/{nid}/narrate")
def narrate(nid: int, request: Request):
    deal_side(request, nid)

    if not available():
        raise HTTPException(503, "AI assist is not configured")

    with conn() as c:
        row = c.execute(
            """
            SELECT transcript_json, narration_json, buyer_json
            FROM negotiations
            WHERE id=?
            """,
            (nid,),
        ).fetchone()

    if not row:
        raise HTTPException(404, "Negotiation not found")

    if row["narration_json"]:
        return {
            "narrated": len(json.loads(row["narration_json"])),
            "cached": True,
        }

    transcript = json.loads(row["transcript_json"] or "[]")
    max_rounds = json.loads(row["buyer_json"]).get("max_rounds", 8)

    engine = get_engine()
    out, rejected, last = {}, 0, {}

    try:
        for i, t in enumerate(transcript):
            if t["action"] == "reject":
                continue

            if t["action"] == "accept" and i > 0:
                src, style = transcript[i - 1], "accept"
            else:
                src = t
                style = move_style(
                    t["round"],
                    max_rounds,
                    last.get(t["role"]),
                    t["price"],
                )
                last[t["role"]] = t["price"]

            move = {
                "speaker": t["role"],
                "action": t["action"],
                "style": style,
                "price": fmt_inr(src["price"]),
                "delivery": fmt_days(src["delivery_days"]),
            }

            text = (
                engine.generate("narrator", narrator_messages(move))
                .strip()
                .split("\n")[0]
                .strip('"')
            )

            if text and numbers_ok(
                text, src["price"], src["delivery_days"]
            ):
                out[str(t["turn"])] = text[:300]
            else:
                rejected += 1  # Keep the original templated message.

    except Exception as e:
        raise HTTPException(
            502, f"Model error: {e.__class__.__name__}"
        )

    with conn() as c:
        c.execute(
            "UPDATE negotiations SET narration_json=? WHERE id=?",
            (json.dumps(out), nid),
        )

    return {
        "narrated": len(out),
        "rejected_by_number_check": rejected,
        "cached": False,
    }
