import random
from .schemas import Limits, Scenario

PRODUCTS = [
    "Logo design", "Bulk stationery (500 pcs)", "Landing page website",
    "Handmade wooden table", "Laptop refurbishing", "Catering for 50 people",
    "Video editing (10 min)", "Printed T-shirts (100 pcs)",
]

# beta > 1: concedes late (stubborn). beta < 1: concedes early.
# flex: 0..1, how readily the agent trades delivery time for price.
PERSONALITIES = {
    "stubborn": {"beta": 3.0, "flex": 0.2},
    "balanced": {"beta": 1.2, "flex": 0.5},
    "flexible": {"beta": 0.6, "flex": 0.5},
    "eager":    {"beta": 0.35, "flex": 0.9},
}


def random_scenario(seed=None) -> Scenario:
    rng = random.Random(seed)
    market = rng.uniform(1000, 8000)
    max_rounds = rng.choice([6, 8, 10])
    buyer_days = rng.randint(3, 14)
    seller_days = rng.randint(1, 7)

    buyer = Limits(
        role="buyer",
        price_limit=round(market * rng.uniform(0.85, 1.15), 2),
        ideal_price=round(market * rng.uniform(0.6, 0.8), 2),
        delivery_limit=buyer_days,
        ideal_delivery=rng.randint(1, buyer_days),
        max_rounds=max_rounds,
    )
    seller = Limits(
        role="seller",
        price_limit=round(market * rng.uniform(0.65, 0.95), 2),
        ideal_price=round(market * rng.uniform(1.05, 1.3), 2),
        delivery_limit=seller_days,
        ideal_delivery=rng.randint(seller_days, seller_days + 10),
        max_rounds=max_rounds,
    )
    return Scenario(product=rng.choice(PRODUCTS), buyer=buyer, seller=seller)
