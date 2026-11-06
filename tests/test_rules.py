import pytest
from backend.agentdeal.rules import utility, validate
from backend.agentdeal.schemas import Action, Limits


def buyer():
    return Limits(role="buyer", price_limit=4000, ideal_price=3000, delivery_limit=7, ideal_delivery=2)


def seller():
    return Limits(role="seller", price_limit=3500, ideal_price=5000, delivery_limit=3, ideal_delivery=9)


def test_buyer_offer_above_budget_rejected():
    ok, _ = validate(buyer(), Action(action="offer", price=4500, delivery_days=5))
    assert not ok


def test_seller_offer_below_minimum_rejected():
    ok, _ = validate(seller(), Action(action="offer", price=3000, delivery_days=5))
    assert not ok


def test_accepting_offer_that_breaks_limits_rejected():
    last = Action(action="offer", price=4500, delivery_days=5)
    ok, _ = validate(buyer(), Action(action="accept"), last)
    assert not ok


def test_utility_bounds():
    assert utility(buyer(), 3000, 2) == pytest.approx(1.0)
    assert utility(buyer(), 4000, 7) == pytest.approx(0.0)
    assert utility(seller(), 5000, 9) == pytest.approx(1.0)
    assert utility(seller(), 3500, 3) == pytest.approx(0.0)