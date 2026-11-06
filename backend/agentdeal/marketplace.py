import json
import os
import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from .agents.heuristic import HeuristicAgent
from .auth import deal_side, require_user
from .db import audit, conn, negotiation_view, review_minutes
from .engine import get_engine
from .rules import utility
from .schemas import Limits, Scenario
from .simulator import run_negotiation

router = APIRouter(tags=["marketplace"])

_lock = threading.Lock()   # one GPU, one negotiation at a time
ESCALATE_GAP = 0.15        # final prices this close (share of the seller's last offer) go to a human


class ListingIn(BaseModel):
    product: str = Field(min_length=1, max_length=120)
    ask_price: float = Field(gt=0)        # seller's hoped-for price
    min_price: float = Field(gt=0)        # seller's walk-away price (private)
    fastest_days: int = Field(ge=1)       # fastest the seller can deliver (private)
    ideal_days: int = Field(ge=1)

    @model_validator(mode="after")
    def check(self):
        if self.ask_price < self.min_price:
            raise ValueError("ask_price cannot be below min_price")
        if self.ideal_days < self.fastest_days:
            raise ValueError("ideal_days cannot be below fastest_days")
        return self


class MandateIn(BaseModel):
    budget: float = Field(gt=0)           # buyer's walk-away price (private)
    ideal_price: float = Field(gt=0)
    latest_days: int = Field(ge=1)        # latest acceptable delivery (private)
    ideal_days: int = Field(ge=1)
    max_rounds: int = Field(default=8, ge=2, le=12)

    @model_validator(mode="after")
    def check(self):
        if self.ideal_price > self.budget:
            raise ValueError("ideal_price cannot exceed budget")
        if self.ideal_days > self.latest_days:
            raise ValueError("ideal_days cannot exceed latest_days")
        return self


class NegotiationIn(BaseModel):
    listing_id: int
    mandate: MandateIn


class BidIn(BaseModel):
    listing_ids: list[int] = Field(min_length=2, max_length=5)
    mandate: MandateIn

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.listing_ids)) != len(self.listing_ids):
            raise ValueError("listing_ids must be different listings")
        return self


class DecisionIn(BaseModel):
    approve: bool = True


class ReviewIn(BaseModel):
    accept: bool


def _agents(sc: Scenario):
    """Pick fine-tuned agents if AGENTDEAL_ENGINE=lora, otherwise heuristic agents."""
    if os.getenv("AGENTDEAL_ENGINE", "heuristic") == "lora":
        from .agents.lora_agent import LoRAAgent
        engine = get_engine()
        return (LoRAAgent(engine, "buyer", sc.buyer, sc.product),
                LoRAAgent(engine, "seller", sc.seller, sc.product), "lora")
    return (HeuristicAgent(sc.buyer, beta=1.2, flex=0.5),
            HeuristicAgent(sc.seller, beta=1.2, flex=0.5), "heuristic")


def _near_miss(transcript: list):
    """If the agents failed but their final public offers were close on price, return the buyer's final
    offer (price, days). It is always inside the buyer's limits, because the rule engine checked it."""
    offers = [t for t in transcript if t.get("action") == "offer"]
    b = [t for t in offers if t["role"] == "buyer"]
    s = [t for t in offers if t["role"] == "seller"]
    if not b or not s or s[-1]["price"] <= 0:
        return None
    if b[-1]["price"] < (1 - ESCALATE_GAP) * s[-1]["price"]:
        return None
    return b[-1]["price"], b[-1]["delivery_days"]


def _open_listing(lid: int, user: dict):
    with conn() as c:
        row = c.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
    if not row or row["active"] == 0 or not row["owner_email"]:
        raise HTTPException(404, f"Listing {lid} not found")
    if row["owner_email"].lower() == user["email"]:
        raise HTTPException(409, "You can't negotiate on your own listing")
    return row


