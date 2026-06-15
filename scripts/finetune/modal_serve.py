"""Serve the published fine-tune serverless on Modal (the Phase-2 'serve serverless'
goal, and the sponsor:modal *runtime* claim — Modal for runtime, not just training).

Deploy:  .venv/bin/modal deploy scripts/finetune/modal_serve.py
That prints a persistent URL; point the app at it:
         UNSTUCK_BACKEND=modal MODAL_ENDPOINT_URL=<url> python app.py
"""

from __future__ import annotations

import modal

MODEL = "art87able/unstuck-qwen2.5-0.5b-steps"

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch==2.5.1", "transformers==4.46.3", "fastapi[standard]"
)
app = modal.App("unstuck-serve", image=image)


@app.cls(gpu="A10G", scaledown_window=120, min_containers=0)
class Server:
    @modal.enter()
    def load(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(MODEL)
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL, torch_dtype="auto"
        ).to("cuda")

    @modal.fastapi_endpoint(method="POST")
    def generate(self, data: dict) -> dict:
        prompt = data.get("prompt", "")
        text = self.tok.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            tokenize=False,
        )
        inputs = self.tok(text, return_tensors="pt").to("cuda")
        with self.torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=512, do_sample=False)
        decoded = self.tok.decode(
            out[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True
        )
        return {"text": decoded}
