import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

r = httpx.post(
    os.environ["PAYPAL_BASE_URL"] + "/v1/oauth2/token",
    auth=(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"]),
    data={"grant_type": "client_credentials"},
    timeout=30,
)
d = r.json()
print("status:", r.status_code)
print("invoicing scope present:", any("invoic" in s for s in d.get("scope", "").split()))
for s in sorted(d.get("scope", "").split()):
    print(" ", s)