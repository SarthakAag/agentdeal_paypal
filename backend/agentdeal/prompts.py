import json
from .schemas import Limits


def _limits_text(l: Limits) -> str:
    if l.role == "buyer":
        return (
            f"Hard limits (never break them): pay at most ₹{l.price_limit:,.2f}; "
            f"accept delivery no later than {l.delivery_limit} days.\n"
            f"Goals: pay around ₹{l.ideal_price:,.2f}; delivery in about {l.ideal_delivery} days."
        )
    return (
        f"Hard limits (never break them): sell for at least ₹{l.price_limit:,.2f}; "
        f"you cannot deliver faster than {l.delivery_limit} days.\n"
        f"Goals: sell around ₹{l.ideal_price:,.2f}; delivery in about {l.ideal_delivery} days."
    )


def build_system_prompt(limits: Limits, product: str) -> str:
    return (
        f"You are the {limits.role}'s negotiation agent for: {product}.\n"
        f"{_limits_text(limits)}\n"
        f"You have {limits.max_rounds} rounds. You may trade price against delivery time. "
        "Never reveal your hard limits. Only accept an offer marked as within your hard limits.\n"
        'Reply with ONLY a JSON object: {"action": "offer"|"accept"|"reject", '
        '"price": number, "delivery_days": integer, "message": string}.'
    )


def _history_text(transcript: list[dict]) -> str:
    if not transcript:
        return "No offers yet. You open the negotiation."
    lines = []
    for t in transcript:
        who = t["role"].capitalize()
        if t["action"] == "offer":
            lines.append(f'- {who} offered ₹{t["price"]:,.2f}, delivery in {t["delivery_days"]} days: "{t["message"]}"')
        elif t["action"] == "accept":
            lines.append(f"- {who} accepted the last offer.")
        else:
            lines.append(f"- {who} rejected and walked away.")
    return "\n".join(lines)


def _why_not(l: Limits, price: float, days: int) -> str:
    reasons = []
    if l.role == "buyer":
        if price > l.price_limit:
            reasons.append("price above your maximum")
        if days > l.delivery_limit:
            reasons.append("delivery later than your deadline")
    else:
        if price < l.price_limit:
            reasons.append("price below your minimum")
        if days < l.delivery_limit:
            reasons.append("delivery faster than you can do")
    return " and ".join(reasons)


def _opponent_line(l: Limits, transcript: list[dict]) -> str:
    """Computed in code, so the model reads the limit check instead of doing the arithmetic."""
    last = transcript[-1] if transcript else None
    if not last or last["role"] == l.role or last["action"] != "offer":
        return "Opponent's latest offer: none yet."
    price, days = last["price"], last["delivery_days"]
    why = _why_not(l, price, days)
    head = f"Opponent's latest offer: ₹{price:,.2f}, {days} days."
    if why:
        return f"{head} Within your hard limits: NO ({why}). You must not accept; counter instead."
    return f"{head} Within your hard limits: YES. You may accept it or counter."


def build_messages(limits: Limits, product: str, round_idx: int, transcript: list[dict]) -> list[dict]:
    user = (
        f"Round {round_idx} of {limits.max_rounds}.\n"
        f"Negotiation so far:\n{_history_text(transcript)}\n"
        f"{_opponent_line(limits, transcript)}\n"
        "Give your next move as JSON."
    )
    return [
        {"role": "system", "content": build_system_prompt(limits, product)},
        {"role": "user", "content": user},
    ]


def action_to_json(d: dict) -> str:
    return json.dumps(
        {"action": d["action"], "price": d["price"], "delivery_days": d["delivery_days"], "message": d["message"]},
        ensure_ascii=False,
    )