# Gemini computer-use — API notes

**Status of sources.** The cloud build sandbox blocks outbound access to
`ai.google.dev` and Google's docs hosts (network egress policy allows only package
registries + Anthropic). So these notes are **not** taken from the live docs.
They are taken from a first-hand source that is better than memory: the installed
`google-genai` SDK (**version 2.25.0**), introspected directly. Anything the SDK
does not pin down is marked ⚠ and must be verified against the live docs before
the first live run.

> Verify the ⚠ items at: https://ai.google.dev/gemini-api/docs/computer-use and
> https://cloud.google.com/vertex-ai/generative-ai/docs/computer-use

## Verified from `google-genai==2.25.0` (introspected)

### Client construction
```python
from google import genai
# Vertex AI (default for this project):
client = genai.Client(vertexai=True, project="<gcp-project>", location="europe-west2")
# Paid Gemini API key:
client = genai.Client(api_key="<key>")
```
`Client.__init__` params: `enterprise, vertexai, api_key, credentials, project, location, debug_config, http_options`.

### The call is standard `generate_content` — NOT `interactions.create`
The research note's `client.interactions.create(...)` shape does **not** exist in
this SDK. Computer use is a normal tool on the content-generation loop:

```python
from google.genai import types

tool = types.Tool(
    computer_use=types.ComputerUse(
        environment=types.Environment.ENVIRONMENT_DESKTOP,
        excluded_predefined_functions=["drag_and_drop"],   # optional
        enable_prompt_injection_detection=True,            # optional
        # disabled_safety_policies=[...]  # NOT supported on Vertex AI
    )
)
resp = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=contents,               # list[types.Content]
    config=types.GenerateContentConfig(tools=[tool], system_instruction=...),
)
```

### `types.ComputerUse` fields (verified)
- `environment: Environment` — required.
- `excluded_predefined_functions: list[str]` — exclude some predefined actions.
- `enable_prompt_injection_detection: bool`.
- `disabled_safety_policies: list[SafetyPolicy]` — **not supported on Vertex AI.**

### `types.Environment` enum values (verified)
`ENVIRONMENT_UNSPECIFIED`, `ENVIRONMENT_BROWSER`, `ENVIRONMENT_MOBILE`,
`ENVIRONMENT_DESKTOP`. → we use `ENVIRONMENT_DESKTOP`.

### Model → us: actions come back as `FunctionCall` parts
`resp.candidates[0].content.parts[i].function_call` is a `types.FunctionCall`:
- `name: str` — the predefined action name (e.g. `click_at`, `type_text_at`).
- `args: dict` — the action arguments (coordinates, text, keys, and, when the
  model wants confirmation, a `safety_decision` object — see below).
- `id: str | None`.

### us → model: reply with `FunctionResponse`, screenshot as an image Part
```python
types.Content(role="user", parts=[
    types.Part(function_response=types.FunctionResponse(
        name=call.name,
        id=call.id,
        response={...},                      # e.g. {"safety_acknowledgement": "CONTINUE"}
        parts=[types.Part(inline_data=types.Blob(
            mime_type="image/png", data=png_bytes))],  # the post-action screenshot
    ))
])
```
Verified: `FunctionResponse` fields = `will_continue, scheduling, parts, id, name,
response`; `Part` supports `inline_data` and `types.Blob(data, mime_type,
display_name)`; `Part.from_function_response(...)` helper exists.

## ⚠ Not pinned by the SDK — verify against live docs before going live

1. **Exact desktop action names + arg schemas.** The predefined functions are
   defined server-side; the SDK does not enumerate them. Our normalisation table
   (`providers/gemini.py::_ACTION_MAP`) is built from the research notes and the
   browser action set, and is the single place to fix once the desktop list is
   confirmed. Expected candidates: `open_web_browser`, `click_at`, `hover_at`,
   `type_text_at`, `key_combination`/`press_keys`, `scroll_document`/`scroll_at`,
   `drag_and_drop`, `wait_5_seconds`, `navigate`, `go_back`, `go_forward`,
   `take_screenshot`.
2. **Coordinate system.** Research notes say normalised **0–999** on both axes for
   Gemini. `screen.py` converts 0–999 → physical pixels. ⚠ confirm the range and
   whether desktop uses the same normalisation as browser.
3. **Safety confirmation shape.** Expectation: when the model wants confirmation
   it includes `safety_decision` in `FunctionCall.args`, e.g.
   `{"decision": "require_confirmation", "explanation": "..."}`; we acknowledge by
   putting `{"safety_acknowledgement": "CONTINUE"}` (⚠ exact key/value) into
   `FunctionResponse.response`. Handled defensively in the adapter — unknown shapes
   pause and ask the user rather than proceeding.
4. **Model IDs / availability.** `gemini-3.8-flash` (preferred) and
   `gemini-3.5-flash` (fallback) — confirm both exist on the configured endpoint
   and support the DESKTOP environment. Startup does a live availability probe.
5. **Vertex region.** `europe-west2` preferred, `global` fallback for computer use.
   ⚠ confirm computer use is served from europe-west2; a report exists of
   "model not found" from us-central1.
6. **Pricing for `gemini-3.8-flash`.** Not captured in research notes. `config.toml`
   carries prices; update before trusting cost figures.

## Design consequence
`providers/gemini.py` is written so that **all** of the above ⚠ items are isolated:
action names in one map, coordinate conversion in `screen.py`, safety-shape parsing
in one defensive function. When the live docs are read on Windows, only those spots
change — the agent loop, guard, executor and GUI are untouched.
