#!/usr/bin/env python3
"""
Firecracker Guest Agent

Runs inside the microVM and handles code execution requests from the host via vsock.
"""

import json
import socket
import struct
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, Any


class GuestAgent:
    """Agent that runs inside Firecracker VM to execute code"""

    def __init__(self):
        # vsock: CID 2 = host, CID 3 = guest
        self.vsock_cid = socket.VMADDR_CID_HOST  # Connect to host (CID 2)
        self.code_execution_port = 5000
        self.output_dir = Path("/tmp/output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def recv_exact(self, sock: socket.socket, length: int) -> bytes:
        """Receive exact number of bytes"""
        data = b''
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                break
            data += chunk
        return data

    def send_response(self, sock: socket.socket, response: Dict[str, Any]):
        """Send JSON response with length prefix"""
        response_data = json.dumps(response).encode('utf-8')
        sock.sendall(struct.pack('!I', len(response_data)) + response_data)

    def handle_execute(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Python code"""
        code = request.get('code', '')
        timeout = request.get('timeout', 30)

        try:
            # Execute code with timeout
            result = subprocess.run(
                [sys.executable, '-c', code],
                capture_output=True,
                timeout=timeout,
                text=True,
                cwd='/tmp/output'
            )

            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'exit_code': result.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': f'Execution timeout after {timeout} seconds',
                'exit_code': -1
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1
            }

    def handle_list_files(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """List files in directory"""
        path = Path(request.get('path', '/tmp/output'))

        try:
            if not path.exists():
                return {'files': []}

            files = [f.name for f in path.iterdir() if f.is_file()]
            return {'files': files}

        except Exception as e:
            return {'error': str(e), 'files': []}

    def handle_get_file(self, request: Dict[str, Any], sock: socket.socket):
        """Send file content"""
        file_path = Path(request.get('path', ''))

        try:
            if not file_path.exists() or not file_path.is_file():
                # Send empty response
                sock.sendall(struct.pack('!I', 0))
                return

            # Read and send file content
            content = file_path.read_bytes()
            sock.sendall(struct.pack('!I', len(content)) + content)

        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sock.sendall(struct.pack('!I', 0))

    def handle_request(self, sock: socket.socket):
        """Handle a single request"""
        try:
            # Receive request length
            length_data = self.recv_exact(sock, 4)
            if not length_data:
                return False

            request_length = struct.unpack('!I', length_data)[0]

            # Receive request data
            request_data = self.recv_exact(sock, request_length)
            if not request_data:
                return False

            request = json.loads(request_data.decode('utf-8'))
            action = request.get('action', '')

            # Handle different actions
            if action == 'execute':
                response = self.handle_execute(request)
                self.send_response(sock, response)

            elif action == 'list_files':
                response = self.handle_list_files(request)
                self.send_response(sock, response)

            elif action == 'get_file':
                self.handle_get_file(request, sock)

            else:
                response = {'error': f'Unknown action: {action}'}
                self.send_response(sock, response)

            return True

        except Exception as e:
            print(f"Error handling request: {e}", file=sys.stderr)
            return False

    def run(self):
        """Main agent loop - listen for connections from host via vsock"""
        try:
            # Create vsock socket
            sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)

            # Bind to vsock address (CID ANY, port 5000)
            sock.bind((socket.VMADDR_CID_ANY, self.code_execution_port))
            sock.listen(5)

            print(f"Guest agent listening on vsock port {self.code_execution_port}", file=sys.stderr)

            while True:
                # Accept connection from host
                conn, addr = sock.accept()
                print(f"Connection from {addr}", file=sys.stderr)

                try:
                    # Handle requests on this connection
                    while self.handle_request(conn):
                        pass
                finally:
                    conn.close()

        except Exception as e:
            print(f"Agent error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    agent = GuestAgent()
    agent.run()
