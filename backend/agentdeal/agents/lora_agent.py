import json
import threading
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from ..prompts import build_messages
from ..rules import utility, validate
from ..schemas import Action
from .heuristic import HeuristicAgent


class LoRAEngine:
    """Loads the base model once and swaps the adapter (buyer, seller, parser, narrator) per call."""

    def __init__(self, models_dir="models"):
        d = Path(models_dir)
        self.roles = [r for r in ("buyer", "seller", "parser", "narrator")
                      if (d / f"{r}_lora" / "adapter_config.json").exists()]
        if not self.roles:
            raise RuntimeError("No trained adapters found in models/")
        self._lock = threading.Lock()   # set_adapter is global state, so one generate at a time
        base = json.load(open(d / f"{self.roles[0]}_lora" / "base.json"))["base_model"]
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

        self.tok = AutoTokenizer.from_pretrained(base)
        model = AutoModelForCausalLM.from_pretrained(
            base,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype,
            ),
            device_map={"": 0},
            dtype=dtype,
        )
        first, *rest = self.roles
        self.model = PeftModel.from_pretrained(model, str(d / f"{first}_lora"), adapter_name=first)
        for r in rest:
            self.model.load_adapter(str(d / f"{r}_lora"), adapter_name=r)
        self.model.eval()

    @torch.no_grad()
    def generate(self, role, messages):
        with self._lock:
            self.model.set_adapter(role)
            prompt = self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            ids = self.tok(prompt, return_tensors="pt", add_special_tokens=False).to(self.model.device)
            out = self.model.generate(
                **ids, max_new_tokens=120, do_sample=False,
                pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id,
            )
            return self.tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True)


def parse_action(text: str) -> Action:
    """Malformed output becomes an empty offer, which fails validation."""
    try:
        d = json.loads(text[text.index("{"): text.rindex("}") + 1])
        days = d.get("delivery_days")
        return Action(
            action=d["action"],
            price=d.get("price"),
            delivery_days=int(round(float(days))) if days is not None else None,
            message=str(d.get("message", "")),
        )
    except Exception:
        return Action(action="offer", message="")


class LoRAAgent:
    """Hybrid agent: rules decide what is allowed, the fine-tuned model proposes counteroffers.

    1. Accept (code): accept an offer inside the hard limits if it is at least as good as
       our planned offer, or if it is the final round (a deal beats no deal).
    2. Counteroffer (model): checked against the hard limits. A malformed, out-of-limit or
       non-offer move is replaced by the planned offer and counted in `self.fixes`.
    3. Concession floor (code): in the last two rounds the model's offer may not be tougher
       than the planned concession, so both sides converge on terms inside their limits.
    """

    FLOOR_ROUNDS = 2

    def __init__(self, engine: LoRAEngine, role, limits, product):
        self.engine, self.role, self.limits, self.product = engine, role, limits, product
        self.planner = HeuristicAgent(limits, beta=1.2, flex=0.5)
        self.fixes = 0

    def _apply_floor(self, action: Action, plan_price: float, plan_days: int) -> Action:
        if self.limits.role == "buyer":    # conceding = paying more, accepting later delivery
            price, days = max(action.price, plan_price), max(action.delivery_days, plan_days)
        else:                              # conceding = charging less, delivering faster
            price, days = min(action.price, plan_price), min(action.delivery_days, plan_days)
        return Action(action="offer", price=round(price, 2), delivery_days=int(days), message=action.message)

    def act(self, round_idx, opp_offer=None, transcript=None) -> Action:
        L = self.limits
        plan_price, plan_days = self.planner.planned(round_idx)

        # 1. Rule-based accept
        if opp_offer is not None and opp_offer.price is not None and opp_offer.delivery_days is not None:
            ok, _ = validate(L, Action(action="accept"), opp_offer)
            last_round = round_idx >= L.max_rounds
            better_than_plan = (
                utility(L, opp_offer.price, opp_offer.delivery_days) >= utility(L, plan_price, plan_days)
            )
            if ok and (last_round or better_than_plan):
                return Action(
                    action="accept",
                    message=f"Deal. I accept ₹{opp_offer.price:,.0f} with delivery in {opp_offer.delivery_days} days.",
                )

        # 2. Model proposes the counteroffer
        msgs = build_messages(L, self.product, round_idx, transcript or [])
        action = parse_action(self.engine.generate(self.role, msgs))
        if action.action == "offer":
            ok, _ = validate(L, action)
            if ok:
                # 3. Concession floor near the end
                if round_idx >= L.max_rounds - (self.FLOOR_ROUNDS - 1):
                    action = self._apply_floor(action, plan_price, plan_days)
                return action

        self.fixes += 1
        return Action(
            action="offer", price=plan_price, delivery_days=plan_days,
            message=f"I can do ₹{plan_price:,.0f} with delivery in {plan_days} days.",
        )