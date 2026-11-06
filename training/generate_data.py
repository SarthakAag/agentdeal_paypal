import argparse
import json
import random
from pathlib import Path

from backend.agentdeal.agents.heuristic import HeuristicAgent
from backend.agentdeal.prompts import action_to_json, build_messages
from backend.agentdeal.rules import utility
from backend.agentdeal.scenarios import PERSONALITIES, random_scenario
from backend.agentdeal.simulator import run_negotiation

OUT_DIR = Path("data/processed")


def make_agent(limits, name, seed):
    p = PERSONALITIES[name]
    return HeuristicAgent(limits, beta=p["beta"], flex=p["flex"], seed=seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000, help="number of simulated negotiations")
    ap.add_argument("--min-utility", type=float, default=0.45, help="keep a closed game's turns only if the agent's final utility >= this")
    ap.add_argument("--nodeal-keep", type=float, default=0.5, help="fraction of no-deal games to use as negative examples")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        (role, split): open(OUT_DIR / f"{role}_{split}.jsonl", "w", encoding="utf-8")
        for role in ("buyer", "seller") for split in ("train", "val")
    }
    rng = random.Random(args.seed)
    names = list(PERSONALITIES)
    stats = {"agreed": 0, "nodeal_used": 0, "buyer": 0, "seller": 0, "negative": 0, "u_buyer": 0.0, "u_seller": 0.0}

    def write(role, split, sc, result, idx, turn, negative):
        limits = sc.buyer if role == "buyer" else sc.seller
        target = {k: turn[k] for k in ("action", "price", "delivery_days", "message")}
        if turn["action"] == "accept":
            prev = result.transcript[idx - 1]
            target["price"], target["delivery_days"] = prev["price"], prev["delivery_days"]
        messages = build_messages(limits, sc.product, turn["round"], result.transcript[:idx])
        messages.append({"role": "assistant", "content": action_to_json(target)})
        files[(role, split)].write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
        stats[role] += 1
        stats["negative"] += int(negative)

    for i in range(args.n):
        sc = random_scenario(args.seed * 1_000_000 + i)
        buyer = make_agent(sc.buyer, rng.choice(names), rng.random())
        seller = make_agent(sc.seller, rng.choice(names), rng.random())
        result = run_negotiation(sc, buyer, seller)
        if result.violations:
            continue
        split = "val" if i % 20 == 0 else "train"

        if result.status == "agreed":
            final = {
                "buyer": utility(sc.buyer, result.agreed_price, result.agreed_days),
                "seller": utility(sc.seller, result.agreed_price, result.agreed_days),
            }
            stats["agreed"] += 1
            stats["u_buyer"] += final["buyer"]
            stats["u_seller"] += final["seller"]
            for idx, turn in enumerate(result.transcript):
                if final[turn["role"]] >= args.min_utility:
                    write(turn["role"], split, sc, result, idx, turn, negative=False)
        elif rng.random() < args.nodeal_keep:
            # Negative examples: no deal was possible, so every offer on the table is outside
            # at least one side's limits. Late rounds teach "counter, do not accept".
            stats["nodeal_used"] += 1
            for idx, turn in enumerate(result.transcript):
                if turn["action"] == "offer":
                    write(turn["role"], split, sc, result, idx, turn, negative=True)

    for f in files.values():
        f.close()

    agreed = max(stats["agreed"], 1)
    total = stats["buyer"] + stats["seller"]
    print(f"Negotiations simulated : {args.n}")
    print(f"Closed deals           : {stats['agreed']} ({stats['agreed'] / args.n:.1%})")
    print(f"No-deal games used     : {stats['nodeal_used']}")
    print(f"Avg buyer utility      : {stats['u_buyer'] / agreed:.3f}")
    print(f"Avg seller utility     : {stats['u_seller'] / agreed:.3f}")
    print(f"Buyer examples         : {stats['buyer']}")
    print(f"Seller examples        : {stats['seller']}")
    print(f"Negative examples      : {stats['negative']} ({stats['negative'] / max(total, 1):.1%} of all)")
    print(f"Files written to       : {OUT_DIR}/")


if __name__ == "__main__":
    main()