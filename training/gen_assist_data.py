import argparse
import json
import random
from pathlib import Path

from backend.agentdeal.assist_prompts import fmt_days, fmt_inr, narrator_messages, parser_messages

OUT = Path("data/processed")

# ---------------------------------------------------------------- parser

BUDGET_T = ["under {m}", "max {m}", "up to {m}", "no more than {m}", "budget is {m}", "my budget: {m}",
            "not above {m}", "{m} at most", "I can pay up to {m}", "cap it at {m}", "below {m}", "budget {m}",
            "{m} is my ceiling", "can't exceed {m}", "won't go above {m}"]
DAYS_T = ["within {d}", "in {d}", "latest {d}", "by {d}", "I need it in {d}", "deadline {d}",
          "no later than {d}", "delivered within {d}", "{d} max", "want it within {d}"]
IDEAL_P_T = ["ideally {m}", "I would love {m}", "hoping for {m}", "{m} would be great", "target price {m}"]
IDEAL_D_T = ["ideally {d}", "{d} would be perfect", "preferably {d}", "hoping for {d}"]
# bare numbers with no unit: days, because prices in this data are always >= 100 and days are <= 30
IDEAL_D_BARE_T = ["ideally {n}", "I'd like {n}", "{n} would be nice", "hoping for {n}", "{n} would be perfect"]

PRIO = {
    "price": ["price matters more", "keep the price low", "I care more about cost than speed",
              "cheap is more important than fast", "cost is the priority", "save money if you can",
              "as cheap as possible", "every rupee counts", "I'm tight on money so keep it cheap",
              "get me the lowest price", "I'm hunting for a bargain"],
    "speed": ["speed matters more", "I need it fast", "delivery speed is the priority",
              "faster is better even if it costs more", "it is urgent", "time matters more than price",
              "money is no object", "price doesn't matter, speed does", "I'll pay extra to get it quickly",
              "spare no expense on speed", "rush it", "urgent, I need it asap"],
}
PREFIX = ["", "", "", "Hi, ", "Please negotiate: ", "I want this. ", "Hey, ", "I'd like to buy this, "]
SUFFIX = ["", "", "", " please", " thanks", "."]
DAY_CHOICES = [1, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 15, 20, 21, 30]

# relative time phrases; each is a complete clause that means the given number of days
REL_1 = ["need it tomorrow", "by tomorrow", "tomorrow at the latest", "deliver it tomorrow",
         "I need it by tomorrow", "within a day", "in a day", "tomorrow"]
REL_2 = ["the day after tomorrow at the latest", "in a couple of days", "within a couple of days",
         "need it the day after tomorrow"]
REL_7 = ["by next week", "next week at the latest", "within the week", "need it next week"]


def money(rng, v):
    opts = [str(v), f"{v:,}", f"₹{v}", f"₹{v:,}", f"Rs {v}", f"Rs. {v:,}", f"{v} rupees", f"INR {v}", f"{v} rs"]
    if v % 1000 == 0:
        opts += [f"{v // 1000}k", f"₹{v // 1000}k", f"{v // 1000}K"]
    elif v % 500 == 0:
        opts += [f"{v / 1000:.1f}k"]
    return rng.choice(opts)


def day_phrase(rng, d):
    opts = [f"{d} days" if d != 1 else "1 day"] * 3
    if d == 7:
        opts += ["a week", "1 week", "one week"]
    if d == 14:
        opts += ["two weeks", "2 weeks", "a fortnight"]
    if d == 21:
        opts += ["three weeks"]
    if d == 30:
        opts += ["a month", "1 month"]
    return rng.choice(opts)


def days_clause(rng, d):
    """Either a relative phrase ('tomorrow') or a template with a day count."""
    if d == 1 and rng.random() < 0.7:
        return rng.choice(REL_1)
    if d == 2 and rng.random() < 0.25:
        return rng.choice(REL_2)
    if d == 7 and rng.random() < 0.2:
        return rng.choice(REL_7)
    return rng.choice(DAYS_T).format(d=day_phrase(rng, d))


def noise(rng, s):
    if rng.random() < 0.3:
        s = s.lower()
    if rng.random() < 0.2:
        s = s.replace(",", "")
    if rng.random() < 0.15:
        words = s.split(" ")
        idx = [i for i, w in enumerate(words) if w.isalpha() and len(w) >= 5]
        if idx:
            i = rng.choice(idx)
            w, j = words[i], rng.randrange(len(words[i]) - 1)
            words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
            s = " ".join(words)
    return s


