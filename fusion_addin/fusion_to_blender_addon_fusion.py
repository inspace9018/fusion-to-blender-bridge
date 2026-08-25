"""
Fusion to Blender Lite - Fusion 360 Add-in entry point
Install location: %appdata%\\Autodesk\\Autodesk Fusion 360\\API\\AddIns\\fusion_to_blender_addon_fusion\\

Mesh quality settings are managed on the Blender side. Fusion 360 only acts as a server.
"""

# Fusion to Blender Lite
# Copyright (C) 2026 inspace
#
# This file is part of Fusion to Blender Lite.
#
# Fusion to Blender Lite is free software: you can redistribute it and/or modify it
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

import os
import shutil
import struct
import sys
import threading
import traceback
import zlib

try:
    import adsk.core
    import adsk.fusion
    import adsk.cam
except ImportError:
    pass

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

# Reload our own submodules on reinstall-without-restart. Fusion caches imported
# modules in sys.modules, so reinstalling the add-in WITHOUT restarting Fusion
# would keep running the OLD code (the same trap we hit on the Blender side --
# version bumps show but behaviour doesn't change). Force-reload here.
import importlib as _importlib
for _name in ("i18n", "exporter", "server"):
    _m = sys.modules.get(_name)
    if _m is not None:
        try:
            _importlib.reload(_m)
        except Exception:
            pass

from server import FusionBridgeServer
from exporter import export_design, export_joints, build_delete_message, _count_visible_bodies, _strip_occ_all, _build_hidden_occ_paths  # noqa: F401
from i18n import t as ft, set_language as ft_set_language, get_language as ft_get_language

# ─── Global state ─────────────────────────────────────────────────────────────
_app: "adsk.core.Application" = None
_ui:  "adsk.core.UserInterface" = None
_toolbar_controls = []
_manager: "FusionBlenderBridgeManager" = None

DEFAULT_PORT           = 9080

# Fusion identifies custom events by string, globally. Namespaced so a second
# copy of this add-in (an old one still registered from another folder) cannot
# collide with ours.
SYNC_EVENT_ID          = "FusionToBlenderBridge_RunSync"
DEFAULT_INCLUDE_HIDDEN = False
# Bind loopback only by default (127.0.0.1) -- the bridge stays private to this
# PC. Turn on in Settings to accept LAN connections (Fusion on another machine).
DEFAULT_ALLOW_REMOTE   = False
DEFAULT_QUALITY        = {"preset": "medium"}

_NAV_SRV_ON  = "FTB_NavSrvOn"   # Server ON icon
_NAV_SRV_OFF = "FTB_NavSrvOff"  # Server OFF icon

_CMD_IDS = [
    "FTB_StartServer", "FTB_StopServer", "FTB_Settings",
    _NAV_SRV_ON, _NAV_SRV_OFF,
]

# Legacy IDs from previous versions (for cleanup -- backward compatibility)
_LEGACY_IDS = [
    "FTB_LiveLink", "FTB_NavLiveOn", "FTB_NavLiveOff",
    "FTB_Push", "FTB_NavPush", "FTB_Diagnostic",
]


