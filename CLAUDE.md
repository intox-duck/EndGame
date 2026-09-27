# Operator — project memory for Claude Code

## What this is
A Windows desktop agent: a small GUI where the user types a task or picks a playbook, and an LLM drives the real desktop through a screenshot → action loop. Main use: repeatable talent-research runs for a UK recruitment firm. Full spec: `PROMPT.md`. Research behind the decisions: `docs/RESEARCH_NOTES.md`.

## Owner
James: Senior Talent Intelligence Lead, UK. Self-taught engineer (Python/FastAPI, TS/Next.js, Microsoft Fabric). Wants direct, terse communication and British spelling. Push back when he's wrong.

## Non-negotiables
- Model: `gemini-3.8-flash` preferred, `gemini-3.5-flash` fallback. Check availability and desktop computer-use support at startup; show the active model.
- Auth: Vertex AI (europe-west2, then global) by default. A paid-tier Gemini API key is allowed. Never the free tier: it can be used for training.
- Read the CURRENT Gemini computer use docs before coding against them. The API is in preview and its action names have changed between versions.
- Our own guard layer confirms any send/submit/delete/pay/message action, independently of the model's safety flags. Kill switch: Ctrl+Alt+Q.
- Never type passwords or secrets. Hand control back to the user instead.
- Screenshots are the main data leaving the machine: blocklist, redaction regions and an on-screen indicator are required.
- The recorder keeps keystrokes local until the user reviews and approves an upload.
- LinkedIn automation breaches its user agreement: warn in the README and GUI, and never build LinkedIn-specific automation.
- Candidate personal data needs employer DPA/DPIA sign-off. Say so in the README.
- Provider-agnostic: Anthropic adapter stub alongside Gemini, same interface.

## Conventions
- Python 3.11+, uv, PySide6, pytest. Typed, small modules, no giant files.
- Windows-only code sits behind interfaces with fakes; tests marked `@pytest.mark.windows`.
- Config in `config.toml`, secrets in `.env`, never logged.
- Per-run logs in `logs/<timestamp>/` (JSONL steps, screenshots, `summary.md` with the model used, tokens and cost).
- Prices live in config, not code.

## Definition of done (cloud phase)
All non-Windows tests pass; the MockProvider runs the loop end to end; README and HANDOFF.md written; code pushed to GitHub.
