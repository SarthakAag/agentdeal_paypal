import argparse
import json
import re
from pathlib import Path

from backend.agentdeal.agents.lora_agent import LoRAEngine
from backend.agentdeal.assist import numbers_ok
from backend.agentdeal.assist_prompts import extract_json, parser_messages

KEYS = ["budget", "ideal_price", "latest_days", "ideal_days", "priority", "max_rounds"]


def load(path, n):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()][:n]


def eval_parser(engine, n):
    rows = load("data/processed/parser_val.jsonl", n)
    per, exact, bad = {k: 0 for k in KEYS}, 0, 0
    for r in rows:
        gold = json.loads(r["messages"][-1]["content"])
        out = extract_json(engine.generate("parser", r["messages"][:-1]))
        if not isinstance(out, dict):
            bad += 1
            continue
        hits = [out.get(k) == gold[k] for k in KEYS]
        for k, h in zip(KEYS, hits):
            per[k] += h
        exact += all(hits)
    print(f"parser (same-template val, {len(rows)} rows): exact match {exact / len(rows):.0%}, unreadable {bad}")
    print("  per field:", {k: f"{v / len(rows):.0%}" for k, v in per.items()})


def eval_hand(engine, path):
    p = Path(path)
    if not p.exists():
        print(f"{path} not found, skipped")
        return
    rows = load(p, 1000)
    ok = 0
    for r in rows:
        out = extract_json(engine.generate("parser", parser_messages(r["text"], r.get("ask_price"))))
        good = isinstance(out, dict) and all(out.get(k) == v for k, v in r["expect"].items())
        ok += good
        if not good:
            print("  MISS:", r["text"], "->", out)
    print(f"parser {p.name}: {ok}/{len(rows)} correct")


def eval_narrator(engine, n):
    rows = load("data/processed/narrator_val.jsonl", n)
    ok, outs = 0, []
    for r in rows:
        move = json.loads(r["messages"][1]["content"])
        price = float(re.sub(r"[^0-9]", "", move["price"]))
        days = int(re.search(r"\d+", move["delivery"]).group())
        text = engine.generate("narrator", r["messages"][:-1]).strip().split("\n")[0]
        outs.append(text)
        ok += numbers_ok(text, price, days)
    print(f"narrator ({len(rows)} rows): numbers verified {ok / len(rows):.0%}, "
          f"distinct sentences {len(set(outs)) / len(rows):.0%}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    a = ap.parse_args()
    eng = LoRAEngine()
    eval_parser(eng, a.n)
    for path in ("data/eval/parser_regression.jsonl", "data/eval/parser_fresh.jsonl"):
        eval_hand(eng, path)
    eval_narrator(eng, a.n)