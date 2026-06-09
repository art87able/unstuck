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
---

# Unstuck

Unstuck turns one overwhelming task into tiny timed steps, then learns your personal time-blindness and recalibrates the estimates to you. Built for the HF Build Small Hackathon (Backyard AI track). Runs a ≤4B model (`Qwen/Qwen3-4B-Instruct-2507`).

Runs a ≤4B model you can host yourself; your task history stays in the app's own store and is never sent to a third-party LLM.

## Run locally

```bash
pip install -r requirements.txt gradio
UNSTUCK_BACKEND=hf_inference HF_TOKEN=... python app.py
```

The default backend is `zerogpu`, which the Space uses. The `hf_inference` path is the lightweight local option.

Space storage is ephemeral, so use the in-app **Export** button to keep a copy of your task history.

Source: https://github.com/art87able/unstuck (Codex Track)
