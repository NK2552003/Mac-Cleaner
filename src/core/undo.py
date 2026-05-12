"""
Mac Deep Cleaner v1.5.0 — Undo / Restore (Staged Deletion)
========================================================
Instead of permanently deleting files, mac-cleaner moves them to a staging
area (~/.mac_cleaner_trash/) with a JSON manifest so they can be restored.

Design
------
- Each deletion session creates a manifest file:
    ~/.mac_cleaner_trash/sessions/<timestamp>.json
- The manifest records the original path, staging path, and size.
- `mac-cleaner undo` lists sessions and lets the user pick one to restore.
- Staging area entries older than RETENTION_DAYS are purged automatically.

Thread safety: manifest writes are not concurrent; the CLI is single-threaded.
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from constants import HOME
from utils import bytes_human, size_of

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

TRASH_ROOT = HOME / ".mac_cleaner_trash"
STAGING_DIR = TRASH_ROOT / "files"
SESSION_DIR = TRASH_ROOT / "sessions"
RETENTION_DAYS = 30   # Sessions older than this are purged automatically

TRASH_ROOT.mkdir(parents=True, exist_ok=True)
STAGING_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class StagedFile:
    """One file/directory that has been staged for potential restoration."""
    original_path: str        # absolute path before staging
    staging_path: str         # path inside ~/.mac_cleaner_trash/files/
    size: int
    category: str             # e.g. "Orphan", "Junk"
    staged_at: str            # ISO timestamp

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StagedFile":
        return cls(**d)


@dataclass
class DeletionSession:
    """A batch of files staged during one `mac-cleaner clean` run."""
    session_id: str
    created_at: str           # ISO timestamp
    files: List[StagedFile] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.files)

    @property
    def total_size_human(self) -> str:
        return bytes_human(self.total_size)

    @property
    def manifest_path(self) -> Path:
        return SESSION_DIR / f"{self.session_id}.json"

    def save(self) -> None:
        """Persist this session to disk."""
        data = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "files": [f.to_dict() for f in self.files],
        }
        self.manifest_path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, manifest_path: Path) -> Optional["DeletionSession"]:
        """Load a session from its manifest file. Returns None on error."""
        try:
            data = json.loads(manifest_path.read_text())
            files = [StagedFile.from_dict(fd) for fd in data.get("files", [])]
            return cls(
                session_id=data["session_id"],
                created_at=data["created_at"],
                files=files,
            )
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def __repr__(self) -> str:
        return (
            f"<DeletionSession {self.session_id[:8]}… "
            f"files={len(self.files)} size={self.total_size_human}>"
        )


# ── Session management ─────────────────────────────────────────────────────────

def new_session() -> DeletionSession:
    """Create a fresh DeletionSession for the current clean run."""
    return DeletionSession(
        session_id=str(uuid.uuid4()),
        created_at=datetime.now().isoformat(),
    )


def list_sessions() -> List[DeletionSession]:
    """Return all stored sessions, newest first."""
    sessions: List[DeletionSession] = []
    for manifest in sorted(SESSION_DIR.glob("*.json"), reverse=True):
        s = DeletionSession.load(manifest)
        if s:
            sessions.append(s)
    return sessions


def purge_old_sessions(retention_days: int = RETENTION_DAYS) -> int:
    """
    Delete sessions (and their staged files) older than retention_days.
    Returns the number of sessions purged.
    """
    cutoff = datetime.now() - timedelta(days=retention_days)
    purged = 0
    for session in list_sessions():
        try:
            created = datetime.fromisoformat(session.created_at)
        except ValueError:
            continue
        if created < cutoff:
            _purge_session(session)
            purged += 1
    return purged


def purge_all_sessions() -> int:
    """
    Delete ALL sessions (and their staged files) regardless of age.
    Returns the number of sessions purged.
    """
    purged = 0
    for session in list_sessions():
        _purge_session(session)
        purged += 1
    return purged


def _purge_session(session: DeletionSession) -> None:
    """Remove all staged files and the manifest for a session."""
    for f in session.files:
        staged = Path(f.staging_path)
        if staged.exists():
            try:
                if staged.is_dir():
                    shutil.rmtree(staged)
                else:
                    staged.unlink()
            except OSError as exc:
                logger.debug("Failed to purge staged file %s: %s", staged, exc)
    session.manifest_path.unlink(missing_ok=True)


# ── Stage (move to trash) ──────────────────────────────────────────────────────

def stage_file(
    path: Path,
    session: DeletionSession,
    category: str = "Junk",
) -> Tuple[bool, int]:
    """
    Move *path* to the staging area and record it in *session*.

    Returns:
        (success, bytes_moved)
    """
    if not path.exists():
        return False, 0

    sz = size_of(path)
    unique_name = f"{uuid.uuid4().hex}_{path.name}"
    staging_path = STAGING_DIR / unique_name

    try:
        shutil.move(str(path), str(staging_path))
    except (shutil.Error, OSError) as exc:
        logger.debug("Failed to move to staging for %s: %s", path, exc)
        # Fallback: copy then delete
        try:
            if path.is_dir():
                shutil.copytree(path, staging_path)
                shutil.rmtree(path)
            else:
                shutil.copy2(path, staging_path)
                path.unlink()
        except (shutil.Error, OSError) as e:
            logger.debug("Failed staging fallback for %s: %s", path, e)
            return False, 0

    session.files.append(StagedFile(
        original_path=str(path),
        staging_path=str(staging_path),
        size=sz,
        category=category,
        staged_at=datetime.now().isoformat(),
    ))
    return True, sz


# ── Restore ────────────────────────────────────────────────────────────────────

@dataclass
class RestoreResult:
    """Summary of a restore operation."""
    restored: int = 0
    failed: int = 0
    bytes_restored: int = 0
    errors: List[str] = field(default_factory=list)


def restore_session(session: DeletionSession) -> RestoreResult:
    """
    Move all staged files in *session* back to their original locations.
    """
    result = RestoreResult()

    for f in session.files:
        staging = Path(f.staging_path)
        original = Path(f.original_path)

        if not staging.exists():
            result.failed += 1
            result.errors.append(f"Staging copy missing: {f.original_path}")
            continue

        # Ensure parent directory exists
        original.parent.mkdir(parents=True, exist_ok=True)

        try:
            if original.exists():
                # Don't overwrite; rename the staging copy with a suffix
                suffix_path = original.with_name(original.name + ".restored")
                shutil.move(str(staging), str(suffix_path))
                result.errors.append(
                    f"Destination exists; restored as {suffix_path.name}"
                )
            else:
                shutil.move(str(staging), str(original))
            result.restored += 1
            result.bytes_restored += f.size
        except (shutil.Error, OSError) as e:
            logger.debug("Restore failed for %s: %s", f.original_path, e)
            result.failed += 1
            result.errors.append(f"{f.original_path}: {e}")

    if result.restored > 0:
        # Clean up the session manifest (files are back)
        session.manifest_path.unlink(missing_ok=True)

    return result
