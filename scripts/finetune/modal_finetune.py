"""LoRA fine-tune a tiny Qwen for Unstuck on Modal GPU, publish the merged model to HF.

This is both deliverables in one pipeline:
  - sponsor:modal       -> Modal runs the training (development of the app)
  - achievement:welltuned -> the published fine-tune is wired into the app as a backend

Auth once:   .venv/bin/modal setup
Run:         NEBIUS_API_KEY unused here; needs a local HF token (art87able):
             .venv/bin/python -m modal run scripts/finetune/modal_finetune.py
"""

from __future__ import annotations

import json
import pathlib
import sys

import modal

HF_REPO = "art87able/unstuck-qwen2.5-0.5b-steps"
BASE = "Qwen/Qwen2.5-0.5B-Instruct"
DATA = pathlib.Path(__file__).resolve().parent / "unstuck_sft.jsonl"

image = (
    modal.Image.debian_slim(python_version="3.11").pip_install(
        "torch==2.5.1",
        "transformers==4.46.3",
        "peft==0.13.2",
        "accelerate==1.1.1",
        "huggingface_hub==0.26.2",
    )
)

app = modal.App("unstuck-finetune", image=image)


@app.function(gpu="A10G", timeout=60 * 30)
def train(pairs: list[dict], hf_token: str, sample_prompt: str) -> str:
    import random

    import torch
    from huggingface_hub import login
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    login(token=hf_token)
    tok = AutoTokenizer.from_pretrained(BASE)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16).to(
        "cuda"
    )
    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()
    model.train()

    def render(ex: dict) -> str:
        return tok.apply_chat_template(
            [
                {"role": "user", "content": ex["prompt"]},
                {"role": "assistant", "content": ex["completion"]},
            ],
            tokenize=False,
        )

    texts = [render(p) for p in pairs]
    opt = torch.optim.AdamW(model.parameters(), lr=2e-4)
    batch = 4
    last = 0.0
    for epoch in range(3):
        random.shuffle(texts)
        for i in range(0, len(texts), batch):
            enc = tok(
                texts[i : i + batch],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=1024,
            ).to("cuda")
            labels = enc.input_ids.clone()
            labels[enc.attention_mask == 0] = -100
            out = model(**enc, labels=labels)
            out.loss.backward()
            opt.step()
            opt.zero_grad()
            last = float(out.loss.item())
        print(f"epoch {epoch} loss {last:.4f}", flush=True)

    merged = model.merge_and_unload()
    merged.save_pretrained("/tmp/out")
    tok.save_pretrained("/tmp/out")
    merged.push_to_hub(HF_REPO)
    tok.push_to_hub(HF_REPO)

    # Sanity: generate one breakdown from the freshly tuned model as evidence.
    merged.eval()
    text = tok.apply_chat_template(
        [{"role": "user", "content": sample_prompt}],
        add_generation_prompt=True,
        tokenize=False,
    )
    inputs = tok(text, return_tensors="pt").to("cuda")
    with torch.no_grad():
        gen = merged.generate(**inputs, max_new_tokens=256, do_sample=False)
    sample = tok.decode(gen[0][inputs.input_ids.shape[-1] :], skip_special_tokens=True)
    return f"final_loss={last:.4f}\nsample={sample}"


@app.local_entrypoint()
def main() -> None:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
    from huggingface_hub import get_token
    from unstuck.prompts import breakdown_prompt  # type: ignore

    token = get_token()
    if not token:
        raise SystemExit("no local HF token — run `hf auth login` first")
    pairs = [json.loads(line) for line in DATA.read_text().splitlines() if line.strip()]
    sample_prompt = breakdown_prompt("Organise my overflowing inbox", "regular")
    print(f"training on {len(pairs)} pairs -> {HF_REPO}")
    print(train.remote(pairs, token, sample_prompt))