def parser_sample(rng):
    ask = rng.randrange(8, 90) * 100
    budget = max(100, int(round(ask * rng.uniform(0.6, 1.3) / 100) * 100))
    latest = rng.choice(DAY_CHOICES) if rng.random() < 0.8 else rng.randint(1, 30)
    prio = rng.choices(["price", "speed", None], [0.3, 0.3, 0.4])[0]
    label = {"budget": None, "ideal_price": None, "latest_days": None, "ideal_days": None,
             "priority": prio, "max_rounds": None}
    parts = []
    drop_b = rng.random() < 0.05
    drop_d = (not drop_b) and rng.random() < 0.05

    if not drop_b:
        if rng.random() < 0.06:
            label["budget"] = ask
            parts.append(rng.choice(["no more than the asking price", "up to the asking price",
                                     "at most the asking price"]))
        else:
            label["budget"] = budget
            parts.append(rng.choice(BUDGET_T).format(m=money(rng, budget)))
        if rng.random() < 0.2:
            ip = int(round(label["budget"] * rng.uniform(0.6, 0.9) / 50) * 50)
            if 0 < ip < label["budget"]:
                label["ideal_price"] = ip
                parts.append(rng.choice(IDEAL_P_T).format(m=money(rng, ip)))
    if not drop_d:
        label["latest_days"] = latest
        parts.append(days_clause(rng, latest))
        if latest > 1 and rng.random() < 0.2:
            idd = rng.randint(1, latest - 1)
            label["ideal_days"] = idd
            if rng.random() < 0.3:
                parts.append(rng.choice(IDEAL_D_BARE_T).format(n=idd))
            else:
                parts.append(rng.choice(IDEAL_D_T).format(d=day_phrase(rng, idd)))
    if prio:
        parts.append(rng.choice(PRIO[prio]))
    if rng.random() < 0.15:
        r = rng.choice([6, 8, 10])
        label["max_rounds"] = r
        parts.append(rng.choice(["use {r} rounds", "negotiate for {r} rounds", "{r} rounds please"]).format(r=r))

    rng.shuffle(parts)
    text = rng.choice(PREFIX) + rng.choice([", ", ", ", " and ", ". ", "; "]).join(parts) + rng.choice(SUFFIX)
    text = noise(rng, text)
    msgs = parser_messages(text, ask)
    msgs.append({"role": "assistant", "content": json.dumps(label)})
    return msgs, label


# ---------------------------------------------------------------- narrator

INTRO = {
    "opening": ["Hello! ", "Hi there. ", "Thanks for listing this. ", "Good to meet you. ", ""],
    "firm": ["I'd like to hold near this level. ", "I can't move much from here. ",
             "That's still a little off for me. ", ""],
    "flexible": ["I'm happy to meet you partway. ", "Let's find some middle ground. ",
                 "I'm willing to move on this. ", "Thanks for the counter. ", ""],
    "final": ["This is close to my best. ", "I'd really like to wrap this up. ", "We're nearly there. ",
              "Let's close this out. ", ""],
}
CORE = {
    "buyer": ["I can offer {p} with delivery in {d}.", "Would {p} work, delivered in {d}?",
              "My proposal is {p} and {d} for delivery.", "How about {p}, with delivery within {d}?",
              "I'm prepared to pay {p} if it arrives in {d}.", "{p} with delivery in {d} is what I can do."],
    "seller": ["I can do {p} with delivery in {d}.", "I'd be able to deliver in {d} for {p}.",
               "My price is {p}, delivered within {d}.", "For {p}, I can have it to you in {d}.",
               "I can offer {p} and a delivery time of {d}.", "{p} with {d} for delivery works from my side."],
}
ACCEPT = ["Deal! I accept {p} with delivery in {d}.", "That works for me: {p}, delivered in {d}.",
          "Agreed. {p} and {d} for delivery is fine.", "Happy to accept {p} with delivery in {d}.",
          "You have a deal at {p} with delivery in {d}.", "Sounds good. I accept {p} and delivery in {d}."]


def narrator_sample(rng):
    speaker = rng.choice(["buyer", "seller"])
    action = rng.choices(["offer", "accept"], [0.75, 0.25])[0]
    style = "accept" if action == "accept" else rng.choice(["opening", "firm", "flexible", "final"])
    price, days = round(rng.uniform(800, 9000), 2), rng.randint(1, 30)
    p, d = fmt_inr(price), fmt_days(days)
    move = {"speaker": speaker, "action": action, "style": style, "price": p, "delivery": d}
    if action == "accept":
        text = rng.choice(ACCEPT).format(p=p, d=d)
    else:
        text = rng.choice(INTRO[style]) + rng.choice(CORE[speaker]).format(p=p, d=d)
    return move, text, price, days


# ---------------------------------------------------------------- main

def write(rows, name, val):
    OUT.mkdir(parents=True, exist_ok=True)
    for split, chunk in (("val", rows[:val]), ("train", rows[val:])):
        with open(OUT / f"{name}_{split}.jsonl", "w", encoding="utf-8") as f:
            for r in chunk:
                f.write(json.dumps({"messages": r}, ensure_ascii=False) + "\n")


def collect(make, n):
    seen, rows = set(), []
    for _ in range(n * 30):
        msgs = make()
        key = json.dumps(msgs[1:], ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            rows.append(msgs)
        if len(rows) >= n:
            break
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parser-n", type=int, default=6000)
    ap.add_argument("--narrator-n", type=int, default=4000)
    ap.add_argument("--val", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--only", choices=["both", "parser", "narrator"], default="both",
                    help="regenerate only one dataset and leave the other files untouched")
    a = ap.parse_args()

    if a.only in ("both", "parser"):
        rng = random.Random(a.seed)
        prows = collect(lambda: parser_sample(rng)[0], a.parser_n + a.val)
        write(prows, "parser", a.val)
        print(f"parser rows   : {len(prows)} (val {a.val})")
        for r in prows[:3]:
            print("  P>", r[1]["content"].replace("\n", " | "), "->", r[2]["content"])

    if a.only in ("both", "narrator"):
        rng = random.Random(a.seed + 1)

        def narr():
            move, text, _, _ = narrator_sample(rng)
            return narrator_messages(move) + [{"role": "assistant", "content": text}]

        nrows = collect(narr, a.narrator_n + a.val)
        write(nrows, "narrator", a.val)
        print(f"narrator rows : {len(nrows)} (val {a.val})")
        for r in nrows[:3]:
            print("  N>", r[1]["content"], "->", r[2]["content"])


if __name__ == "__main__":
    main()