# Vsock Communication Protocol

## Overview

Communication between Firecracker host and guest VM uses **vsock** (Virtual Socket) - a socket interface designed specifically for host-guest communication in virtualized environments.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Host (Python FastAPI)                                       │
│                                                              │
│  FirecrackerExecutor                                        │
│       │                                                      │
│       │ 1. Start Firecracker Process                        │
│       │ 2. Configure vsock via API                          │
│       │                                                      │
│       v                                                      │
│  Unix Socket: /tmp/firecracker/<vm-id>.vsock                │
│       │                                                      │
│       │ 3. Send JSON requests                               │
│       │    (execute, list_files, get_file)                  │
│       │                                                      │
│       v                                                      │
└───────┼──────────────────────────────────────────────────────┘
        │
        │ Vsock Bridge (Firecracker VMM)
        │
┌───────┼──────────────────────────────────────────────────────┐
│       v                                                      │
│  Vsock Socket (CID=3, Port=5000)                            │
│       │                                                      │
│       v                                                      │
│  Guest Agent (/opt/guest-agent/agent.py)                    │
│       │                                                      │
│       │ 4. Handle requests                                  │
│       │    - execute: Run Python code                       │
│       │    - list_files: List /tmp/output                   │
│       │    - get_file: Send file content                    │
│       │                                                      │
│       v                                                      │
│  Python Subprocess                                          │
│  Working dir: /tmp/output                                   │
│                                                              │
│ Guest (microVM - Alpine Linux)                              │
└─────────────────────────────────────────────────────────────┘
```

## Protocol Details

### Message Format

All messages use **length-prefixed JSON**:

```
[4 bytes: length (uint32, network byte order)]
[N bytes: JSON payload (UTF-8)]
```

**Example**:
```python
# Send
data = json.dumps({"action": "execute", "code": "print(123)"}).encode('utf-8')
sock.sendall(struct.pack('!I', len(data)) + data)

# Receive
length_bytes = recv_exact(sock, 4)
length = struct.unpack('!I', length_bytes)[0]
payload = recv_exact(sock, length)
response = json.loads(payload.decode('utf-8'))
```

### Request Types

#### 1. Execute Code

**Request**:
```json
{
  "action": "execute",
  "code": "import pandas as pd\nprint(pd.__version__)",
  "timeout": 30
}
```

**Response**:
```json
{
  "success": true,
  "stdout": "2.0.3\n",
  "stderr": "",
  "exit_code": 0
}
```

#### 2. List Files

**Request**:
```json
{
  "action": "list_files",
  "path": "/tmp/output"
}
```

**Response**:
```json
{
  "files": ["output.csv", "report.xlsx"]
}
```

#### 3. Get File

**Request**:
```json
{
  "action": "get_file",
  "path": "/tmp/output/output.csv"
}
```

**Response** (binary):
```
[4 bytes: file size (uint32)]
[N bytes: file content (raw bytes)]
```

## Implementation Details

### Host Side (FirecrackerExecutor)

**1. Configure vsock**:
```python
vsock_config = {
    "guest_cid": 3,  # Guest context ID
    "uds_path": f"/tmp/firecracker/{vm_id}.vsock"
}
# PUT to Firecracker API /vsock endpoint
```

**2. Wait for guest agent**:
```python
async def _wait_for_guest_agent(vsock_path, timeout=10):
    # Wait for Unix socket to exist
    # Try connecting to verify agent is ready
```

**3. Send requests**:
```python
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(vsock_path)
sock.settimeout(timeout)

# Send request with length prefix
request_data = json.dumps(request).encode('utf-8')
sock.sendall(struct.pack('!I', len(request_data)) + request_data)

# Receive response
response_length = struct.unpack('!I', recv_exact(sock, 4))[0]
response_data = recv_exact(sock, response_length)
response = json.loads(response_data.decode('utf-8'))
```

### Guest Side (Guest Agent)

**1. Start vsock listener**:
```python
sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
sock.bind((socket.VMADDR_CID_ANY, 5000))  # Listen on port 5000
sock.listen(5)

while True:
    conn, addr = sock.accept()
    handle_connection(conn)
```

**2. Handle requests**:
```python
def handle_request(conn):
    # Receive request with length prefix
    length = struct.unpack('!I', recv_exact(conn, 4))[0]
    request_data = recv_exact(conn, length)
    request = json.loads(request_data.decode('utf-8'))

    # Dispatch based on action
    if request['action'] == 'execute':
        result = subprocess.run([sys.executable, '-c', request['code']], ...)
        response = {'success': result.returncode == 0, ...}
        send_response(conn, response)

    elif request['action'] == 'list_files':
        files = list(Path(request['path']).iterdir())
        response = {'files': [f.name for f in files]}
        send_response(conn, response)

    elif request['action'] == 'get_file':
        content = Path(request['path']).read_bytes()
        conn.sendall(struct.pack('!I', len(content)) + content)
```

## Boot Sequence

1. **Firecracker starts** (host)
2. **VM boots** with custom kernel and rootfs
3. **Init script runs** (`/sbin/init`)
   - Mounts proc, sys, dev
   - Starts guest agent: `exec python3 /opt/guest-agent/agent.py`
4. **Guest agent listens** on vsock port 5000
5. **Host connects** via Unix socket mapped to vsock
6. **Communication begins** - host sends requests, guest responds

## Error Handling

### Timeouts
- **Connection timeout**: 10s for guest agent to be ready
- **Execution timeout**: User-specified (default 30s)
- **File transfer timeout**: 30s per file

### Retries
- **No automatic retries** - fail fast and report error
- Host handles errors gracefully and reports to user

### Cleanup
- Always close sockets after use
- Kill Firecracker process on error
- Remove Unix socket files

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| VM boot + agent start | ~500ms | One-time per execution |
| vsock connection | <10ms | Fast, local Unix socket |
| Code execution | Variable | Depends on user code |
| File transfer (1MB) | ~50ms | Fast, memory-to-memory |

## Security

1. **Isolation**: VM cannot access host filesystem (except via vsock)
2. **No network**: Guest has no network access by default
3. **Timeout protection**: All operations have timeouts
4. **Size limits**: File size limits enforced on host
5. **Process isolation**: Each execution gets fresh VM

## Debugging

**Host side**:
```bash
# Check if vsock socket exists
ls -l /tmp/firecracker/*.vsock

# Try connecting manually
socat - UNIX-CONNECT:/tmp/firecracker/<vm-id>.vsock
```

**Guest side** (requires serial console access):
```bash
# Check if agent is running
ps aux | grep agent.py

# Check vsock device
ls -l /dev/vsock

# Test vsock connectivity
python3 -c "import socket; s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM); s.bind((socket.VMADDR_CID_ANY, 5000)); print('OK')"
```

## References

- [Firecracker vsock documentation](https://github.com/firecracker-microvm/firecracker/blob/main/docs/vsock.md)
- [Linux vsock(7) man page](https://man7.org/linux/man-pages/man7/vsock.7.html)
- [Python socket.AF_VSOCK](https://docs.python.org/3/library/socket.html#socket.AF_VSOCK)
