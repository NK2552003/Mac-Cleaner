"""Visual disk space map."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set

from rich.tree import Tree

from utils import bytes_human, iterdir_safe, size_of

_SKIP_PREFIXES = (
    "/System",
    "/private/var",
    "/Volumes/.com.apple.TimeMachine",
    "/dev",
    "/proc",
)

_SKIP_NAMES: Set[str] = {
    ".git",
    ".Spotlight-V100",
    ".fseventsd",
    ".DocumentRevisions-V100",
    ".TemporaryItems",
    "__pycache__",
    "node_modules",
}


@dataclass
class DiskUsageNode:
    """One node in the disk usage tree."""
    path: Path
    size: int
    children: List["DiskUsageNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "size": self.size,
            "size_human": bytes_human(self.size),
            "children": [c.to_dict() for c in self.children],
        }


def _should_skip(path: Path) -> bool:
    s = str(path)
    if any(s.startswith(prefix) for prefix in _SKIP_PREFIXES):
        return True
    if path.name in _SKIP_NAMES:
        return True
    if path.name.startswith("."):
        return True
    return False


def _build_node(path: Path, depth: int, max_depth: int, min_size: int) -> DiskUsageNode:
    size = size_of(path)
    node = DiskUsageNode(path=path, size=size)
    if depth >= max_depth or not path.is_dir():
        return node

    children: List[DiskUsageNode] = []
    for child in iterdir_safe(path):
        if _should_skip(child):
            continue
        if not child.is_dir():
            continue
        child_node = _build_node(child, depth + 1, max_depth, min_size)
        if child_node.size >= min_size:
            children.append(child_node)

    children.sort(key=lambda c: c.size, reverse=True)
    node.children = children
    return node


def build_usage_tree(
    root: Path,
    max_depth: int = 2,
    min_size: int = 0,
) -> DiskUsageNode:
    """Build a disk usage tree for a root directory."""
    return _build_node(root, 0, max_depth, min_size)


def _bar(size: int, total: int, width: int = 20) -> str:
    if total <= 0:
        return "".ljust(width)
    filled = int((size / total) * width)
    if filled < 1 and size > 0:
        filled = 1
    return ("#" * filled) + ("." * (width - filled))


def _render_node(tree: Tree, node: DiskUsageNode, parent_size: int, limit: int) -> None:
    for child in node.children[:limit]:
        bar = _bar(child.size, parent_size)
        label = f"{child.path.name}  {bytes_human(child.size)}  {bar}"
        branch = tree.add(label)
        _render_node(branch, child, child.size, limit)
    if len(node.children) > limit:
        tree.add(f"... {len(node.children) - limit} more")


def render_usage_tree(node: DiskUsageNode, limit: int = 12) -> Tree:
    """Render a DiskUsageNode as a Rich Tree."""
    root_label = f"{node.path}  {bytes_human(node.size)}"
    tree = Tree(root_label)
    _render_node(tree, node, node.size, limit)
    return tree