# ─── Bridge manager ───────────────────────────────────────────────────────────
class FusionBlenderBridgeManager:
    def __init__(self):
        self._handlers       = []
        self._server         = None
        self.port            = DEFAULT_PORT
        self.include_hidden  = DEFAULT_INCLUDE_HIDDEN
        self.allow_remote    = DEFAULT_ALLOW_REMOTE
        self._last_quality   = DEFAULT_QUALITY
        # Sync requests arrive on a socket thread but must run on Fusion's main
        # thread -- see _on_sync_requested.
        self._pending_syncs  = []
        self._pending_lock   = threading.Lock()
        self._custom_event   = None

    # ── Main-thread hand-off ──────────────────────────────────────────────────
    # The websocket server hands each message to us on that client's own thread.
    # Fusion's API is only safe on the main thread; called from elsewhere it may
    # work, return None, or raise, depending on what the main thread happens to
    # be doing. That is why a sync could silently do nothing while neither
    # application froze: activeDocument came back None off-thread, and the old
    # code returned without a word.
    #
    # A custom event is Fusion's documented way across: fireCustomEvent() is
    # callable from any thread, and the registered handler's notify() runs on
    # the main thread.
    def _setup_custom_event(self):
        """Returns True when the hand-off is available."""
        if self._custom_event is not None:
            return True
        try:
            # A stale registration survives a crashed session; clearing first
            # makes Run-after-a-bad-Stop behave like a fresh start.
            try:
                _app.unregisterCustomEvent(SYNC_EVENT_ID)
            except Exception:
                pass
            self._custom_event = _app.registerCustomEvent(SYNC_EVENT_ID)
            handler = _SyncEventHandler(self)
            self._custom_event.add(handler)
            self._handlers.append(handler)
            return True
        except Exception:
            traceback.print_exc()
            self._custom_event = None
            return False

    def _drain_pending_syncs(self):
        """Main thread: run everything the socket threads queued."""
        with self._pending_lock:
            pending, self._pending_syncs = self._pending_syncs, []
        for client, msg in pending:
            try:
                self._run_sync(client, msg)
            except Exception:
                traceback.print_exc()

    # ── Server control ────────────────────────────────────────────────────────
    def start_server(self):
        if self._server and self._server.running:
            return
        # Bind loopback by default; only expose on the LAN if the user opted in.
        host = "0.0.0.0" if self.allow_remote else "127.0.0.1"
        # Register the hand-off here, before any client can connect: this runs
        # on the main thread (a Fusion command started it), whereas the lazy
        # path inside _on_sync_requested would register from a socket thread --
        # the very thing this mechanism exists to avoid.
        self._setup_custom_event()
        self._server = FusionBridgeServer(host=host, port=self.port)
        self._server.on_client_count_changed = self._on_client_count_changed
        self._server.set_sync_callback(self._on_sync_requested)
        self._server.start()

    def stop_server(self):
        if self._server:
            self._server.stop()
            self._server = None

    @property
    def server_running(self) -> bool:
        return self._server is not None and self._server.running

    @property
    def client_count(self) -> int:
        return self._server.client_count if self._server else 0

    # ── Callbacks ─────────────────────────────────────────────────────────────
    def _on_client_count_changed(self, count: int):
        print(f"[FusionBridge] Connected clients: {count}")

    def _on_sync_requested(self, client, msg: dict):
        """Socket thread: queue the request and wake the main thread.

        Does no Fusion API work itself -- that is the whole point. If the
        hand-off cannot be set up (an older Fusion, a refused registration), it
        falls back to running inline, which is what every previous version did.
        Degrading to the old behaviour beats refusing to sync at all.
        """
        with self._pending_lock:
            self._pending_syncs.append((client, msg))
        if self._setup_custom_event():
            try:
                _app.fireCustomEvent(SYNC_EVENT_ID, "")
                return
            except Exception:
                traceback.print_exc()
        print("[FusionBridge] Main-thread hand-off unavailable; running inline")
        self._drain_pending_syncs()

    def _run_sync(self, client, msg: dict):
        """Main thread: Blender -> Fusion streaming sync request.

        Protocol:
          1. sync_start  { object_count }        <- expected total count
          2. object_add  { object }  x N         <- streamed as each is computed
          3. sync_end    { object_count }        <- completion signal
        """
        def _refuse(reason: str):
            """Tell Blender we cannot sync, and why.

            Every path out of this function used to be a bare `return`, so a
            failure here looked identical to a slow sync: Blender sat on
            "Fusion computing..." forever with nothing in its console. The
            traceback went to Fusion's Text Commands window, which nobody has
            open. Answering is not optional -- the other end is waiting.
            """
            print(f"[FusionBridge] Refusing sync: {reason}")
            try:
                self._server.send_to(client, {"type": "sync_error", "reason": reason})
            except Exception:
                traceback.print_exc()

        design = self._get_active_design()
        if design is None:
            # Usually: no document open, or the active tab is not a Design
            # (drawing, simulation, the home screen).
            _refuse("no active design in Fusion")
            return
        try:
            if "mesh_quality" in msg:
                self._last_quality = msg["mesh_quality"]

            # If the Blender request specifies include_hidden, use that value.
            # Otherwise use the Fusion-side setting.
            req_include_hidden = msg.get("include_hidden", self.include_hidden)

            root = design.rootComponent
            total = _count_visible_bodies(root, req_include_hidden)

            # Include design root name so Blender can scope deletion to this design only
            try:
                design_root = _strip_occ_all(root.name) if root.name else ""
            except Exception:
                design_root = ""

            # Stable per-document id so same-named bodies from DIFFERENT files are
            # never merged on the Blender side (F050). Prefer the saved dataFile
            # id (a UUID); fall back to the document name. Empty if neither is
            # available -- in which case Blender degrades to the old behavior.
            doc_id = ""
            try:
                _doc = _app.activeDocument
                if _doc is not None:
                    try:
                        _df = _doc.dataFile
                        doc_id = str(_df.id) if (_df and _df.id) else ""
                    except Exception:
                        doc_id = ""
                    if not doc_id:
                        doc_id = _doc.name or ""
            except Exception:
                doc_id = ""

            # Hidden-occurrence detection summary, surfaced to the Blender console
            # so we can see (a) whether THIS (new) Fusion add-in is running and
            # (b) how many occurrences Fusion thinks are hidden -- without needing
            # the separate Fusion-side log file.
            try:
                _hidden = _build_hidden_occ_paths(root)
                hidden_count = len(_hidden)
                hidden_sample = list(_hidden)[:3]
            except Exception:
                hidden_count = -1
                hidden_sample = []

            # Partial sync: Blender named the bodies it wants. The flag rides
            # in sync_start because the RECEIVER needs it -- a partial payload
            # must not trigger the delete-what-was-not-seen sweep at sync_end,
            # or re-syncing one body would erase the rest of the design.
            only_ids = msg.get("only_ids")
            if only_ids:
                only_ids = set(only_ids)
                total = len(only_ids)

            self._server.send_to(client, {
                "type": "sync_start",
                "partial": bool(only_ids),
                "object_count": total,
                "design_root": design_root,
                "doc": doc_id,
                "addon_version": "1.0.0",
                "hidden_count": hidden_count,
                "hidden_sample": hidden_sample,
            })

            processed = [0]

            def on_body(data: dict):
                processed[0] += 1
                self._server.send_to(client, {"type": "object_add", "object": data})

            export_design(
                design,
                quality=self._last_quality,
                include_hidden=req_include_hidden,
                body_callback=on_body,
                only_ids=only_ids,
            )

            self._server.send_to(client, {"type": "sync_end", "object_count": processed[0]})

            # Send joint/motion link data. Not on a partial sync: the request
            # was one body's mesh, and re-running the whole joint rebuild for
            # it is noise the user did not ask for.
            try:
                joints = [] if only_ids else export_joints(design)
                if joints:
                    self._server.send_to(client, {"type": "joints_data", "joints": joints})
                    print(f"[FusionBridge] Sent {len(joints)} joints")
            except Exception:
                traceback.print_exc()

            preset = self._last_quality.get("preset", "custom")
            print(f"[FusionBridge] Streamed {processed[0]} objects (quality={preset})")
        except Exception as exc:
            traceback.print_exc()
            # Blender is mid-sync and waiting. If sync_start already went out it
            # will also see the stream stop, but only this tells it why.
            _refuse(f"{type(exc).__name__}: {exc}")

    # ── Utilities ─────────────────────────────────────────────────────────────
    def _get_active_design(self):
        try:
            doc = _app.activeDocument
            if doc is None:
                return None
            return doc.products.itemByProductType("DesignProductType")
        except Exception:
            traceback.print_exc()
            return None

    def cleanup(self):
        self.stop_server()
        if self._custom_event is not None:
            # Leaving this registered makes the next Run fail to register it,
            # so the hand-off would silently fall back to the broken inline path.
            try:
                _app.unregisterCustomEvent(SYNC_EVENT_ID)
            except Exception:
                traceback.print_exc()
            self._custom_event = None
        for h in self._handlers:
            try:
                h.detach()
            except Exception:
                pass
        self._handlers.clear()


