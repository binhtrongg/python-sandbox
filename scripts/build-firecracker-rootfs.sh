#!/bin/bash
# Build Firecracker rootfs with Python and guest agent

set -e

ROOTFS_SIZE="2G"
WORK_DIR="/tmp/firecracker-rootfs-build"
OUTPUT_DIR="/var/firecracker"
ROOTFS_IMG="${OUTPUT_DIR}/rootfs.ext4"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔨 Building Firecracker rootfs with guest agent"

# Create work directory
mkdir -p ${WORK_DIR}
cd ${WORK_DIR}

# Create empty ext4 filesystem
echo "📦 Creating empty filesystem (${ROOTFS_SIZE})..."
dd if=/dev/zero of=rootfs.ext4 bs=1M count=2048
mkfs.ext4 rootfs.ext4

# Mount filesystem
mkdir -p rootfs
sudo mount rootfs.ext4 rootfs

# Install Alpine Linux as base (minimal)
echo "📥 Installing Alpine Linux base..."
wget http://dl-cdn.alpinelinux.org/alpine/v3.18/releases/x86_64/alpine-minirootfs-3.18.4-x86_64.tar.gz
sudo tar xzf alpine-minirootfs-3.18.4-x86_64.tar.gz -C rootfs

# Copy guest agent
echo "📋 Installing guest agent..."
sudo mkdir -p rootfs/opt/guest-agent
sudo cp "${PROJECT_ROOT}/firecracker-guest-agent/agent.py" rootfs/opt/guest-agent/
sudo chmod +x rootfs/opt/guest-agent/agent.py

# Chroot and install Python + packages
echo "🐍 Installing Python and packages..."
sudo chroot rootfs /bin/sh <<'EOF'
# Setup Alpine repos
echo "http://dl-cdn.alpinelinux.org/alpine/v3.18/main" > /etc/apk/repositories
echo "http://dl-cdn.alpinelinux.org/alpine/v3.18/community" >> /etc/apk/repositories

# Update and install base tools
apk update
apk add python3 py3-pip

# Install Python packages
pip3 install --no-cache-dir \
    pandas==2.0.3 \
    numpy==1.24.3 \
    openpyxl==3.1.2 \
    matplotlib==3.7.2 \
    scipy==1.11.1 \
    requests==2.31.0

# Create output directory
mkdir -p /tmp/output
chmod 777 /tmp/output

# Create init script that starts guest agent
cat > /sbin/init <<'INIT'
#!/bin/sh

# Mount essential filesystems
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev

# Start guest agent
exec /usr/bin/python3 /opt/guest-agent/agent.py
INIT

chmod +x /sbin/init

# Cleanup
apk cache clean
rm -rf /var/cache/apk/*
EOF

# Unmount
sudo umount rootfs

# Move to output directory
sudo mkdir -p ${OUTPUT_DIR}
sudo mv rootfs.ext4 ${ROOTFS_IMG}
sudo chmod 644 ${ROOTFS_IMG}

echo "✅ Rootfs built successfully: ${ROOTFS_IMG}"
echo "   Size: $(du -h ${ROOTFS_IMG} | cut -f1)"
echo "   Guest agent: /opt/guest-agent/agent.py"

# Cleanup
cd ~
rm -rf ${WORK_DIR}
