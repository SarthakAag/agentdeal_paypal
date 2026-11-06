import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

missing = [k for k in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_BASE_URL") if not os.getenv(k)]
if missing:
    raise SystemExit(f"Missing in .env: {missing}")

r = httpx.post(
    os.environ["PAYPAL_BASE_URL"] + "/v1/oauth2/token",
    auth=(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"]),
    data={"grant_type": "client_credentials"},
    timeout=30,
)
print("status:", r.status_code)
print("token length:", len(r.json().get("access_token", "")))