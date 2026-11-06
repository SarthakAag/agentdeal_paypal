from typing import Optional
from .schemas import Action, Limits


def validate(limits: Limits, action: Action, last_offer: Optional[Action] = None) -> tuple[bool, str]:
    """Hard limits live here, never inside the model."""
    if action.action == "reject":
        return True, "ok"
    if action.action == "accept" and last_offer is None:
        return False, "nothing to accept"

    src = last_offer if action.action == "accept" else action
    price, days = src.price, src.delivery_days
    if price is None or days is None or price <= 0 or days < 1:
        return False, "price and delivery_days must be positive"

    if limits.role == "buyer":
        if price > limits.price_limit:
            return False, f"price {price} above budget {limits.price_limit}"
        if days > limits.delivery_limit:
            return False, f"delivery {days}d later than {limits.delivery_limit}d"
    else:
        if price < limits.price_limit:
            return False, f"price {price} below minimum {limits.price_limit}"
        if days < limits.delivery_limit:
            return False, f"delivery {days}d faster than possible {limits.delivery_limit}d"
    return True, "ok"


def clamp_terms(limits: Limits, price: float, days: float) -> tuple[float, int]:
    """Pull terms back inside the hard limits."""
    if limits.role == "buyer":
        price, days = min(price, limits.price_limit), min(days, limits.delivery_limit)
    else:
        price, days = max(price, limits.price_limit), max(days, limits.delivery_limit)
    return round(max(price, 0.01), 2), max(int(days), 1)


def _score(value: float, ideal: float, limit: float) -> float:
    """1.0 at the ideal, 0.0 at the hard limit."""
    span = limit - ideal
    if span == 0:
        return 1.0
    return (limit - value) / span


def utility(limits: Limits, price: float, days: float, price_weight: float = 0.6) -> float:
    p = _score(price, limits.ideal_price, limits.price_limit)
    d = _score(days, limits.ideal_delivery, limits.delivery_limit)
    return round(price_weight * p + (1 - price_weight) * d, 4)