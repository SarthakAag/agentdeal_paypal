import json
import sqlite3

c = sqlite3.connect("data/agentdeal.db")
c.row_factory = sqlite3.Row
rows = c.execute("SELECT buyer_json, seller_json, transcript_json FROM negotiations "
                 "WHERE source='simulated' AND engine='lora' AND status='no_deal'").fetchall()
n = bad_b = bad_s = 0
for r in rows:
    b, s = json.loads(r["buyer_json"]), json.loads(r["seller_json"])
    if not (b["price_limit"] >= s["price_limit"] and b["delivery_limit"] >= s["delivery_limit"]):
        continue   # infeasible deals can never close
    t = [x for x in json.loads(r["transcript_json"]) if x["action"] == "offer"]
    lb = [x for x in t if x["role"] == "buyer"][-1]
    ls = [x for x in t if x["role"] == "seller"][-1]
    n += 1
    # can the seller accept the buyer's last offer? can the buyer accept the seller's?
    bad_s += not (lb["price"] >= s["price_limit"] and lb["delivery_days"] >= s["delivery_limit"])
    bad_b += not (ls["price"] <= b["price_limit"] and ls["delivery_days"] <= b["delivery_limit"])
print(f"feasible deals that failed: {n}")
print(f"buyer's last offer unacceptable to seller: {bad_s}")
print(f"seller's last offer unacceptable to buyer: {bad_b}")