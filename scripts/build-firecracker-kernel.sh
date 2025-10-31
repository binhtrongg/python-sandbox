#!/bin/bash
# Build custom Linux kernel for Firecracker

set -e

KERNEL_VERSION="5.10.198"
WORK_DIR="/tmp/firecracker-kernel-build"
OUTPUT_DIR="/var/firecracker"

echo "🔨 Building Firecracker kernel v${KERNEL_VERSION}"
echo "⏱️  This will take 10-30 minutes depending on your CPU"
echo ""

# Check dependencies
echo "🔍 Checking build dependencies..."
MISSING_DEPS=()
for cmd in wget tar make gcc bc flex bison libelf-dev; do
    if ! command -v $cmd &> /dev/null && ! dpkg -l | grep -q "^ii  $cmd"; then
        MISSING_DEPS+=($cmd)
    fi
done

if [ ${#MISSING_DEPS[@]} -ne 0 ]; then
    echo "❌ Missing dependencies: ${MISSING_DEPS[*]}"
    echo "   Install with: sudo apt-get install -y build-essential bc flex bison libelf-dev wget"
    exit 1
fi

# Create work directory
mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"

# Download kernel source
echo "📥 Downloading kernel source..."
if [ ! -f "linux-${KERNEL_VERSION}.tar.xz" ]; then
    wget -q --show-progress \
        "https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-${KERNEL_VERSION}.tar.xz"
fi

echo "📦 Extracting kernel source..."
tar xf "linux-${KERNEL_VERSION}.tar.xz"
cd "linux-${KERNEL_VERSION}"

# Download Firecracker's recommended kernel config
echo "⚙️  Applying Firecracker kernel configuration..."
wget -q \
    "https://raw.githubusercontent.com/firecracker-microvm/firecracker/main/resources/guest_configs/microvm-kernel-x86_64-5.10.config" \
    -O .config

# Enable vsock support (critical for our implementation)
echo "🔧 Enabling vsock support..."
cat >> .config <<EOF

# Vsock support for host-guest communication
CONFIG_VSOCKETS=y
CONFIG_VSOCKETS_DIAG=y
CONFIG_VIRTIO_VSOCKETS=y
CONFIG_VIRTIO_VSOCKETS_COMMON=y
EOF

# Build kernel
echo "🏗️  Building kernel (this takes 10-30 minutes)..."
echo "   Progress: cores=$(nproc), using $(nproc) parallel jobs"
make vmlinux -j$(nproc)

# Install kernel
echo "📦 Installing kernel..."
sudo mkdir -p "${OUTPUT_DIR}"
sudo cp vmlinux "${OUTPUT_DIR}/vmlinux"
sudo chmod 644 "${OUTPUT_DIR}/vmlinux"

echo ""
echo "✅ Kernel built successfully!"
echo "   Location: ${OUTPUT_DIR}/vmlinux"
echo "   Size: $(du -h ${OUTPUT_DIR}/vmlinux | cut -f1)"
echo ""

# Cleanup
echo "🧹 Cleaning up build directory..."
cd ~
rm -rf "${WORK_DIR}"

echo "📝 Next steps:"
echo "   1. Build rootfs: sudo ./scripts/build-firecracker-rootfs.sh"
echo "   2. Setup host: sudo ./scripts/setup-firecracker-host.sh"
