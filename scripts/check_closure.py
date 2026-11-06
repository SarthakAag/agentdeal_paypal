import json
import sqlite3

c = sqlite3.connect("data/agentdeal.db")
c.row_factory = sqlite3.Row
rows = c.execute("SELECT status, buyer_json, seller_json FROM negotiations WHERE source='simulated' AND engine='lora'").fetchall()
feasible = closed = feasible_closed = 0
for r in rows:
    b, s = json.loads(r["buyer_json"]), json.loads(r["seller_json"])
    ok = b["price_limit"] >= s["price_limit"] and b["delivery_limit"] >= s["delivery_limit"]
    done = r["status"] != "no_deal"
    feasible += ok
    closed += done
    feasible_closed += ok and done
print(f"lora deals: {len(rows)} | feasible: {feasible} | closed: {closed} | feasible AND closed: {feasible_closed}")
print(f"closure on feasible deals: {feasible_closed / max(feasible, 1):.0%}")