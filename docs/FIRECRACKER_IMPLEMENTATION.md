# Firecracker Executor Implementation Guide

## 🎯 Overview

This document provides a complete guide to implementing the Firecracker executor for ultra-fast, secure Python code execution.

## 📋 Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+ or Amazon Linux 2)
- **CPU**: x86_64 with KVM support
- **Memory**: 4GB+ RAM
- **Disk**: 10GB+ free space
- **Permissions**: Root/sudo access for setup

### Software Requirements
- Firecracker binary (v1.0+)
- Linux kernel 4.14+
- KVM enabled
- Python 3.11+
- Build tools (gcc, make, etc.)

### Check Prerequisites
```bash
# Check KVM support
lsmod | grep kvm
# Should show: kvm_intel or kvm_amd

# Check CPU virtualization
egrep -c '(vmx|svm)' /proc/cpuinfo
# Should return > 0

# Check /dev/kvm exists
ls -l /dev/kvm
# Should exist with permissions
```

---

## 🏗️ Architecture

### Firecracker microVM Structure
```
Host Machine
└── Firecracker Process (per execution)
    ├── VMM (Virtual Machine Monitor)
    ├── microVM Instance
    │   ├── Custom Linux Kernel (vmlinux)
    │   ├── Root Filesystem (rootfs.ext4)
    │   │   ├── Python 3.11
    │   │   ├── pandas, numpy, etc.
    │   │   ├── Guest Agent (/opt/guest-agent/agent.py)
    │   │   └── /tmp/output/ directory
    │   └── Vsock Communication (Port 5000)
    ├── API Socket (/tmp/firecracker-<id>.sock)
    └── Vsock Socket (/tmp/firecracker/<vm-id>.vsock)
```

### Execution Flow
1. **Prepare**: Create VM configuration JSON
2. **Start**: Launch Firecracker process with socket
3. **Configure**: Send VM config via API (kernel, rootfs, resources, vsock)
4. **Boot**: Start microVM instance (guest agent auto-starts)
5. **Execute**: Send Python code via vsock to guest agent
6. **Extract**: Request files from guest via vsock
7. **Cleanup**: Kill Firecracker process, remove socket

---

## 📦 Part 1: Build Custom Linux Kernel

### Why Custom Kernel?
Firecracker requires a minimal, uncompressed Linux kernel (vmlinux) optimized for fast boot times.

### Build Script
```bash
#!/bin/bash
# scripts/build-firecracker-kernel.sh

set -e

KERNEL_VERSION="5.10.198"
WORK_DIR="/tmp/firecracker-kernel-build"
OUTPUT_DIR="/var/firecracker"

echo "🔨 Building Firecracker kernel v${KERNEL_VERSION}"

# Create work directory
mkdir -p ${WORK_DIR}
cd ${WORK_DIR}

# Download kernel source
echo "📥 Downloading kernel source..."
wget https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-${KERNEL_VERSION}.tar.xz
tar xf linux-${KERNEL_VERSION}.tar.xz
cd linux-${KERNEL_VERSION}

# Download Firecracker's recommended kernel config
echo "⚙️  Applying Firecracker kernel configuration..."
wget https://raw.githubusercontent.com/firecracker-microvm/firecracker/main/resources/guest_configs/microvm-kernel-x86_64-5.10.config -O .config

# Build kernel
echo "🏗️  Building kernel (this takes 10-30 minutes)..."
make vmlinux -j$(nproc)

# Copy kernel to output directory
echo "📦 Installing kernel..."
sudo mkdir -p ${OUTPUT_DIR}
sudo cp vmlinux ${OUTPUT_DIR}/vmlinux
sudo chmod 644 ${OUTPUT_DIR}/vmlinux

echo "✅ Kernel built successfully: ${OUTPUT_DIR}/vmlinux"
echo "   Size: $(du -h ${OUTPUT_DIR}/vmlinux | cut -f1)"

# Cleanup
cd ~
rm -rf ${WORK_DIR}
```

