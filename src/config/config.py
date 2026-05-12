"""
Mac Deep Cleaner v1.5.0 — Configuration Manager
=============================================
Reads and writes a YAML config file at ~/.config/mac-cleaner/config.yaml.

Config schema (all keys optional)
----------------------------------
whitelist:
  - ~/Library/Application Support/Slack
  - ~/Library/Caches/MyApp

skip_categories:
  - "System Cache"
  - "Log File"

dev_junk_roots:
    - ~/Projects
    - ~/Code

scan_dev_junk: false
scan_dev_junk_global: false
dev_junk_max_depth: 6

custom_scan_roots:
  - ~/Projects/tools
  - /opt/company

profile: developer     # name of an active profile (merged on top of base config)

profiles:
  minimal:
    skip_categories: ["Xcode Junk", "npm Cache", "Cargo Cache"]
  developer:
    custom_scan_roots: [~/Projects]
    skip_categories: []

undo_mode: true        # stage deletions in ~/.mac_cleaner_trash instead of permanent delete
retention_days: 30     # how long staged files are kept
large_file_threshold_mb: 100
duplicate_min_size_kb: 4
notify_after_scan: false

Usage
-----
    from mac_cleaner.config import load_config, Config

    cfg = load_config()               # reads file or returns defaults
    cfg = load_config(profile="developer")
    cfg.save()                        # writes back to disk
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

try:
    import yaml
    _YAML_OK = True
except ImportError:
    _YAML_OK = False

# ── Paths ──────────────────────────────────────────────────────────────────────

_CONFIG_DIR = Path.home() / ".config" / "mac-cleaner"
_CONFIG_FILE = _CONFIG_DIR / "config.yaml"

# ── Built-in profiles ─────────────────────────────────────────────────────────

_BUILTIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "beginner": {
        "skip_categories": [
            "Xcode Junk", "npm Cache", "Yarn Cache", "pnpm Cache",
            "Gradle Cache", "Maven Cache", "Cargo Cache", "Go Build Cache",
            "CocoaPods Cache", "pip Cache",
        ],
        "scan_dev_junk": False,
    },
    "minimal": {
        "skip_categories": [
            "Xcode Junk", "npm Cache", "Yarn Cache", "pnpm Cache",
            "Gradle Cache", "Maven Cache", "Cargo Cache", "Go Build Cache",
            "CocoaPods Cache", "pip Cache",
        ],
    },
    "developer": {
        "skip_categories": [],       # scan everything
        "custom_scan_roots": [],
        "large_file_threshold_mb": 50,
        "duplicate_min_size_kb": 4,
        "scan_dev_junk": True,
    },
    "professional": {
        "skip_categories": [],
        "large_file_threshold_mb": 50,
        "duplicate_min_size_kb": 4,
        "scan_dev_junk": True,
    },
    "designer": {
        "skip_categories": [],
        "large_file_threshold_mb": 80,
        "duplicate_min_size_kb": 8,
        "scan_dev_junk": False,
    },
    "student": {
        "skip_categories": [
            "Xcode Junk", "npm Cache", "Yarn Cache", "pnpm Cache",
            "Gradle Cache", "Maven Cache", "Cargo Cache", "Go Build Cache",
            "CocoaPods Cache", "pip Cache",
        ],
        "scan_dev_junk": False,
    },
    "children": {
        "skip_categories": [
            "Xcode Junk", "npm Cache", "Yarn Cache", "pnpm Cache",
            "Gradle Cache", "Maven Cache", "Cargo Cache", "Go Build Cache",
            "CocoaPods Cache", "pip Cache",
        ],
        "scan_dev_junk": False,
    },
    "aggressive": {
        "skip_categories": [],
        "large_file_threshold_mb": 25,
        "duplicate_min_size_kb": 1,
        "undo_mode": False,
        "scan_dev_junk": True,
    },
}


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class Config:
    """Resolved configuration, ready for use by the CLI."""

    # Paths
    whitelist: List[Path] = field(default_factory=list)
    custom_scan_roots: List[Path] = field(default_factory=list)

    # Category filtering
    skip_categories: Set[str] = field(default_factory=set)

    # Behaviour
    scan_orphans: bool = True
    scan_junk: bool = True
    scan_dev_junk: bool = False
    scan_dev_junk_global: bool = False
    undo_mode: bool = True
    retention_days: int = 30
    notify_after_scan: bool = False
    profile: Optional[str] = None

    # Dev junk scan
    dev_junk_roots: List[Path] = field(default_factory=list)
    dev_junk_max_depth: int = 6

    # Thresholds
    large_file_threshold_mb: int = 100
    duplicate_min_size_kb: int = 4

    # Raw profile data (for round-trip saving)
    _raw_profiles: Dict[str, Any] = field(
        default_factory=lambda: copy.deepcopy(_BUILTIN_PROFILES),
        repr=False,
    )

    # ── Derived properties ─────────────────────────────────────────────────

    @property
    def large_file_threshold_bytes(self) -> int:
        return self.large_file_threshold_mb * 1024 * 1024

    @property
    def duplicate_min_size_bytes(self) -> int:
        return self.duplicate_min_size_kb * 1024

    @property
    def whitelist_set(self) -> Set[Path]:
        return set(self.whitelist)

    # ── Persistence ────────────────────────────────────────────────────────

    def save(self) -> None:
        """Write the current config to disk as YAML."""
        if not _YAML_OK:
            raise RuntimeError("pyyaml is required to save config. pip install pyyaml")

        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        data: Dict[str, Any] = {
            "whitelist": [str(p) for p in self.whitelist],
            "skip_categories": sorted(self.skip_categories),
            "custom_scan_roots": [str(p) for p in self.custom_scan_roots],
            "scan_orphans": self.scan_orphans,
            "scan_junk": self.scan_junk,
            "scan_dev_junk": self.scan_dev_junk,
            "scan_dev_junk_global": self.scan_dev_junk_global,
            "undo_mode": self.undo_mode,
            "retention_days": self.retention_days,
            "notify_after_scan": self.notify_after_scan,
            "large_file_threshold_mb": self.large_file_threshold_mb,
            "duplicate_min_size_kb": self.duplicate_min_size_kb,
            "dev_junk_roots": [str(p) for p in self.dev_junk_roots],
            "dev_junk_max_depth": self.dev_junk_max_depth,
            "profiles": self._raw_profiles,
        }
        if self.profile:
            data["profile"] = self.profile

        with open(_CONFIG_FILE, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "whitelist": [str(p) for p in self.whitelist],
            "skip_categories": sorted(self.skip_categories),
            "custom_scan_roots": [str(p) for p in self.custom_scan_roots],
            "scan_orphans": self.scan_orphans,
            "scan_junk": self.scan_junk,
            "scan_dev_junk": self.scan_dev_junk,
            "scan_dev_junk_global": self.scan_dev_junk_global,
            "undo_mode": self.undo_mode,
            "retention_days": self.retention_days,
            "large_file_threshold_mb": self.large_file_threshold_mb,
            "duplicate_min_size_kb": self.duplicate_min_size_kb,
            "dev_junk_roots": [str(p) for p in self.dev_junk_roots],
            "dev_junk_max_depth": self.dev_junk_max_depth,
            "profile": self.profile,
        }


# ── Loader ─────────────────────────────────────────────────────────────────────

def _expand(paths: List[Any]) -> List[Path]:
    """Expand a list of path strings into Path objects."""
    result = []
    for p in paths:
        try:
            result.append(Path(str(p)).expanduser().resolve())
        except (TypeError, ValueError) as exc:
            logger.debug("Invalid config path entry: %s", exc)
    return result


def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow merge: override keys win."""
    merged = copy.copy(base)
    merged.update(override)
    return merged