def _negotiate_listing(row, m: MandateIn, buyer_email: str):
    """Runs one negotiation against a listing and stores it. Returns (id, buyer limits, result, status)."""
    seller = Limits(role="seller", price_limit=row["min_price"], ideal_price=row["ask_price"],
                    delivery_limit=row["fastest_days"], ideal_delivery=row["ideal_days"], max_rounds=m.max_rounds)
    buyer = Limits(role="buyer", price_limit=m.budget, ideal_price=m.ideal_price,
                   delivery_limit=m.latest_days, ideal_delivery=m.ideal_days, max_rounds=m.max_rounds)
    sc = Scenario(product=row["product"], buyer=buyer, seller=seller)

    with _lock:
        b_agent, s_agent, engine = _agents(sc)
        result = run_negotiation(sc, b_agent, s_agent)

    status = "awaiting_approval" if result.status == "agreed" else "no_deal"
    proposal = _near_miss(result.transcript) if status == "no_deal" else None
    if proposal:
        status = "seller_review"

    with conn() as c:
        cur = c.execute(
            """INSERT INTO negotiations (listing_id, engine, buyer_json, seller_json, status, agreed_price,
               agreed_days, rounds, violations, transcript_json, buyer_email) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (row["id"], engine, buyer.model_dump_json(), seller.model_dump_json(), status,
             result.agreed_price, result.agreed_days, result.rounds, result.violations,
             json.dumps(result.transcript), buyer_email),
        )
        nid = cur.lastrowid
        if proposal:
            c.execute("UPDATE negotiations SET proposal_price=?, proposal_days=?, review_by=datetime('now', ?) "
                      "WHERE id=?", (proposal[0], proposal[1], f"+{review_minutes()} minutes", nid))

    audit(nid, "system", "negotiation_started",
          f"{engine} agents, {result.rounds} rounds, {status.replace('_', ' ')}")
    if status == "awaiting_approval":
        audit(nid, "system", "deal_reached")
    elif status == "seller_review":
        audit(nid, "system", "review_requested", f"final offer ₹{proposal[0]:,.0f}, {proposal[1]} days")
    else:
        audit(nid, "system", "no_deal")
    return nid, buyer, result, status


@router.post("/listings", status_code=201)
def create_listing(body: ListingIn, request: Request):
    u = require_user(request, "seller")
    with conn() as c:
        cur = c.execute(
            "INSERT INTO listings (product, ask_price, min_price, fastest_days, ideal_days, owner_email) "
            "VALUES (?,?,?,?,?,?)",
            (body.product, body.ask_price, body.min_price, body.fastest_days, body.ideal_days, u["email"]),
        )
        lid = cur.lastrowid
    return {"id": lid, **body.model_dump()}


@router.post("/listings/{lid}/close")
def close_listing(lid: int, request: Request):
    """Hides the listing from the marketplace. Deals already in progress continue."""
    u = require_user(request, "seller")
    with conn() as c:
        r = c.execute("SELECT owner_email FROM listings WHERE id=?", (lid,)).fetchone()
        if not r or (r["owner_email"] or "").lower() != u["email"]:
            raise HTTPException(404, "Listing not found")
        c.execute("UPDATE listings SET active=0 WHERE id=?", (lid,))
    return {"ok": True}


@router.post("/negotiations", status_code=201)
def start_negotiation(body: NegotiationIn, request: Request):
    u = require_user(request, "buyer")
    row = _open_listing(body.listing_id, u)
    nid, _, _, status = _negotiate_listing(row, body.mandate, u["email"])
    return {"id": nid, "status": status}   # nothing about the seller's limits


@router.post("/bids", status_code=201)
def bid(body: BidIn, request: Request):
    """One buyer mandate against several listings, ranked by the buyer's own score.
    The response holds public offers and the buyer's score only."""
    u = require_user(request, "buyer")
    rows = [_open_listing(i, u) for i in body.listing_ids]
    bids = []
    for row in rows:
        nid, buyer, result, status = _negotiate_listing(row, body.mandate, u["email"])
        agreed = result.status == "agreed"
        bids.append({
            "negotiation_id": nid,
            "listing_id": row["id"],
            "product": row["product"],
            "ask_price": row["ask_price"],
            "status": status,
            "agreed_price": result.agreed_price,
            "agreed_days": result.agreed_days,
            "rounds": result.rounds,
            "score": utility(buyer, result.agreed_price, result.agreed_days) if agreed else None,
        })
    bids.sort(key=lambda b: (b["score"] is None, -(b["score"] or 0), b["agreed_price"] or 0))
    best = bids[0]["negotiation_id"] if bids and bids[0]["score"] is not None else None
    return {"bids": bids, "best": best}


@router.post("/negotiations/{nid}/review")
def review(nid: int, body: ReviewIn, request: Request):
    """The seller decides on the buyer's final offer after the agents failed to close."""
    side, row = deal_side(request, nid)
    if side != "seller":
        raise HTTPException(403, "Only the seller can answer this")
    if row["status"] != "seller_review":
        raise HTTPException(409, f"This deal is {row['status'].replace('_', ' ')}, not waiting for your review")
    with conn() as c:
        if body.accept:
            cur = c.execute(
                "UPDATE negotiations SET status='awaiting_approval', agreed_price=proposal_price, "
                "agreed_days=proposal_days, seller_approved=1, buyer_approved=0 "
                "WHERE id=? AND status='seller_review'", (nid,))
        else:
            cur = c.execute("UPDATE negotiations SET status='no_deal' WHERE id=? AND status='seller_review'", (nid,))
    if cur.rowcount == 0:
        raise HTTPException(409, "This review was already answered or has expired")
    if body.accept:
        audit(nid, "seller", "review_accepted", f"₹{row['proposal_price']:,.0f} in {row['proposal_days']} days")
        return {"status": "awaiting_approval"}
    audit(nid, "seller", "review_declined")
    return {"status": "no_deal"}


@router.post("/negotiations/{nid}/decision")
def decide(nid: int, body: DecisionIn, request: Request):
    """Each human approves or declines as their own side. Payment unlocks only when both approve."""
    side, row = deal_side(request, nid)
    if row["status"] != "awaiting_approval":
        raise HTTPException(409, f"Negotiation is {row['status'].replace('_', ' ')}, not awaiting approval")
    both = False
    with conn() as c:
        if not body.approve:
            c.execute("UPDATE negotiations SET status='declined' WHERE id=?", (nid,))
        else:
            c.execute(f"UPDATE negotiations SET {side}_approved=1 WHERE id=?", (nid,))
            r = c.execute("SELECT buyer_approved, seller_approved FROM negotiations WHERE id=?", (nid,)).fetchone()
            both = bool(r["buyer_approved"] and r["seller_approved"])
            if both:
                c.execute("UPDATE negotiations SET status='approved' WHERE id=?", (nid,))
        out = c.execute("SELECT status, buyer_approved, seller_approved FROM negotiations WHERE id=?", (nid,)).fetchone()
    audit(nid, side, "approved" if body.approve else "declined")
    if both:
        audit(nid, "system", "both_approved")
    return {"status": out["status"], "buyer_approved": bool(out["buyer_approved"]),
            "seller_approved": bool(out["seller_approved"])}