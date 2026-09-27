# Research notes (27 Sep 2026)

Gathered in a Claude session before the build. Verify anything marked ⚠ against live docs.

## Gemini computer use
- `gemini-3.5-flash`: generally available; computer use supported **in preview**. Source: ai.google.dev/gemini-api/docs/models/gemini-3.5-flash
- The computer use docs list `gemini-3.8-flash` and `gemini-3.5-flash` (legacy: `gemini-2.5-computer-use-preview-10-2025`). Source: ai.google.dev/gemini-api/docs/computer-use
- Environments: `ENVIRONMENT_BROWSER`, `ENVIRONMENT_MOBILE`, `ENVIRONMENT_DESKTOP`.
- Coordinates are normalised **0–999** on both axes. Convert to physical pixels.
- The SDK shape shown in the docs (⚠ verify, it's preview):
  ```python
  client.interactions.create(model=..., input=..., tools=[{
      "type": "computer_use", "environment": "browser",
      "enable_prompt_injection_detection": True,
      "excluded_predefined_functions": ["drag_and_drop"]}])
  ```
- Browser actions (3.x): click, double_click, type, navigate, scroll, press_key, hotkey, take_screenshot, go_back, go_forward. ⚠ Desktop action names not captured; read the docs.
- Safety: if `safety_decision.decision == "require_confirmation"`, ask the user; on approval send `"safety_acknowledgement": "CONTINUE"` in the function result.
- Screenshots go back as a `function_result` with an image part (base64 PNG).

## Vertex AI (enterprise)
- Third-party tracker lists `gemini-3.5-flash` on Vertex: **global**, **europe-west2 (London)**, europe-west3, among others. ⚠ Unconfirmed in Google's own docs.
- Vertex docs have a computer use page, but its contents weren't readable. ⚠ Confirm computer use works via Vertex for both models.
- A developer reported "model not found" calling from `us-central1`, so use europe-west2 or global.

## Google Antigravity CLI (`agy`)
- An agentic coding assistant, like Claude Code. Runs on Windows. Not suitable as the engine for this screenshot loop. Use the `google-genai` SDK directly.

## Pricing (per million tokens)
| Model | Input | Output | Cached input |
|---|---|---|---|
| Gemini 3.5 Flash | $1.50 | $9.00 | $0.15 |
| Claude Sonnet 5 | $2 | $10 | $0.20 |
| Claude Opus 5.5 | $4 | $20 | $0.20 |
| OpenAI GPT-6 Sol | $2 | $10 | $0.20 |
⚠ Gemini 3.8 Flash price not captured. Check before setting config defaults.

## Cost model
- Per step: about 1,400 tokens per 1280×800 screenshot, plus tool/system overhead (~4.5k for Claude, cached), plus a playbook (~3k, cached), plus about 300 output tokens.
- About 1p per step with caching. A 200-step run costs about $2–3 on Sonnet, roughly 25% less on Gemini Flash.
- Levers: caching, keep only the last 3 screenshots, downscale to 1280 wide (a 1080p screenshot is about 2,800 tokens), and script the steps that never change so screen control handles only the rest (roughly two-thirds cheaper).

## Benchmarks
- OSWorld-Verified (self-reported by each vendor): Gemini 3.5 Flash 78.4, GPT-5.5 78.7, Claude Opus 4.7 78.0. Effectively a tie. Measure cost per *completed run* on our own playbooks.

## Privacy
- Data leaving the machine: screenshots, the task text, and recorder uploads after review.
- The Gemini API free tier may be used for training and human review. The paid tier and Vertex are not used for training (⚠ confirm against current terms for the account in use).
- UK GDPR: candidate personal data processed by a third-party AI needs a DPA and a DPIA from the employer.

## Legal / platform
- LinkedIn's user agreement prohibits bots and automated access, Recruiter included. Accounts get restricted.