# ─── Icon PNG generation (no external libraries needed) ──────────────────────
def _write_png(path: str, color_rgba: tuple, size: int):
    r, g, b, a = color_rgba
    cx = cy = (size - 1) / 2.0
    radius = size / 2.0 - 1.0

    def chunk(ctype, data):
        crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))

    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter=None per row
        for x in range(size):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist <= radius:
                raw += bytes([r, g, b, a])
            elif dist <= radius + 1.5:
                aa = int(a * max(0.0, 1.0 - (dist - radius) / 1.5))
                raw += bytes([r, g, b, aa])
            else:
                raw += b"\x00\x00\x00\x00"

    idat = chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    iend = chunk(b"IEND", b"")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend)


_ICON_COLORS = {
    "server_on":  (60,  200,  60, 255),
    "server_off": (200,  60,  60, 255),
    "live_on":    (255, 160,  30, 255),   # unused (backward compatibility)
    "live_off":   (130, 130, 130, 200),
    "push":       (100, 160, 255, 255),
}


def _setup_resources():
    """Generate NavToolbar icon PNGs if they don't exist."""
    res = os.path.join(_dir, "resources")
    for name, color in _ICON_COLORS.items():
        for size in (16, 32, 64):
            path = os.path.join(res, name, f"{size}x{size}.png")
            if not os.path.exists(path):
                _write_png(path, color, size)


