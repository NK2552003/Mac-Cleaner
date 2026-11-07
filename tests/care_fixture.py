"""Isolated browser fixture. No host cleanup, launchd, or external translation calls."""

import contextlib
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mac_deep_cleaner import review_tools
from mac_deep_cleaner.history import History
from mac_deep_cleaner.scanner import Scanner
from mac_deep_cleaner.server import LocalServer
from mac_deep_cleaner.service import CleanerService

with (
    tempfile.TemporaryDirectory(prefix="mdc-care-ui-") as directory,
    contextlib.ExitStack() as stack,
):
    root = Path(directory).resolve()
    stack.enter_context(patch.object(Path, "home", return_value=root))
    for target, value in [
        ("mac_deep_cleaner.cleanup.HOME", str(root)),
        ("mac_deep_cleaner.feature_config.CONFIG", root / "config.json"),
        ("mac_deep_cleaner.settings.SETTINGS_DIR", str(root / "settings")),
        ("mac_deep_cleaner.settings.SETTINGS_FILE", str(root / "settings/settings.json")),
    ]:
        stack.enter_context(patch(target, value))
    service = CleanerService(
        SimpleNamespace(view="care"),
        {"mode": "normal", "min_mb": 0, "pinned": [], "ghost_allowlist": []},
    )
    service.scanner = Scanner(quiet=True)
    service.scanner.done = True
    service.scanner.progress = "Complete"
    service.scan_id = "care-fixture"
    for index, name in enumerate(
        [
            "Design archive.zip",
            "Video project.mov",
            "Installer.dmg",
            "Build cache",
            "Vacation photo.jpg",
            "Old render.mp4",
        ]
    ):
        path = root / name
        path.write_text("fixture")
        size = (6 - index) * 400_000_000
        service.scanner.add(
            name=name,
            path=str(path),
            size=size,
            category="App Caches" if index == 3 else "Large & Old Files",
            safety="safe" if index == 3 else "caution",
        )
        service.scanner.walk_files.append(
            (str(path), size, size, time.time() - 200 * 86400, 0, index, 1)
        )
    removed = root / "Restorable cache"
    removed.write_text("restore fixture")
    History(root).move(str(removed))
    history = History(root)
    with history.connect() as db:
        for i in range(8):
            db.execute(
                "INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?)",
                (
                    int(time.time() // 3600) - 24 * i,
                    time.time() - 86400 * i,
                    500_000_000_000,
                    (260 + i * 8) * 1_000_000_000,
                    (240 - i * 8) * 1_000_000_000,
                ),
            )
    stack.enter_context(
        patch.object(
            review_tools,
            "startup_items",
            return_value=[
                {
                    "path": str(root / "Library/LaunchAgents/example.plist"),
                    "label": "org.example.sync",
                    "program": "/Applications/Example Sync.app",
                    "explanation": "starts when loaded at login; launchd keeps it running",
                    "editable": True,
                    "identity": (1, 2, 3, 4, 5),
                }
            ],
        )
    )
    stack.enter_context(
        patch.object(
            review_tools,
            "browser_extensions",
            return_value=[
                {
                    "name": "Chrome",
                    "installed": True,
                    "notice": "Manage extensions in the browser.",
                    "extensions": [
                        {"name": "Example extension", "version": "1.0", "profile": "Default"}
                    ],
                }
            ],
        )
    )
    stack.enter_context(
        patch.object(
            review_tools,
            "slimming_inventory",
            return_value=[
                {
                    "name": "Example.app",
                    "path": "/Applications/Example.app",
                    "size": 900_000_000,
                    "identity": (1, 2, 3, 4, 5),
                    "languages": [{"name": "en", "bytes": 1000}, {"name": "fr", "bytes": 1000}],
                }
            ],
        )
    )
    service.care().media = {
        "checked": 2,
        "pairs": [
            {
                "left": str(root / "Vacation photo.jpg"),
                "right": str(root / "Video project.mov"),
                "score": 94,
                "kind": "image",
                "reason": "Perceptual dHash similarity",
                "review_only": True,
            }
        ],
        "notice": "Review originals before removing anything.",
        "partial": False,
        "video_available": False,
        "errors": [],
    }
    if '--workspace' in sys.argv:
        from workspace_fixture import configure
        configure(service, root, stack)
    server = LocalServer(service)
    artifacts = Path("/tmp/mdc-care-check")
    artifacts.mkdir(exist_ok=True)
    (artifacts / "launch-url").write_text(server.url)
    print("Care fixture ready", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        service.close()
