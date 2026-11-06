import collections
from backend.agentdeal.agents.heuristic import HeuristicAgent
from backend.agentdeal.agents.lora_agent import LoRAAgent, LoRAEngine
from backend.agentdeal.rules import validate
from backend.agentdeal.scenarios import PERSONALITIES, random_scenario
from backend.agentdeal.simulator import run_negotiation

NAMES = list(PERSONALITIES)
LOG = []


class Spy(LoRAAgent):
    def act(self, round_idx, opp_offer=None, transcript=None):
        a = super().act(round_idx, opp_offer, transcript)
        ok, why = validate(self.limits, a, opp_offer)
        if not ok:
            LOG.append(dict(role=self.role, rnd=round_idx, of=self.limits.max_rounds, act=a.action,
                            price=a.price, days=a.delivery_days,
                            plim=self.limits.price_limit, dlim=self.limits.delivery_limit, why=why))
        return a


def category(why):
    for key, name in [("above budget", "price over budget"), ("below minimum", "price under minimum"),
                      ("later than", "delivery too slow"), ("faster than", "delivery too fast"),
                      ("nothing to accept", "accept w/ no offer"), ("must be positive", "malformed/missing")]:
        if key in why:
            return name
    return why


engine = LoRAEngine()
for role in ("buyer", "seller"):
    LOG.clear()
    for k in range(30):
        seed = 2_000_000 + k
        sc = random_scenario(seed)
        p = PERSONALITIES[NAMES[k % 4]]
        if role == "buyer":
            b, s = Spy(engine, "buyer", sc.buyer, sc.product), HeuristicAgent(sc.seller, p["beta"], p["flex"], seed)
        else:
            b, s = HeuristicAgent(sc.buyer, p["beta"], p["flex"], seed), Spy(engine, "seller", sc.seller, sc.product)
        run_negotiation(sc, b, s)
    print(f"\n=== {role}: {len(LOG)} violations in 30 games ===")
    print("by type :", dict(collections.Counter(category(x["why"]) for x in LOG)))
    print("by action:", dict(collections.Counter(x["act"] for x in LOG)))
    print("by round (early/mid/late):", dict(collections.Counter(
        "early" if x["rnd"] <= x["of"] / 3 else "mid" if x["rnd"] <= 2 * x["of"] / 3 else "late" for x in LOG)))
    for x in LOG[:6]:
        print("  ", x)
