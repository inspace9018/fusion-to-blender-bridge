"""
Fusion to Blender Lite - Blender Add-on
All settings, including mesh quality, are managed on the Blender side.
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

bl_info = {
    "name": "Fusion to Blender Lite",
    "description": "Fusion 360 ↔ Blender real-time geometry sync (preserves materials/modifiers/light links)",
    "author": "FusionToBlenderBridge",
    "version": (1, 0, 1),
    "blender": (4, 1, 0),
    "location": "View3D > Sidebar > Fusion 360",
    "category": "Import-Export",
}

# Installed as an extension, Blender takes the manifest as the source of truth
# and deletes `bl_info` off the module -- so a later read of it raises
# "name 'bl_info' is not defined" and the add-on refuses to enable. It has to
# be copied here, at import time, while it still exists. Nothing below this
# line may read `bl_info` again.
ADDON_NAME = bl_info["name"]
ADDON_VERSION = bl_info["version"]

import bpy
import traceback

# This package is installed three ways, and Blender calls the add-on something
# different in each:
#
#   blender_addon                                    the free add-on, on its own
#   bridge_pro.core                                  vendored inside Bridge Pro
#   bl_ext.user_default.fusion_to_blender_bridge     from the extensions platform
#
# ADDON_KEY has to be whatever Blender filed the add-on under, because that is
# the key its preferences live at and the bl_idname AddonPreferences must carry.
# VENDORED has to mean "someone else's add-on owns those preferences".
#
# Splitting on the first dot got both wrong for an extension: the key became
# "bl_ext", and the dots in the name read as "vendored", so the preferences
# class was never registered. The Preferences page came up empty -- no language,
# no auto-connect, and no privacy link, which the marketplaces require.
_parts = __package__.split(".")
if _parts[0] == "bl_ext":
    # bl_ext.<repository>.<extension id> is the add-on; anything deeper is ours.
    ADDON_KEY = ".".join(_parts[:3])
    VENDORED = len(_parts) > 3
else:
    ADDON_KEY = _parts[0]
    VENDORED = len(_parts) > 1

# One address, named once. It appears in the preferences panel, in the Fusion
# ribbon, in the packaged EULA and on every store page -- four places that must
# not be allowed to say different things.
PRIVACY_URL = ("https://github.com/inspace9018/fusion-to-blender-bridge"
               "/blob/main/PRIVACY.md")

# ── Reload submodules on reinstall-without-restart ───────────────────────────
# Python caches already-imported submodules, so reinstalling the add-on WITHOUT
# restarting Blender keeps running the OLD code -- only __init__ re-runs (which
# is why the version updates but the behavior would not). Force-reload our own
# submodules here so a plain reinstall actually takes effect. Leaf modules
# first; skipped on the very first load (nothing is cached yet).
import importlib as _importlib
import sys as _sys
# NOTE: "hooks" is deliberately NOT in this list. It holds the subscriber
# registry other add-ons (Bridge Pro) register into; reloading it would reset
# that list to empty while those add-ons still believe they are subscribed,
# and they would silently stop running with no error anywhere.
for _name in ("state", "i18n", "progress", "lighting_presets",
              "step_import", "handler", "client",
              "operators", "ui"):
    # step_import is absent from the extensions-platform build; _sys.modules
    # simply has no entry for it and the loop skips it.
    _mod = _sys.modules.get(f"{__package__}.{_name}")
    if _mod is not None:
        try:
            _importlib.reload(_mod)
        except Exception:
            pass

from . import state
from .handler import SceneHandler
from .client import FusionBridgeClient
from . import operators, ui, progress


# ─── Addon Preferences (Edit > Preferences > Add-ons) ────────────────────────
class FTBPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_KEY

    ftb_language: bpy.props.EnumProperty(
        name="Language",
        description="UI language for Fusion to Blender Lite",
        items=[
            ("auto", "Auto (System)", "Auto-detect from Blender system language"),
            ("en",   "English",       "English"),
            ("ko",   "한국어",         "Korean"),
        ],
        default="auto",
    )

    # EU02: connect to the bridge automatically when Blender starts, so the
    # common same-PC user never has to press Connect -- just Sync.
    ftb_auto_connect: bpy.props.BoolProperty(
        name="Auto-connect on startup",
        description=(
            "Connect to the Fusion bridge when Blender starts, so you can go\n"
            "straight to Sync. Fusion runs on this same computer, so this only\n"
            "ever talks to 127.0.0.1 — it never reaches the internet."
        ),
        default=True,
    )

    def draw(self, context):
        from .i18n import t as _t
        layout = self.layout
        layout.prop(self, "ftb_language")
        layout.prop(self, "ftb_auto_connect")

        # The policy has to be reachable from inside the add-on, not only from
        # a store page -- that is the marketplace requirement, and it is also
        # where someone actually wonders. It goes ABOVE the STEP notice on
        # purpose: that block returns early on builds that carry the reader,
        # and a privacy link that only appears in half the builds is worse
        # than none.
        layout.operator("wm.url_open", text=_t("pref_privacy_btn"),
                        icon="URL").url = PRIVACY_URL

        # Only in the build without the STEP reader, i.e. the one from Blender's
        # extensions platform. Someone who came looking for "open a .step file"
        # deserves to be told where it lives instead of concluding it does not
        # exist. The build that has it needs no notice.
        if has_step_support():
            return

        layout.separator()
        box = layout.box()
        col = box.column(align=True)
        col.label(text=_t("pref_step_title"), icon="INFO")
        note = box.column(align=True)
        note.scale_y = 0.8
        for line in _t("pref_step_body").split("\n"):
            note.label(text=line)
        box.operator("wm.url_open", text=_t("pref_step_btn"), icon="URL").url = (
            "https://github.com/inspace9018/fusion-to-blender-bridge/releases/latest"
        )


# Fusion runs on this machine, so the bridge only ever talks to this machine.
#
# It used to accept any host:port, which let you drive Blender from Fusion on a
# second PC. Nobody was using that, and it cost more than it was worth: reaching
# another machine is an internet connection as far as Blender is concerned, which
# drags in the "Allow Online Access" preference, a network permission on the
# extensions platform, and a firewall hole on the user's LAN. Pinning it to the
# loopback address removes all three at once -- Blender's own extension rules say
# in as many words that depending on external servers is not allowed, but
# "localhost is fine".
BRIDGE_PORT = 9080
BRIDGE_HOST = "127.0.0.1"
BRIDGE_SERVER = f"{BRIDGE_HOST}:{BRIDGE_PORT}"


def _register_properties():
    # ── Connection ──────────────────────────────────────────────────────────
    bpy.types.Scene.ftb_server = bpy.props.StringProperty(
        name="Server",
        description="Fusion 360 bridge address on this machine",
        default=BRIDGE_SERVER,
    )

    # ── Coordinate system: Fusion mesh raw coords → Blender Z-up conversion ─
    bpy.types.Scene.ftb_up_axis = bpy.props.EnumProperty(
        name="Fusion Up Axis",
        description=(
            "Specify which axis the Fusion mesh raw data uses as 'up'.\n"
            "Z: No conversion (Fusion 3D is Z-up, same as Blender).\n"
            "Y: Apply Rx(+90°) (for Y-up source data)."
        ),
        items=[
            ("Z", "Z-up (identity)", "No conversion (Fusion 3D = Z-up, default)"),
            ("Y", "Y-up → Rx(+90°)", "Apply Rx(+90°) rotation (for Y-up source data)"),
        ],
        default="Z",
        update=lambda self, ctx: _refresh_all_transforms(),
    )

    # ── Hidden Body toggle (instant hide/show without re-sync) ─────────────
    # Default False = bodies/collections marked hidden in Fusion are also hidden in Blender.
    #   Collections: exclude_from_view_layer (checkbox)
    #   Objects: hide_viewport + hide_render
    def _on_show_hidden_changed(self, ctx):
        try:
            from .handler import _refresh_hidden_state
            _refresh_hidden_state()
        except Exception:
            pass

    bpy.types.Scene.ftb_show_hidden_bodies = bpy.props.BoolProperty(
        name="Show Hidden Bodies",
        description=(
            "Toggle whether occurrences/bodies hidden in Fusion are also shown in Blender.\n"
            "Applied instantly without re-sync.\n"
            "Off (default): Fusion hidden → collection exclude / object hide.\n"
            "On:            Ignore Fusion hidden state, show everything."
        ),
        default=False,
        update=_on_show_hidden_changed,
    )

    # ── Empty parent per top-level group ────────────────────────────────────
    bpy.types.Scene.ftb_create_root_empty = bpy.props.BoolProperty(
        name="Create Top-level Empty Parent",
        description=(
            "Create an Empty at world origin for each top-level occurrence\n"
            "(PM1893D, front_1, etc.) and parent its child bodies to it.\n"
            "Moving/rotating the Empty moves the entire sub-assembly."
        ),
        default=True,
    )

    # ── Mesh quality preset ─────────────────────────────────────────────────
    # Ultra and Custom moved to Bridge Pro. The three items left keep their
    # original order on purpose: Blender stores an enum as an index, so
    # reordering would silently give every saved .blend a different preset.
    # A .blend saved on Ultra or Custom no longer has a matching item and falls
    # back to the default, which is the intended product change -- with Pro
    # installed its own precision setting takes over.
    bpy.types.Scene.ftb_mesh_preset = bpy.props.EnumProperty(
        name="Quality Preset",
        items=[
            ("low",    "Low",    "Rough, fast — quick layout check"),
            ("medium", "Medium", "Default quality — general work"),
            ("high",   "High",   "Precise — render-ready"),
        ],
        default="medium",
    )

    # ── Import options ──────────────────────────────────────────────────────
    bpy.types.Scene.ftb_update_transforms = bpy.props.BoolProperty(
        name="Update Transforms",
        description="Also update object position/rotation/scale during sync",
        default=True,
    )
    bpy.types.Scene.ftb_update_collections = bpy.props.BoolProperty(
        name="Auto Update Collections",
        description=(
            "On: Automatically move collections to match Fusion component paths on each sync\n"
            "Off: Preserve manually organized collections/hierarchy in Blender (recommended)"
        ),
        default=False,
    )

    # ── Sync state (internal, shown in UI) ──────────────────────────────────
    bpy.types.Scene.ftb_sync_status = bpy.props.StringProperty(
        default="Idle",
    )
    bpy.types.Scene.ftb_sync_progress = bpy.props.FloatProperty(
        default=0.0, min=0.0, max=1.0,
    )
    bpy.types.Scene.ftb_is_syncing = bpy.props.BoolProperty(
        default=False,
    )
    bpy.types.Scene.ftb_sync_error = bpy.props.BoolProperty(
        default=False,
    )



def _refresh_all_transforms():
    """Re-apply matrix_world for all Fusion objects when ftb_up_axis changes."""
    try:
        from .handler import update_transform
        for obj in bpy.data.objects:
            if "fusion_id" in obj:
                update_transform(obj, [])
    except Exception:
        pass


def _unregister_properties():
    for prop in ("ftb_server", "ftb_up_axis", "ftb_show_hidden_bodies",
                 "ftb_create_root_empty", "ftb_mesh_preset", "ftb_update_transforms",
                 "ftb_update_collections", "ftb_sync_status", "ftb_sync_progress",
                 "ftb_is_syncing", "ftb_sync_error",
                 # Edge marking moved to Bridge Pro. A .blend saved while it
                 # lived here still carries these, so they are cleaned up on
                 # the way out rather than left behind as stray properties.
                 "ftb_mark_sharp", "ftb_mark_seam", "ftb_mark_smart",
                 "ftb_auto_mark_on_sync",
                 # Custom tolerances moved with Ultra.
                 "ftb_surface_tol_mm", "ftb_normal_tol_deg", "ftb_max_edge_mm"):
        try:
            delattr(bpy.types.Scene, prop)
        except AttributeError:
            pass


def has_step_support() -> bool:
    """Is the STEP reader part of this build?

    It is not, in the build published to Blender's extensions platform. Reading a
    STEP file needs a CAD kernel, and that kernel drags in ~150 MB of wheels
    (OpenCascade, and VTK, which OpenCascade's loader insists on even though
    nothing here calls it) plus a second copy of numpy alongside Blender's own.
    The platform's limit is 100 MB and the numpy clash is worse than the size.

    So `step_import.py` is simply absent from that zip, and everything STEP hides
    itself. Anyone who wants it downloads the full build from GitHub. Nobody
    finding this add-on inside Blender is short of a way to get CAD in -- they
    have Fusion, which is the entire point of the bridge.
    """
    import importlib.util
    return importlib.util.find_spec(f"{__package__}.step_import") is not None


def _step_import_menu(self, context):
    """Add STEP import to File > Import menu."""
    self.layout.operator("ftb.import_step", text="STEP via Fusion Bridge (.step/.stp)")


def _try_auto_connect():
    """EU02: one-shot auto-connect on startup if the preference is enabled.

    Deferred via a timer so the context/scene is ready and we don't start a
    thread inside register(). Returns None so it runs exactly once.
    """
    try:
        client = state.get_client()
        # Already gone, already connected, or already connecting -- nothing to do.
        if client is None or client.connected or client._should_reconnect:
            return None
        prefs = bpy.context.preferences.addons.get(ADDON_KEY)
        if not prefs or not getattr(prefs.preferences, "ftb_auto_connect", True):
            return None
        server = "localhost:9080"
        scene = getattr(bpy.context, "scene", None)
        if scene is not None:
            server = getattr(scene, "ftb_server", server) or server
        client.connect(server)
        print(f"[FusionBridge] Auto-connect to {server} (EU02)")
    except Exception as e:
        print(f"[FusionBridge] Auto-connect skipped: {e}")
    return None  # one-shot


@bpy.app.handlers.persistent
def _restore_queue_drain(_dummy):
    """Opening a .blend removes every registered timer, including the one that
    reads what Fusion sends back. Put it back.

    Marked persistent because a handler that is not survives exactly the event
    it exists to react to.
    """
    client = state.get_client()
    if client is not None:
        try:
            client.reinstate_timer()
        except Exception:
            traceback.print_exc()


_VALID_PRESETS = {"low", "medium", "high"}


@bpy.app.handlers.persistent
def _fix_stale_mesh_preset(_dummy):
    """Repair a quality preset that no longer exists.

    Ultra and Custom moved to Bridge Pro. Blender stores an enum as an index,
    so a .blend saved on one of them now points past the end of the list: the
    dropdown draws EMPTY and the tolerance readout shows dashes. Seen in the
    real app -- it reads as the add-on being broken, not as a setting having
    moved.

    Reset rather than left alone, and said out loud rather than silently: the
    sync would otherwise go out at whatever the empty value resolves to.
    """
    for scene in bpy.data.scenes:
        try:
            current = scene.ftb_mesh_preset
        except Exception:
            current = None
        if current in _VALID_PRESETS:
            continue
        try:
            scene.ftb_mesh_preset = "medium"
            print(f"[FusionBridge] '{scene.name}' had a quality preset that no "
                  f"longer exists (Ultra and Custom are in Bridge Pro now); "
                  f"reset to Medium.")
        except Exception:
            traceback.print_exc()


def _fix_stale_mesh_preset_once():
    """Timer wrapper: run the repair once, then stop."""
    try:
        _fix_stale_mesh_preset(None)
    except Exception:
        traceback.print_exc()
    return None


def register():
    # Read, never typed. This line said v1.4 for a whole release after the
    # add-on was renumbered, because a hand-written version drifts the moment
    # anyone forgets it exists.
    ver = ".".join(str(x) for x in ADDON_VERSION)
    print(f"[FusionBridge] v{ver} Registering add-on...")

    # Vendored inside Bridge Pro, the host registers ONE preferences class
    # carrying these same property names. Two classes claiming the same
    # bl_idname is an error, and the second one silently wins.
    if not VENDORED:
        bpy.utils.register_class(FTBPreferences)

    state._handler = SceneHandler()
    state._client  = FusionBridgeClient(state._handler)

    _register_properties()

    for cls in operators.OPERATOR_CLASSES:
        bpy.utils.register_class(cls)


    for cls in ui.PANEL_CLASSES:
        bpy.utils.register_class(cls)

    progress.register()

    # Register in File > Import menu
    if has_step_support():
        bpy.types.TOPBAR_MT_file_import.append(_step_import_menu)

    if _restore_queue_drain not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_restore_queue_drain)
    if _fix_stale_mesh_preset not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_fix_stale_mesh_preset)
    # Also for the file that is already open when the add-on is enabled -- but
    # NOT from here. During registration bpy.data is a _RestrictData stand-in
    # and touching it raises, which at startup means a traceback on every launch
    # and the add-on failing to enable. A zero-delay timer runs at the first
    # moment data is real.
    bpy.app.timers.register(_fix_stale_mesh_preset_once, first_interval=0.0)

    # EU02: auto-connect shortly after startup (deferred so context is ready).
    try:
        bpy.app.timers.register(_try_auto_connect, first_interval=1.0)
    except Exception:
        pass

    print("[FusionBridge] Add-on registered")


def unregister():
    print("[FusionBridge] Unregistering add-on...")

    if _restore_queue_drain in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_restore_queue_drain)
    if _fix_stale_mesh_preset in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_fix_stale_mesh_preset)

    # EU02: drop the deferred auto-connect timer if it hasn't fired yet.
    try:
        if bpy.app.timers.is_registered(_try_auto_connect):
            bpy.app.timers.unregister(_try_auto_connect)
    except Exception:
        pass

    # Remove from File > Import menu
    try:
        bpy.types.TOPBAR_MT_file_import.remove(_step_import_menu)
    except Exception:
        pass          # never added (build without STEP)

    progress.unregister()

    if state._client and state._client.connected:
        state._client.disconnect()
    state._client  = None
    state._handler = None

    for cls in reversed(ui.PANEL_CLASSES):
        bpy.utils.unregister_class(cls)


    for cls in reversed(operators.OPERATOR_CLASSES):
        bpy.utils.unregister_class(cls)

    _unregister_properties()

    if not VENDORED:
        bpy.utils.unregister_class(FTBPreferences)

    print("[FusionBridge] Add-on unregistered")


if __name__ == "__main__":
    register()
