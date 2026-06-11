from __future__ import annotations

import os


MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
BACKEND = os.environ.get("UNSTUCK_BACKEND", "zerogpu")
NEBIUS_BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/")
NEBIUS_MODEL = os.environ.get("NEBIUS_MODEL", MODEL_ID)


if BACKEND == "zerogpu":
    import spaces
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    # ZeroGPU requires plain .to("cuda") at module scope, not accelerate's
    # device_map dispatch, so its monkey-patch can register the weights.
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype="auto",
    ).to("cuda")

    @spaces.GPU(duration=30)
    def generate(prompt: str) -> str:
        """Generate text on the Space GPU and return decoded new tokens only."""
        inputs = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        ).to(model.device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
            )

        generated_ids = output_ids[0][inputs["input_ids"].shape[-1] :]
        return str(tokenizer.decode(generated_ids, skip_special_tokens=True))

elif BACKEND == "hf_inference":
    from huggingface_hub import InferenceClient

    client = InferenceClient(MODEL_ID)

    def generate(prompt: str) -> str:
        """Generate text through the Hugging Face Inference API fallback."""
        response = client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0,
        )
        return str(response.choices[0].message.content)

elif BACKEND == "nebius":
    from huggingface_hub import InferenceClient

    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise RuntimeError("NEBIUS_API_KEY is required for the nebius backend")

    client = InferenceClient(base_url=NEBIUS_BASE_URL, api_key=key)

    def generate(prompt: str) -> str:
        """Generate text through the Nebius AI Studio serverless backend."""
        response = client.chat_completion(
            model=NEBIUS_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0,
        )
        return str(response.choices[0].message.content)

else:
    raise ValueError(f"unsupported UNSTUCK_BACKEND: {BACKEND}")