def _res(name: str) -> str:
    return os.path.join(_dir, "resources", name)


# ─── NavToolbar status sync ───────────────────────────────────────────────────
def update_nav_status():
    """Toggle NavToolbar button visibility based on server state."""
    if _ui is None or _manager is None:
        return
    try:
        nav = _find_nav_toolbar()
        if not nav:
            return
        c = nav.controls
        is_srv = _manager.server_running

        for cid, show in ((_NAV_SRV_ON, is_srv), (_NAV_SRV_OFF, not is_srv)):
            ctrl = c.itemById(cid)
            if ctrl:
                ctrl.isVisible = show
    except Exception:
        pass


# ─── UI construction ─────────────────────────────────────────────────────────
def _build_ui():
    try:
        _setup_resources()
        _build_tab_ui()
        nav = _find_nav_toolbar()
        if nav:
            _build_nav_ui(nav)
    except Exception:
        traceback.print_exc()


# Fusion 360 finding: QAT (Quick Access Toolbar) is the toolbar containing File/Save/Undo/Redo.
_TOOLBAR_CANDIDATES = ["QAT", "QuickAccessToolbar", "NavToolbar"]


def _find_nav_toolbar():
    """Return the top-left toolbar containing undo/redo."""
    for tid in _TOOLBAR_CANDIDATES:
        tb = _ui.toolbars.itemById(tid)
        if tb:
            return tb
    return None


# ─── Blender add-on, when it travels with this add-in ────────────────────────
# The Autodesk App Store repackages a submission with its own installer, and
# that installer only writes into Fusion's AddIns folder. The Blender half
# rides along as a zip in the same package, which means it lands somewhere
# inside that folder tree -- and "somewhere inside AppData" is not an
# instruction a buyer can follow. So the add-in finds it and hands it over.
#
# Not present in the free installer's layout, which installs the Blender side
# directly. Nothing is found, so no button is built. Same code, both builds.
_BLENDER_ADDON_NAMES = ("bridge_pro.zip", "fusion_to_blender_addon_blender.zip")


def _find_blender_addon_zip():
    """Path to the bundled Blender add-on zip, or None.

    Searches this folder and up to two levels above it. How the App Store
    installer lays a bundle out is not something we get to know in advance, so
    the search is deliberately wider than any one expected layout.
    """
    here = _dir
    for _ in range(3):
        for name in _BLENDER_ADDON_NAMES:
            candidate = os.path.join(here, name)
            if os.path.isfile(candidate):
                return candidate
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    return None


