# Build: Windows desktop agent ("Operator") — Gemini computer use, provider-agnostic

## Goal
A Windows 10/11 desktop app: I type a task (or pick a saved playbook) into a small GUI, and an LLM drives my real desktop (mouse, keyboard, screen) via a screenshot → action → screenshot loop until done. Primary use: repeatable talent-research runs. Must install and run on any Windows machine with Python 3.11+, including this one.

## Before writing code
1. Read the CURRENT Gemini computer use docs (https://ai.google.dev/gemini-api/docs/computer-use) and the google-genai Python SDK docs. Do NOT rely on memory: the API surface (interactions API, action names, desktop environment, tool config, safety_decision) has changed across versions. Record the exact desktop action names and request/response shapes in `docs/API_NOTES.md` with links.
2. Confirm computer use works on Vertex AI (google-genai with `vertexai=True`, location `europe-west2` preferred, `global` fallback) for BOTH `gemini-3.8-flash` and `gemini-3.5-flash`. Default auth = Vertex AI (enterprise terms, UK region). A Gemini API key is allowed only on a PAID tier. Refuse to start if config indicates the free tier, and say why in the GUI.
3. Ask me before choosing anything irreversible. Otherwise proceed.

## Stack
- Python 3.11+, managed with uv (fallback: pip + requirements.txt)
- GUI: PySide6 (small always-on-top window)
- Screen: mss (capture), Pillow (resize), pyautogui for mouse/keyboard (+ pydirectinput fallback for apps that ignore synthetic input)
- Hotkeys/recording: pynput
- Config: `config.toml` + `.env` (API keys and credentials never in code or logs)
- Model: google-genai SDK. Preferred model `gemini-3.8-flash`; fallback `gemini-3.5-flash`.
  - On startup, check availability (list models or a 1-token test call on the configured endpoint).
  - Use 3.8 if it is available AND supports computer use with the desktop environment; otherwise fall back to 3.5 and show which model is active in the GUI.
  - Log the model actually used in every run summary.

## Architecture (keep modules small and testable)
- `providers/base.py` — Provider interface: `start(task, playbook, screenshot) -> Step`, `continue_(results) -> Step`. `Step` = list of normalised actions + text + usage + done flag + safety flags.
- `providers/gemini.py` — Gemini computer use, desktop environment. Map its actions to our normalised `Action` type. Handle `safety_decision: require_confirmation` → pause and ask me in the GUI; on approval, send the acknowledgement the docs specify.
- `providers/anthropic.py` — stub implementing the same interface (Claude computer use), so I can A/B later. Mark TODO where untested.
- `screen.py` — Windows DPI awareness (call `SetProcessDpiAwareness`/`SetProcessDpiAwarenessContext` at startup, before any capture), capture primary monitor (configurable), downscale to max 1280px wide for the model, and convert model coordinates (normalised 0–999 for Gemini; pixel-space for others) back to PHYSICAL screen pixels. This is the #1 bug source — unit-test it with multiple resolutions and 100/125/150% scaling.
- `executor.py` — executes normalised actions (click, double_click, right_click, move, drag, type, key/hotkey, scroll, wait, screenshot). Small settle delay after each action (configurable). pyautogui FAILSAFE on (mouse to top-left corner aborts).
- `agent.py` — the loop. Caps: `max_steps` (default 150), `max_cost_per_run` (default $3), `max_runtime`. Keep only the last N=3 screenshots in context; summarise older steps as text. Use context caching where the SDK supports it. Detect "stuck" (same screenshot hash 3× or repeated identical action) → one recovery prompt, then stop and ask me.
- `guard.py` — my safety layer, independent of the model's:
  - Global kill switch hotkey **Ctrl+Alt+Q** (works even when the GUI isn't focused).
  - Confirmation required before any action whose target text/context matches: send, submit, post, publish, delete, remove, pay, purchase, confirm, apply, connect, message, InMail (configurable list), and before typing into any email/chat compose box. Show screenshot + proposed action; approve/deny.
  - Never type passwords, card numbers or secrets; if the model asks for credentials, pause and hand control to me.
  - Optional allowlist of window titles/apps the agent may interact with.
- `playbooks/` — Markdown playbooks with YAML header (name, description, inputs, success criteria, max_steps). GUI lets me pick one and fill its inputs; the playbook is sent as a cached system instruction.
- `recorder.py` — "Record" mode. Captures screenshots + my mouse/keyboard events to `recordings/<timestamp>/`, stored locally only. Password fields masked; a "pause recording" hotkey. A "Draft playbook" button first shows a review/edit screen of exactly what will be sent (sampled screenshots + event log, with the ability to delete events or redact), then sends it to the model and writes a draft playbook `.md` for me to edit. Never auto-run a drafted playbook.
- `gui.py` — task input box, playbook picker + input fields, provider/model display (showing the active model and fallback status), Dry-run toggle (model proposes actions, nothing executes; I step through), Run/Pause/Stop, live log (model reasoning text + actions), running token count and £/$ cost estimate, confirmation dialog.
- `logs/` — per-run folder: JSONL of every step (action, model text, usage tokens, latency, model used), screenshots, final `summary.md` with outcome, steps, tokens, cost and model used. Prices live in config so I can update them.

## Privacy & data protection
- Screenshots are the main data leaving the machine. Add:
  - Window/app blocklist (default: Outlook, Teams, password managers, banking) → if the foreground window matches, pause and ask before capturing.
  - Optional redaction regions (screen rectangles blacked out before sending).
  - A visible "Screen is being shared with the model" indicator while a run is active.
- Recorder: keystrokes stay local; never send the raw keystroke log during normal runs; only send recorder data after the review step above.
- Local retention: auto-delete run screenshots after N days (config, default 7); logs stay local; no telemetry.
- README section: what leaves the machine, where it goes (endpoint + region), the provider's training/retention terms for the configured auth, and a note that processing candidate personal data requires employer approval (DPA/DPIA) first.

## Deliverables
- Working app, `run.bat` (one-click launch), `setup.bat` (creates the venv, installs deps, copies `config.example.toml` and `.env.example`).
- Optional: PyInstaller spec to build a single `.exe`.
- README: setup, Vertex vs paid API-key auth, model selection/fallback, config, playbook format, safety features, privacy, known limits.
- Tests (pytest): coordinate mapping, action normalisation from recorded fixture responses, model fallback logic, guard rules, cost calculator, and a MockProvider so the loop runs end-to-end with no API calls.
- A safe demo playbook: open Notepad, type a paragraph, save to `Documents\operator-demo.txt`. Use this for the first live test.

## Constraints
- Windows-first; no admin rights required.
- No telemetry. Keys only from `.env` / environment.
- Clear, typed, commented code; no giant files.
- Prominent warning in README and GUI: automating LinkedIn (including Recruiter) breaches its user agreement and risks account restriction. Use permitted APIs/data sources for LinkedIn steps.

## Two-phase build (IMPORTANT)
- **Phase 1 — cloud (Linux sandbox, now):** build everything that doesn't need a real Windows desktop: package layout, config, providers (incl. Gemini adapter against docs + recorded fixtures), MockProvider, agent loop, guard, cost/logging, playbook parsing, recorder data model + review step, GUI code, packaging scripts, README, full test suite. Windows-only code paths (DPI calls, pyautogui/pydirectinput, pynput global hotkeys, win32 foreground-window checks) must be isolated behind interfaces with fakes, and their tests marked `@pytest.mark.windows` (skipped off Windows). Everything else must pass in the cloud. Commit and push to a GitHub repo I'll clone locally. Finish with `HANDOFF.md`: what's done, what's untested on Windows, and the exact local steps.
- **Phase 2 — local (my Windows PC, later):** run `setup.bat`, run the Windows-marked tests, fix DPI/coordinate issues, then the Notepad demo in dry-run, then live.

## Working method
Plan first (write `PLAN.md`), then build in this order: screen + coordinate tests → executor → MockProvider loop → GUI → Gemini provider (with 3.8 → 3.5 fallback) → guard → privacy controls → logging/cost → recorder → playbook drafting → packaging. Use sub-agents in parallel where modules are independent. Run tests after each stage. Stop and show me the demo playbook working in dry-run before the first live run.
