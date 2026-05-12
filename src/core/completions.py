"""Shell completion helpers."""

from __future__ import annotations

import os
from typing import Callable, cast

SUPPORTED_SHELLS = ("bash", "zsh", "fish")


def detect_shell() -> str:
    """Best-effort shell detection from $SHELL."""
    shell = os.environ.get("SHELL", "")
    base = os.path.basename(shell)
    return base if base in SUPPORTED_SHELLS else "bash"


def _complete_var(prog_name: str) -> str:
    return f"_{prog_name.replace('-', '_').upper()}_COMPLETE"


def _fallback_line(shell: str, prog_name: str) -> str:
    complete_var = _complete_var(prog_name)
    if shell == "fish":
        return f"env {complete_var}=fish_source {prog_name} | source"
    return f"eval \"$({complete_var}={shell}_source {prog_name})\""


def _fallback_script(shell: str, prog_name: str) -> str:
    line = _fallback_line(shell, prog_name)
    return f"# Fallback completion line\n{line}\n"


def completion_script(shell: str, prog_name: str, command=None) -> str:
    """Return a shell completion script for Click-based CLIs."""
    shell = shell.lower()
    if shell not in SUPPORTED_SHELLS:
        raise ValueError(f"Unsupported shell: {shell}")

    try:
        import click.shell_completion as shell_completion
    except Exception:
        return _fallback_script(shell, prog_name)

    get_completion_script = getattr(shell_completion, "get_completion_script", None)
    if not callable(get_completion_script):
        return _fallback_script(shell, prog_name)

    get_completion_script_typed = cast(Callable[..., str], get_completion_script)

    import inspect

    params = list(inspect.signature(get_completion_script).parameters)
    has_command = "command" in params
    has_complete_var = "complete_var" in params

    try:
        if has_command and command is not None:
            return get_completion_script_typed(prog_name, shell, command)
        if has_complete_var:
            return get_completion_script_typed(prog_name, shell, _complete_var(prog_name))
        return get_completion_script_typed(prog_name, shell)
    except TypeError:
        return _fallback_script(shell, prog_name)


def install_instructions(shell: str, prog_name: str) -> str:
    """Return shell-specific install instructions."""
    line = _fallback_line(shell, prog_name)
    if shell == "zsh":
        return f"Add this line to ~/.zshrc:\n{line}"
    if shell == "fish":
        return f"Run this once, or add to ~/.config/fish/config.fish:\n{line}"
    return f"Add this line to ~/.bashrc:\n{line}"
