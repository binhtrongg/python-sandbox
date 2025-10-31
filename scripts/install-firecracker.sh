#!/bin/bash
# Install Firecracker binary

set -e

FIRECRACKER_VERSION="v1.5.0"
ARCH="x86_64"

echo "📥 Installing Firecracker ${FIRECRACKER_VERSION}"

# Check if already installed
if command -v firecracker &> /dev/null; then
    CURRENT_VERSION=$(firecracker --version 2>&1 | head -n1 || echo "unknown")
    echo "ℹ️  Firecracker already installed: ${CURRENT_VERSION}"
    read -p "Reinstall? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "✅ Using existing installation"
        exit 0
    fi
fi

# Create temp directory
TEMP_DIR=$(mktemp -d)
cd "${TEMP_DIR}"

echo "📥 Downloading Firecracker ${FIRECRACKER_VERSION}..."
wget -q --show-progress \
    "https://github.com/firecracker-microvm/firecracker/releases/download/${FIRECRACKER_VERSION}/firecracker-${FIRECRACKER_VERSION}-${ARCH}.tgz"

# Extract
echo "📦 Extracting..."
tar -xzf "firecracker-${FIRECRACKER_VERSION}-${ARCH}.tgz"

# Install binary
echo "🔧 Installing to /usr/local/bin..."
sudo mv "release-${FIRECRACKER_VERSION}-${ARCH}/firecracker-${FIRECRACKER_VERSION}-${ARCH}" /usr/local/bin/firecracker
sudo chmod +x /usr/local/bin/firecracker

# Verify
echo ""
echo "✅ Firecracker installed successfully!"
firecracker --version

# Cleanup
cd ~
rm -rf "${TEMP_DIR}"

echo ""
echo "📝 Next steps:"
echo "   1. Build kernel: ./scripts/build-firecracker-kernel.sh"
echo "   2. Build rootfs: sudo ./scripts/build-firecracker-rootfs.sh"
echo "   3. Setup host: sudo ./scripts/setup-firecracker-host.sh"
