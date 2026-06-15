"""Load the *published* fine-tuned model fresh from the Hub and prove it produces
a schema-valid Unstuck breakdown — airtight evidence for achievement:welltuned.

Run:  .venv/bin/python -m modal run scripts/finetune/modal_verify.py
"""

from __future__ import annotations

import pathlib
import sys

import modal

MODEL = "art87able/unstuck-qwen2.5-0.5b-steps"

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch==2.5.1", "transformers==4.46.3", "huggingface_hub==0.26.2"
)
app = modal.App("unstuck-verify", image=image)


@app.function(gpu="A10G", timeout=600)
def verify(prompt: str) -> str:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype="auto").to("cuda")
    text = tok.apply_chat_template(
        [{"role": "user", "content": prompt}],
        add_generation_prompt=True,
        tokenize=False,
    )
    inputs = tok(text, return_tensors="pt").to("cuda")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=512, do_sample=False)
    return tok.decode(out[0][inputs.input_ids.shape[-1] :], skip_special_tokens=True)


@app.local_entrypoint()
def main() -> None:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
    from unstuck.model_adapter import _extract_json  # type: ignore
    from unstuck.prompts import breakdown_prompt  # type: ignore
    from unstuck.schema import validate_steps_payload  # type: ignore

    prompt = breakdown_prompt("Plan a small birthday dinner for six friends", "regular")
    raw = verify.remote(prompt)
    print("RAW:", raw)
    steps = validate_steps_payload(_extract_json(raw))
    print(
        f"VALID ✓ {len(steps.steps)} steps; "
        f"categories={sorted({s.category for s in steps.steps})}; "
        f"max_minutes={max(s.est_minutes for s in steps.steps)}"
    )
