import random
from typing import Optional

from ..rules import clamp_terms, utility, validate
from ..schemas import Action, Limits


class HeuristicAgent:
    """Time-dependent concession agent. Teacher for the dataset and fallback for the demo.

    react=False (default): follows its own concession curve, ignoring the opponent's
    delivery offer. This is the behaviour the original baseline was measured with.
    react=True: never asks for worse delivery than the opponent already offers.
    It lowered scores for both sides in testing, so it is off by default.
    """

    def __init__(self, limits: Limits, beta: float = 1.0, flex: float = 0.5, seed=None, react: bool = False):
        self.limits = limits
        self.beta = beta
        self.flex = flex
        self.react = react
        self.rng = random.Random(seed)

    def _concession(self, round_idx: int) -> float:
        total = self.limits.max_rounds
        progress = 0.0 if total <= 1 else (round_idx - 1) / (total - 1)
        return progress ** self.beta

    def planned(self, round_idx: int) -> tuple[float, int]:
        L = self.limits
        c = self._concession(round_idx)
        c_price = c ** (1 + 0.5 * self.flex)   # flexible-on-delivery agents hold price longer
        c_days = c ** (1 - 0.5 * self.flex)    # ...and give on delivery sooner
        price = L.ideal_price + (L.price_limit - L.ideal_price) * c_price
        days = L.ideal_delivery + (L.delivery_limit - L.ideal_delivery) * c_days
        return clamp_terms(L, price, round(days))

    def act(self, round_idx: int, opp_offer: Optional[Action] = None, transcript=None) -> Action:
        L = self.limits
        price, days = self.planned(round_idx)

        # Optional: react to the opponent's delivery offer
        if self.react and opp_offer is not None and opp_offer.delivery_days is not None:
            if L.role == "buyer":
                days = min(days, opp_offer.delivery_days)   # buyer wants fast delivery
            else:
                days = max(days, opp_offer.delivery_days)   # seller wants slow delivery
            price, days = clamp_terms(L, price, days)

        if opp_offer is not None:
            ok, _ = validate(L, Action(action="accept"), opp_offer)
            if ok and utility(L, opp_offer.price, opp_offer.delivery_days) >= utility(L, price, days):
                return Action(
                    action="accept",
                    message=f"Deal. I accept ₹{opp_offer.price:,.0f} with delivery in {opp_offer.delivery_days} days.",
                )

        message = self.rng.choice([
            f"I can do ₹{price:,.0f} with delivery in {days} days.",
            f"How about ₹{price:,.0f} and {days} days for delivery?",
            f"My offer is ₹{price:,.0f}, delivered in {days} days.",
        ])
        return Action(action="offer", price=price, delivery_days=days, message=message)