---
title: Unstuck
emoji: 🧩
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: "6.17.3"
python_version: "3.12.12"
app_file: app.py
pinned: false
short_description: "Tiny timed steps that learn your time-blindness"
tags:
  - build-small-hackathon
  - backyard-ai
  - track:backyard
  - achievement:offbrand
  - achievement:fieldnotes
  - achievement:sharing
  - achievement:offgrid
  - sponsor:openai
  - tiny-titan
  - tiny-model
  - llama-cpp
  - off-brand
  - field-notes
  - sharing-is-caring
  - codex
  - agent-trace
  - zerogpu
  - qwen
  - adhd
  - time-blindness
  - task-breakdown
  - calibration
  - privacy
  - small-models
---

# Unstuck

Unstuck turns one overwhelming task into tiny timed steps, then learns your personal time-blindness and recalibrates the estimates to you. Built for the HF Build Small Hackathon (Backyard AI track). Runs a ≤4B model (`Qwen/Qwen3-4B-Instruct-2507`).

**Your data stays yours.** Plans and calibration history live in your browser (localStorage), not on the server — nothing is shared between users, and only the task text you submit ever reaches the model. Export/Import gives you the full round-trip.

What it does beyond a breakdown bot: a built-in step timer (Start → Done measures for you), per-category calibration learned from your actual times with a visible "Your patterns" history, progressive reveal (only the next step is live — no wall of steps), recursive "Still stuck?" re-breakdown, skip-without-polluting-the-data, plan persistence across reloads, and a markdown checklist export. One `generate()` seam serves four backends: ZeroGPU, HF serverless inference, Nebius Token Factory, and a fully-offline local GGUF (`offgrid`).

## Demo & submission

- 📺 **Demo video:** [watch the ~90-second demo](https://huggingface.co/spaces/build-small-hackathon/unstuck/resolve/main/unstuck-demo.mp4)
- 📣 **Social post:** https://x.com/arty_able/status/2066306266843021603
- 🧾 **Agent trace (open trace):** https://huggingface.co/datasets/build-small-hackathon/unstuck-agent-trace
- 📝 **Field notes (build write-up):** [docs/field-notes.md](https://github.com/art87able/unstuck/blob/main/docs/field-notes.md)
- 💻 **Source:** https://github.com/art87able/unstuck

**Model:** `Qwen/Qwen3-4B-Instruct-2507` (4B — within the Tiny Titan ≤4B bar). **Built small, in the open** with OpenAI Codex (Codex-attributed commits) and an honest deterministic calibration layer — no AI in the differentiator.

## Run locally

```bash
pip install -r requirements.txt gradio
UNSTUCK_BACKEND=hf_inference HF_TOKEN=... python app.py
```

The default backend is `zerogpu`, which the Space uses. The `hf_inference` path is the lightweight local option.

### Run fully offline (`offgrid`)

No network, no cloud — a local quantised GGUF drives the same `generate()` seam (the honest basis for the `offgrid` badge):

```bash
pip install -r requirements.txt gradio llama-cpp-python
# drop a Qwen3-4B GGUF (e.g. Qwen3-4B-Instruct-2507-Q4_K_M.gguf) into ./models/
UNSTUCK_BACKEND=offgrid OFFGRID_GGUF_PATH=models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf python app.py
```

`llama-cpp-python` is deliberately left out of `requirements.txt` (it would bloat the Space build) — install it only for offline use.

Your history lives in your browser. Use the in-app **Export**/**Import** buttons to move it between devices.

Source: https://github.com/art87able/unstuck (Codex Track)
