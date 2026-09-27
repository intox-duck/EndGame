# HANDOFF — cloud phase → your Windows PC

Phase 1 (everything that doesn't need a real Windows desktop) is built, tested and
pushed. This is what's done, what's untested, and the exact steps to take on
Windows.

## What's done (and verified in the cloud)

- Full package under `src/operator_app/` (the import name is `operator_app`; the
  bare name `operator` collides with a Python stdlib module — the CLI command is
  still `operator`).
- Normalised action/step types; config loader with **free-tier refusal**; screen
  coordinate maths; executor; **guard** (send/secret/allowlist rules); **privacy**
  (blocklist/redaction/retention); cost; per-run logging; playbook parser;
  recorder data model + review/redaction + draft builder.
- Providers: `MockProvider`, **Gemini** adapter (built against the installed
  `google-genai==2.25.0` surface), Anthropic **stub**.
- Agent loop with caps (steps/cost/runtime), keep-last-3-screenshots, stuck
  detection + one recovery, guard integration, dry-run.
- GUI (`gui.py`), `__main__` wiring, `setup.bat`, `run.bat`, `operator.spec`.
- **103 tests pass** off-Windows. `uv run operator --selfcheck` runs the whole
  loop headless with no API and no desktop.

## What is NOT tested (Windows-only — do these first)

Everything behind a Windows backend, marked `@pytest.mark.windows` or compiled but
not run:

1. **DPI / coordinate accuracy** (`screen/windows.py`) — the #1 risk. The pure
   maths is unit-tested; the real capture + physical-pixel clicks are not.
2. **Input** (`input_windows.py`) — pyautogui / pydirectinput, key aliases.
3. **Global kill-switch hotkey** `Ctrl+Alt+Q` (`pynput`, in `__main__`).
4. **Foreground-window title** reads (win32) used by the guard/blocklist.
5. **GUI** (`gui.py`) — needs a display and PySide6.

## ⚠ Confirm against the live docs before the first LIVE run

The build sandbox can't reach Google's docs, so these came from introspecting the
SDK, not the live API. All are isolated (see `docs/API_NOTES.md`):

1. **Desktop action names** → `providers/gemini.py::_ACTION_MAP`. Run one real
   task in dry-run, watch `logs/<ts>/steps.jsonl` for any `Unknown model action`
   safety flags, and add the real names to the map.
2. **Coordinate range** (assumed normalised 0–999) → `screen/base.py::MODEL_COORD_MAX`.
3. **Safety ack key/value** (`safety_acknowledgement: CONTINUE`) →
   `providers/gemini.py::continue_`.
4. **Model availability + Vertex region** for `gemini-3.8-flash` / `3.5-flash`.
5. **`gemini-3.8-flash` price** → `config.toml [prices]` (placeholder today).

## Steps on Windows

```bat
git clone <this repo>
cd <repo>
setup.bat
REM edit config.toml (project, region, prices) and .env (credentials)

uv run pytest -m windows        REM run the Windows-only tests; fix DPI/coord issues first
uv run operator --selfcheck     REM sanity: headless loop

run.bat                         REM launch the GUI
```

Then, in the GUI:
1. Pick the **demo-notepad** playbook.
2. **Dry-run ON.** Step through — confirm the proposed clicks land on the right
   spots (this is where DPI/coordinate bugs show up). Fix `screen/windows.py` if
   the pointer is off.
3. Dry-run OFF, run demo-notepad **live**. It should open Notepad, type the
   paragraph, and save `Documents\operator-demo.txt` — pausing for your
   confirmation at the save.
4. Only then try your own tasks. Keep dry-run on for anything new.

## Before real candidate data

Get **DPA + DPIA** sign-off from your employer. Until then, use it on your own
inbox/desktop, not candidate PII.

## Scope note (deviation from PROMPT.md)

PROMPT.md's default capture blocklist included Outlook and Teams. Since you want
those triaged, the default now **captures** them and blocks only banking apps and
password managers. Both lists are in `config.toml [privacy]`. Reading/flagging is
free; sending is gated by the guard.
