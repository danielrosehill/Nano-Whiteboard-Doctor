#!/usr/bin/env bash
set -euo pipefail

PKG_NAME="nano-tech-diagrams"
VERSION="0.3.0"
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
exec /opt/nano-tech-diagrams/venv/bin/python -m nano_tech_diagrams "$@"
LAUNCHER
chmod 755 "${BUILD_DIR}/usr/bin/${PKG_NAME}"

# Create .desktop file
cat > "${BUILD_DIR}/usr/share/applications/${PKG_NAME}.desktop" << DESKTOP
[Desktop Entry]
Name=Nano Tech Diagrams
Comment=Create and edit tech diagrams with AI (Nano Banana 2 via Fal AI)
Exec=${PKG_NAME}
Terminal=false
Type=Application
Categories=Graphics;Utility;Development;
Keywords=diagram;ai;image;whiteboard;tech;flowchart;network;architecture;
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
Description: Desktop tool for creating and editing tech diagrams using AI
 Nano Tech Diagrams creates and edits tech diagrams using the Nano Banana 2
 model (via Fal AI). Supports whiteboard cleanup, image-to-image transformation,
 and text-to-image generation with 24 visual styles and 18 diagram types.
 Features a modern PyQt6 GUI, CLI, and MCP server interface.
CONTROL

# Build the package
fakeroot dpkg-deb --build "${BUILD_DIR}" "${PKG_NAME}_${VERSION}_${ARCH}.deb"

echo "==> Built: ${PKG_NAME}_${VERSION}_${ARCH}.deb"
