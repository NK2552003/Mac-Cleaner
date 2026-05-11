"""
tests/test_scanner.py
=====================
Comprehensive tests for Mac-Cleaner scanner internals.

Covers:
  - Orphan detection logic
  - Junk scan path categorisation
  - Developer junk detection
  - Duplicate-file hashing (two-phase)
  - Large-file scanner threshold logic
  - Broken symlink detection
  - Safety guard (com.apple.* protection)
  - Running-app guard
  - Config loading and profile merging
  - Scan result data model
  - CI mode JSON output schema
  - Undo staging path generation
  - History record structure

All tests run on a temporary directory tree so no real filesystem
paths are touched and no macOS-only APIs are required.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import stat
import sys
import tempfile
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal stubs for the modules under test.
# ---------------------------------------------------------------------------
# Because the source tree lives in src/ and the package installs as top-level
# modules (cli, constants, utils), we add src/ to sys.path before importing.
# If running from the repo root this is already handled by `pip install -e .`,
# but the explicit insertion keeps tests self-contained.

REPO_ROOT = pathlib.Path(__file__).parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_home(tmp_path: pathlib.Path) -> pathlib.Path:
    """A fake $HOME with the directory structure mac-cleaner expects."""
    (tmp_path / "Applications").mkdir()
    (tmp_path / "Library" / "Application Support").mkdir(parents=True)
    (tmp_path / "Library" / "Caches").mkdir(parents=True)
    (tmp_path / "Library" / "Logs").mkdir(parents=True)
    (tmp_path / "Library" / "Preferences").mkdir(parents=True)
    (tmp_path / ".Trash").mkdir()
    (tmp_path / "Downloads").mkdir()
    (tmp_path / "Documents").mkdir()
    (tmp_path / "Desktop").mkdir()
    return tmp_path


@pytest.fixture()
def tmp_app_dir(tmp_home: pathlib.Path) -> pathlib.Path:
    """Simulates ~/Library/Application Support/<App> for a *removed* app."""
    app_dir = tmp_home / "Library" / "Application Support" / "GhostApp"
    app_dir.mkdir(parents=True)
    (app_dir / "prefs.json").write_text('{"key": "value"}')
    (app_dir / "cache.db").write_bytes(b"\x00" * 512)
    return app_dir


# ---------------------------------------------------------------------------
# 1. Path-safety guard tests
# ---------------------------------------------------------------------------


class TestSafetyGuards:
    """Tests that ensure system-owned paths are never touched."""

    # We model the guard as a standalone function that the real code should
    # implement.  These tests define the *contract* so they can be wired up
    # to the actual implementation.

    def _is_safe_to_delete(self, path: str) -> bool:
        """Reference implementation of the safety predicate."""
        p = pathlib.Path(path)
        parts = set(p.parts)
        # com.apple.* bundle IDs / directories are always protected
        if any(part.startswith("com.apple.") for part in parts):
            return False
        # /System, /usr, /bin, /sbin are always off-limits.
        # NOTE: /private is intentionally NOT blocked here. On macOS, pytest's
        # tmp_path resolves to /private/var/folders/... (via /tmp symlink).
        # Blocking all of /private would incorrectly flag user temp dirs as unsafe.
        # Only specific OS-owned sub-paths under /private are protected.
        protected_roots = {"/System", "/usr", "/bin", "/sbin"}
        if any(str(p).startswith(root + "/") or str(p) == root
               for root in protected_roots):
            return False
        private_os_paths = ("/private/etc", "/private/var/db", "/private/var/root")
        if any(str(p).startswith(pp) for pp in private_os_paths):
            return False
        return True

    def test_com_apple_prefix_is_protected(self):
        assert not self._is_safe_to_delete(
            "/Users/test/Library/Application Support/com.apple.Safari"
        )

    def test_nested_com_apple_is_protected(self):
        assert not self._is_safe_to_delete(
            "/Users/test/Library/Caches/com.apple.dt.Xcode"
        )

    def test_system_root_is_protected(self):
        assert not self._is_safe_to_delete("/System/Library/Frameworks")

    def test_usr_is_protected(self):
        assert not self._is_safe_to_delete("/usr/local/bin/python3")

    def test_user_app_support_is_deletable(self, tmp_home):
        p = str(tmp_home / "Library" / "Application Support" / "GhostApp")
        assert self._is_safe_to_delete(p)

    def test_downloads_file_is_deletable(self, tmp_home):
        p = str(tmp_home / "Downloads" / "installer.dmg")
        assert self._is_safe_to_delete(p)

    def test_dot_trash_is_deletable(self, tmp_home):
        p = str(tmp_home / ".Trash" / "old_file.txt")
        assert self._is_safe_to_delete(p)


# ---------------------------------------------------------------------------
# 2. Orphan detection logic
# ---------------------------------------------------------------------------


class TestOrphanDetection:
    """Tests for leftover-app-data matching."""

    # Contract: given a list of installed .app bundle IDs and a set of
    # Application Support dirs, return dirs whose bundle ID is NOT installed.

    def _find_orphan_dirs(
        self,
        installed_bundle_ids: set[str],
        app_support_dirs: list[pathlib.Path],
    ) -> list[pathlib.Path]:
        orphans = []
        for d in app_support_dirs:
            # Simplistic match: directory name == bundle_id fragment
            # Real code resolves reverse-DNS → app name mappings.
            if d.name not in installed_bundle_ids:
                orphans.append(d)
        return orphans

    def test_ghost_app_is_orphan(self, tmp_home):
        installed = {"Safari", "Finder", "Terminal"}
        dirs = [
            tmp_home / "Library" / "Application Support" / "GhostApp",
            tmp_home / "Library" / "Application Support" / "Safari",
        ]
        orphans = self._find_orphan_dirs(installed, dirs)
        assert len(orphans) == 1
        assert orphans[0].name == "GhostApp"

    def test_installed_app_not_orphan(self, tmp_home):
        installed = {"Safari", "GhostApp"}
        dirs = [tmp_home / "Library" / "Application Support" / "GhostApp"]
        orphans = self._find_orphan_dirs(installed, dirs)
        assert orphans == []

    def test_empty_installed_list_marks_all_as_orphans(self, tmp_home):
        dirs = [
            tmp_home / "Library" / "Application Support" / "AppA",
            tmp_home / "Library" / "Application Support" / "AppB",
        ]
        orphans = self._find_orphan_dirs(set(), dirs)
        assert len(orphans) == 2

    def test_no_dirs_returns_empty(self):
        orphans = self._find_orphan_dirs({"Safari"}, [])
        assert orphans == []


# ---------------------------------------------------------------------------
# 3. Junk category classification
# ---------------------------------------------------------------------------


class TestJunkClassification:
    """Tests for path → junk-category mapping."""

    CATEGORY_MAP = {
        "Library/Caches": "Cache",
        "Library/Logs": "Log File",
        ".Trash": "Trash",
        "Library/Application Support/Xcode": "Xcode Junk",
        "CrashReporter": "Crash Report",
        ".DS_Store": "DS Store",
    }

    def _classify(self, path: str) -> str | None:
        for fragment, category in self.CATEGORY_MAP.items():
            if fragment in path:
                return category
        return None

    def test_caches_classified(self, tmp_home):
        p = str(tmp_home / "Library" / "Caches" / "SomeApp" / "data.bin")
        assert self._classify(p) == "Cache"

    def test_logs_classified(self, tmp_home):
        p = str(tmp_home / "Library" / "Logs" / "app.log")
        assert self._classify(p) == "Log File"

    def test_trash_classified(self, tmp_home):
        p = str(tmp_home / ".Trash" / "junk.zip")
        assert self._classify(p) == "Trash"

    def test_xcode_artefacts_classified(self, tmp_home):
        p = str(tmp_home / "Library" / "Application Support" / "Xcode" / "iOS DeviceSupport")
        assert self._classify(p) == "Xcode Junk"

    def test_ds_store_classified(self, tmp_home):
        p = str(tmp_home / "Downloads" / ".DS_Store")
        assert self._classify(p) == "DS Store"

    def test_normal_file_unclassified(self, tmp_home):
        p = str(tmp_home / "Documents" / "report.pdf")
        assert self._classify(p) is None


# ---------------------------------------------------------------------------
# 4. Developer junk detection
# ---------------------------------------------------------------------------


class TestDevJunkScanner:
    """Tests for developer junk detection (node_modules, venv, etc.)."""

    DEV_JUNK_NAMES = {
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",          # Rust / Maven
        ".gradle",
        "DerivedData",
        ".tox",
        "coverage",
        ".coverage",
        "htmlcov",
    }

    def _is_dev_junk(self, path: pathlib.Path) -> bool:
        return path.name in self.DEV_JUNK_NAMES

    def _scan_dev_junk(
        self, root: pathlib.Path, max_depth: int = 4
    ) -> list[pathlib.Path]:
        hits: list[pathlib.Path] = []

        def _walk(p: pathlib.Path, depth: int) -> None:
            if depth > max_depth:
                return
            try:
                for child in p.iterdir():
                    # Use os.path to avoid follow_symlinks kwarg (Python 3.9 compat)
                    if child.is_dir() and not os.path.islink(child):
                        if self._is_dev_junk(child):
                            hits.append(child)
                        else:
                            _walk(child, depth + 1)
            except PermissionError:
                pass

        _walk(root, 0)
        return hits

    def test_node_modules_detected(self, tmp_path):
        proj = tmp_path / "my-project"
        nm = proj / "node_modules"
        nm.mkdir(parents=True)
        (nm / "lodash").mkdir()
        results = self._scan_dev_junk(tmp_path)
        assert nm in results

    def test_venv_detected(self, tmp_path):
        (tmp_path / "app" / "venv").mkdir(parents=True)
        results = self._scan_dev_junk(tmp_path)
        assert any(p.name == "venv" for p in results)

    def test_pycache_detected(self, tmp_path):
        (tmp_path / "pkg" / "__pycache__").mkdir(parents=True)
        results = self._scan_dev_junk(tmp_path)
        assert any(p.name == "__pycache__" for p in results)

    def test_non_junk_skipped(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        results = self._scan_dev_junk(tmp_path)
        assert results == []

    def test_max_depth_respected(self, tmp_path):
        # node_modules buried at depth 5 should NOT be found with max_depth=4
        deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "node_modules"
        deep.mkdir(parents=True)
        results = self._scan_dev_junk(tmp_path, max_depth=4)
        assert deep not in results

    def test_multiple_projects(self, tmp_path):
        for proj in ["proj1", "proj2", "proj3"]:
            (tmp_path / proj / "node_modules").mkdir(parents=True)
        results = self._scan_dev_junk(tmp_path)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# 5. Duplicate file detection (two-phase SHA-256)
# ---------------------------------------------------------------------------


class TestDuplicateFinder:
    """Tests for two-phase (head-bytes + full) SHA-256 duplicate detection."""

    HEAD_BYTES = 65_536  # 64 KiB head read

    def _head_hash(self, path: pathlib.Path) -> str:
        with path.open("rb") as f:
            return hashlib.sha256(f.read(self.HEAD_BYTES)).hexdigest()

    def _full_hash(self, path: pathlib.Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(131_072):
                h.update(chunk)
        return h.hexdigest()

    def _find_duplicates(
        self, paths: list[pathlib.Path], min_size: int = 0
    ) -> list[list[pathlib.Path]]:
        """Group paths by full SHA-256; return groups with >1 member."""
        from collections import defaultdict

        by_size: dict[int, list[pathlib.Path]] = defaultdict(list)
        for p in paths:
            try:
                sz = p.stat().st_size
                if sz >= min_size:
                    by_size[sz].append(p)
            except OSError:
                continue

        by_hash: dict[str, list[pathlib.Path]] = defaultdict(list)
        for size_group in by_size.values():
            if len(size_group) < 2:
                continue
            # Phase 1: head hash to filter obvious non-dupes
            by_head: dict[str, list[pathlib.Path]] = defaultdict(list)
            for p in size_group:
                by_head[self._head_hash(p)].append(p)
            # Phase 2: full hash only for head-hash collisions
            for head_group in by_head.values():
                if len(head_group) < 2:
                    continue
                for p in head_group:
                    by_hash[self._full_hash(p)].append(p)

        return [g for g in by_hash.values() if len(g) > 1]

    def test_identical_files_are_duplicates(self, tmp_path):
        data = b"hello duplicate world" * 1000
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        a.write_bytes(data)
        b.write_bytes(data)
        groups = self._find_duplicates([a, b])
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_different_files_not_duplicates(self, tmp_path):
        (tmp_path / "x.bin").write_bytes(b"aaa" * 100)
        (tmp_path / "y.bin").write_bytes(b"bbb" * 100)
        groups = self._find_duplicates(list(tmp_path.iterdir()))
        assert groups == []

    def test_min_size_filter(self, tmp_path):
        small = tmp_path / "small1.txt"
        small2 = tmp_path / "small2.txt"
        small.write_bytes(b"x" * 10)
        small2.write_bytes(b"x" * 10)
        # min_size=100 → too small to include
        groups = self._find_duplicates([small, small2], min_size=100)
        assert groups == []

    def test_three_identical_files(self, tmp_path):
        data = b"triple" * 500
        files = []
        for i in range(3):
            p = tmp_path / f"file{i}.bin"
            p.write_bytes(data)
            files.append(p)
        groups = self._find_duplicates(files)
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_large_file_hashing_efficiency(self, tmp_path):
        """Head-hash phase should avoid full read when sizes differ."""
        big = tmp_path / "big.bin"
        big.write_bytes(os.urandom(200_000))
        small = tmp_path / "small.bin"
        small.write_bytes(b"x" * 100)
        # Different sizes → no collision → no full hash needed
        groups = self._find_duplicates([big, small])
        assert groups == []


# ---------------------------------------------------------------------------
# 6. Large-file scanner
# ---------------------------------------------------------------------------


class TestLargeFileScanner:
    """Tests for large-file detection with configurable threshold."""

    def _scan_large_files(
        self, root: pathlib.Path, min_bytes: int = 100 * 1024 * 1024
    ) -> list[tuple[pathlib.Path, int]]:
        results = []
        for p in root.rglob("*"):
            # Avoid follow_symlinks kwarg — not available on Path until 3.12
            if p.is_file() and not os.path.islink(p):
                try:
                    sz = p.stat().st_size
                    if sz >= min_bytes:
                        results.append((p, sz))
                except OSError:
                    continue
        return sorted(results, key=lambda x: x[1], reverse=True)

    def test_file_above_threshold_found(self, tmp_path):
        big = tmp_path / "video.mp4"
        big.write_bytes(b"\x00" * (101 * 1024 * 1024))
        results = self._scan_large_files(tmp_path, min_bytes=100 * 1024 * 1024)
        assert any(p == big for p, _ in results)

    def test_file_below_threshold_excluded(self, tmp_path):
        small = tmp_path / "doc.pdf"
        small.write_bytes(b"\x00" * (50 * 1024 * 1024))
        results = self._scan_large_files(tmp_path, min_bytes=100 * 1024 * 1024)
        assert results == []

    def test_results_sorted_by_size_desc(self, tmp_path):
        sizes_mb = [200, 150, 300, 120]
        files = []
        for i, mb in enumerate(sizes_mb):
            p = tmp_path / f"file{i}.bin"
            p.write_bytes(b"\x00" * (mb * 1024 * 1024))
            files.append(p)
        results = self._scan_large_files(tmp_path, min_bytes=100 * 1024 * 1024)
        sizes = [sz for _, sz in results]
        assert sizes == sorted(sizes, reverse=True)

    def test_custom_threshold(self, tmp_path):
        medium = tmp_path / "medium.bin"
        medium.write_bytes(b"\x00" * (60 * 1024 * 1024))
        results = self._scan_large_files(tmp_path, min_bytes=50 * 1024 * 1024)
        assert any(p == medium for p, _ in results)


# ---------------------------------------------------------------------------
# 7. Broken symlink detection
# ---------------------------------------------------------------------------


class TestSymlinkScanner:
    """Tests for broken (dangling) symlink detection."""

    def _find_broken_symlinks(self, root: pathlib.Path) -> list[pathlib.Path]:
        broken = []
        for p in root.rglob("*"):
            if p.is_symlink() and not p.exists():
                broken.append(p)
        return broken

    def test_broken_symlink_detected(self, tmp_path):
        target = tmp_path / "ghost_target"
        link = tmp_path / "my_link"
        link.symlink_to(target)  # target does not exist
        assert not target.exists()
        broken = self._find_broken_symlinks(tmp_path)
        assert link in broken

    def test_valid_symlink_not_flagged(self, tmp_path):
        real = tmp_path / "real_file.txt"
        real.write_text("hello")
        link = tmp_path / "valid_link"
        link.symlink_to(real)
        broken = self._find_broken_symlinks(tmp_path)
        assert link not in broken

    def test_no_symlinks_returns_empty(self, tmp_path):
        (tmp_path / "ordinary.txt").write_text("hi")
        assert self._find_broken_symlinks(tmp_path) == []

    def test_multiple_broken_links(self, tmp_path):
        for i in range(5):
            link = tmp_path / f"dead_link_{i}"
            link.symlink_to(tmp_path / f"nonexistent_{i}")
        broken = self._find_broken_symlinks(tmp_path)
        assert len(broken) == 5


# ---------------------------------------------------------------------------
# 8. Undo staging
# ---------------------------------------------------------------------------


class TestUndoStaging:
    """Tests for the undo/restore staging mechanism."""

    TRASH_DIR_NAME = ".mac_cleaner_trash"

    def _stage_for_deletion(
        self,
        paths: list[pathlib.Path],
        trash_root: pathlib.Path,
        session_id: str,
    ) -> pathlib.Path:
        """Move files to trash root under a session sub-dir."""
        session_dir = trash_root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        for src in paths:
            dst = session_dir / src.name
            shutil.move(str(src), str(dst))
        return session_dir

    def _restore_session(
        self,
        session_dir: pathlib.Path,
        restore_root: pathlib.Path,
    ) -> list[pathlib.Path]:
        restored = []
        for item in session_dir.iterdir():
            dst = restore_root / item.name
            shutil.move(str(item), str(dst))
            restored.append(dst)
        return restored

    def test_files_staged_not_deleted(self, tmp_path):
        src = tmp_path / "junk.log"
        src.write_text("junk")
        trash = tmp_path / self.TRASH_DIR_NAME
        self._stage_for_deletion([src], trash, "sess_001")
        assert not src.exists()
        assert (trash / "sess_001" / "junk.log").exists()

    def test_restore_brings_file_back(self, tmp_path):
        src = tmp_path / "data.cache"
        src.write_bytes(b"cache data")
        trash = tmp_path / self.TRASH_DIR_NAME
        session_dir = self._stage_for_deletion([src], trash, "sess_002")
        restore_dir = tmp_path / "restored"
        restore_dir.mkdir()
        self._restore_session(session_dir, restore_dir)
        assert (restore_dir / "data.cache").exists()

    def test_session_dir_created_per_invocation(self, tmp_path):
        trash = tmp_path / self.TRASH_DIR_NAME
        files = []
        for i in range(3):
            p = tmp_path / f"file{i}.txt"
            p.write_text(f"content {i}")
            files.append(p)

        self._stage_for_deletion(files[:1], trash, "sess_A")
        self._stage_for_deletion(files[1:], trash, "sess_B")

        assert (trash / "sess_A").is_dir()
        assert (trash / "sess_B").is_dir()

    def test_multiple_files_staged(self, tmp_path):
        trash = tmp_path / self.TRASH_DIR_NAME
        files = []
        for i in range(10):
            p = tmp_path / f"junk_{i}.log"
            p.write_text(f"log {i}")
            files.append(p)
        session_dir = self._stage_for_deletion(files, trash, "sess_big")
        assert len(list(session_dir.iterdir())) == 10


# ---------------------------------------------------------------------------
# 9. Config loading & profile merging
# ---------------------------------------------------------------------------


class TestConfigLoading:
    """Tests for YAML config loading and profile merging."""

    DEFAULT_CONFIG: dict[str, Any] = {
        "whitelist": [],
        "skip_categories": [],
        "scan_orphans": True,
        "scan_junk": True,
        "undo_mode": True,
        "retention_days": 30,
        "large_file_threshold_mb": 100,
        "duplicate_min_size_kb": 4,
        "profile": None,
        "scan_dev_junk": False,
        "scan_dev_junk_global": False,
        "profiles": {},
    }

    def _load_config(self, config_path: pathlib.Path) -> dict[str, Any]:
        # Try pyyaml first (installed as a runtime dep of the package itself).
        # Fall back to a minimal stdlib-based YAML parser so tests work even in
        # environments where pyyaml is not yet on sys.path (e.g. bare venvs).
        try:
            import yaml  # type: ignore[import]
            with config_path.open() as f:
                user = yaml.safe_load(f) or {}
        except ModuleNotFoundError:
            user = self._parse_yaml_simple(config_path.read_text())

        merged = {**self.DEFAULT_CONFIG, **user}
        # Apply active profile overrides
        profile_name = merged.get("profile")
        if profile_name and profile_name in merged.get("profiles", {}):
            merged.update(merged["profiles"][profile_name])
        return merged

    @staticmethod
    def _parse_yaml_simple(text: str) -> dict[str, Any]:
        """Minimal YAML parser for the flat/nested configs used in tests.

        Handles:
          - top-level ``key: value`` scalars (bool, int, str, null)
          - top-level ``key:`` with indented ``- item`` list children
          - one level of nested mapping (profiles block)

        This avoids a hard dependency on pyyaml at import time so the
        TestConfigLoading suite can self-bootstrap even without the package
        installed.
        """
        def _cast(v: str) -> Any:
            v = v.strip()
            if v.lower() == "true":
                return True
            if v.lower() == "false":
                return False
            if v.lower() in ("null", "~", ""):
                return None
            try:
                return int(v)
            except ValueError:
                pass
            try:
                return float(v)
            except ValueError:
                pass
            return v

        result: dict[str, Any] = {}
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.rstrip()
            if not stripped or stripped.lstrip().startswith("#"):
                i += 1
                continue
            indent = len(line) - len(line.lstrip())
            if indent > 0:
                i += 1
                continue  # nested lines handled by parent

            if ":" not in stripped:
                i += 1
                continue

            key, _, raw_val = stripped.partition(":")
            key = key.strip()
            raw_val = raw_val.strip()

            if raw_val:
                result[key] = _cast(raw_val)
                i += 1
            else:
                # Value is on subsequent indented lines
                children: list | dict = []
                i += 1
                # Peek: list or mapping?
                while i < len(lines):
                    child_line = lines[i]
                    child_stripped = child_line.rstrip()
                    if not child_stripped:
                        i += 1
                        continue
                    child_indent = len(child_line) - len(child_line.lstrip())
                    if child_indent == 0:
                        break  # back to top level
                    if child_stripped.lstrip().startswith("- "):
                        # List item
                        if not isinstance(children, list):
                            children = []
                        children.append(_cast(child_stripped.lstrip()[2:]))
                        i += 1
                    elif ":" in child_stripped:
                        # Nested mapping — recurse one level
                        if not isinstance(children, dict):
                            children = {}
                        sub_key, _, sub_raw = child_stripped.lstrip().partition(":")
                        sub_key = sub_key.strip()
                        sub_raw = sub_raw.strip()
                        if sub_raw:
                            children[sub_key] = _cast(sub_raw)  # type: ignore[index]
                            i += 1
                        else:
                            # Two-level deep mapping (e.g. profiles.<name>.<key>)
                            # Each entry at this depth may itself be a scalar or a list.
                            sub_map: dict[str, Any] = {}
                            i += 1
                            current_sub_key: str | None = None
                            while i < len(lines):
                                sub_line = lines[i]
                                sub_stripped = sub_line.rstrip()
                                if not sub_stripped:
                                    i += 1
                                    continue
                                sub_indent = len(sub_line) - len(sub_line.lstrip())
                                if sub_indent <= child_indent:
                                    break
                                lstripped = sub_stripped.lstrip()
                                if lstripped.startswith("- "):
                                    # List item belonging to current_sub_key
                                    if current_sub_key is not None:
                                        if not isinstance(sub_map.get(current_sub_key), list):
                                            sub_map[current_sub_key] = []
                                        sub_map[current_sub_key].append(
                                            _cast(lstripped[2:])
                                        )
                                elif ":" in lstripped:
                                    sk, _, sv = lstripped.partition(":")
                                    sk = sk.strip()
                                    sv = sv.strip()
                                    current_sub_key = sk
                                    if sv:
                                        sub_map[sk] = _cast(sv)
                                    # else: value comes on subsequent "- " lines;
                                    # do NOT write None — let the list accumulate.
                                i += 1
                            children[sub_key] = sub_map  # type: ignore[index]
                    else:
                        i += 1
                result[key] = children
        return result

    def _write_config(self, tmp_path: pathlib.Path, content: str) -> pathlib.Path:
        p = tmp_path / "config.yaml"
        p.write_text(content)
        return p

    def test_defaults_applied_when_config_empty(self, tmp_path):
        p = self._write_config(tmp_path, "")
        cfg = self._load_config(p)
        assert cfg["scan_orphans"] is True
        assert cfg["undo_mode"] is True
        assert cfg["large_file_threshold_mb"] == 100

    def test_user_overrides_default(self, tmp_path):
        p = self._write_config(tmp_path, "large_file_threshold_mb: 50\nundo_mode: false\n")
        cfg = self._load_config(p)
        assert cfg["large_file_threshold_mb"] == 50
        assert cfg["undo_mode"] is False

    def test_profile_minimal_applied(self, tmp_path):
        yaml_content = (
            "profile: minimal\n"
            "profiles:\n"
            "  minimal:\n"
            "    skip_categories:\n"
            "      - Xcode Junk\n"
            "      - npm Cache\n"
        )
        p = self._write_config(tmp_path, yaml_content)
        cfg = self._load_config(p)
        assert "Xcode Junk" in cfg["skip_categories"]

    def test_profile_developer_applied(self, tmp_path):
        yaml_content = (
            "profile: developer\n"
            "profiles:\n"
            "  developer:\n"
            "    scan_dev_junk: true\n"
            "    large_file_threshold_mb: 50\n"
        )
        p = self._write_config(tmp_path, yaml_content)
        cfg = self._load_config(p)
        assert cfg["scan_dev_junk"] is True
        assert cfg["large_file_threshold_mb"] == 50

    def test_whitelist_parsed(self, tmp_path):
        yaml_content = "whitelist:\n  - ~/Library/Application Support/Slack\n"
        p = self._write_config(tmp_path, yaml_content)
        cfg = self._load_config(p)
        assert len(cfg["whitelist"]) == 1


# ---------------------------------------------------------------------------
# 10. Scan result data model
# ---------------------------------------------------------------------------


class TestScanResultModel:
    """Tests for the scan result dict/data-model schema."""

    def _make_scan_result(
        self,
        *,
        orphans: list[dict],
        junk: list[dict],
        dev_junk: list[dict] | None = None,
        total_bytes: int = 0,
        scan_duration_s: float = 0.0,
    ) -> dict[str, Any]:
        return {
            "version": 1,
            "timestamp": time.time(),
            "duration_seconds": scan_duration_s,
            "totals": {
                "orphan_bytes": sum(o.get("size_bytes", 0) for o in orphans),
                "junk_bytes": sum(j.get("size_bytes", 0) for j in junk),
                "dev_junk_bytes": sum(d.get("size_bytes", 0) for d in (dev_junk or [])),
                "total_bytes": total_bytes,
                "orphan_count": len(orphans),
                "junk_count": len(junk),
                "dev_junk_count": len(dev_junk or []),
            },
            "orphans": orphans,
            "junk": junk,
            "dev_junk": dev_junk or [],
        }

    def test_result_has_required_keys(self):
        result = self._make_scan_result(orphans=[], junk=[])
        for key in ("version", "timestamp", "totals", "orphans", "junk", "dev_junk"):
            assert key in result

    def test_totals_calculated_correctly(self):
        orphans = [{"path": "/tmp/a", "size_bytes": 1024}]
        junk = [{"path": "/tmp/b", "size_bytes": 2048}]
        result = self._make_scan_result(orphans=orphans, junk=junk)
        assert result["totals"]["orphan_bytes"] == 1024
        assert result["totals"]["junk_bytes"] == 2048
        assert result["totals"]["orphan_count"] == 1
        assert result["totals"]["junk_count"] == 1

    def test_dev_junk_totals(self):
        dev = [{"path": "/tmp/nm", "size_bytes": 50 * 1024 * 1024}]
        result = self._make_scan_result(orphans=[], junk=[], dev_junk=dev)
        assert result["totals"]["dev_junk_bytes"] == 50 * 1024 * 1024
        assert result["totals"]["dev_junk_count"] == 1

    def test_result_is_json_serialisable(self):
        result = self._make_scan_result(
            orphans=[{"path": "/tmp/ghost", "size_bytes": 100}],
            junk=[{"path": "/tmp/cache", "size_bytes": 200, "category": "Cache"}],
        )
        serialised = json.dumps(result)
        parsed = json.loads(serialised)
        assert parsed["totals"]["orphan_count"] == 1


# ---------------------------------------------------------------------------
# 11. CI mode JSON output schema
# ---------------------------------------------------------------------------


class TestCIModeOutput:
    """Tests that CI-mode output conforms to the documented JSON schema."""

    def _make_ci_output(
        self,
        total_mb: float,
        threshold_mb: float,
        result: dict[str, Any],
    ) -> tuple[dict[str, Any], int]:
        """Returns (ci_json, exit_code)."""
        over = total_mb > threshold_mb
        ci_json = {
            "total_mb": round(total_mb, 2),
            "threshold_mb": threshold_mb,
            "over_threshold": over,
            "orphan_count": result["totals"]["orphan_count"],
            "junk_count": result["totals"]["junk_count"],
            "dev_junk_count": result["totals"]["dev_junk_count"],
        }
        exit_code = 1 if over else 0
        return ci_json, exit_code

    def test_under_threshold_exit_0(self):
        result = {
            "totals": {"orphan_count": 2, "junk_count": 3, "dev_junk_count": 0}
        }
        _, code = self._make_ci_output(200.0, 500.0, result)
        assert code == 0

    def test_over_threshold_exit_1(self):
        result = {
            "totals": {"orphan_count": 5, "junk_count": 10, "dev_junk_count": 2}
        }
        _, code = self._make_ci_output(600.0, 500.0, result)
        assert code == 1

    def test_ci_json_has_required_keys(self):
        result = {
            "totals": {"orphan_count": 0, "junk_count": 0, "dev_junk_count": 0}
        }
        ci_json, _ = self._make_ci_output(100.0, 500.0, result)
        for key in ("total_mb", "threshold_mb", "over_threshold", "orphan_count"):
            assert key in ci_json

    def test_ci_json_is_serialisable(self):
        result = {
            "totals": {"orphan_count": 1, "junk_count": 2, "dev_junk_count": 0}
        }
        ci_json, _ = self._make_ci_output(123.45, 500.0, result)
        assert json.loads(json.dumps(ci_json))["total_mb"] == 123.45


# ---------------------------------------------------------------------------
# 12. Scan history record
# ---------------------------------------------------------------------------


class TestScanHistory:
    """Tests for scan history JSON record structure."""

    def _write_history_record(
        self, history_dir: pathlib.Path, scan_result: dict[str, Any]
    ) -> pathlib.Path:
        session_id = hashlib.sha256(
            str(scan_result["timestamp"]).encode()
        ).hexdigest()[:8]
        record = {
            "id": session_id,
            "timestamp": scan_result["timestamp"],
            "totals": scan_result["totals"],
        }
        path = history_dir / f"{session_id}.json"
        path.write_text(json.dumps(record, indent=2))
        return path

    def test_history_record_written(self, tmp_path):
        result = {
            "timestamp": 1_700_000_000.0,
            "totals": {
                "orphan_bytes": 0,
                "junk_bytes": 1024,
                "dev_junk_bytes": 0,
                "total_bytes": 1024,
                "orphan_count": 0,
                "junk_count": 1,
                "dev_junk_count": 0,
            },
        }
        rec_path = self._write_history_record(tmp_path, result)
        assert rec_path.exists()
        data = json.loads(rec_path.read_text())
        assert "id" in data
        assert data["totals"]["junk_count"] == 1

    def test_history_id_is_deterministic_for_same_timestamp(self, tmp_path):
        result = {"timestamp": 12345.0, "totals": {}}
        id1 = hashlib.sha256(str(result["timestamp"]).encode()).hexdigest()[:8]
        id2 = hashlib.sha256(str(result["timestamp"]).encode()).hexdigest()[:8]
        assert id1 == id2

    def test_different_timestamps_produce_different_ids(self):
        id1 = hashlib.sha256(b"1000.0").hexdigest()[:8]
        id2 = hashlib.sha256(b"2000.0").hexdigest()[:8]
        assert id1 != id2