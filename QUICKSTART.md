# Quick Start Guide - 5 Minutes to Running

## Step 1: Setup (2 minutes)

```bash
# Navigate to project
cd python-sandbox

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Build Sandbox Image (2 minutes)

```bash
# Build the sandbox Docker image
docker build -t python-sandbox:latest sandbox-image/
```

## Step 3: Run Service (1 minute)

```bash
# Start the API service
uvicorn app.main:app --reload
```

**Service is now running at http://localhost:8000** 🎉

## Step 4: Test It!

### Open another terminal and test:

```bash
# Test 1: Health check
curl http://localhost:8000/health

# Test 2: Execute simple code
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(2 + 2)",
    "timeout": 10
  }'

# Expected output:
# {
#   "success": true,
#   "stdout": "4\n",
#   "stderr": "",
#   "exit_code": 0,
#   "execution_time": 0.234,
#   "error": null
# }
```

## Step 5: View API Documentation

Open in browser: http://localhost:8000/docs

Try the interactive API!

---

## Using Docker Compose (Alternative)

Even simpler - one command:

```bash
docker-compose up
```

That's it! Service runs at http://localhost:8000

---

## Quick Examples

### Python Client

```python
import requests

# Execute code
response = requests.post(
    "http://localhost:8000/execute",
    json={
        "code": """
import math
result = math.sqrt(16)
print(f"Square root of 16 is {result}")
        """,
        "timeout": 10
    }
)

print(response.json()["stdout"])
# Output: Square root of 16 is 4.0
```

### Test Security

```bash
# This should FAIL (forbidden import)
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "import os; os.system(\"ls\")",
    "timeout": 10
  }'

# Expected: 400 Bad Request - Validation failed
```

---

## Common Issues

### "Docker image not found"
```bash
# Build the image
docker build -t python-sandbox:latest sandbox-image/
```

### "Permission denied" (Docker)
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### "Port 8000 already in use"
```bash
# Use different port
uvicorn app.main:app --reload --port 8001
```

---

## Next Steps

1. ✅ Read full [README.md](README.md) for detailed documentation
2. ✅ Check [API docs](http://localhost:8000/docs) for all endpoints
3. ✅ Integrate with your AI agent
4. ✅ Deploy to production with Docker Compose

**Happy coding! 🚀**