def _build_tab_ui():
    """FUSION TO BLENDER ribbon tab + panel."""
    ws = (_ui.workspaces.itemById("FusionSolidEnvironment")
          or _ui.workspaces.itemById("FusionRenderEnvironment"))
    if not ws:
        print("[FusionBridge] Workspace not found")
        return

    tab = ws.toolbarTabs.itemById("FusionToBlenderTab")
    if not tab:
        tab = ws.toolbarTabs.add("FusionToBlenderTab", "Fusion to Blender")

    panel = tab.toolbarPanels.itemById("FusionToBlenderPanel")
    if not panel:
        panel = tab.toolbarPanels.add("FusionToBlenderPanel", "Fusion to Blender", "", False)

    ctrl = panel.controls
    _add_cmd(ctrl, "FTB_StartServer", ft("start_server"),
             ft("start_server_desc"),
             StartServerHandler, promoted=True)
    _add_cmd(ctrl, "FTB_StopServer", ft("stop_server"),
             ft("stop_server_desc"),
             StopServerHandler)
    _add_cmd(ctrl, "FTB_Settings", ft("settings"),
             ft("settings_desc"),
             SettingsHandler)
    # Only in builds that carry the Blender half alongside them. A button that
    # cannot do anything is worse than no button.
    if _find_blender_addon_zip():
        # Not promoted. A promoted control renders as a large icon-over-label
        # button, and this command has no icon of its own -- so promoting it
        # gave a tall blank tile. Unpromoted it sits in the panel list the way
        # Stop Server and Settings do: icon and label side by side.
        _add_cmd(ctrl, "FTB_GetBlenderAddon", ft("get_blender"),
                 ft("get_blender_desc"),
                 GetBlenderAddonHandler)


_KNOWN_UNDO_REDO_IDS = [
    "RedoCommand", "FusionRedo", "Redo", "RedoCmd", "FusionRedoCmd",
    "UndoCommand", "FusionUndo", "Undo", "UndoCmd", "FusionUndoCmd",
]


def _find_after_undo_redo(controls) -> str:
    """Return the ID of the control after Undo/Redo (insert anchor). Empty string if not found."""
    for kid in _KNOWN_UNDO_REDO_IDS:
        anchor = controls.itemById(kid)
        if not anchor:
            continue
        # Find the "next control" by index traversal
        for i in range(controls.count):
            try:
                if controls.item(i).id == kid:
                    if i + 1 < controls.count:
                        try:
                            nxt = controls.item(i + 1).id
                            if nxt:
                                return nxt
                        except Exception:
                            pass
                    return ""
            except Exception:
                pass

    # fallback: search for undo/redo pattern by index traversal
    last_idx = -1
    for i in range(controls.count):
        try:
            cid = (controls.item(i).id or "").lower()
            if "undo" in cid or "redo" in cid or "revert" in cid:
                last_idx = i
        except Exception:
            pass
    if last_idx >= 0 and last_idx + 1 < controls.count:
        try:
            nxt = controls.item(last_idx + 1).id
            if nxt:
                return nxt
        except Exception:
            pass
    return ""


def _build_nav_ui(nav):
    """NavToolbar: 2 server status icons (ON/OFF). Placed right after Undo/Redo."""
    c = nav.controls
    insert_before_id = _find_after_undo_redo(c)

    def _nav_add(cid, name, desc, handler_cls, res_name):
        cmd_def = _ui.commandDefinitions.itemById(cid)
        if not cmd_def:
            cmd_def = _ui.commandDefinitions.addButtonDefinition(
                cid, name, desc, _res(res_name)
            )
        h = handler_cls(_manager)
        cmd_def.commandCreated.add(h)
        _manager._handlers.append(h)
        if not c.itemById(cid):
            try:
                ctrl = (c.addCommand(cmd_def, insert_before_id, False)
                        if insert_before_id else c.addCommand(cmd_def))
            except Exception:
                ctrl = c.addCommand(cmd_def)
            _toolbar_controls.append(ctrl)

    _nav_add(_NAV_SRV_ON,  ft("nav_srv_on"),
             ft("nav_srv_on_desc"),
             NavServerOnHandler,  "server_on")
    _nav_add(_NAV_SRV_OFF, ft("nav_srv_off"),
             ft("nav_srv_off_desc"),
             NavServerOffHandler, "server_off")

    update_nav_status()


