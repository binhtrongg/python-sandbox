#!/bin/bash
# Setup host environment for Firecracker

set -e

echo "⚙️  Setting up Firecracker host environment"
echo ""

# Check if running on Linux
if [ "$(uname -s)" != "Linux" ]; then
    echo "❌ ERROR: Firecracker only works on Linux"
    echo "   Current OS: $(uname -s)"
    exit 1
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# 1. Check KVM availability
echo "🔍 Checking KVM support..."
if [ ! -e /dev/kvm ]; then
    echo "❌ ERROR: /dev/kvm not found"
    echo ""
    echo "   KVM is required for Firecracker. Please:"
    echo "   1. Enable virtualization in BIOS/UEFI"
    echo "   2. Load KVM module:"
    echo "      - Intel: sudo modprobe kvm_intel"
    echo "      - AMD: sudo modprobe kvm_amd"
    echo ""
    exit 1
fi

# Check CPU virtualization support
if ! egrep -c '(vmx|svm)' /proc/cpuinfo > /dev/null 2>&1; then
    echo "⚠️  WARNING: CPU virtualization extensions not detected"
    echo "   Enable VT-x/AMD-V in BIOS/UEFI"
fi

echo "✅ KVM available: /dev/kvm"

# 2. Set KVM permissions
echo "🔧 Configuring KVM permissions..."
chmod 666 /dev/kvm
echo "✅ KVM permissions configured (rw-rw-rw-)"

# 3. Create Firecracker directories
echo "📁 Creating Firecracker directories..."
mkdir -p /var/firecracker
mkdir -p /tmp/firecracker
chmod 755 /var/firecracker
chmod 777 /tmp/firecracker
echo "✅ Directories created:"
echo "   - /var/firecracker (kernel & rootfs)"
echo "   - /tmp/firecracker (runtime sockets)"

# 4. Install system dependencies
echo "📦 Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    curl \
    wget \
    iproute2 \
    ca-certificates \
    > /dev/null 2>&1
echo "✅ System dependencies installed"

# 5. Check kernel and rootfs
echo ""
echo "🔍 Checking Firecracker components..."

KERNEL_PATH="/var/firecracker/vmlinux"
ROOTFS_PATH="/var/firecracker/rootfs.ext4"

if [ -f "$KERNEL_PATH" ]; then
    echo "✅ Kernel found: $KERNEL_PATH ($(du -h $KERNEL_PATH | cut -f1))"
else
    echo "⚠️  Kernel not found: $KERNEL_PATH"
    echo "   Run: ./scripts/build-firecracker-kernel.sh"
fi

if [ -f "$ROOTFS_PATH" ]; then
    echo "✅ Rootfs found: $ROOTFS_PATH ($(du -h $ROOTFS_PATH | cut -f1))"
else
    echo "⚠️  Rootfs not found: $ROOTFS_PATH"
    echo "   Run: sudo ./scripts/build-firecracker-rootfs.sh"
fi

# 6. Check Firecracker binary
echo ""
if command -v firecracker &> /dev/null; then
    echo "✅ Firecracker installed: $(firecracker --version 2>&1 | head -n1)"
else
    echo "⚠️  Firecracker not found"
    echo "   Run: ./scripts/install-firecracker.sh"
fi

# 7. Setup automatic KVM permissions on boot
echo ""
echo "🔧 Setting up automatic KVM permissions..."
UDEV_RULE="/etc/udev/rules.d/99-kvm.rules"
if [ ! -f "$UDEV_RULE" ]; then
    cat > "$UDEV_RULE" <<EOF
# Allow all users to access /dev/kvm for Firecracker
KERNEL=="kvm", GROUP="kvm", MODE="0666"
EOF
    udevadm control --reload-rules
    udevadm trigger
    echo "✅ Udev rule created: $UDEV_RULE"
else
    echo "ℹ️  Udev rule already exists: $UDEV_RULE"
fi

# 8. Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Firecracker host setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Configuration:"
echo "   KVM device: /dev/kvm (rw-rw-rw-)"
echo "   Kernel: $KERNEL_PATH"
echo "   Rootfs: $ROOTFS_PATH"
echo "   Socket directory: /tmp/firecracker"
echo ""

# Check if everything is ready
ALL_READY=true
[ -f "$KERNEL_PATH" ] || ALL_READY=false
[ -f "$ROOTFS_PATH" ] || ALL_READY=false
command -v firecracker &> /dev/null || ALL_READY=false

if [ "$ALL_READY" = true ]; then
    echo "🎉 All components ready! You can now:"
    echo ""
    echo "   # Enable Firecracker executor"
    echo "   echo 'EXECUTOR_PROVIDER=firecracker' >> .env"
    echo "   echo 'EXECUTOR_FALLBACK_PROVIDERS=docker' >> .env"
    echo ""
    echo "   # Start the service"
    echo "   docker-compose up --build"
    echo ""
    echo "   # Test"
    echo "   curl -X POST http://localhost:8000/execute \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"code\":\"print(123)\"}'"
else
    echo "⚠️  Some components missing. Please run:"
    [ ! -f "$KERNEL_PATH" ] && echo "   - ./scripts/build-firecracker-kernel.sh"
    [ ! -f "$ROOTFS_PATH" ] && echo "   - sudo ./scripts/build-firecracker-rootfs.sh"
    command -v firecracker &> /dev/null || echo "   - ./scripts/install-firecracker.sh"
fi

echo ""
