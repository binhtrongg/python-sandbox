#!/bin/bash
# Complete Firecracker setup (all steps)
# Run this on a fresh Linux server to setup everything

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔥 Firecracker Complete Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This will:"
echo "  1. Install Firecracker binary (~2 min)"
echo "  2. Build Linux kernel (~20 min)"
echo "  3. Build rootfs with Python + guest agent (~20 min)"
echo "  4. Setup host environment (~1 min)"
echo ""
echo "Total time: ~40-45 minutes"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

# Check if running on Linux
if [ "$(uname -s)" != "Linux" ]; then
    echo "❌ ERROR: This script only works on Linux"
    echo "   Current OS: $(uname -s)"
    exit 1
fi

START_TIME=$(date +%s)

# Step 1: Install Firecracker
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1/4: Installing Firecracker binary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
"${SCRIPT_DIR}/install-firecracker.sh"

# Step 2: Build kernel
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2/4: Building Linux kernel"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
"${SCRIPT_DIR}/build-firecracker-kernel.sh"

# Step 3: Build rootfs
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3/4: Building rootfs with Python + guest agent"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo "${SCRIPT_DIR}/build-firecracker-rootfs.sh"

# Step 4: Setup host
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4/4: Setting up host environment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo "${SCRIPT_DIR}/setup-firecracker-host.sh"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Firecracker setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⏱️  Total time: ${MINUTES}m ${SECONDS}s"
echo ""
echo "📝 Next steps:"
echo ""
echo "   1. Enable Firecracker executor:"
echo "      echo 'EXECUTOR_PROVIDER=firecracker' >> .env"
echo "      echo 'EXECUTOR_FALLBACK_PROVIDERS=docker' >> .env"
echo ""
echo "   2. Start the service:"
echo "      docker-compose up --build"
echo ""
echo "   3. Test execution:"
echo "      curl -X POST http://localhost:8000/execute \\"
echo "        -H 'Content-Type: application/json' \\"
echo "        -d '{\"code\":\"print(123)\"}'"
echo ""
echo "   4. Check health:"
echo "      curl http://localhost:8000/health"
echo "      # Should show: \"executor\": { \"provider\": \"firecracker\" }"
echo ""
