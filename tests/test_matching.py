from pathlib import Path

from config.models import AppInfo
from scanners.matching import match_to_app


def _apps():
    app = AppInfo(
        name="Visual Studio Code",
        bundle_id="com.microsoft.vscode",
        path=Path("/Applications/Visual Studio Code.app"),
    )
    return {app.bundle_id: app}


def test_match_alias() -> None:
    apps = _apps()
    match = match_to_app("Code", apps)
    assert match is not None
    assert match.bundle_id == "com.microsoft.vscode"


def test_match_saved_state() -> None:
    apps = _apps()
    match = match_to_app("com.microsoft.vscode.savedState", apps)
    assert match is not None
    assert match.bundle_id == "com.microsoft.vscode"


def test_alias_without_app_is_orphan() -> None:
    match = match_to_app("Code", {})
    assert match is None
