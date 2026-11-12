#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "This script must run in a Linux environment." >&2
    exit 1
fi

for command in python3 flatpak flatpak-builder appimagetool magick; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command not found: $command" >&2
        exit 1
    fi
done

VERSION="$(sed -nE 's/^version = "([^"]+)"$/\1/p' pyproject.toml | head -n 1)"
if [[ -z "$VERSION" ]]; then
    echo "Could not read the project version from pyproject.toml." >&2
    exit 1
fi

case "$(uname -m)" in
    x86_64)
        APPIMAGE_ARCH=x86_64
        ;;
    aarch64)
        APPIMAGE_ARCH=aarch64
        ;;
    *)
        echo "AppImage packaging is configured for x86_64 and aarch64, not $(uname -m)." >&2
        exit 1
        ;;
esac

PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "Python 3.10 or newer is required (found $PYTHON_VERSION)." >&2
    exit 1
fi

BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/waifu-gallery-release.XXXXXX")"
trap 'rm -rf "$BUILD_ROOT"' EXIT

OUTPUT_DIR="${RELEASE_OUTPUT_DIR:-$HOME/releases/waifu-gallery}"
mkdir -p "$OUTPUT_DIR"

python3 -m venv "$BUILD_ROOT/venv"
PIP_CACHE_DIR="$BUILD_ROOT/pip-cache" \
    "$BUILD_ROOT/venv/bin/python" -m pip install --upgrade pip
PIP_CACHE_DIR="$BUILD_ROOT/pip-cache" \
    "$BUILD_ROOT/venv/bin/python" -m pip install -r requirements.txt pyinstaller

"$BUILD_ROOT/venv/bin/python" -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name WaifuGallery \
    --add-data "waifu_gallery/assets:waifu_gallery/assets" \
    --collect-all PySide6.QtMultimedia \
    --distpath "$BUILD_ROOT/dist" \
    --workpath "$BUILD_ROOT/pyinstaller" \
    launcher.py

APP_ID="com.fisalia.WaifuGallery"
APP_NAME="Waifu Gallery"
APP_ICON="$SCRIPT_DIR/waifu_gallery/assets/waifugallery.png"
APP_BUNDLE="$BUILD_ROOT/dist/WaifuGallery"

if [[ ! -x "$APP_BUNDLE/WaifuGallery" || ! -f "$APP_ICON" ]]; then
    echo "PyInstaller output or application icon is missing." >&2
    exit 1
fi

APPIMAGE_DIR="$BUILD_ROOT/appimage"
mkdir -p "$APPIMAGE_DIR/usr/lib/waifu-gallery" \
    "$APPIMAGE_DIR/usr/bin" \
    "$APPIMAGE_DIR/usr/share/applications" \
    "$APPIMAGE_DIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$APP_BUNDLE/." "$APPIMAGE_DIR/usr/lib/waifu-gallery/"
install -Dm755 /dev/stdin "$APPIMAGE_DIR/AppRun" <<'APPRUN'
#!/usr/bin/env sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/waifu-gallery/WaifuGallery" "$@"
APPRUN
install -Dm644 "$APP_ICON" "$APPIMAGE_DIR/$APP_ID.png"
install -Dm644 "$APP_ICON" \
    "$APPIMAGE_DIR/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
install -Dm755 /dev/stdin "$APPIMAGE_DIR/usr/bin/waifu-gallery" <<'APPWRAPPER'
#!/usr/bin/env sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/../lib/waifu-gallery/WaifuGallery" "$@"
APPWRAPPER
cat > "$APPIMAGE_DIR/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$APP_NAME
Exec=waifu-gallery
Icon=$APP_ID
Categories=Graphics;Utility;
Terminal=false
DESKTOP
install -Dm644 "$APPIMAGE_DIR/$APP_ID.desktop" \
    "$APPIMAGE_DIR/usr/share/applications/$APP_ID.desktop"

APPIMAGE_PATH="$OUTPUT_DIR/Waifu-Gallery-$VERSION-$APPIMAGE_ARCH.AppImage"
ARCH="$APPIMAGE_ARCH" appimagetool "$APPIMAGE_DIR" "$APPIMAGE_PATH"

FLATPAK_SOURCE="$BUILD_ROOT/flatpak-source"
mkdir -p "$FLATPAK_SOURCE"
cp -a "$APP_BUNDLE" "$FLATPAK_SOURCE/WaifuGallery"
ICON_SIZE="$(magick identify -format '%[fx:max(w,h)]' "$APP_ICON")"
magick "$APP_ICON" -gravity center -background none \
    -extent "${ICON_SIZE}x${ICON_SIZE}" "$FLATPAK_SOURCE/icon.png"
cat > "$FLATPAK_SOURCE/waifu-gallery" <<'FLATPAK_LAUNCHER'
#!/usr/bin/env sh
exec /app/lib/waifu-gallery/WaifuGallery "$@"
FLATPAK_LAUNCHER
chmod 755 "$FLATPAK_SOURCE/waifu-gallery"
cat > "$FLATPAK_SOURCE/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$APP_NAME
Exec=waifu-gallery
Icon=$APP_ID
Categories=Graphics;Utility;
Terminal=false
DESKTOP

FLATPAK_REPO="$BUILD_ROOT/flatpak-repo"
FLATPAK_BUILD="$BUILD_ROOT/flatpak-build"
mkdir -p "$BUILD_ROOT/flatpak"
cp "$SCRIPT_DIR/flatpak/$APP_ID.yml" "$BUILD_ROOT/flatpak/$APP_ID.yml"
flatpak-builder \
    --force-clean \
    --state-dir="$BUILD_ROOT/flatpak-state" \
    --default-branch=stable \
    --repo="$FLATPAK_REPO" \
    "$FLATPAK_BUILD" \
    "$BUILD_ROOT/flatpak/$APP_ID.yml"

FLATPAK_ARCH="$(flatpak --default-arch)"
FLATPAK_PATH="$OUTPUT_DIR/Waifu-Gallery-$VERSION-$FLATPAK_ARCH.flatpak"
flatpak build-bundle \
    --arch="$FLATPAK_ARCH" \
    "$FLATPAK_REPO" \
    "$FLATPAK_PATH" \
    "$APP_ID" \
    stable

echo
echo "Release packages created:"
echo "  $APPIMAGE_PATH"
echo "  $FLATPAK_PATH"
