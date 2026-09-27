"""PySide6 GUI: a small always-on-top control window.

This module imports PySide6, which is only installed via the ``desktop`` extra, so
it is imported lazily by ``__main__`` and never by the test suite. The agent runs
on a worker thread; confirmations are marshalled back to the UI thread through Qt
signals and a blocking event, so the loop pauses until the user answers.

Untested in the cloud phase (no display / no PySide6). See HANDOFF.md.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: PLC0415 (module-level ok here)

from operator_app.agent import Agent, RunOutcome
from operator_app.guard import GuardDecision
from operator_app.types import Action


@dataclass
class _ConfirmExchange:
    action: Action
    decision: GuardDecision
    screenshot_png: bytes
    event: threading.Event
    result: bool = False


class _Worker(QtCore.QObject):
    progress = QtCore.Signal(str)
    confirm = QtCore.Signal(object)      # _ConfirmExchange
    finished = QtCore.Signal(object)     # RunOutcome

    def __init__(self, agent: Agent, task: str, system_instruction: str) -> None:
        super().__init__()
        self._agent = agent
        self._task = task
        self._sys = system_instruction

    def confirm_cb(self, action: Action, decision: GuardDecision, png: bytes) -> bool:
        ex = _ConfirmExchange(action, decision, png, threading.Event())
        self.confirm.emit(ex)
        ex.event.wait()          # block the worker thread until the UI answers
        return ex.result

    @QtCore.Slot()
    def run(self) -> None:
        self._agent.confirm_cb = self.confirm_cb
        self._agent.progress_cb = lambda step: self.progress.emit(
            (step.text or "").strip() + "".join(
                f"\n  → {a.summary()}" for a in step.actions)
        )
        outcome = self._agent.run(task=self._task, system_instruction=self._sys)
        self.finished.emit(outcome)


class OperatorWindow(QtWidgets.QWidget):
    """The main control window."""

    def __init__(self, *, agent_factory, playbooks, model_label: str) -> None:
        super().__init__()
        self._agent_factory = agent_factory     # (task, system_instruction, dry_run, confirm) -> Agent
        self._playbooks = {p.name: p for p in playbooks}
        self._thread: QtCore.QThread | None = None
        self._worker: _Worker | None = None

        self.setWindowTitle("Operator")
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        self.resize(460, 560)
        self._build_ui(model_label)

    def _build_ui(self, model_label: str) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        self.sharing = QtWidgets.QLabel("● Screen is NOT being shared")
        self.sharing.setStyleSheet("color: #2e7d32; font-weight: bold;")
        layout.addWidget(self.sharing)

        layout.addWidget(QtWidgets.QLabel(f"Model: {model_label}"))

        layout.addWidget(QtWidgets.QLabel("Playbook:"))
        self.playbook_box = QtWidgets.QComboBox()
        self.playbook_box.addItem("(free task)")
        for name in self._playbooks:
            self.playbook_box.addItem(name)
        self.playbook_box.currentTextChanged.connect(self._on_playbook)
        layout.addWidget(self.playbook_box)

        layout.addWidget(QtWidgets.QLabel("Task:"))
        self.task_box = QtWidgets.QPlainTextEdit()
        self.task_box.setPlaceholderText("Describe the task, or pick a playbook above.")
        self.task_box.setMaximumHeight(90)
        layout.addWidget(self.task_box)

        self.inputs_form = QtWidgets.QFormLayout()
        self.inputs_container = QtWidgets.QWidget()
        self.inputs_container.setLayout(self.inputs_form)
        layout.addWidget(self.inputs_container)
        self._input_fields: dict[str, QtWidgets.QLineEdit] = {}

        self.dry_run = QtWidgets.QCheckBox("Dry-run (propose actions, execute nothing)")
        self.dry_run.setChecked(True)
        layout.addWidget(self.dry_run)

        buttons = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Run")
        self.run_btn.clicked.connect(self._start_run)
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_run)
        buttons.addWidget(self.run_btn)
        buttons.addWidget(self.stop_btn)
        layout.addLayout(buttons)

        self.cost_label = QtWidgets.QLabel("Cost: -")
        layout.addWidget(self.cost_label)

        layout.addWidget(QtWidgets.QLabel("Log:"))
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, stretch=1)

        note = QtWidgets.QLabel(
            "Kill switch: Ctrl+Alt+Q. Automating LinkedIn breaches its terms.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(note)

    # --------------------------------------------------------------- playbook

    def _on_playbook(self, name: str) -> None:
        for i in reversed(range(self.inputs_form.count())):
            self.inputs_form.itemAt(i).widget().deleteLater()
        self._input_fields.clear()
        pb = self._playbooks.get(name)
        if not pb:
            return
        self.task_box.setPlainText(pb.description)
        for key, default in pb.inputs.items():
            edit = QtWidgets.QLineEdit(default)
            self.inputs_form.addRow(key, edit)
            self._input_fields[key] = edit

    # ------------------------------------------------------------------- run

    def _start_run(self) -> None:
        name = self.playbook_box.currentText()
        pb = self._playbooks.get(name)
        values = {k: e.text() for k, e in self._input_fields.items()}
        if pb:
            missing = pb.missing_inputs(values)
            if missing:
                QtWidgets.QMessageBox.warning(
                    self, "Missing inputs", f"Fill in: {', '.join(missing)}")
                return
            system_instruction = pb.render(values)
            task = pb.description
        else:
            system_instruction = "Follow the task exactly. When unsure, stop and ask."
            task = self.task_box.toPlainText().strip()
        if not task:
            QtWidgets.QMessageBox.warning(self, "No task", "Enter a task or pick a playbook.")
            return

        agent = self._agent_factory(task, system_instruction, self.dry_run.isChecked())
        self._thread = QtCore.QThread()
        self._worker = _Worker(agent, task, system_instruction)
        self._worker.moveToThread(self._thread)
        self._worker.progress.connect(self._on_progress)
        self._worker.confirm.connect(self._on_confirm)
        self._worker.finished.connect(self._on_finished)
        self._thread.started.connect(self._worker.run)

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_sharing(not self.dry_run.isChecked())
        self.log.clear()
        self._thread.start()

    def _stop_run(self) -> None:
        if self._worker and getattr(self._worker._agent, "kill_switch", None):
            self._worker._agent.kill_switch.abort()
        self.stop_btn.setEnabled(False)

    @QtCore.Slot(str)
    def _on_progress(self, text: str) -> None:
        if text.strip():
            self.log.appendPlainText(text)

    @QtCore.Slot(object)
    def _on_confirm(self, ex: _ConfirmExchange) -> None:
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Confirm action")
        msg.setText(ex.decision.reason or "Confirm this action?")
        msg.setInformativeText(ex.action.summary())
        if ex.screenshot_png:
            pix = QtGui.QPixmap()
            pix.loadFromData(ex.screenshot_png)
            if not pix.isNull():
                msg.setIconPixmap(pix.scaledToWidth(360, QtCore.Qt.SmoothTransformation))
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msg.setDefaultButton(QtWidgets.QMessageBox.No)
        ex.result = msg.exec() == QtWidgets.QMessageBox.Yes
        ex.event.set()

    @QtCore.Slot(object)
    def _on_finished(self, outcome: RunOutcome) -> None:
        self.log.appendPlainText(
            f"\n== {outcome.reason.value.upper()} == {outcome.message}\n"
            f"steps={outcome.steps} cost={outcome.cost_total:0.4f} "
            f"model={outcome.model_used}")
        self.cost_label.setText(f"Cost: {outcome.cost_total:0.4f}")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_sharing(False)
        if self._thread:
            self._thread.quit()
            self._thread.wait()

    def _set_sharing(self, active: bool) -> None:
        if active:
            self.sharing.setText("● SCREEN IS BEING SHARED WITH THE MODEL")
            self.sharing.setStyleSheet("color: #c62828; font-weight: bold;")
        else:
            self.sharing.setText("● Screen is NOT being shared")
            self.sharing.setStyleSheet("color: #2e7d32; font-weight: bold;")
