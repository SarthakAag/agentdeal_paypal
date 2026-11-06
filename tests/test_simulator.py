from backend.agentdeal.agents.heuristic import HeuristicAgent
from backend.agentdeal.scenarios import random_scenario
from backend.agentdeal.simulator import run_negotiation


def test_no_violations_over_1000_scenarios():
    for seed in range(1000):
        sc = random_scenario(seed)
        r = run_negotiation(sc, HeuristicAgent(sc.buyer, beta=1.0), HeuristicAgent(sc.seller, beta=1.0))
        assert r.violations == 0
        if r.status == "agreed":
            assert sc.seller.price_limit <= r.agreed_price <= sc.buyer.price_limit
            assert sc.seller.delivery_limit <= r.agreed_days <= sc.buyer.delivery_limit


def test_infeasible_scenario_ends_in_no_deal():
    sc = random_scenario(1).model_copy(deep=True)
    sc.buyer.ideal_price, sc.buyer.price_limit = 50, 100
    sc.seller.price_limit, sc.seller.ideal_price = 5000, 6000
    r = run_negotiation(sc, HeuristicAgent(sc.buyer), HeuristicAgent(sc.seller))
    assert r.status == "no_deal"