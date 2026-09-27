"""Windows input backend using pyautogui, with a pydirectinput fallback.

Some apps (games, certain secured windows) ignore synthetic pyautogui input;
``use_directinput`` routes mouse/keyboard through pydirectinput instead. Imported
lazily so the cloud path never pulls in GUI-input libraries.
"""

from __future__ import annotations

# Maps our chord strings (e.g. "ctrl+s") onto library key names. pyautogui and
# pydirectinput share the same names for the keys we use.
_KEY_ALIASES = {
    "win": "winleft",
    "windows": "winleft",
    "cmd": "winleft",
    "esc": "escape",
    "return": "enter",
    "del": "delete",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "control": "ctrl",
}


def _normalise_keys(keys: str) -> list[str]:
    out = []
    for part in keys.replace(" ", "").lower().split("+"):
        if not part:
            continue
        out.append(_KEY_ALIASES.get(part, part))
    return out


class WindowsInput:
    """Concrete :class:`~operator.executor.InputBackend` for Windows."""

    def __init__(self, *, use_directinput: bool = False, failsafe: bool = True) -> None:
        import pyautogui  # noqa: PLC0415

        pyautogui.FAILSAFE = failsafe   # mouse to top-left corner aborts
        pyautogui.PAUSE = 0             # we manage our own settle delay
        self._pg = pyautogui
        self._di = None
        if use_directinput:
            import pydirectinput  # noqa: PLC0415

            pydirectinput.FAILSAFE = failsafe
            self._di = pydirectinput

    @property
    def _mouse(self):
        return self._di or self._pg

    def move(self, x: int, y: int) -> None:
        self._mouse.moveTo(x, y)

    def click(self, x: int, y: int, button: str = "left", count: int = 1) -> None:
        self._mouse.click(x=x, y=y, clicks=count, button=button)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self._mouse.moveTo(x1, y1)
        self._mouse.dragTo(x2, y2, button="left")

    def type_text(self, text: str) -> None:
        # pydirectinput cannot type arbitrary unicode; text always goes via pyautogui.
        self._pg.write(text, interval=0.01)

    def key(self, keys: str) -> None:
        combo = _normalise_keys(keys)
        if not combo:
            return
        if len(combo) == 1:
            self._mouse.press(combo[0])
            self._mouse.release(combo[0])
        else:
            self._mouse.hotkey(*combo)

    def scroll(self, dx: int, dy: int) -> None:
        if dy:
            self._pg.scroll(-dy)   # pyautogui: positive scrolls up
        if dx:
            self._pg.hscroll(dx)


def make_windows_input(*, use_directinput: bool = False, failsafe: bool = True) -> WindowsInput:
    return WindowsInput(use_directinput=use_directinput, failsafe=failsafe)
