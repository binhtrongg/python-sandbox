"""Firecracker microVM executor

Provides ultra-fast, secure code execution using Firecracker microVMs.

See docs/FIRECRACKER_IMPLEMENTATION.md for setup instructions.
"""

import asyncio
import json
import subprocess
import time
import uuid
import tarfile
import io
import socket
import struct
from typing import Dict, Any, List, Optional
from pathlib import Path
import aiohttp

from app.executors.base import BaseExecutor
from app.executors.factory import ExecutorRegistry
from app.core.exceptions import ExecutionError
from app.config import get_settings
from app.storage import get_storage_manager

settings = get_settings()

# vsock ports
VSOCK_CODE_EXECUTION_PORT = 5000
VSOCK_FILE_TRANSFER_PORT = 5001


@ExecutorRegistry.register("firecracker")
class FirecrackerExecutor(BaseExecutor):
    """
    Firecracker microVM executor

    Provides ultra-fast, secure code execution using Firecracker microVMs.

    Features:
    - Ultra-fast startup (~125ms vs Docker's 1-2s)
    - Hardware-level isolation via KVM
    - Minimal memory footprint (~5MB per VM)
    - Massive scalability (1000+ VMs per host)

    Requirements:
    - Linux host with KVM
    - Firecracker binary
    - Custom kernel (vmlinux)
    - Root filesystem with Python + packages

    See docs/FIRECRACKER_IMPLEMENTATION.md for setup.
    """

    def __init__(self):
        """Initialize Firecracker executor"""
        self.kernel_path = settings.FIRECRACKER_KERNEL_PATH
        self.rootfs_path = settings.FIRECRACKER_ROOTFS_PATH
        self.socket_path = settings.FIRECRACKER_SOCKET_PATH
        self.memory_mb = settings.FIRECRACKER_MEMORY_MB
        self.vcpu_count = settings.FIRECRACKER_VCPU_COUNT

        # Verify Firecracker is available
        try:
            result = subprocess.run(
                ["firecracker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise ExecutionError("Firecracker binary not working properly")

            print(f"✅ Firecracker executor initialized (version: {result.stdout.strip()})")

        except FileNotFoundError:
            raise ExecutionError(
                "Firecracker binary not found. "
                "Install Firecracker: see docs/FIRECRACKER_IMPLEMENTATION.md"
            )
        except subprocess.TimeoutExpired:
            raise ExecutionError("Firecracker binary timeout")
        except Exception as e:
            raise ExecutionError(f"Failed to initialize Firecracker: {e}")

        # Verify kernel exists
        if not Path(self.kernel_path).exists():
            raise ExecutionError(
                f"Firecracker kernel not found: {self.kernel_path}. "
                "Build kernel: see docs/FIRECRACKER_IMPLEMENTATION.md"
            )

        # Verify rootfs exists
        if not Path(self.rootfs_path).exists():
            raise ExecutionError(
                f"Firecracker rootfs not found: {self.rootfs_path}. "
                "Build rootfs: see docs/FIRECRACKER_IMPLEMENTATION.md"
            )

        # Verify KVM available
        if not Path("/dev/kvm").exists():
            raise ExecutionError(
                "/dev/kvm not found. Enable KVM: "
                "see docs/FIRECRACKER_IMPLEMENTATION.md"
            )

        # Create socket directory
        Path(self.socket_path).mkdir(parents=True, exist_ok=True)

        print(f"   Kernel: {self.kernel_path}")
        print(f"   Rootfs: {self.rootfs_path}")
        print(f"   Memory: {self.memory_mb}MB")
        print(f"   vCPUs: {self.vcpu_count}")

    async def execute(self, code: str, timeout: int) -> Dict[str, Any]:
        """
        Execute code in Firecracker microVM

        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds

        Returns:
            Dict with execution results
        """
        vm_id = str(uuid.uuid4())
        start_time = time.time()
        firecracker_process = None
        socket_path = f"{self.socket_path}/{vm_id}.sock"

        try:
            # Step 1: Start Firecracker process
            print(f"🔥 Starting Firecracker VM: {vm_id}")
            firecracker_process = await self._start_firecracker(vm_id, socket_path)

            # Step 2: Wait for socket to be ready
            await self._wait_for_socket(socket_path, timeout=5)

            # Step 3: Configure VM via API
            await self._configure_vm(socket_path, vm_id)

            # Step 4: Boot VM
            await self._boot_vm(socket_path)

            # Step 5: Execute code via vsock
            result = await self._execute_code_in_vm(
                vm_id,
                code,
                timeout
            )

            # Step 6: Extract files if storage enabled
            file_urls = await self._extract_files(vm_id, firecracker_process)

            execution_time = time.time() - start_time

            return {
                'success': result['success'],
                'stdout': result['stdout'],
                'stderr': result['stderr'],
                'exit_code': result['exit_code'],
                'execution_time': round(execution_time, 3),
                'error': result.get('error'),
                'files': file_urls
            }

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            return {
                'success': False,
                'stdout': '',
                'stderr': f'Execution timeout after {timeout} seconds',
                'exit_code': -1,
                'execution_time': round(execution_time, 3),
                'error': 'Execution timeout',
                'files': []
            }

        except Exception as e:
            execution_time = time.time() - start_time
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1,
                'execution_time': round(execution_time, 3),
                'error': f'Firecracker execution failed: {e}',
                'files': []
            }

        finally:
            # Cleanup
            if firecracker_process:
                try:
                    firecracker_process.kill()
                    firecracker_process.wait(timeout=5)
                except Exception:
                    pass

            # Remove socket file
            try:
                Path(socket_path).unlink(missing_ok=True)
            except Exception:
                pass

    async def _start_firecracker(
        self,
        vm_id: str,
        socket_path: str
    ) -> subprocess.Popen:
        """Start Firecracker process"""
        try:
            process = subprocess.Popen(
                [
                    "firecracker",
                    "--api-sock", socket_path,
                    "--id", vm_id
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Give Firecracker time to start
            await asyncio.sleep(0.1)

            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise ExecutionError(
                    f"Firecracker failed to start: {stderr.decode()}"
                )

            return process

        except Exception as e:
            raise ExecutionError(f"Failed to start Firecracker: {e}")

    async def _wait_for_socket(self, socket_path: str, timeout: int = 5):
        """Wait for Firecracker API socket to be ready"""
        start = time.time()
        while time.time() - start < timeout:
            if Path(socket_path).exists():
                return
            await asyncio.sleep(0.1)

        raise ExecutionError("Firecracker socket timeout")

    async def _configure_vm(self, socket_path: str, vm_id: str):
        """Configure VM via Firecracker API with vsock support"""
        base_url = f"http://localhost"

        connector = aiohttp.UnixConnector(path=socket_path)
        async with aiohttp.ClientSession(connector=connector) as session:
            # Configure boot source (kernel)
            boot_config = {
                "kernel_image_path": self.kernel_path,
                "boot_args": "console=ttyS0 reboot=k panic=1 pci=off quiet"
            }
            async with session.put(
                f"{base_url}/boot-source",
                json=boot_config
            ) as resp:
                if resp.status != 204:
                    text = await resp.text()
                    raise ExecutionError(f"Failed to set boot source: {text}")

            # Configure root drive
            drive_config = {
                "drive_id": "rootfs",
                "path_on_host": self.rootfs_path,
                "is_root_device": True,
                "is_read_only": False
            }
            async with session.put(
                f"{base_url}/drives/rootfs",
                json=drive_config
            ) as resp:
                if resp.status != 204:
                    text = await resp.text()
                    raise ExecutionError(f"Failed to set drive: {text}")

            # Configure machine resources
            machine_config = {
                "vcpu_count": self.vcpu_count,
                "mem_size_mib": self.memory_mb
            }
            async with session.put(
                f"{base_url}/machine-config",
                json=machine_config
            ) as resp:
                if resp.status != 204:
                    text = await resp.text()
                    raise ExecutionError(f"Failed to set machine config: {text}")

            # Configure vsock device for host-guest communication
            # CID 3 = guest, CID 2 = host
            vsock_config = {
                "guest_cid": 3,
                "uds_path": f"{self.socket_path}/{vm_id}.vsock"
            }
            async with session.put(
                f"{base_url}/vsock",
                json=vsock_config
            ) as resp:
                if resp.status not in (204, 201):
                    text = await resp.text()
                    raise ExecutionError(f"Failed to set vsock: {text}")

    async def _boot_vm(self, socket_path: str):
        """Boot the VM"""
        base_url = f"http://localhost"

        connector = aiohttp.UnixConnector(path=socket_path)
        async with aiohttp.ClientSession(connector=connector) as session:
            action = {"action_type": "InstanceStart"}
            async with session.put(
                f"{base_url}/actions",
                json=action
            ) as resp:
                if resp.status != 204:
                    text = await resp.text()
                    raise ExecutionError(f"Failed to start VM: {text}")

        # Wait for VM to boot
        await asyncio.sleep(0.5)

    async def _execute_code_in_vm(
        self,
        vm_id: str,
        code: str,
        timeout: int
    ) -> Dict[str, Any]:
        """Execute code in the VM via vsock"""
        vsock_path = f"{self.socket_path}/{vm_id}.vsock"

        try:
            # Wait for guest agent to be ready
            await self._wait_for_guest_agent(vsock_path, timeout=10)

            # Connect to vsock
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            try:
                sock.connect(vsock_path)

                # Send execution request
                request = {
                    "action": "execute",
                    "code": code,
                    "timeout": timeout
                }

                # Send request as JSON with length prefix
                request_data = json.dumps(request).encode('utf-8')
                sock.sendall(struct.pack('!I', len(request_data)) + request_data)

                # Receive response with timeout
                start_time = time.time()
                response_length_data = self._recv_exact(sock, 4, timeout)
                if not response_length_data:
                    raise ExecutionError("Failed to receive response length")

                response_length = struct.unpack('!I', response_length_data)[0]
                remaining_timeout = max(1, timeout - (time.time() - start_time))

                response_data = self._recv_exact(sock, response_length, remaining_timeout)
                if not response_data:
                    raise ExecutionError("Failed to receive response data")

                response = json.loads(response_data.decode('utf-8'))

                return {
                    'success': response.get('success', False),
                    'stdout': response.get('stdout', ''),
                    'stderr': response.get('stderr', ''),
                    'exit_code': response.get('exit_code', -1)
                }

            finally:
                sock.close()

        except socket.timeout:
            return {
                'success': False,
                'stdout': '',
                'stderr': f'Execution timeout after {timeout} seconds',
                'exit_code': -1,
                'error': 'Execution timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1,
                'error': f'Code execution failed: {e}'
            }

    def _recv_exact(self, sock: socket.socket, length: int, timeout: float) -> bytes:
        """Receive exact number of bytes from socket"""
        data = b''
        sock.settimeout(timeout)
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                break
            data += chunk
        return data

    async def _wait_for_guest_agent(self, vsock_path: str, timeout: int = 10):
        """Wait for guest agent to be ready"""
        start = time.time()
        while time.time() - start < timeout:
            if Path(vsock_path).exists():
                # Try to connect
                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    sock.connect(vsock_path)
                    sock.close()
                    return
                except (socket.error, ConnectionRefusedError):
                    pass
            await asyncio.sleep(0.2)

        raise ExecutionError("Guest agent not ready")

    async def _extract_files(
        self,
        vm_id: str,
        firecracker_process: subprocess.Popen
    ) -> List[str]:
        """
        Extract files from VM /tmp/output directory via vsock
        """
        vsock_path = f"{self.socket_path}/{vm_id}.vsock"
        file_urls = []

        if not settings.STORAGE_ENABLED:
            return file_urls

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(10)

            try:
                sock.connect(vsock_path)

                # Request file list
                request = {"action": "list_files", "path": "/tmp/output"}
                request_data = json.dumps(request).encode('utf-8')
                sock.sendall(struct.pack('!I', len(request_data)) + request_data)

                # Receive file list
                response_length_data = self._recv_exact(sock, 4, 10)
                if not response_length_data:
                    return file_urls

                response_length = struct.unpack('!I', response_length_data)[0]
                response_data = self._recv_exact(sock, response_length, 10)
                if not response_data:
                    return file_urls

                response = json.loads(response_data.decode('utf-8'))
                files = response.get('files', [])

                # Download each file
                storage_manager = get_storage_manager()
                for filename in files:
                    # Request file content
                    file_request = {"action": "get_file", "path": f"/tmp/output/{filename}"}
                    file_request_data = json.dumps(file_request).encode('utf-8')
                    sock.sendall(struct.pack('!I', len(file_request_data)) + file_request_data)

                    # Receive file content
                    file_length_data = self._recv_exact(sock, 4, 30)
                    if not file_length_data:
                        continue

                    file_length = struct.unpack('!I', file_length_data)[0]

                    # Check file size limit
                    if file_length > settings.MAX_FILE_SIZE:
                        print(f"Warning: File {filename} exceeds size limit ({file_length} bytes)")
                        continue

                    file_data = self._recv_exact(sock, file_length, 30)
                    if not file_data:
                        continue

                    # Upload to storage
                    file_path = f"{vm_id}/{filename}"
                    file_url = await storage_manager.save_file(
                        file_path=file_path,
                        content=file_data
                    )

                    # Generate presigned URL
                    presigned_url = await storage_manager.generate_presigned_url(
                        file_path=file_url,
                        expiration=18000
                    )
                    file_urls.append(presigned_url)

            finally:
                sock.close()

        except Exception as e:
            print(f"Warning: Failed to extract files: {e}")

        return file_urls

    async def health_check(self) -> bool:
        """Check if Firecracker is available and healthy"""
        try:
            # Check Firecracker binary
            result = subprocess.run(
                ["firecracker", "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                return False

            # Check kernel exists
            if not Path(self.kernel_path).exists():
                return False

            # Check rootfs exists
            if not Path(self.rootfs_path).exists():
                return False

            # Check KVM available
            if not Path("/dev/kvm").exists():
                return False

            return True

        except Exception:
            return False

    def cleanup(self) -> None:
        """Cleanup Firecracker resources"""
        try:
            # Kill any running Firecracker processes
            subprocess.run(
                ["pkill", "-f", "firecracker"],
                capture_output=True
            )

            # Clean up socket files
            socket_dir = Path(self.socket_path)
            if socket_dir.exists():
                for socket_file in socket_dir.glob("*.sock"):
                    socket_file.unlink(missing_ok=True)

            print("🧹 Firecracker executor cleaned up")

        except Exception as e:
            print(f"⚠️  Firecracker cleanup warning: {e}")

    def get_name(self) -> str:
        """Get executor name"""
        return "firecracker"