def _add_cmd(controls, cmd_id, name, desc, handler_cls,
             promoted=False, res=None):
    """Create command definition -> register handler -> add to controls."""
    cmd_def = _ui.commandDefinitions.itemById(cmd_id)
    if not cmd_def:
        cmd_def = _ui.commandDefinitions.addButtonDefinition(
            cmd_id, name, desc, _res(res) if res else ""
        )
    h = handler_cls(_manager)
    cmd_def.commandCreated.add(h)
    _manager._handlers.append(h)
    if not controls.itemById(cmd_id):
        ctrl = controls.addCommand(cmd_def)
        if promoted:
            ctrl.isPromotedByDefault = True
        _toolbar_controls.append(ctrl)


# ─── Button handlers ─────────────────────────────────────────────────────────
class _SyncEventHandler(adsk.core.CustomEventHandler):
    """Runs on Fusion's main thread. This is the only place sync work happens."""

    def __init__(self, manager):
        super().__init__()
        self._manager = manager

    def notify(self, args):
        try:
            self._manager._drain_pending_syncs()
        except Exception:
            # Letting this escape into Fusion's event dispatch is how add-ins
            # take the application down with them.
            traceback.print_exc()


class _SimpleCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def notify(self, args):
        h = self._make_execute_handler()
        args.command.execute.add(h)
        self.manager._handlers.append(h)

    def _make_execute_handler(self):
        raise NotImplementedError


class _SimpleExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def notify(self, args):
        try:
            self.run()
        except Exception as e:
            # Surface the failure instead of swallowing it into the hidden
            # console -- otherwise a failed action (e.g. Start Server when the
            # port is busy) looks like nothing happened. Tell the user why.
            traceback.print_exc()
            try:
                if _ui:
                    _ui.messageBox(ft("action_failed", detail=str(e)),
                                   "Fusion to Blender")
            except Exception:
                pass

    def run(self):
        raise NotImplementedError


def _make_action_handler(action_fn):
    """Helper to create an execute handler class from a simple action function."""
    class H(_SimpleExecuteHandler):
        def run(self):
            action_fn(self.manager)
    return H


class GetBlenderAddonHandler(_SimpleCreatedHandler):
    """Copy the bundled Blender add-on somewhere the buyer can reach it."""

    def _make_execute_handler(self):
        def act(_m):
            src = _find_blender_addon_zip()
            if not src:
                # The button is only built when the file exists, so this means
                # it went missing after startup. Say so rather than failing
                # silently on a button the user can still see.
                _ui.messageBox(ft("get_blender_missing"), "Fusion to Blender")
                return
            dlg = _ui.createFileDialog()
            dlg.title = ft("get_blender")
            dlg.filter = "Blender add-on (*.zip)"
            dlg.initialFilename = os.path.basename(src)
            if dlg.showSave() != adsk.core.DialogResults.DialogOK:
                return                      # user cancelled; nothing to report
            dest = dlg.filename
            shutil.copyfile(src, dest)
            _ui.messageBox(ft("get_blender_saved", path=dest),
                           "Fusion to Blender")
        return _make_action_handler(act)(self.manager)


class StartServerHandler(_SimpleCreatedHandler):
    def _make_execute_handler(self):
        def act(m):
            m.start_server()
            update_nav_status()
        return _make_action_handler(act)(self.manager)


class StopServerHandler(_SimpleCreatedHandler):
    def _make_execute_handler(self):
        def act(m):
            m.stop_server()
            _ui.messageBox(ft("server_stopped_msg"), "Fusion to Blender")
            update_nav_status()
        return _make_action_handler(act)(self.manager)


class NavServerOnHandler(_SimpleCreatedHandler):
    def _make_execute_handler(self):
        def act(m):
            m.stop_server()
            update_nav_status()
        return _make_action_handler(act)(self.manager)


