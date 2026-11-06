import argparse
import json
from pathlib import Path

from backend.agentdeal.agents.heuristic import HeuristicAgent
from backend.agentdeal.rules import utility
from backend.agentdeal.scenarios import PERSONALITIES, random_scenario
from backend.agentdeal.simulator import run_negotiation

NAMES = list(PERSONALITIES)
SEED0 = 1_000_000   # training used seeds 0..19999, so these scenarios are unseen


def heur(limits, name, seed):
    p = PERSONALITIES[name]
    return HeuristicAgent(limits, p["beta"], p["flex"], seed)


def summarize(rows):
    n = len(rows)
    feas = [r for r in rows if r["feasible"]]
    closed = [r for r in rows if r["agreed"]]
    c = max(len(closed), 1)
    return {
        "negotiations": n,
        "closure_all": round(len(closed) / n, 3),
        "closure_feasible": round(sum(r["agreed"] for r in feas) / max(len(feas), 1), 3),
        "utility_closed": round(sum(r["u"] for r in closed) / c, 3),
        "score_incl_failures": round(sum(r["u"] for r in rows) / n, 3),
        "fairness_gap": round(sum(abs(r["u"] - r["u_opp"]) for r in closed) / c, 3),
        "avg_rounds": round(sum(r["rounds"] for r in closed) / c, 2),
        "interventions_per_deal": round(sum(r["interventions"] for r in rows) / n, 3),
    }


def evaluate(role, n, engine):
    from backend.agentdeal.agents.lora_agent import LoRAAgent
    rows = {"heuristic": [], "lora": []}
    for k in range(n):
        seed = SEED0 + k
        sc = random_scenario(seed)
        own_lim = sc.buyer if role == "buyer" else sc.seller
        opp_lim = sc.seller if role == "buyer" else sc.buyer
        feasible = sc.buyer.price_limit >= sc.seller.price_limit and sc.buyer.delivery_limit >= sc.seller.delivery_limit
        for kind in rows:
            if kind == "lora" and engine is None:
                continue
            own = heur(own_lim, "balanced", seed) if kind == "heuristic" else LoRAAgent(engine, role, own_lim, sc.product)
            opp = heur(opp_lim, NAMES[k % len(NAMES)], seed + 1)
            b, s = (own, opp) if role == "buyer" else (opp, own)
            r = run_negotiation(sc, b, s)
            agreed = r.status == "agreed"
            gate_hits = sum(1 for t in r.transcript if t["role"] == role and t["violation"])
            rows[kind].append({
                "agreed": agreed, "feasible": feasible, "rounds": r.rounds,
                "u": utility(own_lim, r.agreed_price, r.agreed_days) if agreed else 0.0,
                "u_opp": utility(opp_lim, r.agreed_price, r.agreed_days) if agreed else 0.0,
                "interventions": gate_hits + getattr(own, "fixes", 0),
            })
        if (k + 1) % 10 == 0:
            print(f"  {role}: {k + 1}/{n}", flush=True)
    return {kind: summarize(v) for kind, v in rows.items() if v}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--roles", nargs="+", default=["buyer", "seller"])
    ap.add_argument("--no-lora", action="store_true", help="heuristic baseline only (no GPU)")
    ap.add_argument("--out", default="results/eval.json")
    args = ap.parse_args()

    engine = None
    if not args.no_lora:
        from backend.agentdeal.agents.lora_agent import LoRAEngine
        engine = LoRAEngine()
        print("adapters loaded:", engine.roles)

    results = {}
    for role in args.roles:
        use = engine if (engine and role in engine.roles) else None
        results[role] = evaluate(role, args.n, use)

    print()
    for role, res in results.items():
        print(f"== {role.upper()} agent vs mixed heuristic opponents ({args.n} unseen scenarios) ==")
        for kind, m in res.items():
            print(f"{kind:>10}: " + " | ".join(f"{k}={v}" for k, v in m.items() if k != "negotiations"))
    Path(args.out).parent.mkdir(exist_ok=True)
    json.dump(results, open(args.out, "w"), indent=2)
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()