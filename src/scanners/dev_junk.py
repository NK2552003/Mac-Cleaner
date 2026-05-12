"""
Finds language-specific build output and dependency directories
(e.g., node_modules, venv, target, bin/obj) inside project folders.

This scanner is opt-in and conservative: it only reports items
when nearby project marker files are detected.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

from constants import DEFAULT_DEV_JUNK_ROOTS, DEV_JUNK_MARKER_DEPTH, DEV_JUNK_SKIP_DIRS
from config.models import DevJunkEntry
from utils import iterdir_safe, size_of

logger = logging.getLogger(__name__)

HOME = Path.home()


@dataclass(frozen=True)
class DevJunkRule:
    category: str
    names: Set[str]
    markers: Set[str]


_NODE_MARKERS: Set[str] = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "pnpm-workspace.yaml", "lerna.json", "nx.json", "turbo.json",
    "bun.lockb", "bun.lock",
}

_PY_MARKERS: Set[str] = {
    "pyproject.toml", "requirements.txt", "setup.py", "setup.cfg",
    "Pipfile", "Pipfile.lock", "poetry.lock",
}

_JAVA_MARKERS: Set[str] = {
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
}

_GO_MARKERS: Set[str] = {"go.mod", "go.sum"}

_RUST_MARKERS: Set[str] = {"Cargo.toml", "Cargo.lock"}

_DOTNET_MARKERS: Set[str] = {"*.sln", "*.csproj", "*.fsproj"}

_RUBY_MARKERS: Set[str] = {"Gemfile", "Gemfile.lock"}

_PHP_MARKERS: Set[str] = {"composer.json", "composer.lock"}

_GENERIC_MARKERS: Set[str] = (
    _NODE_MARKERS
    | _PY_MARKERS
    | _JAVA_MARKERS
    | _GO_MARKERS
    | _RUST_MARKERS
    | _DOTNET_MARKERS
    | _RUBY_MARKERS
    | _PHP_MARKERS
)


_RULES: List[DevJunkRule] = [
    DevJunkRule("Node Modules", {"node_modules"}, _NODE_MARKERS),
    DevJunkRule("JS Build Cache", {".next", ".nuxt", ".svelte-kit", ".astro", ".parcel-cache", ".turbo", ".nx"}, _NODE_MARKERS),
    DevJunkRule("Python Venv", {".venv", "venv", "env", ".env", "virtualenv"}, _PY_MARKERS),
    DevJunkRule("Python Cache", {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", ".hypothesis"}, _PY_MARKERS),
    DevJunkRule("Rust Target", {"target"}, _RUST_MARKERS),
    DevJunkRule("Go Build", {"bin", "pkg"}, _GO_MARKERS),
    DevJunkRule("Java Build", {"target", ".gradle", "build"}, _JAVA_MARKERS),
    DevJunkRule("Dotnet Build", {"bin", "obj"}, _DOTNET_MARKERS),
    DevJunkRule("PHP Vendor", {"vendor"}, _PHP_MARKERS),
    DevJunkRule("Ruby Bundle", {"vendor"}, _RUBY_MARKERS),
    DevJunkRule("Build Output", {"dist", "out", "release", "debug"}, _GENERIC_MARKERS),
    DevJunkRule("Coverage", {"coverage", ".coverage", ".nyc_output"}, _GENERIC_MARKERS),
]

_GLOBAL_CACHE_DIRS: List[Tuple[str, Path]] = [
    ("Global Cache (Node)", HOME / ".npm"),
    ("Global Cache (Node)", HOME / ".yarn"),
    ("Global Cache (Node)", HOME / ".pnpm-store"),
    ("Global Cache (Node)", HOME / ".pnpm"),
    ("Global Cache (Node)", HOME / ".node-gyp"),
    ("Global Cache (Python)", HOME / ".cache" / "pip"),
    ("Global Cache (Python)", HOME / ".cache" / "pypoetry"),
    ("Global Cache (Python)", HOME / ".cache" / "uv"),
    ("Global Cache (Python)", HOME / ".virtualenvs"),
    ("Global Cache (Java)", HOME / ".gradle" / "caches"),
    ("Global Cache (Java)", HOME / ".m2" / "repository"),
    ("Global Cache (Java)", HOME / ".ivy2" / "cache"),
    ("Global Cache (Java)", HOME / ".sbt"),
    ("Global Cache (Go)", HOME / "go" / "pkg" / "mod"),
    ("Global Cache (Rust)", HOME / ".cargo" / "registry"),
    ("Global Cache (Rust)", HOME / ".cargo" / "git"),
    ("Global Cache (Dotnet)", HOME / ".nuget" / "packages"),
    ("Global Cache (Ruby)", HOME / ".bundle" / "cache"),
    ("Global Cache (PHP)", HOME / ".composer" / "cache"),
]


def _resolve_roots(roots: Optional[Iterable[Path]]) -> List[Path]:
    resolved: List[Path] = []
    seen: Set[Path] = set()
    for root in roots or DEFAULT_DEV_JUNK_ROOTS:
        try:
            r = root.expanduser().resolve()
        except OSError as exc:
            logger.debug("Failed to resolve dev junk root %s: %s", root, exc)
            r = root.expanduser()
        if r not in seen and r.exists():
            seen.add(r)
            resolved.append(r)
    if not resolved and roots is None:
        fallback = HOME.expanduser()
        if fallback.exists():
            resolved.append(fallback)
    return resolved


def _has_marker(start: Path, markers: Set[str]) -> bool:
    if not markers:
        return False
    for marker in markers:
        if "*" in marker:
            if any(start.glob(marker)):
                return True
        else:
            if (start / marker).exists():
                return True
    return False


def _markers_nearby(start: Path, markers: Set[str]) -> bool:
    current = start
    for _ in range(DEV_JUNK_MARKER_DEPTH):
        if _has_marker(current, markers):
            return True
        if current.parent == current:
            break
        current = current.parent
    return False


def _match_rule(path: Path) -> Optional[DevJunkRule]:
    name = path.name.lower()
    for rule in _RULES:
        if name in rule.names:
            if _markers_nearby(path.parent, rule.markers):
                return rule
    return None


def _global_cache_entries(seen: Set[Path]) -> List[DevJunkEntry]:
    entries: List[DevJunkEntry] = []
    for category, path in _GLOBAL_CACHE_DIRS:
        if not path.exists() or path in seen:
            continue
        sz = size_of(path)
        if sz > 0:
            entries.append(DevJunkEntry(path=path, category=category, size=sz))
            seen.add(path)
    return entries


def find_dev_junk(
    roots: Optional[Iterable[Path]] = None,
    max_depth: int = 6,
    limit: Optional[int] = None,
    include_global: bool = False,
) -> List[DevJunkEntry]:
    """Return dev junk directories found under the given roots."""
    entries: List[DevJunkEntry] = []
    seen: Set[Path] = set()

    queue = deque((r, 0) for r in _resolve_roots(roots))
    while queue:
        current, depth = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        if depth > max_depth:
            continue

        for child in iterdir_safe(current):
            if child.name in DEV_JUNK_SKIP_DIRS:
                continue
            if child.is_symlink():
                continue
            if child.is_dir():
                rule = _match_rule(child)
                if rule:
                    sz = size_of(child)
                    if sz > 0:
                        entries.append(DevJunkEntry(path=child, category=rule.category, size=sz))
                        if limit and len(entries) >= limit:
                            return sorted(entries, key=lambda e: e.size, reverse=True)
                    continue
                if depth < max_depth:
                    queue.append((child, depth + 1))

    entries.sort(key=lambda e: e.size, reverse=True)

    if include_global:
        entries.extend(_global_cache_entries(seen))
        entries.sort(key=lambda e: e.size, reverse=True)
    return entries
