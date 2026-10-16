"""Scanner and cleaner for Docker container bloat."""

from __future__ import annotations

import logging
import subprocess
import json
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DockerJunkEntry:
    """Represents a category of Docker junk."""
    category: str
    size: int
    description: str


import re


def _parse_size(size_str: str) -> int:
    """Parse container size string (e.g. '1.5GB', '1.5 GiB', '500MB', '500 B') to bytes."""
    if not size_str:
        return 0
    m = re.search(r"([\d.]+)\s*([A-Za-z]+)?", size_str)
    if not m:
        return 0
    try:
        val = float(m.group(1))
        unit = (m.group(2) or "").upper()
        if "T" in unit:
            return int(val * 1024 * 1024 * 1024 * 1024)
        elif "G" in unit:
            return int(val * 1024 * 1024 * 1024)
        elif "M" in unit:
            return int(val * 1024 * 1024)
        elif "K" in unit:
            return int(val * 1024)
        return int(val)
    except (ValueError, OverflowError):
        return 0


def _run_container_cmd(cmd: List[str], timeout: int = 15) -> Optional[subprocess.CompletedProcess]:
    """Run docker or fallback to podman."""
    for bin_name in [cmd[0], "podman" if cmd[0] == "docker" else "docker"]:
        try:
            full_cmd = [bin_name] + cmd[1:]
            res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                return res
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            continue
    return None


def scan_docker_bloat() -> List[DockerJunkEntry]:
    """
    Run `docker system df --format '{{json .}}'` (or podman fallback) and return reclaimable space.
    """
    entries = []
    result = _run_container_cmd(["docker", "system", "df", "--format", "{{json .}}"], timeout=15)
    if not result or result.returncode != 0:
        return []

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            data = json.loads(line)
            category = data.get("Type", "Unknown")
            reclaimable_str = data.get("Reclaimable", "0B")
            
            size_bytes = _parse_size(reclaimable_str)

            if size_bytes > 0:
                entries.append(
                    DockerJunkEntry(
                        category=f"Container {category}",
                        size=size_bytes,
                        description=f"Unused or dangling {category.lower()}",
                    )
                )
        except json.JSONDecodeError:
            pass

    return entries


def clean_docker_bloat(all_images: bool = False, volumes: bool = False) -> int:
    """
    Run `docker system prune -f` (with optional -a and --volumes) and return bytes freed.
    """
    cmd = ["docker", "system", "prune", "-f"]
    if all_images:
        cmd.append("-a")
    if volumes:
        cmd.append("--volumes")

    result = _run_container_cmd(cmd, timeout=90)
    if not result or result.returncode != 0:
        return 0

    # Output looks like:
    # Total reclaimed space: 1.5 GB
    for line in result.stdout.split("\n"):
        if "Total reclaimed space:" in line or "Total Reclaimed Space:" in line:
            size_str = line.split(":")[-1].strip()
            return _parse_size(size_str)
    return 0
