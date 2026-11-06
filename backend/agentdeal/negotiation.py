
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Deal:
    product: str
    buyer_budget: float
    seller_minimum: float
    buyer_offer: float
    seller_offer: float
    delivery_days: int = 5
    max_delivery_days: int = 7
    max_rounds: int = 6
    round_number: int = 0
    status: str = "negotiating"
    agreed_price: Optional[float] = None
    history: list[dict] = field(default_factory=list)


def validate_deal(deal: Deal, price: float) -> tuple[bool, str]:
    if price <= 0:
        return False, "Price must be positive."
    if price > deal.buyer_budget:
        return False, "Offer exceeds the buyer's budget."
    if price < deal.seller_minimum:
        return False, "Offer is below the seller's minimum."
    if deal.delivery_days > deal.max_delivery_days:
        return False, "Delivery exceeds the buyer's limit."
    return True, "Deal terms are valid."


def negotiate(deal: Deal) -> Deal:
    if deal.status != "negotiating":
        return deal

    if deal.buyer_budget < deal.seller_minimum:
        deal.status = "no_deal"
        deal.history.append({
            "round": 0,
            "speaker": "system",
            "message": "No feasible deal: buyer budget is below seller minimum."
        })
        return deal

    if not (
        deal.seller_minimum <= deal.seller_offer
        and deal.buyer_offer <= deal.buyer_budget
        and deal.buyer_offer > 0
    ):
        deal.status = "no_deal"
        deal.history.append({
            "round": 0,
            "speaker": "system",
            "message": "Invalid opening offer or seller asking price."
        })
        return deal

    for round_number in range(1, deal.max_rounds + 1):
        deal.round_number = round_number

        buyer_offer = deal.buyer_offer + (
            deal.buyer_budget - deal.buyer_offer
        ) * round_number / deal.max_rounds

        seller_offer = deal.seller_offer - (
            deal.seller_offer - deal.seller_minimum
        ) * round_number / deal.max_rounds

        buyer_offer = round(buyer_offer, 2)
        seller_offer = round(seller_offer, 2)

        deal.history.append({
            "round": round_number,
            "speaker": "buyer",
            "price": buyer_offer,
            "message": f"Buyer proposes {buyer_offer:.2f}."
        })

        deal.history.append({
            "round": round_number,
            "speaker": "seller",
            "price": seller_offer,
            "message": f"Seller counters at {seller_offer:.2f}."
        })

        if buyer_offer >= seller_offer:
            proposed_price = round((buyer_offer + seller_offer) / 2, 2)
            valid, reason = validate_deal(deal, proposed_price)

            if valid:
                deal.agreed_price = proposed_price
                deal.status = "agreed"
                deal.history.append({
                    "round": round_number,
                    "speaker": "system",
                    "price": proposed_price,
                    "message": f"Deal agreed at {proposed_price:.2f}."
                })
                return deal

            deal.history.append({
                "round": round_number,
                "speaker": "system",
                "message": reason
            })

    deal.status = "no_deal"
    deal.history.append({
        "round": deal.round_number,
        "speaker": "system",
        "message": "Negotiation ended without an agreement."
    })
    return deal
