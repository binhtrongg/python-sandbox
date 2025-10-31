# Python Sandbox Service

A secure, isolated Python code execution sandbox designed for AI agents and automation tools.

## 🎯 Features

- ✅ **Multiple Executors**: Docker (default) + Firecracker (8-16x faster on Linux)
- ✅ **Secure Execution**: Hardware-level isolation with resource limits
- ✅ **Code Validation**: Syntax and security checks before execution
- ✅ **Resource Limits**: CPU, memory, timeout, and output size controls
- ✅ **File Storage**: Cloudflare R2 storage with presigned download URLs (5-hour expiration)
- ✅ **AI-Agent Ready**: Simple REST API for easy integration
- ✅ **Extensible**: Provider pattern for easy executor addition
- ✅ **Production Ready**: Error handling, logging, health checks, automatic fallback

## 🏗️ Architecture

```
AI Agent → FastAPI → Validator → Executor Factory → [Docker | Firecracker]
                                        ↓
                                  Auto Fallback
```

**Components:**
- **FastAPI**: REST API with OpenAPI documentation
- **Validator**: AST-based code validation for security
- **Executor Factory**: Provider pattern with automatic health checks and fallback
- **Docker Executor**: Container-based isolation (works everywhere)
- **Firecracker Executor**: MicroVM-based isolation (Linux only, 8-16x faster)
- **Resource Monitor**: CPU, memory, and timeout enforcement

**Performance:**
| Executor | Startup | Memory | Max Concurrent | Platform |
|----------|---------|--------|----------------|----------|
| Docker | 1-2s | 10-50MB | 100-200 | All |
| Firecracker | ~125ms | ~5MB | 1000+ | Linux+KVM |

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker Engine
- 2GB RAM minimum

### Installation

```bash
# 1. Clone repository
git clone <your-repo>
cd python-sandbox

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Build sandbox image
cd sandbox-image
docker build -t python-sandbox:latest .
cd ..

# 5. Run service
uvicorn app.main:app --reload
```

Service will be available at `http://localhost:8000`

### Using Docker Compose (Recommended)

```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

## 📡 API Usage

### Execute Code

**Endpoint:** `POST /execute`

**Request:**
```json
{
  "code": "print('Hello, World!')",
  "timeout": 10
}
```

**Response:**
```json
{
  "success": true,
  "stdout": "Hello, World!\n",
  "stderr": "",
  "exit_code": 0,
  "execution_time": 0.234,
  "error": null,
  "files": []
}
```

### File Output Example

**Request:**
```json
{
  "code": "import pandas as pd\ndf = pd.DataFrame([{'name': 'Alice', 'age': 25}])\ndf.to_excel('/tmp/output/data.xlsx', index=False)\nprint('File created!')"
}
```

**Response:**
```json
{
  "success": true,
  "stdout": "File created!\n",
  "stderr": "",
  "exit_code": 0,
  "execution_time": 1.042,
  "error": null,
  "files": [
    "https://your-r2-bucket.r2.cloudflarestorage.com/.../data.xlsx?...&X-Amz-Expires=18000"
  ]
}
```

**Note:** Files must be written to `/tmp/output/` directory to be captured. Presigned URLs expire after 5 hours.

### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "executor": {
    "provider": "docker",
    "name": "docker",
    "healthy": true,
    "fallbacks": "docker",
    "available_providers": ["docker", "firecracker"],
    "active_providers": ["docker"]
  }
}
```

## 🔌 Integration Examples

### Python

```python
import requests

response = requests.post(
    "http://localhost:8000/execute",
    json={
        "code": "result = 2 + 2\nprint(result)",
        "timeout": 10
    }
)

result = response.json()
print(result["stdout"])  # "4"
```

### cURL

```bash
# Simple execution
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(2 + 2)",
    "timeout": 10
  }'

# Create Excel file
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"code":"import pandas as pd\ndf=pd.DataFrame([{\"name\":\"Alice\",\"age\":25}])\ndf.to_excel(\"/tmp/output/data.xlsx\",index=False)\nprint(\"Done!\")"}'
```

### JavaScript/TypeScript

```typescript
const response = await fetch('http://localhost:8000/execute', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    code: "print('hello')",
    timeout: 10
  })
});

const result = await response.json();
console.log(result.stdout);
```

## 🛡️ Security Features

### Code Validation

- **Syntax Check**: AST parsing to catch syntax errors
- **Import Check**: Blocks dangerous modules (os, subprocess, socket, etc.)
- **Complexity Check**: Prevents overly complex code
- **Pattern Detection**: Identifies infinite loops and dangerous patterns

