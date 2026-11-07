#!/usr/bin/env bash
# Build, verify, and install Mac Deep Cleaner using the repository's build tools.
# Usage: bash scripts/build.sh [build|app|pkg|venv|test|install|all|clean]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"
VENV_DIR="$ROOT_DIR/.venv"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"

# Respect the selected interpreter (including CI's version matrix).
if [[ -n "${MDC_PYTHON:-}" ]]; then
    TASK_PYTHON="$MDC_PYTHON"
elif [[ -x "$VENV_DIR/bin/python" ]]; then
    TASK_PYTHON="$VENV_DIR/bin/python"
else
    TASK_PYTHON="$(command -v python3)"
fi
"$TASK_PYTHON" -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9+ is required"'
APP_VERSION="$("$TASK_PYTHON" -c 'import runpy; print(runpy.run_path("mac_deep_cleaner/__init__.py")["__version__"])')"
printf 'Mac Deep Cleaner %s — %s\n' "$APP_VERSION" "$("$TASK_PYTHON" --version)"

ensure_venv() {
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        "$TASK_PYTHON" -m venv "$VENV_DIR"
    fi
    BUILD_PYTHON="$VENV_DIR/bin/python"
}

do_venv() {
    ensure_venv
    "$BUILD_PYTHON" -m pip install --quiet --upgrade pip setuptools wheel build
    "$BUILD_PYTHON" -m pip install --quiet -e '.[dev,media]'
    printf 'Development environment ready: source .venv/bin/activate\n'
}

do_build() {
    ensure_venv
    if ! "$BUILD_PYTHON" -m build --version >/dev/null 2>&1; then
        "$BUILD_PYTHON" -m pip install --quiet build
    fi
    mkdir -p "$DIST_DIR"
    # Remove only this package's stale output; preserve native apps and other artifacts.
    rm -f "$DIST_DIR"/mac_deep_cleaner-*.whl "$DIST_DIR"/mac_deep_cleaner-*.tar.gz "$DIST_DIR"/mac-deep-cleaner-*.tar.gz
    rm -rf "$BUILD_DIR/lib" "$BUILD_DIR"/bdist.*
    "$BUILD_PYTHON" -m build --wheel --sdist --outdir "$DIST_DIR"
}

do_app() {
    ensure_venv
    if ! "$BUILD_PYTHON" -c 'import PIL, PyInstaller' >/dev/null 2>&1; then
        "$BUILD_PYTHON" -m pip install --quiet pyinstaller '.[media]'
    fi
    "$BUILD_PYTHON" "$SCRIPT_DIR/build_mac.py" "$@"
}

do_pkg() {
    if [[ "$(uname -s)" != Darwin ]]; then
        printf 'macOS is required to build an installer.\n' >&2
        return 1
    fi
    do_app
    pkgbuild --component "$DIST_DIR/Mac Deep Cleaner.app" --install-location /Applications \
        --identifier com.macdeepcleaner.desktop --version "$APP_VERSION" \
        "$DIST_DIR/mac-deep-cleaner-$APP_VERSION-macos.pkg"
}

do_test() {
    do_venv
    "$BUILD_PYTHON" -m compileall -q mac_deep_cleaner mc.py
    for command in mac-cleaner mdc mac-deep-cleaner; do
        "$VENV_DIR/bin/$command" --help >/dev/null
        "$VENV_DIR/bin/$command" --version
    done
    "$BUILD_PYTHON" -m pytest
}

do_install() {
    ensure_venv
    local wheel="$DIST_DIR/mac_deep_cleaner-$APP_VERSION-py3-none-any.whl"
    if [[ ! -f "$wheel" ]]; then
        printf 'Build the current wheel first: bash scripts/build.sh build\n' >&2
        return 1
    fi
    "$BUILD_PYTHON" -m pip install --force-reinstall "$wheel"
    printf 'Installed into .venv. Run .venv/bin/mdc or activate the environment.\n'
}

do_clean() {
    rm -rf "$DIST_DIR" "$BUILD_DIR" "$ROOT_DIR"/*.egg-info
    find "$ROOT_DIR/mac_deep_cleaner" "$ROOT_DIR/tests" -type d -name __pycache__ -prune -exec rm -rf {} +
}

MODE="${1:-build}"
case "$MODE" in
    build) do_build ;;
    app) shift; do_app "$@" ;;
    pkg) do_pkg ;;
    venv) do_venv ;;
    test) do_test ;;
    install) do_install ;;
    all) do_venv; do_build; do_install ;;
    clean) do_clean ;;
    *) printf 'Usage: bash scripts/build.sh [build|app|pkg|venv|test|install|all|clean]\n' >&2; exit 1 ;;
esac
