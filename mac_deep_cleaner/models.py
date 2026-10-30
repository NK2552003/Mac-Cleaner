"""Storage and application records."""

from dataclasses import dataclass, field
from .common import DAY, MIN_SPEC, NOW, SAFE

@dataclass
class Item:
    id: int = 0
    category: str = ""
    name: str = ""
    path: str = ""
    size: int = 0
    safety: str = SAFE
    reason: str = ""
    regen: str = ""
    action: str = "trash"      # trash | empty | evict | cmd | root
    cmd: str = ""              # terminal command (cmd/root items, or a hint)
    readonly: bool = False
    protected: bool = False    # shown, never selectable
    managed: bool = False      # macOS manages it, tool never deletes, not counted
    manual: bool = False       # excluded from "select all safe" (must be picked by hand)
    active_project: bool = False
    set_id: str = ""
    keep: str = ""             # for duplicates: path of the copy that is kept
    mtime: float = 0.0
    selected: bool = False
    fingerprint: tuple = ()
    keeper_fingerprint: tuple = ()


@dataclass
class Spec:
    cat: str
    path: str
    safety: str
    reason: str
    regen: str
    label: str = ""
    root: bool = False
    cmd: str = ""
    managed: bool = False
    protected: bool = False
    check: str = ""            # "ndk" | "gradle" -> cross-check against real projects
    min_size: int = MIN_SPEC


@dataclass
class AppPart:
    label: str
    kind: str          # cache | data | prefs
    path: str
    size: int = 0
    fingerprint: tuple = ()


@dataclass
class AppInfo:
    id: int = 0
    name: str = ""
    path: str = ""
    bundle_id: str = ""
    version: str = ""
    category: str = ""         # human label derived from LSApplicationCategoryType
    source: str = "Direct"     # App Store | Direct
    size: int = 0              # the .app bundle itself
    parts: list = field(default_factory=list)         # list[AppPart]
    last_used: float = 0.0
    running: bool = False
    apple: bool = False
    removable: bool = True
    fingerprint: tuple = ()

    @property
    def cache_size(self):
        return sum(p.size for p in self.parts if p.kind == "cache")

    @property
    def data_size(self):
        return sum(p.size for p in self.parts)

    @property
    def total(self):
        return self.size + self.data_size

    @property
    def idle_days(self):
        return int((NOW - self.last_used) / DAY) if self.last_used else 0