**Usage**:
```bash
chmod +x scripts/build-firecracker-kernel.sh
./scripts/build-firecracker-kernel.sh
```

**Output**: `/var/firecracker/vmlinux` (~30-50MB)

---

## 📦 Part 2: Build Root Filesystem

### Why Custom Rootfs?
Need a minimal filesystem with:
- Python 3.11 and required packages (pandas, numpy, openpyxl, etc.)
- Guest agent for host-VM communication via vsock
- Auto-start agent on boot

### Build Script
See `scripts/build-firecracker-rootfs.sh` for the complete build script.

**Key Steps**:
1. Create 2GB ext4 filesystem
2. Install Alpine Linux minimal base
3. Install Python 3.11 and packages (pandas, numpy, openpyxl, etc.)
4. Copy guest agent (`firecracker-guest-agent/agent.py`) to `/opt/guest-agent/`
5. Create init script that:
   - Mounts essential filesystems (proc, sys, dev)
   - Starts guest agent listening on vsock port 5000
6. Cleanup and unmount

**Guest Agent**:
- Listens on vsock port 5000 for connections from host
- Handles actions: `execute` (run Python code), `list_files`, `get_file`
- Runs code in `/tmp/output` directory
- Returns stdout/stderr/exit_code to host
- Sends file contents on request

**Usage**:
```bash
chmod +x scripts/build-firecracker-rootfs.sh
sudo ./scripts/build-firecracker-rootfs.sh
```

**Output**:
- `/var/firecracker/rootfs.ext4` (~1-2GB)
- Contains guest agent at `/opt/guest-agent/agent.py`
- Auto-starts on boot via `/sbin/init`

---

## 🔧 Part 3: Install Firecracker Binary

### Download and Install
```bash
#!/bin/bash
# scripts/install-firecracker.sh

set -e

FIRECRACKER_VERSION="v1.5.0"
ARCH="x86_64"

echo "📥 Installing Firecracker ${FIRECRACKER_VERSION}"

# Download release
wget https://github.com/firecracker-microvm/firecracker/releases/download/${FIRECRACKER_VERSION}/firecracker-${FIRECRACKER_VERSION}-${ARCH}.tgz

# Extract
tar -xzf firecracker-${FIRECRACKER_VERSION}-${ARCH}.tgz

# Install binary
sudo mv release-${FIRECRACKER_VERSION}-${ARCH}/firecracker-${FIRECRACKER_VERSION}-${ARCH} /usr/local/bin/firecracker
sudo chmod +x /usr/local/bin/firecracker

# Verify
firecracker --version

echo "✅ Firecracker installed successfully"

# Cleanup
rm -rf release-${FIRECRACKER_VERSION}-${ARCH}* firecracker-${FIRECRACKER_VERSION}-${ARCH}.tgz
```

**Usage**:
```bash
chmod +x scripts/install-firecracker.sh
./scripts/install-firecracker.sh
```

---

## ⚙️ Part 4: Setup Host Environment

### Configure KVM Permissions
```bash
#!/bin/bash
# scripts/setup-firecracker-host.sh

set -e

echo "⚙️  Setting up Firecracker host environment"

# Check KVM exists
if [ ! -e /dev/kvm ]; then
    echo "❌ ERROR: /dev/kvm not found. KVM is required for Firecracker."
    echo "   Enable virtualization in BIOS and install kvm module"
    exit 1
fi

# Set KVM permissions
sudo chmod 666 /dev/kvm
echo "✅ KVM permissions configured"

# Create Firecracker directories
sudo mkdir -p /var/firecracker
sudo mkdir -p /tmp/firecracker-sockets
sudo chmod 755 /var/firecracker
sudo chmod 777 /tmp/firecracker-sockets
echo "✅ Firecracker directories created"

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt-get update
sudo apt-get install -y curl wget iproute2

echo "✅ Host environment setup complete"
```

