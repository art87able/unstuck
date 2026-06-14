from __future__ import annotations

from collections.abc import Callable
import os
from typing import Any


MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
BACKEND = os.environ.get("UNSTUCK_BACKEND", "zerogpu")
TEMPERATURE = float(os.environ.get("UNSTUCK_TEMPERATURE", "0"))
# Token Factory is Nebius's OpenAI-compatible serverless inference API.
# Qwen3-4B is not in its catalog; the 30B-A3B MoE (3B active params) is the
# closest small-model match from the same family.
NEBIUS_BASE_URL = os.environ.get(
    "NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
)
NEBIUS_MODEL = os.environ.get("NEBIUS_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507")


def with_fallback(
    primary: Callable[[str], str], fallback: Callable[[str], str]
) -> Callable[[str], str]:
    """Return generate() that tries primary, then fallback on any exception."""

    def generate(prompt: str) -> str:
        try:
            return primary(prompt)
        except Exception:
            return fallback(prompt)

    return generate


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

    # Prefill the assistant turn with the JSON opening so the model can only
    # continue the object — no preamble, no markdown fence.
    JSON_PREFILL = '{"steps":['

    @spaces.GPU(duration=30)
    def _gpu_generate(prompt: str) -> str:
        """Generate text on the Space GPU and return decoded new tokens only."""
        text = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            tokenize=False,
        )
        inputs = tokenizer(
            text + JSON_PREFILL,
            return_tensors="pt",
            add_special_tokens=False,
        ).to(model.device)

        generate_kwargs: dict[str, object] = {
            "max_new_tokens": 512,
            "do_sample": False,
        }
        if TEMPERATURE > 0:
            generate_kwargs = {
                "max_new_tokens": 512,
                "do_sample": True,
                "temperature": TEMPERATURE,
            }

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                **generate_kwargs,
            )

        generated_ids = output_ids[0][inputs["input_ids"].shape[-1] :]
        decoded = str(tokenizer.decode(generated_ids, skip_special_tokens=True))
        return JSON_PREFILL + decoded

    HF_TOKEN = os.environ.get("HF_TOKEN")
    if HF_TOKEN:
        _serverless_client: Any | None = None

        def _serverless_fallback(prompt: str) -> str:
            """Generate through Hugging Face serverless inference when ZeroGPU is busy."""
            global _serverless_client
            from huggingface_hub import InferenceClient

            if _serverless_client is None:
                _serverless_client = InferenceClient(MODEL_ID, token=HF_TOKEN)

            response = _serverless_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=TEMPERATURE,
            )
            return str(response.choices[0].message.content)

        generate = with_fallback(_gpu_generate, _serverless_fallback)
    else:
        generate = _gpu_generate

elif BACKEND == "hf_inference":
    from huggingface_hub import InferenceClient

    client = InferenceClient(MODEL_ID)

    def generate(prompt: str) -> str:
        """Generate text through the Hugging Face Inference API fallback."""
        response = client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=TEMPERATURE,
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
            temperature=TEMPERATURE,
        )
        return str(response.choices[0].message.content)

elif BACKEND == "offgrid":
    from llama_cpp import Llama

    # Fully on-device: a local quantised GGUF model, no network and no cloud API.
    # This is the honest basis for the achievement:offgrid badge — point
    # OFFGRID_GGUF_PATH at a Qwen3-4B GGUF (e.g. a Q4_K_M build) and the app runs
    # the same generate(prompt) -> str seam with zero outbound calls.
    GGUF_PATH = os.environ.get(
        "OFFGRID_GGUF_PATH", "models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
    )
    _llm = Llama(model_path=GGUF_PATH, n_ctx=4096, verbose=False)

    def generate(prompt: str) -> str:
        """Generate fully on-device via a local GGUF model (no network)."""
        response = _llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=TEMPERATURE,
        )
        return str(response["choices"][0]["message"]["content"])

else:
    raise ValueError(f"unsupported UNSTUCK_BACKEND: {BACKEND}")
