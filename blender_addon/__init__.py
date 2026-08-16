"""
Fusion to Blender Bridge - Blender Add-on
All settings, including mesh quality, are managed on the Blender side.
"""
bl_info = {
    "name": "Fusion to Blender Bridge",
    "description": "Fusion 360 ↔ Blender real-time geometry sync (preserves materials/modifiers/light links)",
    "author": "FusionToBlenderBridge",
    "version": (1, 0, 0),
    "blender": (4, 1, 0),
    "location": "View3D > Sidebar > Fusion 360",
    "category": "Import-Export",
}

import bpy

# ── Reload submodules on reinstall-without-restart ───────────────────────────
# Python caches already-imported submodules, so reinstalling the add-on WITHOUT
# restarting Blender keeps running the OLD code — only __init__ re-runs (which
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
    bl_idname = __package__

    ftb_language: bpy.props.EnumProperty(
        name="Language",
        description="UI language for Fusion to Blender Bridge",
        items=[
            ("auto", "Auto (System)", "Auto-detect from Blender system language"),
            ("en",   "English",       "English"),
            ("ko",   "한국어",         "Korean"),
        ],
        default="auto",
    )

    # EU02: connect to the bridge automatically when Blender starts, so the
    # common same-PC user never has to press Connect — just Sync.
    ftb_auto_connect: bpy.props.BoolProperty(
        name="Auto-connect on startup",
        description=(
            "Automatically connect to the Fusion bridge when Blender starts,\n"
            "so you can just press Sync. Uses the saved server address\n"
            "(default localhost:9080). Turn off if Fusion runs on another PC\n"
            "and you don't want the localhost retry."
        ),
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "ftb_language")
        layout.prop(self, "ftb_auto_connect")


def _register_properties():
    # ── Connection ──────────────────────────────────────────────────────────
    bpy.types.Scene.ftb_server = bpy.props.StringProperty(
        name="Server",
        description="Fusion 360 server address (host:port)",
        default="localhost:9080",
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
    bpy.types.Scene.ftb_mesh_preset = bpy.props.EnumProperty(
        name="Quality Preset",
        items=[
            ("low",    "Low",    "Rough, fast — quick layout check"),
            ("medium", "Medium", "Default quality — general work"),
            ("high",   "High",   "Precise — render-ready"),
            ("ultra",  "Ultra",  "Highest quality, slow — final output"),
            ("custom", "Custom", "Enter parameters manually"),
        ],
        default="medium",
    )

    # ── Custom parameters ──────────────────────────────────────────────────
    bpy.types.Scene.ftb_surface_tol_mm = bpy.props.FloatProperty(
        name="Surface Tolerance",
        description="How far the mesh can deviate from the true surface (mm). Lower = more precise",
        default=0.2, min=0.001, max=10.0, precision=3, step=1,
        unit="NONE",
    )
    bpy.types.Scene.ftb_normal_tol_deg = bpy.props.FloatProperty(
        name="Normal Angle Tolerance",
        description="Tolerance for adjacent triangle normal angles (deg). Lower = denser curves (biggest quality impact)",
        default=15.0, min=1.0, max=60.0, precision=1, step=10,
        unit="NONE",
    )
    bpy.types.Scene.ftb_max_edge_mm = bpy.props.FloatProperty(
        name="Max Triangle Edge Length",
        description="Maximum length of a triangle edge (mm). 0 = unlimited. Controls flat-area density",
        default=0.0, min=0.0, max=100.0, precision=1, step=10,
        unit="NONE",
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

    # ── Mesh utilities (Plasticity-style) ───────────────────────────────
    bpy.types.Scene.ftb_mark_sharp = bpy.props.BoolProperty(
        name="Mark Sharp", default=True)
    bpy.types.Scene.ftb_mark_seam = bpy.props.BoolProperty(
        name="Mark Seam", default=False)
    bpy.types.Scene.ftb_mark_smart = bpy.props.BoolProperty(
        name="Smart Mode",
        description="Mark only boundary edges with different custom normals (5° threshold)",
        default=False)
    bpy.types.Scene.ftb_auto_mark_on_sync = bpy.props.BoolProperty(
        name="Auto Mark on Sync",
        description="Re-apply Auto Mark Edges to every body after each sync. Sync rebuilds "
                    "the mesh, which wipes sharp/seam marks. Objects you marked by hand are "
                    "re-marked anyway, toggle or not",
        default=False)


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
                 "ftb_create_root_empty", "ftb_mesh_preset", "ftb_surface_tol_mm",
                 "ftb_normal_tol_deg", "ftb_max_edge_mm", "ftb_update_transforms",
                 "ftb_update_collections", "ftb_sync_status", "ftb_sync_progress",
                 "ftb_is_syncing", "ftb_sync_error",
                 "ftb_mark_sharp", "ftb_mark_seam", "ftb_mark_smart",
                 "ftb_auto_mark_on_sync"):
        try:
            delattr(bpy.types.Scene, prop)
        except AttributeError:
            pass


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
        # Already gone, already connected, or already connecting — nothing to do.
        if client is None or client.connected or client._should_reconnect:
            return None
        prefs = bpy.context.preferences.addons.get(__package__)
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


def register():
    print("[FusionBridge] v1.0.0 Registering add-on...")

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
    bpy.types.TOPBAR_MT_file_import.append(_step_import_menu)

    # EU02: auto-connect shortly after startup (deferred so context is ready).
    try:
        bpy.app.timers.register(_try_auto_connect, first_interval=1.0)
    except Exception:
        pass

    print("[FusionBridge] Add-on registered")


def unregister():
    print("[FusionBridge] Unregistering add-on...")

    # EU02: drop the deferred auto-connect timer if it hasn't fired yet.
    try:
        if bpy.app.timers.is_registered(_try_auto_connect):
            bpy.app.timers.unregister(_try_auto_connect)
    except Exception:
        pass

    # Remove from File > Import menu
    bpy.types.TOPBAR_MT_file_import.remove(_step_import_menu)

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

    bpy.utils.unregister_class(FTBPreferences)

    print("[FusionBridge] Add-on unregistered")


if __name__ == "__main__":
    register()
