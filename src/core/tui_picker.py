"""Interactive TUI app picker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import click

from config.models import AppInfo


@dataclass
class PickerResult:
    """Result of an app picker."""
    selected: Optional[AppInfo]
    filter_text: str


def pick_app(apps: List[AppInfo], prompt: str = "Select an app") -> PickerResult:
    """Pick an app from the list using a TUI or fallback prompt."""
    if not apps:
        return PickerResult(selected=None, filter_text="")

    try:
        import curses
    except Exception:
        return _pick_simple(apps, prompt)

    try:
        selected = curses.wrapper(lambda stdscr: _pick_curses(stdscr, apps, prompt))
        return PickerResult(selected=selected, filter_text="")
    except Exception:
        return _pick_simple(apps, prompt)


def _pick_simple(apps: List[AppInfo], prompt: str) -> PickerResult:
    click.echo("\n" + prompt)
    sorted_apps = sorted(apps, key=lambda a: a.name.lower())
    for i, app in enumerate(sorted_apps, 1):
        click.echo(f"  {i:>3}  {app.name}  ({app.bundle_id})")
    choice = click.prompt("App number", type=click.IntRange(1, len(sorted_apps)))
    return PickerResult(selected=sorted_apps[choice - 1], filter_text="")


def _pick_curses(stdscr, apps: List[AppInfo], prompt: str) -> Optional[AppInfo]:
    import curses

    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)

    filter_text = ""
    index = 0

    def filtered() -> List[AppInfo]:
        if not filter_text:
            return apps
        needle = filter_text.lower()
        return [a for a in apps if needle in a.name.lower() or needle in a.bundle_id.lower()]

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        header = f"{prompt}  (type to filter, ENTER to select, q to quit)"
        stdscr.addnstr(0, 0, header, width - 1)
        stdscr.addnstr(1, 0, f"Filter: {filter_text}", width - 1)

        items = filtered()
        if not items:
            stdscr.addnstr(3, 0, "No matches", width - 1)
        else:
            index = max(0, min(index, len(items) - 1))
            start = max(0, index - (height - 6))
            view = items[start:start + height - 5]
            for i, app in enumerate(view):
                row = 3 + i
                prefix = ">" if (start + i) == index else " "
                label = f"{prefix} {app.name}  ({app.bundle_id})"
                stdscr.addnstr(row, 0, label, width - 1)

        stdscr.refresh()
        ch = stdscr.getch()
        if ch in (ord("q"), 27):
            return None
        if ch in (curses.KEY_UP, ord("k")):
            index = max(0, index - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            index = min(len(filtered()) - 1, index + 1)
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            filter_text = filter_text[:-1]
            index = 0
        elif ch in (curses.KEY_ENTER, 10, 13):
            items = filtered()
            if items:
                return items[index]
        elif 32 <= ch <= 126:
            filter_text += chr(ch)
            index = 0


