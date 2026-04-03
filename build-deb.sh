#!/usr/bin/env bash
set -euo pipefail

PKG_NAME="nano-whiteboard-doctor"
VERSION="0.1.0"
ARCH="all"
BUILD_DIR="$(mktemp -d)"
INSTALL_PREFIX="opt/${PKG_NAME}"

trap 'rm -rf "$BUILD_DIR"' EXIT

echo "==> Building .deb package v${VERSION}..."

# Create directory structure
mkdir -p "${BUILD_DIR}/${INSTALL_PREFIX}"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/DEBIAN"

# Create a self-contained venv and install the package into it
uv venv "${BUILD_DIR}/${INSTALL_PREFIX}/venv" --python python3
uv pip install --python "${BUILD_DIR}/${INSTALL_PREFIX}/venv/bin/python" .

# Fix shebangs that point to the temp build dir
find "${BUILD_DIR}/${INSTALL_PREFIX}/venv/bin" -type f -exec \
    sed -i "s|#!${BUILD_DIR}/|#!/|g" {} +

# Create launcher script
cat > "${BUILD_DIR}/usr/bin/${PKG_NAME}" << 'LAUNCHER'
#!/usr/bin/env bash
exec /opt/nano-whiteboard-doctor/venv/bin/python -m nano_whiteboard_doctor "$@"
LAUNCHER
chmod 755 "${BUILD_DIR}/usr/bin/${PKG_NAME}"

# Create .desktop file
cat > "${BUILD_DIR}/usr/share/applications/${PKG_NAME}.desktop" << DESKTOP
[Desktop Entry]
Name=Nano Whiteboard Doctor
Comment=Clean up whiteboard photos with AI
Exec=${PKG_NAME}
Terminal=false
Type=Application
Categories=Graphics;Utility;
Keywords=whiteboard;ai;image;cleanup;
DESKTOP

# Calculate installed size (in KB)
INSTALLED_SIZE=$(du -sk "${BUILD_DIR}" | cut -f1)

# Create control file
cat > "${BUILD_DIR}/DEBIAN/control" << CONTROL
Package: ${PKG_NAME}
Version: ${VERSION}
Section: graphics
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Maintainer: Daniel Rosehill <public@danielrosehill.com>
Description: Desktop GUI tool that cleans up whiteboard photos using Fal AI
 Nano Whiteboard Doctor transforms messy whiteboard photographs into clean,
 polished graphics using the Fal AI Nano Banana 2 image-to-image model.
 Supports single and batch image processing with a modern PyQt6 interface.
CONTROL

# Build the package
fakeroot dpkg-deb --build "${BUILD_DIR}" "${PKG_NAME}_${VERSION}_${ARCH}.deb"

echo "==> Built: ${PKG_NAME}_${VERSION}_${ARCH}.deb"
