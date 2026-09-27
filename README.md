# Operator

A Windows desktop agent. You type a task (or pick a saved **playbook**) into a
small always-on-top window, and an LLM drives your real desktop — mouse,
keyboard, screen — through a screenshot → action loop until the task is done.

It is **general-purpose**: point it at whatever is on screen. Triage your Outlook
inbox, tell when a Teams message actually needs you versus noise, draft a reply
and ask before sending, or run a repeatable research playbook. It is
**provider-agnostic**: Gemini computer-use today, a Claude adapter stubbed for
later A/B.

> **Status:** cloud phase complete. Everything that doesn't need a real Windows
> desktop is built and tested. The Windows-only paths (input, capture, global
> hotkey, GUI) are written but untested off-Windows. See `HANDOFF.md`.

---

## Safety first — read this

- **Independent guard.** Before any action that matches `send, submit, post,
  publish, delete, remove, pay, purchase, confirm, apply, connect, message,
  inmail`, Operator pauses, shows you the screenshot and the proposed action, and
  waits for your approval. Drafting is free; **the send is always gated.** This is
  our own layer, separate from the model's safety flags.
- **Kill switch:** `Ctrl+Alt+Q` aborts a run instantly, even when the window
  isn't focused. `pyautogui` failsafe (slam the mouse into the top-left corner)
  also aborts.
- **Never types secrets.** If the model tries to type something that looks like a
  password, card number or key, Operator refuses and hands control back to you.
- **Screen-sharing indicator.** A red banner shows whenever the screen is being
  sent to the model.
- **Capture blocklist.** Password managers and banking apps are never captured
  without asking. (Outlook and Teams are *not* blocked — they're intended
  targets. Change either list in `config.toml`.)

## What leaves your machine

Screenshots (downscaled to ≤1280px wide), your task text, and — only after you
review and approve them — recorder uploads. Nothing else. No telemetry.

- **Where it goes:** your configured endpoint. Default is **Vertex AI**
  (`europe-west2`, London; `global` fallback), under enterprise terms. A **paid**
  Gemini API key is also supported.
- **The free tier is refused at startup** — free-tier requests may be used for
  training and human review.
- **Retention:** run screenshots auto-delete after `screenshot_retention_days`
  (default 7). Logs stay local.
- **UK GDPR:** processing candidate personal data through a third-party LLM needs
  a **DPA** with the provider and a **DPIA** from your employer *before* any real
  candidate data goes near this. Triaging your own inbox is fine; candidate PII in
  a screenshot is the line.

## LinkedIn

Automating LinkedIn — Recruiter included — breaches its User Agreement and risks
account restriction. Operator does not build LinkedIn-specific automation. Use
LinkedIn's permitted APIs / licensed data sources for LinkedIn steps. The GUI and
this README carry the warning; the general tool is unaffected.

---

## Install (Windows)

Requires Python 3.11+. No admin rights needed.

```bat
setup.bat        REM creates the venv, installs deps, copies config.example.toml and .env.example
```

Then edit `config.toml` and `.env`, and:

```bat
run.bat          REM launches the GUI
```

## Auth

**Vertex AI (default, recommended):**
- `provider.auth = "vertex"`, set `provider.project` (or `GOOGLE_CLOUD_PROJECT`).
- Authenticate with `gcloud auth application-default login` or a service-account
  key in `GOOGLE_APPLICATION_CREDENTIALS`.
- Region `europe-west2` preferred, `global` fallback.

**Paid Gemini API key:**
- `provider.auth = "api_key"`, set `GOOGLE_API_KEY` in `.env`. Must be paid tier.

## Model selection & fallback

Preferred `gemini-3.8-flash`, fallback `gemini-3.5-flash`. At startup Operator
lists available models and picks the preferred one if present, else the fallback.
The active model is shown in the GUI and logged in every run summary.

## Playbooks

Markdown files in `playbooks/` with a YAML header:

```markdown
---
name: my-playbook
description: One line on what this achieves.
inputs:
  role_title: ""
  location: "London"
success_criteria:
  - What "done" looks like, checkably
max_steps: 150
---

# Steps
1. One action or check per step. Name buttons and fields exactly.
```

The GUI lists playbooks, lets you fill inputs, and sends the rendered body as the
model's instruction. `{input}` placeholders are substituted. Start from
`playbooks/TEMPLATE.md`; `playbooks/demo-notepad.md` is the safe first live test.

## Config

Everything lives in `config.toml` (copy from `config.example.toml`). Highlights:
loop caps (`max_steps`, `max_cost_per_run`, `max_runtime_seconds`), screenshot
width, **model prices** (per million tokens — update these; they live in config,
not code), guard keywords, window allowlist, capture blocklist, redaction
regions, retention. Secrets live only in `.env`.

## Recorder

Record mode captures your screenshots + input to `recordings/<timestamp>/`,
locally. Password fields are masked at capture time. Nothing is sent to a model
during normal runs. "Draft playbook" first shows a **review/redaction** step —
drop events, confirm masking — and only then asks a model to draft a `.md` for you
to edit. Drafted playbooks are never auto-run.

## Logs & cost

Each run writes `logs/<timestamp>/`: `steps.jsonl` (every action, model text,
tokens, latency, model used), screenshots, and `summary.md` (outcome, steps,
tokens, cost, model). A running £/$ estimate shows in the GUI.

## Development

```bash
uv sync --extra dev
uv run pytest                 # non-Windows suite (103 tests)
uv run pytest -m windows      # Windows-only paths (run on Windows)
uv run operator --selfcheck   # headless end-to-end loop with the MockProvider
```

Architecture: normalised `Action`/`Step` types (`types.py`) that every provider
maps into; `screen/` (coordinate maths + capture behind an interface); `executor`
(actions → input backend); `guard` + `privacy` (safety); `providers/` (mock,
gemini, anthropic stub); `agent` (the loop); `gui` (PySide6). Windows-only code is
isolated behind interfaces with fakes so the whole loop runs in CI.

## Packaging

```bat
uv run pyinstaller operator.spec     REM builds dist\Operator.exe
```
Ship `config.example.toml`, `.env.example` and `playbooks/` alongside the exe.

## Known limits

- Desktop computer-use action names and coordinate range are pinned from the
  installed SDK, not the live docs (unreachable from the build sandbox). See
  `docs/API_NOTES.md` for the ⚠ items to confirm before the first live run.
- The Anthropic provider is a stub.
- DPI/coordinate accuracy is unit-tested but unproven on real hardware until the
  Windows tests run (Phase 2).
