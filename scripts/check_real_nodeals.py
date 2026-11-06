# scripts/check_real_nodeals.py
import json
from backend.agentdeal.db import conn

with conn() as c:
    rows = c.execute(
        """SELECT n.id, l.product, n.status, n.engine, n.buyer_json, n.seller_json
           FROM negotiations n JOIN listings l ON l.id = n.listing_id
           WHERE n.agreed_price IS NULL AND (n.source IS NULL OR n.source != 'simulated')
           ORDER BY n.id""").fetchall()

feasible = 0
for r in rows:
    b, s = json.loads(r["buyer_json"]), json.loads(r["seller_json"])
    gaps = []
    if b["price_limit"] < s["price_limit"]:
        gaps.append(f"price: buyer max {b['price_limit']:,.0f} < seller min {s['price_limit']:,.0f}")
    if b["delivery_limit"] < s["delivery_limit"]:
        gaps.append(f"delivery: buyer needs <= {b['delivery_limit']} d, seller needs >= {s['delivery_limit']} d")
    if not gaps:
        feasible += 1
    print(f"#{r['id']:<4} {r['engine']:<9} {r['product'][:24]:<24} " + ("; ".join(gaps) or "OVERLAP EXISTS, agents should have closed"))
print(f"\n{len(rows)} deals without agreement, {feasible} where the limits overlapped")