from typing import Optional

from .rules import clamp_terms, validate
from .schemas import Action, Limits, NegotiationResult, Scenario


def _enforce(limits: Limits, action: Action, last_offer: Optional[Action]):
    """Rule engine gate: returns a safe action plus the violation reason (or None)."""
    ok, reason = validate(limits, action, last_offer)
    if ok:
        return action, None
    if action.action == "offer" and action.price is not None and action.delivery_days is not None:
        price, days = clamp_terms(limits, action.price, action.delivery_days)
    else:  # invalid accept or malformed output: fall back to a safe offer at own limit
        price, days = clamp_terms(limits, limits.price_limit, limits.delivery_limit)
    return Action(action="offer", price=price, delivery_days=days, message=action.message), reason


def run_negotiation(scenario: Scenario, buyer_agent, seller_agent) -> NegotiationResult:
    sides = {"buyer": (scenario.buyer, buyer_agent), "seller": (scenario.seller, seller_agent)}
    own_rounds = {"buyer": 0, "seller": 0}
    transcript: list[dict] = []
    violations = 0
    last_offer: Optional[Action] = None
    status, agreed_price, agreed_days = "no_deal", None, None

    for turn in range(2 * scenario.buyer.max_rounds):
        role = "buyer" if turn % 2 == 0 else "seller"
        limits, agent = sides[role]
        own_rounds[role] += 1

        raw = agent.act(own_rounds[role], last_offer, transcript)
        action, reason = _enforce(limits, raw, last_offer)
        if reason:
            violations += 1

        transcript.append({
            "turn": turn, "round": own_rounds[role], "role": role,
            **action.model_dump(), "violation": reason,
        })

        if action.action == "accept":
            status, agreed_price, agreed_days = "agreed", last_offer.price, last_offer.delivery_days
            break
        if action.action == "reject":
            break
        last_offer = action

    return NegotiationResult(
        product=scenario.product, status=status,
        agreed_price=agreed_price, agreed_days=agreed_days,
        rounds=max(own_rounds.values()), violations=violations, transcript=transcript,
    )