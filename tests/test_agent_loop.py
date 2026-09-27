from __future__ import annotations

from operator_app.agent import Agent, StopReason
from operator_app.config import Config
from operator_app.executor import Executor, FakeInput
from operator_app.guard import FlagKillSwitch, Guard
from operator_app.privacy import CapturePolicy
from operator_app.providers.mock import MockProvider
from operator_app.screen.base import FakeScreen, ScreenGeometry
from operator_app.types import Action, ActionType, SafetyDecision, SafetyFlag, Step


def build_agent(script, **kw):
    fake_in = FakeInput()
    agent = Agent(
        provider=MockProvider(script, model="gemini-3.5-flash"),
        executor=Executor(fake_in, settle_delay=0, sleep=lambda *_: None),
        screen=kw.pop("screen", FakeScreen(ScreenGeometry(1920, 1080))),
        guard=kw.pop("guard", Guard()),
        config=kw.pop("config", Config()),
        confirm_cb=kw.pop("confirm_cb", lambda *a: True),
        kill_switch=kw.pop("kill_switch", FlagKillSwitch()),
        **kw,
    )
    return agent, fake_in


def test_runs_to_done():
    script = [
        Step(text="one", actions=[Action(type=ActionType.KEY, keys="win")]),
        Step(text="two", actions=[Action(type=ActionType.TYPE, text="hello")]),
        Step(done=True, text="finished"),
    ]
    agent, fake = build_agent(script)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.DONE
    assert out.steps == 3
    assert ("type", "hello") in fake.events
    assert out.cost_total > 0


def test_dry_run_executes_nothing():
    script = [Step(actions=[Action(type=ActionType.TYPE, text="x")]), Step(done=True)]
    agent, fake = build_agent(script, dry_run=True)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.DONE
    assert fake.events == []  # nothing executed


def test_guard_confirm_denied_stops():
    script = [
        Step(actions=[Action(type=ActionType.CLICK, x=1, y=1)], text="Click Send"),
        Step(done=True),
    ]
    agent, fake = build_agent(script, confirm_cb=lambda *a: False)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.USER_DENIED
    assert fake.events == []


def test_guard_confirm_approved_continues():
    script = [
        Step(actions=[Action(type=ActionType.CLICK, x=5, y=5)], text="Click Send"),
        Step(done=True),
    ]
    approvals = []
    agent, fake = build_agent(script, confirm_cb=lambda *a: approvals.append(a) or True)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.DONE
    assert ("click", 5, 5, "left", 1) in fake.events
    assert len(approvals) == 1


def test_secret_refused_by_guard():
    script = [Step(actions=[Action(type=ActionType.TYPE, text="password: abc")])]
    agent, fake = build_agent(script)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.REFUSED
    assert fake.events == []


def test_model_safety_require_confirmation():
    action = Action(type=ActionType.CLICK, x=1, y=1)
    script = [
        Step(actions=[action],
             safety=[SafetyFlag(SafetyDecision.REQUIRE_CONFIRMATION, "risky", 0)]),
        Step(done=True),
    ]
    seen = []
    agent, fake = build_agent(script, confirm_cb=lambda *a: seen.append(a) or True)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.DONE
    assert len(seen) == 1


def test_model_safety_block_refuses():
    script = [
        Step(actions=[Action(type=ActionType.CLICK, x=1, y=1)],
             safety=[SafetyFlag(SafetyDecision.BLOCK, "no", 0)]),
    ]
    agent, fake = build_agent(script)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.REFUSED


def test_max_steps_cap():
    # Distinct actions + a varying screen so stuck-detection doesn't fire first.
    script = [Step(actions=[Action(type=ActionType.TYPE, text=str(i))]) for i in range(200)]
    cfg = Config(max_steps=5)
    agent, fake = build_agent(
        script, config=cfg,
        screen=FakeScreen(ScreenGeometry(1920, 1080), vary=True))
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.MAX_STEPS
    assert out.steps == 5


def test_cost_cap():
    script = [Step(actions=[Action(type=ActionType.KEY, keys="a")]) for _ in range(50)]
    cfg = Config(max_cost_per_run=0.0001)
    agent, fake = build_agent(script, config=cfg)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.MAX_COST


def test_kill_switch_stops():
    kill = FlagKillSwitch()
    script = [Step(actions=[Action(type=ActionType.KEY, keys="a")]) for _ in range(50)]
    agent, fake = build_agent(script, kill_switch=kill)
    # Abort immediately: the loop checks the switch before executing.
    kill.abort()
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.KILLED


def test_capture_blocked_stops_without_confirm():
    screen = FakeScreen(ScreenGeometry(1920, 1080), foreground="Barclays Online")
    pol = CapturePolicy(blocklist=("barclays",))
    script = [Step(done=True)]
    agent, fake = build_agent(script, screen=screen, capture_policy=pol,
                              confirm_cb=None)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.CAPTURE_BLOCKED


def test_stuck_detection_recovers_then_stops():
    # FakeScreen always returns the identical image -> hashes match -> stuck.
    script = [Step(actions=[Action(type=ActionType.KEY, keys="a")]) for _ in range(20)]
    agent, fake = build_agent(script)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.STUCK


def test_logger_writes_summary(tmp_path):
    from operator_app.logging_run import RunLogger
    script = [Step(actions=[Action(type=ActionType.TYPE, text="x")]), Step(done=True)]
    logger = RunLogger(tmp_path, task="t")
    agent, fake = build_agent(script, logger=logger)
    out = agent.run(task="t", system_instruction="s")
    assert out.reason is StopReason.DONE
    assert (logger.dir / "summary.md").exists()
    assert (logger.dir / "steps.jsonl").exists()
