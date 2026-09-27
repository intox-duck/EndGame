# PLAN — Operator (Phase 1, cloud/Linux)

## Scope correction (27 Sep 2026)
Operator is a **general-purpose desktop copilot**, not a scraper. The user points
it at whatever is on screen: Outlook triage, spotting when a Teams message genuinely
needs him vs. noise, answering trivial questions, and repeatable research runs. The
architecture is already app- and provider-agnostic, so this needs no structural
change — only two things:
- **Privacy blocklist is config-driven and defaults to *capture* Outlook/Teams**
  (they are the intended targets), while keeping banking apps and password managers
  hard-blocked. This deviates from PROMPT.md's default and is documented in README +
  HANDOFF.
- **LinkedIn:** we still do not build LinkedIn-*specific* automation and keep the
  ToS warning, but that is a single-site caveat, not a constraint on the tool.

## Definition of done (this phase)
All non-Windows tests pass; MockProvider runs the loop end-to-end; README +
HANDOFF.md written; pushed to `claude/c-apps-endgame-execute-95zdxo`.
Windows-only paths isolated behind interfaces with fakes; their tests marked
`@pytest.mark.windows` (skipped here).

## Module map (`src/operator/`)
- `types.py` — `Action`, `ActionType`, `Step`, `Usage`, `SafetyFlag`. Normalised
  vocabulary every provider maps into and the executor consumes.
- `config.py` — load `config.toml` + `.env`; typed `Config`; free-tier refusal;
  never log secrets.
- `screen/` — `ScreenBackend` interface + `capture`, downscale to ≤1280w,
  coordinate conversion (normalised 0–999 → physical px, DPI/scale aware).
  `FakeScreen` for tests; `windows.py` real backend (DPI calls, mss) behind marker.
- `executor.py` — `InputBackend` interface; `execute(action)`; settle delay;
  failsafe. `FakeInput` for tests; `windows.py` real (pyautogui/pydirectinput).
- `guard.py` — independent confirm layer: keyword match (send/submit/delete/pay/
  message/…), compose-box detection, secret refusal, window allowlist/blocklist,
  kill-switch contract (Ctrl+Alt+Q). Pure-logic core, testable off-Windows.
- `privacy.py` — window capture blocklist/allowlist, redaction regions, retention
  sweep (auto-delete screenshots after N days).
- `cost.py` — token→£/$ from config prices; per-step + run totals.
- `logging_run.py` — per-run folder, JSONL step log, `summary.md`.
- `playbooks.py` — parse YAML-header markdown; inputs; success criteria; `{input}`
  substitution.
- `recorder.py` — recording data model, password masking, review/redaction step,
  draft-playbook builder. No global-hotkey capture off-Windows (behind interface).
- `providers/base.py` — `Provider` protocol: `start(...) -> Step`,
  `continue_(results) -> Step`; `Step`, `NormalisedResult`.
- `providers/mock.py` — scripted provider; drives loop with no API calls.
- `providers/gemini.py` — google-genai adapter; `_ACTION_MAP`; safety parsing;
  3.8→3.5 fallback; Vertex/api-key auth; availability probe. Built against
  `API_NOTES.md`; ⚠ items isolated.
- `providers/anthropic.py` — stub, same interface, TODOs.
- `agent.py` — the loop: caps (max_steps 150, max_cost $3, max_runtime), keep last
  3 screenshots, summarise older, stuck detection (hash/repeat) → recover once →
  stop+ask, guard integration, dry-run.
- `gui.py` — PySide6 window (guarded import; headless-safe). Task box, playbook
  picker, provider/model display, dry-run, run/pause/stop, live log, cost, confirm
  dialog, "screen is being shared" indicator.
- `__main__.py` — CLI entry: `operator` launches GUI; `--selfcheck` runs headless.

## Build order
types → config → screen+coord tests → executor → guard/privacy → cost/logging →
playbooks → MockProvider + agent loop (end-to-end test) → gemini adapter (+fixtures)
→ anthropic stub → recorder → gui → packaging (setup.bat/run.bat/pyinstaller) →
README + HANDOFF. Tests after each stage.

## Test plan (pytest, off-Windows green)
coordinate mapping (multi-res + 100/125/150% scale) · action normalisation from
recorded Gemini fixtures · model-fallback logic · guard rules · cost calculator ·
playbook parsing · MockProvider end-to-end loop · recorder redaction/masking ·
privacy retention sweep. Windows-real paths: `@pytest.mark.windows`.
