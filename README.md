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
short_description: "Learns your personal time-blindness — one overwhelming task becomes tiny timed steps, and the estimates recalibrate to how long YOU actually take."
tags:
  - build-small-hackathon
  - backyard-ai
  - track:backyard
  - achievement:offbrand
  - achievement:fieldnotes
  - achievement:sharing
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

What it does beyond a breakdown bot: a built-in step timer (Start → Done measures for you), per-category calibration learned from your actual times with a visible "Your patterns" history, progressive reveal (only the next step is live — no wall of steps), recursive "Still stuck?" re-breakdown, skip-without-polluting-the-data, plan persistence across reloads, and a markdown checklist export. One `generate()` seam serves three backends: ZeroGPU, HF serverless inference, and Nebius Token Factory.

## Run locally

```bash
pip install -r requirements.txt gradio
UNSTUCK_BACKEND=hf_inference HF_TOKEN=... python app.py
```

The default backend is `zerogpu`, which the Space uses. The `hf_inference` path is the lightweight local option.

Your history lives in your browser. Use the in-app **Export**/**Import** buttons to move it between devices.

Source: https://github.com/art87able/unstuck (Codex Track)
