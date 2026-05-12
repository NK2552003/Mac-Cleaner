#!/usr/bin/env bash
# =============================================================================
# Mac Deep Cleaner v2.0.0 — Build & Install Script
# =============================================================================
# Usage:
#   bash build.sh            → default: build wheel + sdist
#   bash build.sh venv       → create .venv and install in editable mode
#   bash build.sh install    → pip install the built wheel system/user wide
#   bash build.sh clean      → remove build artefacts
#   bash build.sh all        → venv + build + install wheel into venv
#   bash build.sh test       → compile + smoke-test CLI in venv
#   bash build.sh pkg        → build a local macOS .pkg installer
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Build/install must run from repo root (where pyproject.toml/setup.py live)
cd "$ROOT_DIR"

PACKAGE_NAME="mac-deep-cleaner"
VENV_DIR=".venv"
DIST_DIR="dist"
BUILD_DIR="build"

# ── Colour helpers ────────────────────────────────────────────────────────────
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }

# ── Detect python3 ────────────────────────────────────────────────────────────
find_python() {
    for cmd in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(sys.version_info >= (3,9))")
            if [[ "$ver" == "True" ]]; then
                echo "$cmd"
                return
            fi
        fi
    done
    red "ERROR: Python 3.9+ not found. Install it first."
    exit 1
}

PYTHON=$(find_python)
bold "Using Python: $PYTHON ($($PYTHON --version))"

# ── Mode: clean ───────────────────────────────────────────────────────────────
do_clean() {
    yellow "Removing build artefacts…"
    # Run cleanup from repo root so egg-info paths match current structure.
    rm -rf \
        "$ROOT_DIR/$DIST_DIR" \
        "$ROOT_DIR/$BUILD_DIR" \
        "$ROOT_DIR/"*.egg-info \
        "$ROOT_DIR/src/"*.egg-info \
        "$ROOT_DIR/src/mac_deep_cleaner.egg-info" \
        "$ROOT_DIR/src/mac_cleaner.egg-info"

    find "$ROOT_DIR" -type d -name __pycache__ -not -path '*/.venv/*' -exec rm -rf {} + 2>/dev/null || true
    find "$ROOT_DIR" -type f -name '*.pyc' -not -path '*/.venv/*' -delete 2>/dev/null || true
    green "Clean done."
}

# ── Mode: venv ────────────────────────────────────────────────────────────────
do_venv() {
    if [[ ! -d "$VENV_DIR" ]]; then
        yellow "Creating virtual environment at $VENV_DIR …"
        "$PYTHON" -m venv "$VENV_DIR"
    else
        yellow "Virtual environment already exists at $VENV_DIR"
    fi

    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    bold "Upgrading pip, setuptools, wheel, build…"
    pip install --quiet --upgrade pip setuptools wheel build

    bold "Installing mac-deep-cleaner into the venv…"
    pip install --quiet --force-reinstall ".[dev]" 2>/dev/null || pip install --quiet --force-reinstall .

    green ""
    green "✓ Virtual environment ready."
    green "  Activate : source $VENV_DIR/bin/activate"
    green "  Run      : mac-cleaner scan"
    green "  Alias    : mdc scan"
    green "  Deactivate: deactivate"
}

# ── Mode: build ───────────────────────────────────────────────────────────────
do_build() {
    bold "Building wheel and sdist…"
    rm -rf "$DIST_DIR" "$BUILD_DIR"

    # Prefer the 'build' frontend if available, else fall back to setup.py
    if "$PYTHON" -m build --version &>/dev/null 2>&1; then
        "$PYTHON" -m build --wheel --sdist --outdir "$DIST_DIR"
    else
        yellow "'build' not found — installing it first…"
        "$PYTHON" -m pip install --quiet build
        "$PYTHON" -m build --wheel --sdist --outdir "$DIST_DIR"
    fi

    green ""
    green "✓ Build complete. Artefacts:"
    ls -lh "$DIST_DIR/"
}

# ── Mode: test ────────────────────────────────────────────────────────────────
do_test() {
    do_venv
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"

    bold "Running compile checks…"
    python -m compileall -q src

    bold "Running CLI smoke checks…"
    mac-cleaner --help >/dev/null
    mdc --help >/dev/null
    mac-cleaner config --show >/dev/null
    mdc scan --ci --threshold-mb 0 >/tmp/mac-cleaner-ci.json || true

    if command -v pytest &>/dev/null && [[ -d tests ]]; then
        bold "Running pytest…"
        pytest || {
            code=$?
            if [[ "$code" -eq 5 ]]; then
                yellow "No pytest tests collected; smoke checks passed."
            else
                exit "$code"
            fi
        }
    else
        yellow "No tests/ directory found; smoke checks passed."
    fi

    green "✓ Test checks passed."
}

# ── Mode: install (system / user) ─────────────────────────────────────────────
do_install() {
    # Prefer the wheel we just built
    WHEEL=$(ls "$DIST_DIR"/*.whl 2>/dev/null | sort -V | tail -1 || true)

    if [[ -z "$WHEEL" ]]; then
        red "No wheel found in $DIST_DIR — run 'bash build.sh build' first."
        exit 1
    fi

    bold "Installing $WHEEL …"
    # Try --user install first (no sudo needed, works on stock macOS)
    if "$PYTHON" -m pip install --user --force-reinstall "$WHEEL"; then
        green ""
        green "✓ Installed with --user flag."
        green "  Make sure ~/.local/bin (or ~/Library/Python/X.Y/bin) is in your PATH."
        green "  Add this to your shell profile if needed:"
        green "    export PATH=\"\$HOME/.local/bin:\$HOME/Library/Python/$($PYTHON -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")')/bin:\$PATH\""
    else
        yellow "User install failed — trying without --user (may need sudo)…"
        "$PYTHON" -m pip install --force-reinstall "$WHEEL"
        green "✓ Installed system-wide."
    fi
    green "  Run: mac-cleaner scan"
    green "  Or : mdc scan"
}

# ── Mode: all ─────────────────────────────────────────────────────────────────
do_all() {
    do_clean
    do_venv
    do_build
    # Install wheel into the venv we just created
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    WHEEL=$(ls "$DIST_DIR"/*.whl 2>/dev/null | sort -V | tail -1 || true)
    if [[ -n "$WHEEL" ]]; then
        pip install --quiet --force-reinstall "$WHEEL"
        green "✓ Wheel installed into $VENV_DIR"
    fi
    green ""
    green "All done!  Activate your venv:"
    green "  source $VENV_DIR/bin/activate"
    green "  mac-cleaner scan"
    green "  mdc scan"
}

# ── Mode: pkg ─────────────────────────────────────────────────────────────────
do_pkg() {
    "$ROOT_DIR/scripts/build_pkg.sh"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
MODE="${1:-build}"

case "$MODE" in
    clean)   do_clean   ;;
    venv)    do_venv    ;;
    build)   do_build   ;;
    install) do_install ;;
    test)    do_test    ;;
    pkg)     do_pkg     ;;
    all)     do_all     ;;
    *)
        red "Unknown mode: $MODE"
        echo "Usage: bash build.sh [clean|venv|build|install|test|pkg|all]"
        exit 1
        ;;
esac
