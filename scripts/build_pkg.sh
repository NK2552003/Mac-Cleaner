#!/usr/bin/env bash
# Build a local macOS .pkg installer for Mac Deep Cleaner.
#
# The generated package installs launchers at /usr/local/bin/mac-cleaner and
# /usr/local/bin/mdc.
# The launcher creates/uses /Library/Application Support/mac-deep-cleaner/venv
# and installs the wheel there, keeping Python dependencies isolated.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PKG_ID="com.nk2552003.mac-deep-cleaner"
PKG_NAME="mac-deep-cleaner"
VERSION="$("$ROOT_DIR/.venv/bin/python" -c 'import ast,pathlib; m=ast.parse(pathlib.Path("src/__init__.py").read_text()); print(next(n.value.value for n in m.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "__version__" for t in n.targets)))' 2>/dev/null || python3 -c 'import ast,pathlib; m=ast.parse(pathlib.Path("src/__init__.py").read_text()); print(next(n.value.value for n in m.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "__version__" for t in n.targets)))')"
WORK_DIR="$ROOT_DIR/build/pkg"
ROOT_PAYLOAD="$WORK_DIR/root"
SCRIPTS_DIR="$WORK_DIR/scripts"
INSTALL_DIR="$ROOT_PAYLOAD/Library/Application Support/mac-deep-cleaner"
BIN_DIR="$ROOT_PAYLOAD/usr/local/bin"
DIST_DIR="$ROOT_DIR/dist"

green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }

bold "Mac Deep Cleaner .pkg builder"
cat <<'NOTICE'

This builds an unsigned local installer package.

The installer will ask macOS for administrator approval because it writes to:
  - /usr/local/bin/mac-cleaner
  - /usr/local/bin/mdc
  - /Library/Application Support/mac-deep-cleaner

The app itself may later need Full Disk Access for complete scans. The package
does not grant that permission automatically; macOS requires the user to do it
in System Settings > Privacy & Security > Full Disk Access.

NOTICE

read -r -p "Continue building the .pkg? [y/N] " answer
case "$answer" in
    y|Y|yes|YES) ;;
    *) yellow "Cancelled."; exit 0 ;;
esac

if [[ ! -d "$DIST_DIR" ]] || ! ls "$DIST_DIR"/*.whl >/dev/null 2>&1; then
    "$ROOT_DIR/scripts/build.sh" build
fi

WHEEL="$(ls "$DIST_DIR"/*.whl | sort -V | tail -1)"
rm -rf "$WORK_DIR"
mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$SCRIPTS_DIR"
cp "$WHEEL" "$INSTALL_DIR/"

cat > "$BIN_DIR/mac-cleaner" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/Library/Application Support/mac-deep-cleaner"
VENV_DIR="$APP_DIR/venv"
WHEEL="$(ls "$APP_DIR"/*.whl | sort -V | tail -1)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
    "$VENV_DIR/bin/python" -m pip install --force-reinstall "$WHEEL" >/dev/null
fi

exec "$VENV_DIR/bin/mac-cleaner" "$@"
LAUNCHER
chmod 755 "$BIN_DIR/mac-cleaner"

cat > "$BIN_DIR/mdc" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/Library/Application Support/mac-deep-cleaner"
VENV_DIR="$APP_DIR/venv"
WHEEL="$(ls "$APP_DIR"/*.whl | sort -V | tail -1)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
    "$VENV_DIR/bin/python" -m pip install --force-reinstall "$WHEEL" >/dev/null
fi

exec "$VENV_DIR/bin/mdc" "$@"
LAUNCHER
chmod 755 "$BIN_DIR/mdc"

cat > "$SCRIPTS_DIR/postinstall" <<'POSTINSTALL'
#!/usr/bin/env bash
set -euo pipefail
echo "Mac Deep Cleaner installed."
echo "Run: mac-cleaner scan"
echo "Or : mdc scan"
echo "For full scans, grant Terminal or your shell Full Disk Access in System Settings."
exit 0
POSTINSTALL
chmod 755 "$SCRIPTS_DIR/postinstall"

PKG_PATH="$DIST_DIR/${PKG_NAME}-${VERSION}.pkg"
pkgbuild \
    --root "$ROOT_PAYLOAD" \
    --scripts "$SCRIPTS_DIR" \
    --identifier "$PKG_ID" \
    --version "$VERSION" \
    --install-location "/" \
    "$PKG_PATH"

green "✓ Package built: $PKG_PATH"
yellow "Unsigned package. For release distribution, sign with productsign and a Developer ID Installer certificate."
