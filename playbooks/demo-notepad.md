---
name: demo-notepad
description: Safe first live test. Opens Notepad, writes a paragraph, saves it.
inputs:
  text: "Operator demo run. If you can read this, the agent can see, click and type."
success_criteria:
  - File Documents\operator-demo.txt exists and contains the input text
max_steps: 25
---

# Steps
1. Press Win, type "Notepad", press Enter. Wait for the Notepad window.
2. Click in the text area. Type `{text}` exactly.
3. Press Ctrl+S. In the Save dialog, set the filename to `%USERPROFILE%\Documents\operator-demo.txt`.
4. If asked to overwrite, confirm (the guard will ask the user first).
5. Take a screenshot. Report done once the window title shows `operator-demo.txt`.

# Rules
- Interact only with Notepad and its Save dialog.
- If anything else takes focus, stop and ask.
