import argparse
import json
from collections import Counter
from pathlib import Path

from backend.agentdeal.db import conn
from backend.agentdeal.prompts import action_to_json, build_messages
from backend.agentdeal.rules import utility
from backend.agentdeal.schemas import Limits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-utility", type=float, default=0.45)
    ap.add_argument("--out", default="data/processed")
    args = ap.parse_args()

    with conn() as c:
        deals = c.execute(
            """SELECT n.*, l.product, o.outcome FROM negotiations n
               JOIN listings l ON l.id = n.listing_id
               JOIN outcomes o ON o.negotiation_id = n.id
               WHERE n.source = 'simulated'""").fetchall()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = {r: open(out / f"sim_{r}_train.jsonl", "w", encoding="utf-8") for r in ("buyer", "seller")}
    seen, kept, rows = Counter(), Counter(), Counter()

    for d in deals:
        seen[d["outcome"]] += 1
        if d["outcome"] != "delivered_on_time":
            continue   # late, voided and refunded deals are excluded, not imitated
        limits = {"buyer": Limits(**json.loads(d["buyer_json"])), "seller": Limits(**json.loads(d["seller_json"]))}
        util = {r: utility(limits[r], d["agreed_price"], d["agreed_days"]) for r in limits}
        transcript = json.loads(d["transcript_json"])
        for role in ("buyer", "seller"):
            if util[role] < args.min_utility:
                continue
            kept[role] += 1
            for idx, t in enumerate(transcript):
                if t["role"] != role:
                    continue
                tgt = {k: t[k] for k in ("action", "price", "delivery_days", "message")}
                if t["action"] == "accept":
                    tgt["price"], tgt["delivery_days"] = transcript[idx - 1]["price"], transcript[idx - 1]["delivery_days"]
                msgs = build_messages(limits[role], d["product"], t["round"], transcript[:idx])
                msgs.append({"role": "assistant", "content": action_to_json(tgt)})
                files[role].write(json.dumps({"messages": msgs}, ensure_ascii=False) + "\n")
                rows[role] += 1

    for f in files.values():
        f.close()
    print("Outcomes seen      :", dict(seen))
    print("Deals kept as positives:", dict(kept))
    print("Training rows      :", dict(rows))
    print(f"Written to {out}/sim_buyer_train.jsonl and sim_seller_train.jsonl")


if __name__ == "__main__":
    main()