class NavServerOffHandler(_SimpleCreatedHandler):
    def _make_execute_handler(self):
        def act(m):
            m.start_server()
            update_nav_status()
        return _make_action_handler(act)(self.manager)


_LANG_ITEMS = ["Auto (System)", "English", "한국어"]
_LANG_VALUES = ["auto", "en", "ko"]


class SettingsHandler(_SimpleCreatedHandler):
    """Port + include hidden bodies + language option."""

    def notify(self, args):
        try:
            inputs = args.command.commandInputs
            inputs.addIntegerSpinnerCommandInput(
                "port", ft("port_label"), 1024, 65535, 1, self.manager.port
            )
            inputs.addBoolValueInput(
                "include_hidden", ft("include_hidden"), True, "",
                self.manager.include_hidden
            )
            # Remote (LAN) access -- off by default so the server binds loopback only.
            remote_input = inputs.addBoolValueInput(
                "allow_remote", ft("allow_remote"), True, "",
                self.manager.allow_remote
            )
            remote_input.tooltip = ft("allow_remote")
            remote_input.tooltipDescription = ft("allow_remote_desc")
            # Language dropdown
            lang_input = inputs.addDropDownCommandInput(
                "language", ft("language"),
                adsk.core.DropDownStyles.TextListDropDownStyle
            )
            current_lang = ft_get_language()
            for i, label in enumerate(_LANG_ITEMS):
                is_selected = (_LANG_VALUES[i] == current_lang)
                lang_input.listItems.add(label, is_selected, "")

            h = SettingsExecuteHandler(self.manager)
            args.command.execute.add(h)
            self.manager._handlers.append(h)
        except Exception:
            traceback.print_exc()

    def _make_execute_handler(self):
        pass


class SettingsExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def notify(self, args):
        try:
            inputs = args.command.commandInputs
            old_port   = self.manager.port
            old_remote = self.manager.allow_remote
            self.manager.port           = inputs.itemById("port").value
            self.manager.include_hidden = inputs.itemById("include_hidden").value
            remote_item = inputs.itemById("allow_remote")
            if remote_item is not None:
                self.manager.allow_remote = remote_item.value
            # Save language setting
            lang_input = inputs.itemById("language")
            if lang_input:
                selected_name = lang_input.selectedItem.name
                idx = _LANG_ITEMS.index(selected_name) if selected_name in _LANG_ITEMS else 0
                ft_set_language(_LANG_VALUES[idx])
            # Re-bind immediately if a socket-affecting setting changed while the
            # server is running, so a new port -- or turning remote access OFF --
            # takes effect at once (important: disabling remote should close the
            # LAN exposure immediately, not on the next manual restart).
            if self.manager.server_running and (
                self.manager.port != old_port
                or self.manager.allow_remote != old_remote
            ):
                self.manager.stop_server()
                self.manager.start_server()
                try:
                    update_nav_status()
                except Exception:
                    pass
        except Exception:
            traceback.print_exc()


# ─── Add-in entry point ──────────────────────────────────────────────────────
def run(context):
    global _app, _ui, _manager
    try:
        _app     = adsk.core.Application.get()
        _ui      = _app.userInterface
        _manager = FusionBlenderBridgeManager()
        _build_ui()
        print("[FusionBridge] Add-in started (v1.0.0)")
    except Exception:
        if _ui:
            _ui.messageBox(f"Startup error:\n{traceback.format_exc()}")
        traceback.print_exc()


def stop(context):
    global _manager, _toolbar_controls
    try:
        if _manager:
            _manager.cleanup()
            _manager = None

        for ctrl in _toolbar_controls:
            try:
                ctrl.deleteMe()
            except Exception:
                pass
        _toolbar_controls.clear()

        for cmd_id in _CMD_IDS + _LEGACY_IDS:
            try:
                cmd_def = _ui.commandDefinitions.itemById(cmd_id)
                if cmd_def:
                    cmd_def.deleteMe()
            except Exception:
                pass

        print("[FusionBridge] Add-in stopped")
    except Exception:
        traceback.print_exc()
