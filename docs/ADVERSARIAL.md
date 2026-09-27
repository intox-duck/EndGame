# Adversarial review — findings

Attacks run against every component with hostile / malformed input, assuming
`gemini-3.8-flash`. Model output is treated as **untrusted** throughout. Tests live
in `tests/test_adversarial.py` (43 cases). This records what broke, what was
hardened, and the gaps that remain by design.

## Fixed (real bugs found and closed)

| # | Severity | Component | Defect | Fix |
|---|----------|-----------|--------|-----|
| 1 | **High** | config | `tier = " free "` (whitespace/casing) bypassed the free-tier refusal — the one guarantee that must never fail. | `tier`/`auth` normalised (`strip().lower()`) on load; refusal re-checks stripped. |
| 2 | **High** | agent | A confirmation callback that **raised** (a flaky GUI dialog) crashed the run instead of failing safe — could leave a run half-done. | `_confirm` catches any exception and treats it as **denied**. |
| 3 | Med | screen | NaN / infinite coordinates from a malformed model response crashed `model_to_physical` (`ValueError`), killing the loop. | Non-finite coords clamped to 0. |
| 4 | Med | gemini | Non-numeric / wrong-type coordinate args (`"abc"`, over-long vectors) raised inside `_to_action`, killing the loop. | All numeric extraction goes through `_num()`, which returns `None` for junk; bad coords are skipped, not fatal. |
| 5 | Med | gemini | Junk in `scroll`/`wait`/`drag` numeric args (`int()`/`float()` on a string) crashed the step. | Same `_num()` hardening across scroll magnitude, wait seconds, drag destination. |
| 6 | Med | agent | A screen-capture or redaction failure mid-loop crashed the run. | `_capture_guarded` catches capture/redaction/title errors and returns `None` (safe degrade). |
| 7 | **High** | guard | A bare `Enter`/`Ctrl+Enter` in a mail/chat client with no narration would **send unconfirmed** (the gate only fired on "compose" context). | Enter-class keys now also confirm when the foreground window is a known comms app (Outlook/Teams/Slack/Gmail/…). |

## Verified working (defence held under attack)

- **Prompt-injection → send is gated.** Simulated post-injection behaviour (type an
  attacker address, then click Send) is caught end-to-end: typing is free, the send
  action hits the guard and the user's denial stops it before anything leaves. The
  address in a `To:` field is drafting; the send is the gate. (`test_injection_send_is_gated_end_to_end`)
- **Free-tier refusal** across all casings/whitespace (`FREE`, `Free`, `" free "`).
- **Secret typing** refused for labelled secrets (`password:`, `api_key=`) and
  card-shaped numbers.
- **Malformed model responses** — no candidates, `parts = None`, unknown action
  names — resolve to a safe "done" or a skipped action with a flag, never a crash.
- **Provider exceptions** (`start`/`continue_` raising) become a clean `ERROR`
  outcome, not an uncaught traceback.
- **Degenerate geometry** (1×1, negative multi-monitor offsets) doesn't divide by
  zero.
- **Hostile redaction rectangles** (negative, larger-than-image) don't crash and
  still black out the intended area.
- **Keyring read failure** is swallowed (returns no key) rather than crashing.

## Residual limitations (by design — documented, not silently accepted)

1. **Free-form secrets aren't caught.** A passphrase typed as ordinary prose
   (`correct horse battery staple`) has no label or card format, so the guard
   allows it. Mitigation: the model is instructed never to type secrets, and you see
   the live log. Do not rely on the guard as a secret filter of last resort.
2. **Guard keywords are English (partial locale coverage).** German `Senden` is
   caught by accident (shares the `send` stem); `Envoyer`/`Enviar`/`送信` are not
   from the label alone. Mitigation: add locale words to `guard.confirm_keywords`,
   and/or set `guard.window_allowlist`. The comms-window Enter gate (#7) is
   locale-independent and covers the common send path regardless.
3. **`gemini-3.8-flash` price is a placeholder.** Cost figures are estimates until
   you set the real price in `config.toml [prices]`. The cost *cap* still works;
   only the number shown may be off.
4. **Two-state loops can evade stuck-detection.** A model alternating between two
   identical screens (A,B,A,B) won't trip the "3 identical" check; the step/cost/
   runtime caps still terminate it. Low impact.
5. **Guard errs toward asking.** Benign clicks whose context contains a guarded
   stem (e.g. "apply filter") will prompt for confirmation. Chosen deliberately:
   an extra confirmation is cheaper than a missed send.

## Not in scope (single-user, local threat model)

`config.toml` / `profile.toml` path or content injection, and persona injection,
assume an attacker who can already write files on the machine — i.e. who already
owns it. Not defended here; not a meaningful vector for a personal desktop tool.
