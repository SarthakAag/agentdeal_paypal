import pytest
from fastapi.testclient import TestClient

from backend.agentdeal.auth import hash_password, verify_password

LISTING = {"product": "Logo design", "ask_price": 5000, "min_price": 3200, "fastest_days": 3, "ideal_days": 8}
MANDATE = {"budget": 4200, "ideal_price": 3000, "latest_days": 10, "ideal_days": 4}


def test_password_hash():
    h = hash_password("correct horse")
    assert verify_password("correct horse", h)
    assert not verify_password("wrong", h)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setenv("HTTPS_ONLY", "0")
    monkeypatch.delenv("AGENTDEAL_ENGINE", raising=False)
    import backend.agentdeal.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    from backend.agentdeal.main import app
    db.init_db()
    return app


def signup(app, name, email, role):
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"name": name, "email": email, "password": "password123", "role": role})
    assert r.status_code == 200, r.text
    return c


def test_duplicate_and_login(app):
    signup(app, "Sam Seller", "s@x.com", "seller")
    c = TestClient(app)
    dup = c.post("/api/auth/register", json={"name": "Sam", "email": "S@x.com", "password": "password123", "role": "seller"})
    assert dup.status_code == 409
    assert c.post("/api/auth/login", json={"email": "s@x.com", "password": "nope-nope"}).status_code == 401
    assert c.post("/api/auth/login", json={"email": "s@x.com", "password": "password123"}).status_code == 200
    assert c.get("/api/auth/me").json()["user"]["role"] == "seller"


def test_roles_and_privacy(app):
    seller, buyer = signup(app, "Sam Seller", "s@x.com", "seller"), signup(app, "Bea Buyer", "b@x.com", "buyer")
    stranger = signup(app, "Eve Other", "e@x.com", "buyer")

    assert buyer.post("/api/listings", json=LISTING).status_code == 403        # buyers cannot list
    lid = seller.post("/api/listings", json=LISTING).json()["id"]
    body = {"listing_id": lid, "mandate": MANDATE}
    assert seller.post("/api/negotiations", json=body).status_code == 403      # sellers cannot buy

    r = buyer.post("/api/negotiations", json=body)
    assert r.status_code == 201 and set(r.json()) == {"id", "status"}          # no limits in the response
    nid = r.json()["id"]

    bv, sv = buyer.get(f"/api/negotiations/{nid}").json(), seller.get(f"/api/negotiations/{nid}").json()
    assert bv["my_side"] == "buyer" and "seller" not in bv
    assert sv["my_side"] == "seller" and "buyer" not in sv
    assert stranger.get(f"/api/negotiations/{nid}").status_code == 404
    assert TestClient(app).get(f"/api/negotiations/{nid}").status_code == 401

    assert seller.post(f"/api/negotiations/{nid}/pay").status_code == 403      # only the buyer pays
    assert buyer.post(f"/api/negotiations/{nid}/deliver").status_code == 403   # only the seller delivers
    assert stranger.post(f"/api/negotiations/{nid}/decision", json={"approve": True}).status_code == 404

    assert buyer.post(f"/api/negotiations/{nid}/decision", json={"approve": True}).json()["status"] == "awaiting_approval"
    assert seller.post(f"/api/negotiations/{nid}/decision", json={"approve": True}).json()["status"] == "approved"
    hist = [h["what"] for h in buyer.get(f"/api/negotiations/{nid}").json()["history"]]
    assert hist[0] == "negotiation_started" and "both_approved" in hist