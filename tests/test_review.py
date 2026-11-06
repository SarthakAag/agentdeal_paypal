import backend.agentdeal.db as db
from tests.test_accounts import app, signup  # noqa: F401  (fixture and helper)

LISTING = {"product": "Brand kit", "ask_price": 10000, "min_price": 8500, "fastest_days": 20, "ideal_days": 24}
MANDATE = {"budget": 9000, "ideal_price": 7000, "latest_days": 19, "ideal_days": 10, "max_rounds": 8}


def setup_deal(app):
    seller = signup(app, "Sam Seller", "s@x.com", "seller")
    buyer = signup(app, "Bea Buyer", "b@x.com", "buyer")
    lid = seller.post("/api/listings", json=LISTING).json()["id"]
    r = buyer.post("/api/negotiations", json={"listing_id": lid, "mandate": MANDATE})
    assert r.status_code == 201, r.text
    return seller, buyer, r.json()["id"], r.json()["status"]


def test_near_miss_goes_to_seller_then_buyer(app):
    seller, buyer, nid, status = setup_deal(app)
    assert status == "seller_review"
    d = buyer.get(f"/api/negotiations/{nid}").json()
    assert d["proposal_price"] == 9000 and d["proposal_days"] == 19
    assert buyer.post(f"/api/negotiations/{nid}/review", json={"accept": True}).status_code == 403

    notes = seller.get("/api/notifications").json()
    assert notes["unread"] >= 1 and any("could not close" in n["text"] for n in notes["items"])

    assert seller.post(f"/api/negotiations/{nid}/review", json={"accept": True}).json()["status"] == "awaiting_approval"
    assert buyer.post(f"/api/negotiations/{nid}/decision", json={"approve": True}).json()["status"] == "approved"
    assert buyer.get(f"/api/negotiations/{nid}").json()["agreed_price"] == 9000


def test_decline_notifies_buyer(app):
    seller, buyer, nid, _ = setup_deal(app)
    assert seller.post(f"/api/negotiations/{nid}/review", json={"accept": False}).json()["status"] == "no_deal"
    texts = [n["text"] for n in buyer.get("/api/notifications").json()["items"]]
    assert any("declined your final offer" in t for t in texts)


def test_unanswered_review_expires_and_notifies_buyer(app):
    seller, buyer, nid, _ = setup_deal(app)
    with db.conn() as c:
        c.execute("UPDATE negotiations SET review_by='2000-01-01 00:00:00' WHERE id=?", (nid,))
    assert buyer.get(f"/api/negotiations/{nid}").json()["status"] == "no_deal"
    texts = [n["text"] for n in buyer.get("/api/notifications").json()["items"]]
    assert any("did not answer in time" in t for t in texts)