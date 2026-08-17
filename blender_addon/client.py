"""
Fusion to Blender - WebSocket Client (Blender side)
- Auto-reconnect (exponential backoff: 2s -> 4s -> 8s -> ... -> 30s)
- Scene updates safely on main thread via message queue
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

import asyncio
import json
import queue
import threading
import traceback
import zlib
from asyncio import run_coroutine_threadsafe

import bpy

from .libs.websockets import client as ws_client
from .libs.websockets.exceptions import InvalidURI

RECONNECT_DELAY_INIT = 2.0
RECONNECT_DELAY_MAX  = 30.0
RECONNECT_DELAY_MULT = 1.5

# Cap a single decompressed message so a decompression bomb or a corrupt frame
# can't balloon memory (a sane Fusion body streams well under this). Past the
# cap we raise zlib.error so the existing decode-error handling drops the frame.
MAX_DECOMPRESSED_BYTES = 512 * 1024 * 1024  # 512 MB


def _classify_conn_error(e: Exception) -> str:
    """EU05: map a connection exception to a UI hint category."""
    if isinstance(e, ConnectionRefusedError):
        return "refused"      # nothing listening — Fusion add-in not running
    if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
        return "timeout"      # no response — firewall / wrong IP
    if isinstance(e, OSError):
        return "unreachable"  # host unreachable / network down / bad address
    return "error"


def _decompress_capped(data: bytes, max_bytes: int) -> bytes:
    """zlib-decompress with an output ceiling. Raises zlib.error past max_bytes.

    Checks both unconsumed_tail (input left over) and eof (stream finished): a
    high-ratio bomb can consume all input yet leave the stream unfinished with
    more output pending, so eof is the reliable "did it all fit" signal.
    """
    dobj = zlib.decompressobj()
    out = dobj.decompress(data, max_bytes)
    if not dobj.eof or dobj.unconsumed_tail:
        raise zlib.error(f"decompressed payload exceeds {max_bytes}-byte cap")
    return out


class FusionBridgeClient:
    def __init__(self, handler):
        self.handler = handler
        self.server: str = None
        self.connected: bool = False
        self.websocket = None

        self._should_reconnect: bool = False
        self._reconnect_delay: float = RECONNECT_DELAY_INIT
        self.reconnect_countdown: float = 0.0  # for UI display

        # EU05: category of the last connection failure, for a targeted UI hint.
        # One of None / "refused" / "timeout" / "unreachable" / "invalid" / "error".
        self.connect_error: str = None

        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._message_queue: queue.Queue = queue.Queue()
        self._timer_registered: bool = False

        # EU01: when Sync is pressed while disconnected, the request is stashed
        # here and fired exactly once on the next successful connect.
        self._pending_sync: dict = None

    # ── Connect / Disconnect ────────────────────────────────────────────────
    def connect(self, server: str):
        if self._should_reconnect:
            return

        self._should_reconnect = True
        self._reconnect_delay = RECONNECT_DELAY_INIT
        self.connect_error = None  # EU05: fresh attempt starts clean
        self.server = server

        self._loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._reconnect_loop(f"ws://{server}"))

        self._thread = threading.Thread(target=run_loop, daemon=True, name="FusionBridgeWS")
        self._thread.start()
        self._register_timer()

    def disconnect(self):
        """User explicitly disconnects -- no reconnection"""
        self._should_reconnect = False
        self.connected = False
        self.reconnect_countdown = 0.0
        self._pending_sync = None  # EU01: drop any queued auto-sync

        if self.websocket and self._loop and self._loop.is_running():
            try:
                future = run_coroutine_threadsafe(self.websocket.close(), self._loop)
                try:
                    future.result(timeout=2.0)
                except Exception:
                    pass
            except Exception:
                pass

        # Stop the event loop to clean up the background thread
        if self._loop and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass

        self._unregister_timer()

    # ── Reconnect loop ─────────────────────────────────────────────────────────
    async def _reconnect_loop(self, uri: str):
        """Auto-retry on connection failure/disconnect (exponential backoff)"""
        while self._should_reconnect:
            try:
                await self._connect_once(uri)
                if not self._should_reconnect:
                    break
                # Unexpected disconnect -> reset delay and reconnect
                self._reconnect_delay = RECONNECT_DELAY_INIT
            except InvalidURI:
                self.connect_error = "invalid"
                print(f"[FusionBridge] Invalid URI: {uri}")
                break
            except Exception as e:
                self.connect_error = _classify_conn_error(e)
                print(f"[FusionBridge] Connection error ({self.connect_error}): {e}")

            if not self._should_reconnect:
                break

            delay = self._reconnect_delay
            self._reconnect_delay = min(delay * RECONNECT_DELAY_MULT, RECONNECT_DELAY_MAX)
            print(f"[FusionBridge] Reconnecting in {delay:.0f}s...")

            # Countdown in 0.2s intervals (responds immediately to disconnect)
            elapsed = 0.0
            while elapsed < delay and self._should_reconnect:
                self.reconnect_countdown = delay - elapsed
                await asyncio.sleep(0.2)
                elapsed += 0.2

        self.connected = False
        self.reconnect_countdown = 0.0
        print("[FusionBridge] Reconnect loop ended")

    async def _connect_once(self, uri: str):
        """Single connection session"""
        async with ws_client.connect(
            uri,
            max_size=2 ** 32,
            ping_interval=None,
            close_timeout=10,
        ) as websocket:
            self.websocket = websocket
            self.connected = True
            self.reconnect_countdown = 0.0
            self.connect_error = None  # EU05: clear stale failure hint
            print(f"[FusionBridge] Connected to {uri}")

            # EU01: fire a Sync that was requested while disconnected, once.
            # (General auto-sync on connect stays off — only an explicit pending
            # request set by pressing Sync triggers this.)
            pending = self._pending_sync
            self._pending_sync = None
            if pending is not None:
                try:
                    await self.websocket.send(json.dumps(pending))
                    print("[FusionBridge] Sent pending sync after connect")
                except Exception as e:
                    print(f"[FusionBridge] Pending sync send failed: {e}")

            async for raw_msg in websocket:
                if not self._should_reconnect:
                    break
                try:
                    # binary frame = server-side zlib-compressed JSON
                    if isinstance(raw_msg, bytes):
                        raw_msg = _decompress_capped(raw_msg, MAX_DECOMPRESSED_BYTES)
                    msg = json.loads(raw_msg)
                    self._message_queue.put(msg)
                except (json.JSONDecodeError, zlib.error) as e:
                    print(f"[FusionBridge] Message decode error: {e}")

        self.connected = False
        self.websocket = None
        # Notify handler so it can clean up any in-progress streaming sync
        self._message_queue.put({"type": "_connection_lost"})

    # ── Send ──────────────────────────────────────────────────────────────────
    async def _do_send_json(self, data: dict):
        if self.websocket:
            try:
                await self.websocket.send(json.dumps(data))
            except Exception:
                pass

    def send_json(self, data: dict):
        if not self.connected or not self._loop:
            return
        run_coroutine_threadsafe(self._do_send_json(data), self._loop)

    def request_sync(self, quality: dict = None, include_hidden: bool = None):
        """Request full sync. Passes quality dict and include_hidden together.

        If we're not connected yet (EU01), stash the request so it fires once on
        the next successful connect instead of being silently dropped.
        """
        msg = {"type": "request_sync"}
        if quality:
            msg["mesh_quality"] = quality
        if include_hidden is not None:
            msg["include_hidden"] = bool(include_hidden)
        if self.connected:
            self.send_json(msg)
        else:
            self._pending_sync = msg

    # ── Blender timer ──────────────────────────────────────────────────────────
    def _register_timer(self):
        if not self._timer_registered:
            bpy.app.timers.register(self._process_queue, first_interval=0.1)
            self._timer_registered = True

    def _unregister_timer(self):
        if self._timer_registered:
            try:
                bpy.app.timers.unregister(self._process_queue)
            except Exception:
                pass
            self._timer_registered = False

    def _process_queue(self):
        if not self._should_reconnect and not self.connected and self._message_queue.empty():
            self._timer_registered = False
            return None

        processed = 0
        while not self._message_queue.empty() and processed < 50:
            try:
                msg = self._message_queue.get_nowait()
                self.handler.handle_message(msg)
                processed += 1
            except queue.Empty:
                break
            except Exception:
                traceback.print_exc()

        return 0.05
