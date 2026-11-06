from backend.agentdeal.agents.heuristic import HeuristicAgent
from backend.agentdeal.rules import utility
from backend.agentdeal.scenarios import PERSONALITIES, random_scenario
from backend.agentdeal.simulator import run_negotiation


def play(seed, buyer_type, seller_type):
    sc = random_scenario(seed)
    b, s = PERSONALITIES[buyer_type], PERSONALITIES[seller_type]
    buyer = HeuristicAgent(sc.buyer, b["beta"], b["flex"], seed)
    seller = HeuristicAgent(sc.seller, s["beta"], s["flex"], seed + 1)
    return sc, run_negotiation(sc, buyer, seller)


if __name__ == "__main__":
    sc, r = play(7, "balanced", "stubborn")
    print(f"\n=== {sc.product} ===")
    for t in r.transcript:
        print(f"[{t['role']:6}] {t['message']}")
    print(f"Result: {r.status} | price={r.agreed_price} | days={r.agreed_days}\n")

    print(f"{'buyer vs seller':<22}{'closed':>8}{'buyer u':>9}{'seller u':>10}{'rounds':>8}")
    for bt, st in [("balanced", "balanced"), ("stubborn", "flexible"), ("flexible", "stubborn"), ("eager", "eager")]:
        closed = 0
        ub = us = rounds = 0.0
        for seed in range(500):
            sc, r = play(seed, bt, st)
            if r.status == "agreed":
                closed += 1
                ub += utility(sc.buyer, r.agreed_price, r.agreed_days)
                us += utility(sc.seller, r.agreed_price, r.agreed_days)
                rounds += r.rounds
        c = max(closed, 1)
        print(f"{bt + ' vs ' + st:<22}{closed / 500:>8.0%}{ub / c:>9.2f}{us / c:>10.2f}{rounds / c:>8.1f}")