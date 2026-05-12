"""DNS cache flush helpers."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class DNSFlushStep:
    """One DNS flush command."""
    command: List[str]
    success: bool
    stdout: str = ""
    stderr: str = ""


@dataclass
class DNSFlushResult:
    """Summary of DNS flush."""
    success: bool
    steps: List[DNSFlushStep] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _run_cmd(args: List[str], runner=subprocess.run) -> DNSFlushStep:
    try:
        result = runner(
            args,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("DNS command failed: %s", exc)
        return DNSFlushStep(command=args, success=False, stderr=str(exc))

    ok = result.returncode == 0
    return DNSFlushStep(
        command=args,
        success=ok,
        stdout=result.stdout.strip(),
        stderr=result.stderr.strip(),
    )


def flush_dns_cache(runner=subprocess.run) -> DNSFlushResult:
    """Flush DNS cache using standard macOS commands."""
    commands = [
        ["dscacheutil", "-flushcache"],
        ["killall", "-HUP", "mDNSResponder"],
        ["killall", "-HUP", "mDNSResponderHelper"],
    ]

    steps: List[DNSFlushStep] = []
    errors: List[str] = []
    success_count = 0

    for cmd in commands:
        step = _run_cmd(cmd, runner=runner)
        if not step.success:
            if step.stderr and "no matching processes" in step.stderr.lower():
                step.success = True
        if step.success:
            success_count += 1
        else:
            errors.append(" ".join(cmd))
        steps.append(step)

    return DNSFlushResult(
        success=success_count > 0,
        steps=steps,
        errors=errors,
    )
