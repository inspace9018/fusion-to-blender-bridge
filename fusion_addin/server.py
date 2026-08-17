"""
Fusion to Blender - WebSocket Server (Fusion 360 side)
Fusion 360 Python environment has limited asyncio support,
so WebSocket protocol is implemented directly using standard socket + threading.
"""

# Fusion to Blender Bridge
# Copyright (C) 2026 inspace
#
# This file is part of Fusion to Blender Bridge.
#
# Fusion to Blender Bridge is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.

import socket
import threading
import json
import hashlib
import base64
import struct
import traceback
import zlib

# ─── WebSocket Constants ──────────────────────────────────────────────────────
WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
WS_HANDSHAKE_RESPONSE = (
    "HTTP/1.1 101 Switching Protocols\r\n"
    "Upgrade: websocket\r\n"
    "Connection: Upgrade\r\n"
    "Sec-WebSocket-Accept: {accept}\r\n"
    "\r\n"
)

# WebSocket opcodes
OP_CONTINUATION = 0x0
OP_TEXT         = 0x1
OP_BINARY       = 0x2
OP_CLOSE        = 0x8
OP_PING         = 0x9
OP_PONG         = 0xA

# Idle seconds on a client socket before we probe it with a ping.
# During a long sync the server only *sends*, so its recv legitimately idles —
# so on timeout we PING (not drop). A healthy peer pongs and the sync continues;
# only a failed ping send means the peer is truly gone. This detects dead
# connections without false-disconnecting a long sync.
RECV_IDLE_TIMEOUT = 30.0


def _ws_accept_key(key: str) -> str:
    combined = key.strip() + WS_MAGIC
    sha1 = hashlib.sha1(combined.encode()).digest()
    return base64.b64encode(sha1).decode()


def _make_ws_frame(data: bytes, opcode: int = OP_TEXT) -> bytes:
    """Create server→client frame (no masking)"""
    length = len(data)
    header = bytearray()
    header.append(0x80 | opcode)  # FIN + opcode
    if length <= 125:
        header.append(length)
    elif length <= 65535:
        header.append(126)
        header += struct.pack(">H", length)
    else:
        header.append(127)
        header += struct.pack(">Q", length)
    return bytes(header) + data


