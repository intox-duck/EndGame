"""Operator entry point.

* ``operator`` (or ``python -m operator``) launches the GUI (Windows/desktop).
* ``operator --selfcheck`` runs the full agent loop headless with the MockProvider
  and fake backends — no display, no API, no real desktop — and prints the
  outcome. This is the cloud-phase smoke test and works on any platform.
"""

from __future__ import annotations

import argparse
import sys

from operator_app.config import ConfigError, load_config


def _selfcheck() -> int:
    from operator_app.agent import Agent, StopReason
    from operator_app.config import Config
    from operator_app.executor import Executor, FakeInput
    from operator_app.guard import FlagKillSwitch, Guard
    from operator_app.providers.mock import MockProvider
    from operator_app.screen.base import FakeScreen
    from operator_app.types import Action, ActionType, Step

    cfg = Config()  # defaults; no config.toml needed
    script = [
        Step(text="Opening Notepad", actions=[Action(type=ActionType.KEY, keys="win")]),
        Step(text="Typing", actions=[Action(type=ActionType.TYPE, text="hello")]),
        Step(text="Done", done=True),
    ]
    agent = Agent(
        provider=MockProvider(script, model=cfg.fallback_model),
        executor=Executor(FakeInput(), settle_delay=0, sleep=lambda *_: None),
        screen=FakeScreen(),
        guard=Guard(),
        config=cfg,
        kill_switch=FlagKillSwitch(),
        confirm_cb=lambda *a: True,
    )
    outcome = agent.run(task="self-check", system_instruction="test")
    print(f"selfcheck: {outcome.reason.value} steps={outcome.steps} "
          f"model={outcome.model_used} cost={outcome.cost_total:0.4f}")
    return 0 if outcome.reason is StopReason.DONE else 1


def _launch_gui(config_path: str) -> int:  # pragma: no cover - needs display/PySide6
    from PySide6 import QtWidgets

    from operator_app.agent import Agent
    from operator_app.executor import Executor
    from operator_app.guard import FlagKillSwitch, Guard
    from operator_app.input_windows import make_windows_input
    from operator_app.logging_run import RunLogger
    from operator_app.persona import load_persona
    from operator_app.playbooks import list_playbooks
    from operator_app.privacy import CapturePolicy
    from operator_app.providers.gemini import GeminiProvider
    from operator_app.screen.windows import make_windows_screen
    from operator_app.setup_wizard import ensure_files, ensure_setup, needs_api_key

    # Create the Qt app first so any setup dialog reuses it.
    app = QtWidgets.QApplication(sys.argv)

    # First run: create config.toml / profile.toml from examples so load works.
    ensure_files()
    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    # Prompt once for the API key if api_key auth is selected and none is stored.
    if needs_api_key(cfg.auth):
        for note in ensure_setup(cfg.auth):
            print(note)

    persona = load_persona()
    screen = make_windows_screen(cfg.monitor_index)
    input_backend = make_windows_input()
    kill = FlagKillSwitch()
    _install_hotkey(kill)

    provider = GeminiProvider(cfg)
    model_label = f"{provider.active_model} (fallback {cfg.fallback_model})"

    def agent_factory(task: str, system_instruction: str, dry_run: bool) -> Agent:
        return Agent(
            provider=GeminiProvider(cfg),
            executor=Executor(input_backend, settle_delay=cfg.settle_delay_seconds),
            screen=screen,
            guard=Guard(confirm_keywords=cfg.confirm_keywords,
                        window_allowlist=cfg.window_allowlist),
            config=cfg,
            capture_policy=CapturePolicy(
                blocklist=cfg.capture_blocklist,
                redaction_regions=cfg.redaction_regions),
            logger=RunLogger(cfg.logs_dir, task=task),
            kill_switch=kill,
            dry_run=dry_run,
        )

    # Bake the persona into every run: the GUI's instruction is composed under it.
    factory_with_persona = lambda task, si, dry: agent_factory(  # noqa: E731
        task, persona.compose(si), dry)

    from operator_app.gui import OperatorWindow

    win = OperatorWindow(
        agent_factory=factory_with_persona,
        playbooks=list_playbooks("playbooks"),
        model_label=model_label,
    )
    win.show()
    return app.exec()


def _install_hotkey(kill) -> None:  # pragma: no cover - Windows/desktop
    try:
        from pynput import keyboard

        def on_activate() -> None:
            kill.abort()

        listener = keyboard.GlobalHotKeys({"<ctrl>+<alt>+q": on_activate})
        listener.daemon = True
        listener.start()
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: global kill-switch hotkey unavailable: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="operator")
    parser.add_argument("--selfcheck", action="store_true",
                        help="Run the loop headless with the MockProvider and exit.")
    parser.add_argument("--setup", action="store_true",
                        help="Run first-run setup (files + API key prompt) and exit.")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    args = parser.parse_args(argv)

    if args.selfcheck:
        return _selfcheck()
    if args.setup:
        from operator_app.setup_wizard import ensure_setup
        auth = "api_key"
        try:
            auth = load_config(args.config).auth
        except ConfigError:
            pass
        for note in ensure_setup(auth):
            print(note)
        return 0
    return _launch_gui(args.config)


if __name__ == "__main__":
    raise SystemExit(main())
