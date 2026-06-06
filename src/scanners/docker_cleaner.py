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


def _parse_size(size_str: str) -> int:
    """Parse docker size string (e.g. '1.5GB', '500MB') to bytes."""
    size_str = size_str.upper().replace("B", "").strip()
    if not size_str:
        return 0
    try:
        if size_str.endswith("K"):
            return int(float(size_str[:-1]) * 1024)
        elif size_str.endswith("M"):
            return int(float(size_str[:-1]) * 1024 * 1024)
        elif size_str.endswith("G"):
            return int(float(size_str[:-1]) * 1024 * 1024 * 1024)
        elif size_str.endswith("T"):
            return int(float(size_str[:-1]) * 1024 * 1024 * 1024 * 1024)
        return int(float(size_str))
    except ValueError:
        return 0


def scan_docker_bloat() -> List[DockerJunkEntry]:
    """
    Run `docker system df --format '{{json .}}'` and return reclaimable space.
    """
    entries = []
    try:
        result = subprocess.run(
            ["docker", "system", "df", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                category = data.get("Type", "Unknown")
                reclaimable_str = data.get("Reclaimable", "0B")
                
                # Reclaimable often looks like "1.2GB (50%)", so extract the size part
                size_part = reclaimable_str.split(" ")[0]
                size_bytes = _parse_size(size_part)

                if size_bytes > 0:
                    entries.append(
                        DockerJunkEntry(
                            category=f"Docker {category}",
                            size=size_bytes,
                            description=f"Unused or dangling {category.lower()}",
                        )
                    )
            except json.JSONDecodeError:
                pass
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass

    return entries


def clean_docker_bloat() -> int:
    """
    Run `docker system prune -f` and return the bytes freed.
    """
    try:
        result = subprocess.run(
            ["docker", "system", "prune", "-f"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return 0
        
        # Output looks like:
        # Total reclaimed space: 1.5 GB
        for line in result.stdout.split("\n"):
            if "Total reclaimed space:" in line:
                size_str = line.split(":")[-1].strip()
                return _parse_size(size_str)
        return 0
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return 0
