"""Find a non-reasoning NVIDIA Nemotron that produces schema-valid Unstuck plans,
by running it on Modal GPU (open weights, my creds only) through the app's prompt.

Run:  .venv/bin/modal run scripts/finetune/modal_nemotron_test.py --model-id nvidia/Nemotron-Mini-4B-Instruct
"""

from __future__ import annotations

import pathlib
import sys

import modal

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch==2.5.1", "transformers==4.46.3", "huggingface_hub==0.26.2", "sentencepiece"
)
app = modal.App("unstuck-nemotron", image=image)


@app.function(gpu="A10G", timeout=900)
def gen(model_id: str, prompts: list[str], hf_token: str) -> list[str]:
    import torch
    from huggingface_hub import login
    from transformers import AutoModelForCausalLM, AutoTokenizer

    login(token=hf_token)
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype="auto").to("cuda")
    outs = []
    for p in prompts:
        text = tok.apply_chat_template(
            [{"role": "user", "content": p}], add_generation_prompt=True, tokenize=False
        )
        inp = tok(text, return_tensors="pt").to("cuda")
        with torch.no_grad():
            g = model.generate(**inp, max_new_tokens=512, do_sample=False)
        outs.append(tok.decode(g[0][inp["input_ids"].shape[-1] :], skip_special_tokens=True))
    return outs


@app.local_entrypoint()
def main(model_id: str = "nvidia/Nemotron-Mini-4B-Instruct") -> None:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
    from huggingface_hub import get_token  # type: ignore
    from unstuck.model_adapter import _extract_json  # type: ignore
    from unstuck.prompts import breakdown_prompt  # type: ignore
    from unstuck.schema import validate_steps_payload  # type: ignore

    tasks = [
        "Clean my apartment before a friend visits tonight",
        "Catch up on overdue email without losing the whole morning",
        "Prepare to call the dentist and book an appointment",
        "Make progress on a bug report that feels too vague to start",
        "Start the first draft of a hackathon demo script",
    ]
    prompts = [breakdown_prompt(t, "regular") for t in tasks]
    raws = gen.remote(model_id, prompts, get_token())
    valid = 0
    for r in raws:
        try:
            validate_steps_payload(_extract_json(r))
            valid += 1
        except Exception:  # noqa: BLE001
            pass
    print(f"RESULT {model_id}: {valid}/{len(tasks)} valid")
    print("SAMPLE:", raws[0][:320])
