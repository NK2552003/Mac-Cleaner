"""
Mac Deep Cleaner v1.0.0 — App Matching Engine
==========================================
Determines whether a directory/file belongs to an installed app.
Uses multi-strategy matching: alias table, bundle ID prefix/suffix,
and token overlap analysis.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Set

from constants import APP_DIR_ALIASES
from config.models import AppInfo
from utils import stem_of


def match_to_app(
    candidate: str,
    apps: Dict[str, AppInfo],
    running_bids: Optional[Set[str]] = None,
) -> Optional[AppInfo]:
    """
    Determine whether `candidate` belongs to any installed app.

    Returns:
        AppInfo if matched (the item is NOT an orphan)
        None if no match (the item IS potentially an orphan)

    Matching strategy (in order of priority):
      1. Alias table lookup — handles non-standard dir names ("Code" → VS Code)
      2. Exact bundle ID match
      3. Bundle ID prefix/suffix matching
      4. Token overlap analysis — ≥2 tokens OR 1 token of ≥4 chars
      5. App name substring matching
    """
    c = candidate.lower().strip()

    # ── 1. Alias table ───────────────────────────────────────────────────────
    if c in APP_DIR_ALIASES:
        target_bid = APP_DIR_ALIASES[c].lower()
        for bid, app in apps.items():
            if bid == target_bid or bid.startswith(target_bid + ".") or bid.startswith(target_bid):
                return app
        # Known alias but app not installed → it IS an orphan of that app.
        # Return None but don't continue matching (prevents false positives).
        return None

    # ── 2. Exact bundle ID ───────────────────────────────────────────────────
    if c in apps:
        return apps[c]

    # ── 3. Bundle ID prefix/suffix matching ──────────────────────────────────
    for bid, app in apps.items():
        if c == bid:
            return app
        # candidate is a prefix of the bundle ID
        if bid.startswith(c + "."):
            return app
        # bundle ID is a prefix of the candidate
        if c.startswith(bid + "."):
            return app
        # Saved state pattern: com.foo.bar.savedState
        if c.endswith(".savedstate"):
            base = c.replace(".savedstate", "")
            if base == bid or bid.startswith(base + ".") or base.startswith(bid + "."):
                return app

    # ── 4. Token overlap analysis ────────────────────────────────────────────
    c_tokens = {t for t in re.split(r"[.\-_\s]+", c) if len(t) >= 3}
    if c_tokens:
        for bid, app in apps.items():
            overlap = c_tokens & app.tokens
            if not overlap:
                continue
            strong = any(len(t) >= 4 for t in overlap)
            multi = len(overlap) >= 2
            if strong or multi:
                return app

    # ── 5. App name substring matching ───────────────────────────────────────
    # Only for longer candidates (≥5 chars) to avoid false positives
    if len(c) >= 5:
        for bid, app in apps.items():
            # Check if the candidate appears in the app name
            if c in app.name_lower and len(c) >= 5:
                return app
            # Check if the app name appears in the candidate
            if app.name_lower in c and len(app.name_lower) >= 5:
                return app

    return None


def resolve_candidate_name(candidate: str) -> Optional[str]:
    """
    If a candidate matches an alias, return the canonical app name
    even if the app isn't installed. Used for display purposes.
    """
    c = candidate.lower().strip()
    if c in APP_DIR_ALIASES:
        bid = APP_DIR_ALIASES[c]
        # Extract app name from bundle ID
        parts = bid.split(".")
        if len(parts) >= 3:
            return parts[-1].replace("-", " ").replace("_", " ").title()
    return None
