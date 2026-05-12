
"""Core data models for scan results and metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Set

from utils import size_of


# ── Filler tokens to ignore during matching ───────────────────────────────────
_FILLER_TOKENS: Set[str] = {
    "com", "org", "net", "io", "app", "inc", "ltd",
    "co", "de", "uk", "us", "eu", "me", "tv", "ai",
    "mac", "macos", "desktop", "helper",
}


@dataclass
class AppInfo:
    """Represents a single installed application.

    Attributes:
        name: Display name of the app.
        bundle_id: App bundle identifier.
        path: Filesystem path to the app bundle.
    """
    name: str
    bundle_id: str
    path: Path
    tokens: Set[str] = field(init=False, repr=False)
    name_lower: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.bundle_id = self.bundle_id.lower()
        self.name_lower = self.name.lower()

        parts = self.bundle_id.split(".")
        self.tokens: Set[str] = set()

        # Add bundle ID and prefixes
        self.tokens.add(self.bundle_id)
        if len(parts) >= 2:
            self.tokens.add(".".join(parts[:2]))
        if len(parts) >= 3:
            self.tokens.add(".".join(parts[:3]))

        # Add meaningful tokens from bundle ID
        for p in parts:
            if p and p not in _FILLER_TOKENS and len(p) >= 3:
                self.tokens.add(p)

        # Add meaningful words from display name
        for word in re.split(r"[\s\-_]+", self.name_lower):
            if len(word) >= 3 and word not in _FILLER_TOKENS:
                self.tokens.add(word)

    def __repr__(self) -> str:
        return f"<App {self.name!r} ({self.bundle_id})>"


@dataclass
class OrphanEntry:
    """A leftover file or directory from an uninstalled app.

    Attributes:
        path: Filesystem path to the orphaned item.
        app_name: Display name of the app, if known.
        reason: Reason category for the orphan entry.
        size: Size in bytes.
        category: Normalized category label.
        bundle_id: Associated bundle identifier, if available.
        vendor: Vendor name, if known.
    """
    path: Path
    app_name: str = ""
    reason: str = "Other"  # e.g. "App Support", "Cache", "Container"
    size: int = 0
    category: str = ""
    bundle_id: str = ""
    vendor: str = "Unknown"

    def __post_init__(self) -> None:
        if self.category and self.reason == "Other":
            self.reason = self.category
        if not self.category:
            self.category = self.reason
        if not self.app_name:
            self.app_name = self.path.stem
        if self.size <= 0:
            self.size = size_of(self.path)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the entry to a JSON-serializable dictionary."""
        return {
            "path": str(self.path),
            "app_name": self.app_name,
            "reason": self.reason,
            "category": self.category,
            "bundle_id": self.bundle_id,
            "vendor": self.vendor,
            "size": self.size,
        }


@dataclass
class JunkEntry:
    """A general junk file or directory.

    Attributes:
        path: Filesystem path to the junk item.
        category: Category label (e.g., "User Cache").
        is_system: Whether the item is system-owned (never auto-delete).
        size: Size in bytes.
        bundle_id: Associated bundle identifier, if available.
    """
    path: Path
    category: str = "Other"       # e.g. "User Cache", "Log File", "Trash"
    is_system: bool = False  # If True, never auto-delete
    size: int = 0
    bundle_id: str = ""

    def __post_init__(self) -> None:
        if self.size <= 0:
            self.size = size_of(self.path)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the entry to a JSON-serializable dictionary."""
        return {
            "path": str(self.path),
            "category": self.category,
            "is_system": self.is_system,
            "bundle_id": self.bundle_id,
            "size": self.size,
        }


@dataclass
class DevJunkEntry:
    """Developer junk directory (build output, venv, node_modules, etc.).

    Attributes:
        path: Filesystem path to the dev junk directory.
        category: Category label.
        size: Size in bytes.
    """
    path: Path
    category: str = "Other"
    size: int = 0

    def __post_init__(self) -> None:
        if self.size <= 0:
            self.size = size_of(self.path)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the entry to a JSON-serializable dictionary."""
        return {
            "path": str(self.path),
            "category": self.category,
            "size": self.size,
        }