def _recv_exact(conn: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes (raises ConnectionError if insufficient)"""
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed during recv")
        buf += chunk
    return buf


def _read_ws_frame(conn: socket.socket):
    """
    Receive and parse WebSocket frames.
    Collects fragmented frames and returns assembled data.
    Returns (data: bytes, opcode: int)
    """
    accumulated = b""
    first_opcode = None

    while True:
        header = _recv_exact(conn, 2)
        b0, b1 = header[0], header[1]

        fin    = bool(b0 & 0x80)
        opcode = b0 & 0x0F
        masked = bool(b1 & 0x80)
        length = b1 & 0x7F

        if length == 126:
            length = struct.unpack(">H", _recv_exact(conn, 2))[0]
        elif length == 127:
            length = struct.unpack(">Q", _recv_exact(conn, 8))[0]

        mask = _recv_exact(conn, 4) if masked else b""
        data = _recv_exact(conn, length)

        if masked:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))

        # Control frames can appear mid-stream — return immediately
        if opcode in (OP_PING, OP_PONG, OP_CLOSE):
            return data, opcode

        # Collect data frame fragments
        if opcode != OP_CONTINUATION:
            first_opcode = opcode
        accumulated += data

        if fin:
            return accumulated, first_opcode


# ─── Client Connection ────────────────────────────────────────────────────────
class ClientConnection:
    def __init__(self, conn: socket.socket, addr, server: "FusionBridgeServer"):
        self.conn = conn
        self.addr = addr
        self.server = server
        self.alive = True
        self._send_lock = threading.Lock()

    def send_json(self, data: dict):
        if not self.alive:
            return
        try:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            compressed = zlib.compress(payload, level=1)  # level=1 = fastest
            frame = _make_ws_frame(compressed, opcode=OP_BINARY)
            with self._send_lock:
                self.conn.sendall(frame)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.alive = False
        except OSError as e:
            # Catch socket errors (e.g., send buffer full, connection dropped)
            print(f"[FusionBridge] Send error: {e}")
            self.alive = False
        except Exception:
            self.alive = False

    def _send_pong(self, payload: bytes):
        """Respond to ping with pong immediately — essential for keepalive"""
        try:
            frame = _make_ws_frame(payload, opcode=OP_PONG)
            with self._send_lock:
                self.conn.sendall(frame)
        except Exception:
            self.alive = False

    def _send_ping(self) -> bool:
        """Probe the client with a WS ping. Returns False if the peer is gone."""
        try:
            frame = _make_ws_frame(b"", opcode=OP_PING)
            with self._send_lock:
                self.conn.sendall(frame)
            return True
        except Exception:
            self.alive = False
            return False

    def close(self):
        self.alive = False
        try:
            frame = _make_ws_frame(struct.pack(">H", 1000), opcode=OP_CLOSE)
            with self._send_lock:
                self.conn.sendall(frame)
        except Exception:
            pass
        try:
            self.conn.close()
        except Exception:
            pass

    def handle(self):
        """HTTP upgrade → WebSocket handshake → message loop"""
        try:
            # Receive HTTP headers (with size limit)
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = self.conn.recv(4096)
                if not chunk:
                    return
                request += chunk
                if len(request) > 65536:
                    self.conn.close()
                    return

            # Extract Sec-WebSocket-Key
            ws_key = None
            for line in request.decode("utf-8", errors="ignore").splitlines():
                if line.lower().startswith("sec-websocket-key:"):
                    ws_key = line.split(":", 1)[1].strip()
                    break

            if not ws_key:
                self.conn.close()
                return

            # Handshake response
            accept = _ws_accept_key(ws_key)
            self.conn.sendall(WS_HANDSHAKE_RESPONSE.format(accept=accept).encode())

            # Register connection
            self.server._on_client_connected(self)

            # ── Message loop ─────────────────────────────────────────────────
            while self.alive:
                try:
                    data, opcode = _read_ws_frame(self.conn)
                except socket.timeout:
                    # No inbound frame for RECV_IDLE_TIMEOUT. Don't assume death:
                    # during a long sync the recv channel idles while we stream.
                    # Probe with a ping — only give up if it can't be sent.
                    if not self._send_ping():
                        break
                    continue

                if opcode == OP_CLOSE:
                    break

                if opcode == OP_PING:
                    # ★ ping → pong immediate response (client disconnects on timeout otherwise)
                    self._send_pong(data)
                    continue

                if opcode == OP_PONG:
                    continue

                if opcode in (OP_TEXT, OP_BINARY):
                    try:
                        msg = json.loads(data.decode("utf-8"))
                        self.server._on_message(self, msg)
                    except Exception as e:
                        print(f"[FusionBridge] Failed to decode/handle inbound message from {self.addr}: {e}")

        except (ConnectionError, socket.timeout):
            # socket.timeout here = idle during the HTTP handshake (a stale/dead
            # peer that never completed the upgrade) → abandon cleanly.
            pass
        except Exception:
            if self.alive:
                traceback.print_exc()
        finally:
            self.alive = False
            self.server._on_client_disconnected(self)
            try:
                self.conn.close()
            except Exception:
                pass


# ─── WebSocket Server ────────────────────────────────────────────────────────────
class FusionBridgeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 9080):
        # Default to loopback (127.0.0.1) so the bridge is NOT exposed on the
        # LAN. The Fusion side passes host="0.0.0.0" only when the user opts in
        # to remote (another-PC) connections in Settings. See start_server().
        self.host = host
        self.port = port
        self._socket = None
        self._thread = None
        self._clients: list[ClientConnection] = []
        self._lock = threading.Lock()
        self.running = False
        self.on_client_count_changed = None
        self._sync_callback = None

    def start(self):
        if self.running:
            return
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._socket.bind((self.host, self.port))
            self._socket.listen(5)
        except OSError as e:
            # Don't fail silently: clean up and raise a clear reason the UI can
            # show the user (most common cause: the port is already in use).
            try:
                self._socket.close()
            finally:
                self._socket = None
            self.running = False
            in_use = e.errno in (48, 98, 10048)  # EADDRINUSE on mac / linux / win
            reason = ("the port is already in use by another program"
                      if in_use else (e.strerror or str(e)))
            raise OSError(
                f"Could not start the bridge server on {self.host}:{self.port} "
                f"({reason}). Try a different port in Server Settings."
            ) from e
        self._socket.settimeout(1.0)
        self.running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        print(f"[FusionBridge] Server started on port {self.port}")

    def stop(self):
        self.running = False
        with self._lock:
            for client in list(self._clients):
                client.close()
            self._clients.clear()
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        print("[FusionBridge] Server stopped")

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self._socket.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                conn.settimeout(RECV_IDLE_TIMEOUT)
                client = ClientConnection(conn, addr, self)
                t = threading.Thread(target=client.handle, daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    traceback.print_exc()
                break

    def _on_client_connected(self, client: ClientConnection):
        with self._lock:
            self._clients.append(client)
        count = self.client_count
        print(f"[FusionBridge] Client connected: {client.addr} (total: {count})")
        if self.on_client_count_changed:
            self.on_client_count_changed(count)

    def _on_client_disconnected(self, client: ClientConnection):
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)
        count = self.client_count
        print(f"[FusionBridge] Client disconnected (total: {count})")
        if self.on_client_count_changed:
            self.on_client_count_changed(count)

    def _on_message(self, client: ClientConnection, msg: dict):
        msg_type = msg.get("type")
        if msg_type == "request_sync" and self._sync_callback:
            self._sync_callback(client, msg)

    def broadcast(self, data: dict):
        with self._lock:
            dead = []
            for client in self._clients:
                client.send_json(data)
                if not client.alive:
                    dead.append(client)
            for c in dead:
                self._clients.remove(c)

    def send_to(self, client: ClientConnection, data: dict):
        client.send_json(data)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len([c for c in self._clients if c.alive])

    def set_sync_callback(self, callback):
        """callback(client, msg) — msg may contain quality settings"""
        self._sync_callback = callback
