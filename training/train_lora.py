import argparse
import json
import random
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, prepare_model_for_kbit_training, get_peft_model
from transformers import (
    AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
    DataCollatorForSeq2Seq, Trainer, TrainingArguments,
)

MAX_LEN = 1280


def load_jsonl(path, limit, seed):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    random.Random(seed).shuffle(rows)
    return rows[:limit] if limit else rows


def encode(tok, rows):
    out = []
    for r in rows:
        msgs = r["messages"]
        prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
        completion = msgs[-1]["content"] + tok.eos_token
        p = tok(prompt, add_special_tokens=False)["input_ids"]
        c = tok(completion, add_special_tokens=False)["input_ids"]
        if len(p) + len(c) > MAX_LEN:
            continue
        out.append({
            "input_ids": p + c,
            "attention_mask": [1] * (len(p) + len(c)),
            "labels": [-100] * len(p) + c,   # loss only on the reply
        })
    return Dataset.from_list(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["buyer", "seller", "parser", "narrator"], required=True)
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--max-samples", type=int, default=12000)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--accum", type=int, default=4)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    out_dir = Path("models") / f"{args.role}_lora"
    out_dir.mkdir(parents=True, exist_ok=True)

    use_bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if use_bf16 else torch.float16

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    train = encode(tok, load_jsonl(f"data/processed/{args.role}_train.jsonl", args.max_samples, args.seed))
    val = encode(tok, load_jsonl(f"data/processed/{args.role}_val.jsonl", 300, args.seed))
    print(f"train examples: {len(train)} | val examples: {len(val)}")

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype,
        ),
        device_map={"": 0},
        dtype=dtype,
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    ))
    model.print_trainable_parameters()

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(out_dir / "checkpoints"),
            per_device_train_batch_size=args.batch,
            per_device_eval_batch_size=args.batch,
            gradient_accumulation_steps=args.accum,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            lr_scheduler_type="cosine",
            warmup_steps=0.03,
            logging_steps=5,
            eval_strategy="steps",
            eval_steps=200,
            save_strategy="no",
            bf16=use_bf16,
            fp16=not use_bf16,
            gradient_checkpointing=True,
            report_to="none",
            seed=args.seed,
        ),
        train_dataset=train,
        eval_dataset=val,
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
    )
    trainer.train()
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    json.dump({"base_model": args.model}, open(out_dir / "base.json", "w"))
    print(f"Saved adapter to {out_dir}")


if __name__ == "__main__":
    main()