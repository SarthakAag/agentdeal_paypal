import argparse
import json
import random
from collections import Counter

from backend.agentdeal.agents.heuristic import HeuristicAgent
from backend.agentdeal.db import conn, init_db
from backend.agentdeal.rules import utility
from backend.agentdeal.scenarios import PERSONALITIES, random_scenario
from backend.agentdeal.simulator import run_negotiation

NAMES = list(PERSONALITIES)
STATUS = {"delivered_on_time": "paid", "delivered_late": "paid", "voided": "voided", "refunded": "refunded"}


def late_probability(sc, price, days):
    """Term-dependent: squeezed on price and/or tight on delivery means more likely late."""
    s = sc.seller
    squeeze = 1 - min(max(utility(s, price, days), 0), 1)
    span = max(s.ideal_delivery - s.delivery_limit, 1)
    tight = min(max(1 - (days - s.delivery_limit) / span, 0), 1)
    return min(max(0.05 + 0.40 * squeeze + 0.30 * tight, 0.02), 0.85)


def draw_outcome(rng, p_late):
    if rng.random() < p_late:
        return "voided" if rng.random() < 0.5 else "delivered_late"
    return "refunded" if rng.random() < 0.04 else "delivered_on_time"


def purge():
    with conn() as c:
        nids = [r["id"] for r in c.execute("SELECT id FROM negotiations WHERE source='simulated'")]
        lids = [r["listing_id"] for r in c.execute("SELECT listing_id FROM negotiations WHERE source='simulated'")]
        for n in nids:
            c.execute("DELETE FROM outcomes WHERE negotiation_id=?", (n,))
            c.execute("DELETE FROM negotiations WHERE id=?", (n,))
        for l in set(lids):
            c.execute("DELETE FROM listings WHERE id=?", (l,))
    print(f"Purged {len(nids)} simulated negotiations")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--engine", choices=["heuristic", "lora"], default="heuristic")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--purge", action="store_true", help="delete all simulated rows and exit")
    args = ap.parse_args()

    init_db()
    if args.purge:
        return purge()

    engine = None
    if args.engine == "lora":
        from backend.agentdeal.agents.lora_agent import LoRAAgent, LoRAEngine
        engine = LoRAEngine()

    rng = random.Random(args.seed)
    stats = Counter()
    for i in range(args.n):
        sc = random_scenario(3_000_000 + args.seed * 100_000 + i)   # disjoint from training and eval seeds
        bstyle, sstyle = rng.choice(NAMES), rng.choice(NAMES)
        if engine:
            b = LoRAAgent(engine, "buyer", sc.buyer, sc.product)
            s = LoRAAgent(engine, "seller", sc.seller, sc.product)
        else:
            pb, ps = PERSONALITIES[bstyle], PERSONALITIES[sstyle]
            b = HeuristicAgent(sc.buyer, pb["beta"], pb["flex"], rng.random())
            s = HeuristicAgent(sc.seller, ps["beta"], ps["flex"], rng.random())
        r = run_negotiation(sc, b, s)

        outcome = status = p_late = None
        if r.status == "agreed":
            p_late = late_probability(sc, r.agreed_price, r.agreed_days)
            outcome = draw_outcome(rng, p_late)
            status = STATUS[outcome]
        else:
            status = "no_deal"

        with conn() as c:
            lid = c.execute(
                "INSERT INTO listings (product, ask_price, min_price, fastest_days, ideal_days) VALUES (?,?,?,?,?)",
                (sc.product, sc.seller.ideal_price, sc.seller.price_limit,
                 sc.seller.delivery_limit, sc.seller.ideal_delivery)).lastrowid
            nid = c.execute(
                """INSERT INTO negotiations (listing_id, engine, buyer_json, seller_json, status, agreed_price,
                   agreed_days, rounds, violations, transcript_json, buyer_approved, seller_approved, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (lid, args.engine, sc.buyer.model_dump_json(), sc.seller.model_dump_json(), status,
                 r.agreed_price, r.agreed_days, r.rounds, r.violations, json.dumps(r.transcript),
                 int(r.status == "agreed"), int(r.status == "agreed"), "simulated")).lastrowid
            if outcome:
                c.execute("INSERT INTO outcomes (negotiation_id, outcome, detail_json) VALUES (?,?,?)",
                          (nid, outcome, json.dumps({"simulated": True, "p_late": round(p_late, 3),
                                                     "buyer_style": bstyle, "seller_style": sstyle})))
        stats[outcome or "no_deal"] += 1
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{args.n}", flush=True)

    print("\nSimulated outcomes:", dict(stats))
    agreed = args.n - stats["no_deal"]
    if agreed:
        bad = stats["voided"] + stats["delivered_late"] + stats["refunded"]
        print(f"Closed deals: {agreed} | with a bad outcome: {bad} ({bad / agreed:.0%})")


if __name__ == "__main__":
    main()