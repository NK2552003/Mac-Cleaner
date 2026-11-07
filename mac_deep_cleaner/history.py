"""Durable Trash journal and conflict-safe restore."""

import fcntl
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .common import fingerprint
from .errors import APIError


class History:
    def __init__(self, home=None):
        self.home = Path(home or Path.home()).absolute()
        self.directory = self.home / "Library/Application Support/Mac Deep Cleaner"
        self.path = self.directory / "history.sqlite3"

    @contextmanager
    def connect(self):
        if self.directory.resolve() != self.directory or self.path.is_symlink():
            raise OSError("History location cannot contain symbolic links.")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        db = sqlite3.connect(str(self.path), timeout=15)
        os.chmod(self.path, 0o600)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        db.execute(
            "CREATE TABLE IF NOT EXISTS moves (id TEXT PRIMARY KEY, original TEXT, trash TEXT, identity TEXT, created REAL, restored REAL, status TEXT)"
        )
        try:
            with db:
                yield db
        finally:
            db.close()

    def move(self, path):
        """Journal intent before an atomic rename. Never overwrite a Trash entry."""
        source = Path(path)
        trash = self.home / ".Trash"
        if trash.resolve() != trash:
            raise OSError("Trash cannot contain symbolic links.")
        trash.mkdir(mode=0o700, exist_ok=True)
        identifier = secrets.token_hex(16)
        # Separate container avoids collisions even for maximum-length filenames.
        container = trash / ("MDC-" + identifier)
        container.mkdir(mode=0o700)
        destination = container / source.name
        identity = fingerprint(str(source))
        if not identity:
            container.rmdir()
            raise OSError("The source disappeared.")
        try:
            with self.connect() as db:
                db.execute(
                    "INSERT INTO moves VALUES (?,?,?,?,?,NULL,?)",
                    (
                        identifier,
                        str(source),
                        str(destination),
                        json.dumps(identity),
                        time.time(),
                        "prepared",
                    ),
                )
            os.rename(source, destination)  # EXDEV fails safely; never copy then delete.
            try:
                with self.connect() as db:
                    db.execute("UPDATE moves SET status='moved' WHERE id=?", (identifier,))
            except (OSError, sqlite3.Error):
                pass  # The durable prepared record is recoverable from the destination identity.
        except Exception:
            if not destination.exists():
                container.rmdir()
            raise
        return identifier

    def records(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM moves ORDER BY created DESC LIMIT 1000").fetchall()
        result = []
        for row in rows:
            entry = dict(row)
            identity = tuple(json.loads(entry.pop("identity")))
            present = fingerprint(entry["trash"]) == identity
            if entry["status"] == "prepared":
                entry["status"] = "moved" if present else "interrupted"
            if entry["status"] == "restoring":
                entry["status"] = (
                    "restored" if not present and fingerprint(entry["original"]) == identity
                    else "moved" if present else "interrupted"
                )
            entry["available"] = present and entry["status"] == "moved"
            entry["conflict"] = entry["available"] and os.path.lexists(entry["original"])
            result.append(entry)
        return result

    def restore(self, identifier):
        with mutation_lock(self.home):
            return self._restore(identifier)

    def _restore(self, identifier):
        from .cleanup import guard_ok

        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM moves WHERE id=?", (identifier,)).fetchone()
            if not row or row["status"] not in ("moved", "prepared", "restoring"):
                raise APIError(409, "This history entry cannot be restored.")
            source, target = Path(row["trash"]), Path(row["original"])
            if (
                source.parent.parent != self.home / ".Trash"
                or source.resolve() != source
                or not guard_ok(str(target))
                or not target.parent.is_dir()
            ):
                raise APIError(
                    409, "The original parent is missing or a location is no longer safe."
                )
            if os.path.lexists(target):
                raise APIError(
                    409, "The original location is occupied. Move that item before restoring."
                )
            if fingerprint(str(source)) != tuple(json.loads(row["identity"])):
                raise APIError(
                    409, "This Trash entry changed or was emptied; it cannot be restored."
                )
            db.execute("UPDATE moves SET status='restoring' WHERE id=?", (identifier,))
            db.commit()
            # macOS renamex_np with RENAME_EXCL prevents even concurrent overwrites.
            try:
                exclusive_rename(source, target)
            except OSError:
                db.execute("UPDATE moves SET status='moved' WHERE id=?", (identifier,))
                db.commit()
                raise
            db.execute(
                "UPDATE moves SET status='restored', restored=? WHERE id=?",
                (time.time(), identifier),
            )
            try:
                source.parent.rmdir()
            except OSError:
                pass
        return {"ok": True, "path": str(target)}


def exclusive_rename(source, target):
    import sys

    if sys.platform == "darwin":
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        if libc.renamex_np(os.fsencode(source), os.fsencode(target), 4) != 0:  # RENAME_EXCL
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
    elif sys.platform.startswith("linux"):
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        if libc.renameat2(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
    else:
        raise OSError("Exclusive restore is not supported on this platform.")


@contextmanager
def mutation_lock(home):
    directory = Path(home) / "Library/Application Support/Mac Deep Cleaner"
    if directory.resolve() != directory:
        raise OSError("Cleanup lock location cannot contain symbolic links.")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(directory / "cleanup.lock", flags, 0o600)
    with os.fdopen(fd, "a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise APIError(
                409, "Another cleanup or restore is running in a different process."
            ) from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
