---
name: my-playbook
description: One line on what this run achieves.
inputs:
  role_title: ""
  location: ""
success_criteria:
  - What "done" looks like, checkably
max_steps: 150
---

# Context
Why this run exists and what the output feeds into.

# Steps
1. Start with the app or window to open.
2. One action or check per step. Name buttons and fields exactly as they appear on screen.
3. Say where results go (for example, append rows to an Excel file at a fixed path).

# Rules
- Apps/windows the agent may use:
- Never: send messages, submit forms, or use LinkedIn automation.
- When unsure, stop and ask.

# Output
Format and location of the results.