def load_config(
    path: Optional[Path] = None,
    profile: Optional[str] = None,
) -> Config:
    """
    Load configuration from disk (YAML) and apply profile overrides.

    Args:
        path:    Path to the config file. Defaults to ~/.config/mac-cleaner/config.yaml.
        profile: Profile name to activate (overrides file's 'profile' key).

    Returns:
        Config object with all settings resolved.
    """
    config_path = path or _CONFIG_FILE
    raw: Dict[str, Any] = {}

    if config_path.exists() and _YAML_OK:
        try:
            with open(config_path) as f:
                loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict):
                raw = loaded
        except Exception as exc:
            logger.debug("Failed to load config %s: %s", config_path, exc)

    # Resolve active profile
    active_profile = profile or raw.get("profile")
    all_profiles: Dict[str, Any] = copy.deepcopy(_BUILTIN_PROFILES)
    file_profiles = raw.get("profiles", {})
    if isinstance(file_profiles, dict):
        for k, v in file_profiles.items():
            if isinstance(v, dict):
                all_profiles[k] = v

    profile_data: Dict[str, Any] = {}
    if active_profile and active_profile in all_profiles:
        profile_data = all_profiles[active_profile]

    # Merge: defaults ← file config ← profile overrides
    effective = _merge(raw, profile_data)

    # Build Config object
    cfg = Config(
        whitelist=_expand(effective.get("whitelist", [])),
        custom_scan_roots=_expand(effective.get("custom_scan_roots", [])),
        skip_categories=set(effective.get("skip_categories", [])),
        scan_orphans=bool(effective.get("scan_orphans", True)),
        scan_junk=bool(effective.get("scan_junk", True)),
        scan_dev_junk=bool(effective.get("scan_dev_junk", False)),
        scan_dev_junk_global=bool(effective.get("scan_dev_junk_global", False)),
        undo_mode=bool(effective.get("undo_mode", True)),
        retention_days=int(effective.get("retention_days", 30)),
        notify_after_scan=bool(effective.get("notify_after_scan", False)),
        large_file_threshold_mb=int(effective.get("large_file_threshold_mb", 100)),
        duplicate_min_size_kb=int(effective.get("duplicate_min_size_kb", 4)),
        profile=active_profile,
        dev_junk_roots=_expand(effective.get("dev_junk_roots", [])),
        dev_junk_max_depth=int(effective.get("dev_junk_max_depth", 6)),
    )
    cfg._raw_profiles = all_profiles
    return cfg


def default_config() -> Config:
    """Return a Config with all default values (no file required)."""
    return Config()


def config_file_path() -> Path:
    """Return the expected config file path."""
    return _CONFIG_FILE


def ensure_config_dir() -> Path:
    """Create the config directory and return its path."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return _CONFIG_DIR


def init_default_config(profile: Optional[str] = None) -> Config:
    """
    Write a default config file if none exists, then load and return it.
    """
    if not _CONFIG_FILE.exists():
        cfg = default_config()
        if profile:
            cfg.profile = profile
        cfg.save()
    return load_config(profile=profile)