### Execution Isolation

- **Network Disabled**: No outbound network access
- **Isolated Filesystem**: Code can only write to `/tmp/output/` directory
- **Resource Limits**: CPU, memory, PIDs, timeout enforcement
- **Non-Root User**: Execution as unprivileged user
- **Security Options**: no-new-privileges, capabilities dropped
- **File Limits**: 10MB per file, 50MB total, max 10 files

### Forbidden Modules

The following modules are blocked by default:
- `os`, `subprocess` - System commands
- `socket`, `sys` - Network and system access
- `importlib`, `ctypes` - Dynamic imports
- `multiprocessing`, `threading` - Process/thread creation

## ⚙️ Configuration

Create `.env` file (see `.env.example`):

```bash
# Application
APP_NAME=Python Sandbox
DEBUG=false
PORT=8000

# Executor Provider
EXECUTOR_PROVIDER=docker  # docker (default) or firecracker (Linux only)
EXECUTOR_FALLBACK_PROVIDERS=docker  # Comma-separated fallback chain

# Docker Configuration
DOCKER_IMAGE=python-sandbox:latest
DOCKER_TIMEOUT=30
DOCKER_MEMORY=128m
DOCKER_CPU_QUOTA=50000

# Firecracker Configuration (Linux with KVM only)
FIRECRACKER_KERNEL_PATH=/var/firecracker/vmlinux
FIRECRACKER_ROOTFS_PATH=/var/firecracker/rootfs.ext4
FIRECRACKER_SOCKET_PATH=/tmp/firecracker
FIRECRACKER_MEMORY_MB=128
FIRECRACKER_VCPU_COUNT=1

# Security
MAX_CODE_LENGTH=50000
FORBIDDEN_IMPORTS=os,subprocess,socket,sys

# File Extraction Limits
MAX_FILE_SIZE=10485760  # 10MB per file
MAX_TOTAL_SIZE=52428800  # 50MB total
MAX_FILE_COUNT=10  # Max files to extract

# Output Limits
MAX_OUTPUT_SIZE=10240

# Storage (optional)
STORAGE_ENABLED=true
STORAGE_PROVIDER=r2
STORAGE_R2_BUCKET=your-bucket
STORAGE_R2_ACCOUNT_ID=your-account-id
STORAGE_R2_ACCESS_KEY=your-access-key
STORAGE_R2_SECRET_KEY=your-secret-key
```

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest

# Run specific test file
pytest tests/test_validator.py

# Run with coverage
pytest --cov=app tests/
```

## 📚 Documentation

### API Documentation
Interactive API documentation available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Implementation Guides
- **Firecracker Setup**: `docs/FIRECRACKER_IMPLEMENTATION.md`
- **Vsock Protocol**: `docs/VSOCK_PROTOCOL.md`
- **Scripts**: `scripts/` directory

## 🔧 Customization

### Adding Allowed Python Packages

Edit `sandbox-image/Dockerfile`:

```dockerfile
RUN pip install --no-cache-dir \
    numpy==1.24.3 \
    pandas==2.0.3 \
    your-package==1.0.0
```

Rebuild sandbox image:
```bash
docker build -t python-sandbox:latest sandbox-image/
```

### Adding New Executor

Create new executor using the provider pattern:

```python
# app/executors/gvisor.py
from app.executors.base import BaseExecutor
from app.executors.factory import ExecutorRegistry

@ExecutorRegistry.register("gvisor")
class GVisorExecutor(BaseExecutor):
    async def execute(self, code: str, timeout: int):
        # Your implementation
        pass

    async def health_check(self) -> bool:
        # Health check logic
        return True

    def cleanup(self) -> None:
        # Cleanup resources
        pass

    def get_name(self) -> str:
        return "gvisor"
```

Then enable in `.env`:
```bash
EXECUTOR_PROVIDER=gvisor
EXECUTOR_FALLBACK_PROVIDERS=docker
```

### Adding Middleware

Add custom middleware to `app/main.py`:

```python
@app.middleware("http")
async def custom_middleware(request: Request, call_next):
    # Your logic here
    response = await call_next(request)
    return response
```

## 🚀 Deployment

### Docker Deployment (Quick)

```bash
# Build and run with Docker Compose
docker-compose up --build -d

# Scale horizontally
docker-compose up --scale api=3
```

### Firecracker Deployment (Linux Only)

For 8-16x faster execution on Linux:

```bash
# 1. Complete setup (~40 minutes, one-time)
./scripts/setup-firecracker-full.sh

