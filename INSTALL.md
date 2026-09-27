# Operator — install & use

A Windows desktop agent: type a task or pick a playbook, and an LLM drives your
real desktop (mouse, keyboard, screen) through a screenshot → action loop. Drafting
is free; **anything that sends/submits/deletes stops and asks you first.** Kill
switch: **Ctrl+Alt+Q**.

This zip is the source. You build the app **on Windows** (a Windows binary can't be
produced anywhere else). Two routes: a one-click installer, or run from source.

---

## What you need

- **Windows 10/11**, no admin rights required.
- **Python 3.11+**.
- **[uv](https://docs.astral.sh/uv/)** (recommended): `winget install astral-sh.uv`
  (or the app's `setup.bat` falls back to plain `python -m venv` + pip).
- A **paid-tier Gemini API key** (the free tier is refused — it can be used for
  training). *Or* a Vertex AI project (enterprise terms, UK region) — see Auth.
- For the one-click installer only: **Inno Setup 6** (`iscc` on PATH).

---

## Option A — one-click installer (recommended)

1. Unzip this folder.
2. Open a terminal in it and run:
   ```bat
   build_installer.bat
   ```
   This builds `dist\Operator.exe`, then wraps it as `Output\OperatorSetup.exe`.
3. Run **`Output\OperatorSetup.exe`**. It installs Operator, makes shortcuts, and on
   **first launch** asks for your **Gemini API key** — stored in Windows Credential
   Manager, never on disk.

## Option B — run from source (dev / test machine)

```bat
setup.bat        REM creates the venv, installs deps, copies the example configs
run.bat          REM launches the app (first run asks for your API key)
```
Re-run the key prompt any time: `run.bat --setup`.

---

## First run

On first launch Operator:
1. Creates `config.toml` and `profile.toml` from the shipped examples.
2. Asks for your API key (if using `auth = "api_key"`) and stores it securely.

Then **fill in `profile.toml`** — this is what makes it *yours*. It's composed into
every run, so the agent works in your voice and to your rules from step one. Paste a
few real examples of messages you've sent into `voice.voice_samples`, set your
sign-offs, list recurring tasks and a do-not-contact list. Personal data stays
local; `profile.toml` is never shared or bundled.

## Auth

- **Paid Gemini API key (simplest):** in `config.toml` set `provider.auth = "api_key"`.
  The app prompts for the key on first run.
- **Vertex AI (enterprise, UK region):** set `provider.auth = "vertex"` and
  `provider.project` (or `GOOGLE_CLOUD_PROJECT`), then authenticate with
  `gcloud auth application-default login`. No key prompt.

## Using it

1. Launch the app (small always-on-top window).
2. **Keep "Dry-run" ON for anything new** — it proposes actions without executing so
   you can check the clicks land correctly (this is where display-scaling bugs show).
3. Pick the **demo-notepad** playbook and step through it dry-run first.
4. Turn dry-run off to run live. It opens Notepad, types a paragraph and saves it,
   pausing for your OK at the save.
5. Then try your own tasks. Free-text a task, or write playbooks in `playbooks/`
   (copy `TEMPLATE.md`). A red banner shows whenever your screen is being sent to
   the model.

## Safety & the rules that matter

- **Confirm-before-send.** Send / submit / post / delete / pay / message all pause
  for your approval, independently of the model.
- **Never types secrets.** If the model tries to type a password or card number it
  refuses and hands control back.
- **Capture blocklist.** Password managers and banking apps aren't captured without
  asking. Outlook and Teams *are* captured (they're intended targets) — change
  either list in `config.toml [privacy]`.
- **LinkedIn:** automating it breaches its terms; don't point this at LinkedIn.
- **Candidate data:** processing candidate personal data through a third-party LLM
  needs your employer's **DPA + DPIA** sign-off first. Use it on your own
  inbox/desktop until that's in place.

## Verify before trusting it

The desktop-specific paths (screen capture, clicking, the global hotkey, the GUI)
are built but were tested on Windows for the first time by you — run the Windows
test suite once: `uv run pytest -m windows`. A few Gemini API details are pinned
from the SDK, not the live docs (the build machine couldn't reach them); see
`docs/API_NOTES.md` for the short list to confirm on your first live run.

## Troubleshooting

- **"No API key found"** → run `run.bat --setup`, or set `GOOGLE_API_KEY`.
- **Refuses to start on free tier** → that's deliberate; use a paid key or Vertex.
- **Clicks land in the wrong place** → a display-scaling issue; run in dry-run and
  see `HANDOFF.md` → the `screen/windows.py` notes.
- **`iscc` not found** → install Inno Setup 6, or just use `dist\Operator.exe`
  directly (it's a working standalone build).

Full detail: `README.md`. Handover notes and the Windows checklist: `HANDOFF.md`.
