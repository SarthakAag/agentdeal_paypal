import json

PRICE_FACTOR = {"price": 0.70, "speed": 0.90, None: 0.85}
DAYS_FACTOR = {"price": 0.90, "speed": 0.40, None: 0.70}

PARSER_SYSTEM = (
    "You extract a buyer's limits from one sentence. All money is Indian rupees. "
    'Reply with ONLY a JSON object: {"budget": number|null, "ideal_price": number|null, '
    '"latest_days": integer|null, "ideal_days": integer|null, "priority": "price"|"speed"|null, '
    '"max_rounds": 6|8|10|null}. Use null for anything the sentence does not say. Never invent numbers.'
)

NARRATOR_SYSTEM = (
    "Rewrite one negotiation move as a single natural sentence in the first person, under 25 words. "
    "Use exactly the given price and delivery time and no other numbers. Reply with the sentence only."
)


def fmt_inr(x: float) -> str:
    return "₹" + format(int(round(x)), ",")


def fmt_days(d: int) -> str:
    return "1 day" if d == 1 else f"{d} days"


def parser_messages(text: str, ask_price=None) -> list:
    ask = f"Asking price: {fmt_inr(ask_price)}\n" if ask_price else ""
    return [
        {"role": "system", "content": PARSER_SYSTEM},
        {"role": "user", "content": f"{ask}Sentence: {text}"},
    ]


def narrator_messages(move: dict) -> list:
    return [
        {"role": "system", "content": NARRATOR_SYSTEM},
        {"role": "user", "content": json.dumps(move, ensure_ascii=False)},
    ]


def extract_json(text: str):
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None


def _pos(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 else None


def derive_mandate(d: dict, ask_price=None):
    """Model output -> form fields. The model extracts; this code does the arithmetic."""
    prio = d.get("priority") if d.get("priority") in ("price", "speed") else None
    budget, latest = _pos(d.get("budget")), _pos(d.get("latest_days"))
    ideal_p, ideal_d = _pos(d.get("ideal_price")), _pos(d.get("ideal_days"))
    latest = int(round(latest)) if latest else None
    if budget and not ideal_p:
        ideal_p = round(budget * PRICE_FACTOR[prio])
    if budget and ideal_p and ideal_p > budget:
        ideal_p = budget
    if latest and not ideal_d:
        ideal_d = max(1, round(latest * DAYS_FACTOR[prio]))
    if latest and ideal_d:
        ideal_d = min(int(round(ideal_d)), latest)
    rounds = d.get("max_rounds") if d.get("max_rounds") in (6, 8, 10) else None
    fields = {"budget": budget, "ideal_price": ideal_p, "latest_days": latest,
              "ideal_days": int(ideal_d) if ideal_d else None, "max_rounds": rounds}
    missing = [k for k in ("budget", "latest_days") if not fields[k]]
    return fields, missing


def move_style(round_idx: int, max_rounds: int, prev_price, price) -> str:
    """Flavour label for the narrator, computed from the transcript."""
    if prev_price is None:
        return "opening"
    if round_idx >= max_rounds - 1:
        return "final"
    return "flexible" if abs(price - prev_price) / prev_price > 0.03 else "firm"