# 2. Enable Firecracker
echo "EXECUTOR_PROVIDER=firecracker" >> .env
echo "EXECUTOR_FALLBACK_PROVIDERS=docker" >> .env

# 3. Start
docker-compose up --build
```

**See**: `docs/FIRECRACKER_IMPLEMENTATION.md` for detailed setup instructions.

### Cloud Deployment

**Recommended Instances:**
- **AWS EC2**: t3.medium (2 vCPU, 4GB RAM)
- **DigitalOcean**: Basic (2 vCPU, 4GB RAM)
- **Hetzner**: CPX21 (3 vCPU, 4GB RAM, €8.50/month)

```bash
# On Linux server
git clone <repo>
cd python-sandbox

# Option 1: Docker only (works immediately)
docker-compose up --build -d

# Option 2: Firecracker (40min setup, 8-16x faster)
./scripts/setup-firecracker-full.sh
echo "EXECUTOR_PROVIDER=firecracker" >> .env
docker-compose up --build -d
```

### Scaling

**Docker Executor:**
- Small (2 vCPU, 4GB): ~50 concurrent executions
- Medium (4 vCPU, 8GB): ~200 concurrent executions

**Firecracker Executor:**
- Small (2 vCPU, 4GB): ~200 concurrent executions
- Medium (4 vCPU, 8GB): ~500 concurrent executions
- Large (8 vCPU, 16GB): ~1000+ concurrent executions

## 📊 Monitoring

### Health Checks

```bash
# Check service health
curl http://localhost:8000/health

# Docker healthcheck
docker inspect --format='{{.State.Health.Status}}' container_name
```

### Logs

```bash
# View logs
docker-compose logs -f api

# Follow specific service
docker-compose logs -f api | grep ERROR
```

## 🔄 Implemented Features & Future Enhancements

### ✅ Completed (Phase 1 & 2)
- [x] **Provider Pattern Architecture** - Self-registering executors
- [x] **Docker Executor** - Container-based isolation
- [x] **Firecracker Executor** - MicroVM with vsock communication
- [x] **Guest Agent** - Production-grade host-VM communication
- [x] **File Extraction** - Optimized /tmp/output extraction
- [x] **Presigned URLs** - 5-hour expiration, forced downloads
- [x] **Automatic Fallback** - Health checks with graceful degradation
- [x] **File Size Limits** - 10MB/file, 50MB total, 10 files max

### 📝 Future Enhancements (Phase 3)
- [ ] API key authentication
- [ ] Rate limiting (Redis-based)
- [ ] Request logging and metrics collection
- [ ] Prometheus metrics export
- [ ] VM pooling (Firecracker)
- [ ] Additional executors (gVisor, Kata Containers)
- [ ] Async job queue
- [ ] Container/VM warm pools

## 🐛 Troubleshooting

### Docker Image Not Found

```bash
# Build sandbox image
docker build -t python-sandbox:latest sandbox-image/
```

### Permission Denied (Docker Socket)

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Restart session
newgrp docker
```

### Container Timeout

Increase timeout in `.env`:
```bash
DOCKER_TIMEOUT=60
```

### Firecracker Not Working (Linux Only)

```bash
# Check KVM availability
ls -l /dev/kvm
# Should show: crw-rw-rw- 1 root kvm

# Check CPU virtualization
egrep -c '(vmx|svm)' /proc/cpuinfo
# Should return > 0

# Enable KVM module
sudo modprobe kvm_intel  # Intel CPUs
# or
sudo modprobe kvm_amd    # AMD CPUs

# Fix permissions
sudo chmod 666 /dev/kvm

# Verify kernel and rootfs
ls -lh /var/firecracker/
# Should show vmlinux and rootfs.ext4

# Re-run setup if needed
sudo ./scripts/setup-firecracker-host.sh
```

**Note**: Firecracker only works on Linux with KVM. On macOS/Windows, use Docker executor.

## 📝 License

MIT License - see LICENSE file

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Submit pull request

## 📧 Support

For issues and questions:
- GitHub Issues: [binhtrongg/python-sandbox/issues](https://github.com/binhtrongg/python-sandbox/issues)
- Documentation: http://localhost:8000/docs

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Docker](https://www.docker.com/) - Container platform
- [Firecracker](https://firecracker-microvm.github.io/) - Secure microVM technology
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [Cloudflare R2](https://www.cloudflare.com/products/r2/) - Object storage

---

**Made with ❤️ for AI Agents**