**Usage**:
```bash
chmod +x scripts/setup-firecracker-host.sh
sudo ./scripts/setup-firecracker-host.sh
```

---

## 🐍 Part 5: Implement Firecracker Executor

See `app/executors/firecracker.py` for full implementation.

### Key Implementation Points

#### 1. VM Configuration with vsock
```python
async def _configure_vm(self, socket_path: str, vm_id: str):
    # Configure boot source, drives, machine resources
    # Configure vsock for host-guest communication
    vsock_config = {
        "guest_cid": 3,  # Guest context ID
        "uds_path": f"{self.socket_path}/{vm_id}.vsock"
    }
    # PUT /vsock
```

#### 2. Execute Code via vsock
```python
async def _execute_code_in_vm(self, vm_id: str, code: str, timeout: int):
    # Connect to vsock Unix socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(vsock_path)

    # Send execution request as JSON
    request = {"action": "execute", "code": code, "timeout": timeout}
    sock.sendall(struct.pack('!I', len(request_data)) + request_data)

    # Receive response
    response = recv_json_response(sock)
    return response  # {success, stdout, stderr, exit_code}
```

#### 3. Extract Files via vsock
```python
async def _extract_files(self, vm_id: str):
    # Request file list from guest
    request = {"action": "list_files", "path": "/tmp/output"}
    files = send_request(sock, request)

    # Download each file
    for filename in files:
        file_request = {"action": "get_file", "path": f"/tmp/output/{filename}"}
        file_data = send_request(sock, file_request)
        # Upload to storage
```

#### 4. Guest Agent (runs inside VM)
```python
# firecracker-guest-agent/agent.py
class GuestAgent:
    def run(self):
        # Listen on vsock port 5000
        sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
        sock.bind((socket.VMADDR_CID_ANY, 5000))

        # Handle requests: execute, list_files, get_file
        while True:
            conn, addr = sock.accept()
            self.handle_request(conn)
```

---

## 🧪 Testing

### Test Script
```bash
# Test kernel and rootfs exist
ls -lh /var/firecracker/vmlinux
ls -lh /var/firecracker/rootfs.ext4

# Test Firecracker binary
firecracker --version

# Test KVM access
test -r /dev/kvm && test -w /dev/kvm && echo "KVM OK" || echo "KVM FAIL"

# Test Python execution
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"code":"print(\"Firecracker test!\")"}'
```

---

## 📊 Performance Benchmarks

Expected performance improvements over Docker:

| Metric | Docker | Firecracker | Improvement |
|--------|---------|-------------|-------------|
| Cold Start | 1-2s | ~125ms | **8-16x faster** |
| Memory/Instance | 10-50MB | ~5MB | **2-10x less** |
| Max Instances | 100-200 | 1000+ | **5-10x more** |

---

## 🔒 Security

Firecracker provides:
- Hardware-level isolation (KVM)
- Minimal attack surface
- No network by default
- Read-only kernel
- Process isolation

---

## 🐛 Troubleshooting

### Common Issues

**KVM not available**:
```bash
# Check virtualization enabled
egrep -c '(vmx|svm)' /proc/cpuinfo

# Load KVM module
sudo modprobe kvm_intel  # or kvm_amd
```

**Permission denied on /dev/kvm**:
```bash
sudo chmod 666 /dev/kvm
# Or add user to kvm group
sudo usermod -aG kvm $USER
```

**Firecracker socket timeout**:
```bash
# Check Firecracker process running
ps aux | grep firecracker

# Check socket exists
ls -l /tmp/firecracker-sockets/
```

---

## 📚 References

- [Firecracker GitHub](https://github.com/firecracker-microvm/firecracker)
- [Getting Started Guide](https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md)
- [API Documentation](https://github.com/firecracker-microvm/firecracker/blob/main/src/api_server/swagger/firecracker.yaml)

---

**Status**: Implementation guide ready
**Estimated Time**: 15-20 hours total
**Prerequisites**: Linux with KVM
