"""
Fusion to Blender - Blender Operators
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

import math
import os

import bpy
from bpy.props import StringProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper

from . import state
from .handler import update_transform
from .i18n import t


def _local_server():
    """The one address the bridge talks to. See __init__.BRIDGE_SERVER."""
    from . import BRIDGE_SERVER
    return BRIDGE_SERVER


_get_client = state.get_client
_get_handler = state.get_handler


def _build_quality(context) -> dict:
    """The quality to ask Fusion for, after subscribers have had their say.

    Density is decided by Fusion while it tessellates, so this is the only
    moment it can be influenced -- nothing on the Blender side can add detail
    to a mesh that arrived without it. Bridge Pro subscribes here to ask for
    tolerances finer than the presets offered below.
    """
    from . import hooks
    return hooks.run_quality({"preset": context.scene.ftb_mesh_preset})


def _selected_fusion_objects(context):
    """Return only selected objects that have a fusion_id."""
    return [obj for obj in context.selected_objects if "fusion_id" in obj]


class FTB_OT_Connect(bpy.types.Operator):
    bl_idname = "ftb.connect"
    bl_label = "Connect"
    bl_description = "Connect to Fusion 360 bridge server"

    @classmethod
    def poll(cls, context):
        client = _get_client()
        return client is not None and not client._should_reconnect

    def execute(self, context):
        client = _get_client()
        # Not read from the scene. A .blend saved with the old build can carry a
        # remote address in ftb_server, and honouring it would quietly reopen the
        # off-machine connection this version deliberately dropped. The address
        # comes from one constant now, and nothing can steer it elsewhere.
        server = _local_server()
        context.scene.ftb_server = server
        client.connect(server)
        self.report({"INFO"}, t("connecting_to", server=server))
        return {"FINISHED"}


class FTB_OT_Disconnect(bpy.types.Operator):
    bl_idname = "ftb.disconnect"
    bl_label = "Disconnect"
    bl_description = "Stop connection and auto-reconnect"

    @classmethod
    def poll(cls, context):
        client = _get_client()
        return client is not None and client._should_reconnect

    def execute(self, context):
        client = _get_client()
        client.disconnect()
        self.report({"INFO"}, t("disconnected"))
        return {"FINISHED"}


class FTB_OT_RequestSync(bpy.types.Operator):
    bl_idname = "ftb.request_sync"
    bl_label = "Sync"
    bl_description = "Request full sync from Fusion 360 with current quality settings"

    @classmethod
    def poll(cls, context):
        # EU01: Sync is usable even while disconnected -- it connects first, then
        # syncs. Enabled whenever a client exists and a server address is set.
        client = _get_client()
        if client is None:
            return False
        return client.connected or bool(getattr(context.scene, "ftb_server", ""))

    def execute(self, context):
        client = _get_client()
        quality = _build_quality(context)
        # Both modes (show_all / import_hide) load all Fusion hidden bodies.
        # Visibility in Blender is handled differently by the handler.
        show_hidden = getattr(context.scene, "ftb_show_hidden_bodies", False)
        mode_str = "show_all" if show_hidden else "import_hide"

        # Show the syncing state NOW. Otherwise nothing changes until Fusion finishes
        # counting bodies and sends sync_start, and the add-on looks frozen.
        handler = _get_handler()
        if handler is not None:
            handler._set_status(t("fusion_computing"))
            handler._set_syncing(True)
            handler._set_progress(0.0)
            handler._tag_redraw()
            # Bound the wait. Without this, a Fusion side that never answers
            # leaves the panel saying "Fusion computing..." indefinitely.
            handler.arm_sync_watchdog()

        if client.connected:
            client.request_sync(quality=quality, include_hidden=True)
            self.report({"INFO"}, t("sync_requested",
                                  preset=quality.get('preset', 'custom'),
                                  mode=mode_str))
            return {"FINISHED"}

        # EU01: not connected -- stash the sync, then connect. The client fires
        # the pending sync automatically the moment the connection is up.
        client.request_sync(quality=quality, include_hidden=True)
        if not client._should_reconnect:
            server = _local_server()
            context.scene.ftb_server = server
            client.connect(server)
            self.report({"INFO"}, t("connecting_then_sync", server=server))
        else:
            # Already connecting (reconnect countdown) -- pending sync will fire.
            self.report({"INFO"}, t("sync_after_connect"))
        return {"FINISHED"}


class FTB_OT_ClearAll(bpy.types.Operator):
    bl_idname = "ftb.clear_all"
    bl_label = "Delete All Fusion Objects"
    bl_description = "Delete all Fusion 360 objects from the Blender scene"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # The handler is None until the bridge starts, so without this the button is
        # live from launch and clicking it raises AttributeError.
        return _get_handler() is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        handler = _get_handler()
        if handler is None:
            self.report({"WARNING"}, t("bridge_not_ready"))
            return {"CANCELLED"}
        handler.clear_all()
        self.report({"INFO"}, t("all_deleted"))
        return {"FINISHED"}


class FTB_OT_SelectFusionObjects(bpy.types.Operator):
    bl_idname = "ftb.select_fusion_objects"
    bl_label = "Select Fusion Objects"
    bl_description = "Select all objects imported from Fusion 360"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        count = 0
        for obj in bpy.data.objects:
            if "fusion_id" in obj.keys():
                obj.select_set(True)
                count += 1
        self.report({"INFO"}, t("obj_selected", count=count))
        return {"FINISHED"}


class FTB_OT_ToggleHiddenBodies(bpy.types.Operator):
    bl_idname = "ftb.toggle_hidden_bodies"
    bl_label = "Toggle Hidden Bodies"
    bl_description = (
        "Toggle Blender visibility of occurrences/bodies hidden in Fusion 360.\n"
        "Applied immediately without re-sync.\n"
        "  Collection: exclude_from_view_layer (checkbox)\n"
        "  Object:     hide_viewport + hide_render"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        new_state = not bool(getattr(scene, "ftb_show_hidden_bodies", False))
        # Property update callback automatically calls _refresh_hidden_state
        scene.ftb_show_hidden_bodies = new_state
        self.report({"INFO"},
                    t("hidden_shown") if new_state else t("hidden_hidden"))
        return {"FINISHED"}


# ─── Manual rotation correction (stand up lying components) ─────────────────────
def _cycle_rotation(obj, axis: str, delta_deg: float = 90.0):
    """Update the object's rotation hint property and immediately reapply transform."""
    key = f'ftb_rot_{axis.lower()}_deg'
    current = obj.get(key, 0.0)
    obj[key] = (current + delta_deg) % 360.0
    update_transform(obj, [])


class _RotateBase(bpy.types.Operator):
    bl_options = {"REGISTER", "UNDO"}
    axis = "X"

    @classmethod
    def poll(cls, context):
        return any("fusion_id" in obj for obj in context.selected_objects)

    def execute(self, context):
        objs = _selected_fusion_objects(context)
        for obj in objs:
            _cycle_rotation(obj, self.axis, 90.0)
        self.report({"INFO"}, t("rotated", n=len(objs), axis=self.axis))
        return {"FINISHED"}


class FTB_OT_RotateX90(_RotateBase):
    bl_idname = "ftb.rotate_x_90"
    bl_label = "X +90°"
    bl_description = "Rotate selected Fusion object(s) +90° on X axis (persists through re-sync)"
    axis = "X"


class FTB_OT_RotateY90(_RotateBase):
    bl_idname = "ftb.rotate_y_90"
    bl_label = "Y +90°"
    bl_description = "Rotate selected Fusion object(s) +90° on Y axis (persists through re-sync)"
    axis = "Y"


class FTB_OT_RotateZ90(_RotateBase):
    bl_idname = "ftb.rotate_z_90"
    bl_label = "Z +90°"
    bl_description = "Rotate selected Fusion object(s) +90° on Z axis (persists through re-sync)"
    axis = "Z"


class FTB_OT_ResetRotation(bpy.types.Operator):
    bl_idname = "ftb.reset_rotation"
    bl_label = "Reset Rotation"
    bl_description = "Remove all manual rotation hints from selected Fusion object(s)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any("fusion_id" in obj for obj in context.selected_objects)

    def execute(self, context):
        objs = _selected_fusion_objects(context)
        for obj in objs:
            for k in ('ftb_rot_x_deg', 'ftb_rot_y_deg', 'ftb_rot_z_deg'):
                if k in obj:
                    del obj[k]
            update_transform(obj, [])
        self.report({"INFO"}, t("rotation_reset", n=len(objs)))
        return {"FINISHED"}


# ─── Plasticity-style face/edge utilities ────────────────────────────────────
import random
import bmesh


def _get_face_groups(mesh):
    """Read face group data from mesh custom properties."""
    groups = list(mesh.get("ftb_face_groups", []))
    face_ids = list(mesh.get("ftb_face_ids", []))
    return groups, face_ids


def _get_selected_group_ids(groups, bm):
    """Return set of group indices that the selected faces belong to."""
    if not groups:
        return set()
    selected_ids = set()
    for face in bm.faces:
        if not face.select:
            continue
        loop_start = face.loops[0].index
        g_idx = 0
        g_start = groups[0]
        g_count = groups[1]
        while g_idx + 1 < len(groups) // 2:
            if loop_start < g_start + g_count:
                break
            g_idx += 1
            g_start = groups[g_idx * 2]
            g_count = groups[g_idx * 2 + 1]
        selected_ids.add(g_idx)
    return selected_ids


def _face_boundary_edges(groups, mesh, bm):
    """Return set of edges on face group boundaries (Plasticity symmetric difference)."""
    if not groups:
        return set()
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    all_boundary = set()
    g_idx = 0
    g_start = groups[0]
    g_count = groups[1]
    current_edges = set()

    for poly in mesh.polygons:
        while g_idx + 1 < len(groups) // 2 and poly.loop_start >= g_start + g_count:
            all_boundary |= current_edges
            current_edges = set()
            g_idx += 1
            g_start = groups[g_idx * 2]
            g_count = groups[g_idx * 2 + 1]

        try:
            bm_face = bm.faces[poly.index]
        except IndexError:
            continue
        for edge in bm_face.edges:
            if edge in current_edges:
                current_edges.discard(edge)
            else:
                current_edges.add(edge)

    all_boundary |= current_edges
    return all_boundary


def _get_boundary_edges_for_groups(groups, bm, selected_ids):
    """Return only the boundary edges of the selected groups."""
    if not groups or not selected_ids:
        return set()
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    boundary = set()
    g_idx = 0
    g_start = groups[0]
    g_count = groups[1]
    current_edges = set()

    for face in bm.faces:
        ls = face.loops[0].index
        while g_idx + 1 < len(groups) // 2 and ls >= g_start + g_count:
            if g_idx in selected_ids:
                boundary |= current_edges
            current_edges = set()
            g_idx += 1
            g_start = groups[g_idx * 2]
            g_count = groups[g_idx * 2 + 1]

        if g_idx not in selected_ids:
            continue
        for edge in face.edges:
            if edge in current_edges:
                current_edges.discard(edge)
            else:
                current_edges.add(edge)

    if g_idx in selected_ids:
        boundary |= current_edges
    return boundary


class FTB_OT_SelectByFaceID(bpy.types.Operator):
    bl_idname = "mesh.ftb_select_by_face_id"
    bl_label = "Select Fusion Face"
    bl_description = "Select entire BRep Face containing the selected triangle(s)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and obj.mode == 'EDIT'
                and "fusion_id" in obj and "ftb_face_groups" in obj.data)

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        groups, face_ids = _get_face_groups(mesh)
        if not groups:
            self.report({"WARNING"}, t("no_face_groups"))
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        selected_ids = _get_selected_group_ids(groups, bm)
        if not selected_ids:
            self.report({"WARNING"}, t("no_faces_selected"))
            return {"CANCELLED"}

        g_idx = 0
        g_start = groups[0]
        g_count = groups[1]
        for face in bm.faces:
            ls = face.loops[0].index
            while g_idx + 1 < len(groups) // 2 and ls >= g_start + g_count:
                g_idx += 1
                g_start = groups[g_idx * 2]
                g_count = groups[g_idx * 2 + 1]
            if g_idx in selected_ids:
                face.select = True

        bmesh.update_edit_mesh(mesh)
        self.report({"INFO"}, t("faces_selected", n=len(selected_ids)))
        return {"FINISHED"}


class FTB_OT_SelectByFaceIDEdge(bpy.types.Operator):
    bl_idname = "mesh.ftb_select_by_face_id_edge"
    bl_label = "Select Fusion Face Boundary Edges"
    bl_description = "Select boundary edges of the BRep Face containing the selected triangle(s)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and obj.mode == 'EDIT'
                and "fusion_id" in obj and "ftb_face_groups" in obj.data)

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        groups, face_ids = _get_face_groups(mesh)
        if not groups:
            self.report({"WARNING"}, t("no_face_groups"))
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        selected_ids = _get_selected_group_ids(groups, bm)
        if not selected_ids:
            self.report({"WARNING"}, t("no_faces_selected"))
            return {"CANCELLED"}

        boundary = _get_boundary_edges_for_groups(groups, bm, selected_ids)

        for face in bm.faces:
            face.select = False
        for edge in bm.edges:
            edge.select = edge in boundary
        for vert in bm.verts:
            vert.select = any(e.select for e in vert.link_edges)

        bmesh.update_edit_mesh(mesh)
        self.report({"INFO"}, t("edges_selected", n=len(boundary)))
        return {"FINISHED"}


class FTB_OT_MergeUVSeams(bpy.types.Operator):
    bl_idname = "mesh.ftb_merge_uv_seams"
    bl_label = "Merge UV Seams"
    bl_description = "Merge UV seams, keeping only boundary seams"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH' and obj.mode == 'EDIT'
                and mesh_has_active_polygon(obj))

    def execute(self, context):
        bpy.ops.mesh.select_linked(delimit={'SEAM'})
        bpy.ops.mesh.mark_seam(clear=True)
        bpy.ops.mesh.region_to_loop()
        bpy.ops.mesh.mark_seam(clear=False)
        bpy.ops.mesh.select_all(action='DESELECT')
        context.tool_settings.mesh_select_mode = (False, False, True)
        return {"FINISHED"}


def mesh_has_active_polygon(obj):
    try:
        return obj.data.polygons.active is not None
    except Exception:
        return False


class FTB_OT_PaintFaces(bpy.types.Operator):
    bl_idname = "mesh.ftb_paint_faces"
    bl_label = "Paint Fusion Faces"
    bl_description = "Paint random colors per BRep Face group"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any("fusion_id" in obj and obj.type == 'MESH'
                   for obj in context.selected_objects)

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != 'MESH' or "fusion_id" not in obj:
                continue
            self._colorize(obj)
        return {"FINISHED"}

    def _colorize(self, obj):
        mesh = obj.data
        groups, face_ids = _get_face_groups(mesh)
        if not groups:
            self.report({"WARNING"}, t("no_face_groups_obj", name=obj.name))
            return

        if not mesh.vertex_colors:
            mesh.vertex_colors.new(name="FusionFaceColor")
        color_layer = mesh.vertex_colors.active

        g_idx = 0
        g_start = groups[0]
        g_count = groups[1]

        for poly in mesh.polygons:
            while g_idx + 1 < len(groups) // 2 and poly.loop_start >= g_start + g_count:
                g_idx += 1
                g_start = groups[g_idx * 2]
                g_count = groups[g_idx * 2 + 1]

            fid = face_ids[g_idx] if g_idx < len(face_ids) else g_idx
            rng = random.Random(fid)
            color = (rng.random(), rng.random(), rng.random(), 1.0)
            for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
                color_layer.data[li].color = color

        mat_name = "FusionFaceColor_Mat"
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes = True
            tree = mat.node_tree
            tree.nodes.clear()
            output = tree.nodes.new('ShaderNodeOutputMaterial')
            bsdf = tree.nodes.new('ShaderNodeBsdfPrincipled')
            vcol = tree.nodes.new('ShaderNodeVertexColor')
            vcol.layer_name = "FusionFaceColor"
            tree.links.new(vcol.outputs['Color'], bsdf.inputs['Base Color'])
            tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

        if mat.name not in [s.material.name for s in obj.material_slots if s.material]:
            obj.data.materials.append(mat)

        mesh.update()
        self.report({"INFO"}, t("face_groups_colored", n=len(groups)//2))


# ─── STEP File Import ─────────────────────────────────────────────────────────

class FTB_OT_ImportStepConfirm(bpy.types.Operator):
    """Confirmation dialog shown when STEP objects already exist in the scene"""
    bl_idname = "ftb.import_step_confirm"
    bl_label = "Update Existing Objects?"
    bl_options = {"INTERNAL"}

    filepath: StringProperty(options={"HIDDEN"})
    quality: StringProperty(default="medium", options={"HIDDEN"})
    step_count: bpy.props.IntProperty(default=0, options={"HIDDEN"})
    bridge_count: bpy.props.IntProperty(default=0, options={"HIDDEN"})

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def execute(self, context):
        from .step_import import import_step_file, get_deflection_for_preset

        lin, ang = get_deflection_for_preset(self.quality)
        result = import_step_file(self.filepath, linear_deflection=lin,
                                  angular_deflection=ang, operator=self)

        if "error" in result:
            self.report({"ERROR"}, result["error"])
            return {"CANCELLED"}

        filename = os.path.basename(self.filepath)
        self.report({"INFO"}, t("step_import_started",
                                file=filename, total=result["total"]))
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        if self.step_count > 0:
            layout.label(text=t("step_existing_step", count=self.step_count),
                         icon="OBJECT_DATA")
        if self.bridge_count > 0:
            layout.label(text=t("step_existing_bridge", count=self.bridge_count),
                         icon="LINKED")
        layout.separator()
        layout.label(text=t("step_update_confirm"), icon="INFO")


class FTB_OT_InstallStepSupport(bpy.types.Operator):
    """Download & install OpenCascade (cadquery-ocp) into Blender's Python so
    you can open .step/.stp files directly. ~hundreds of MB; needs internet."""
    bl_idname = "ftb.install_step_support"
    bl_label = "Install STEP Support"

    @classmethod
    def poll(cls, context):
        from .step_import import is_occ_available, get_ocp_install_state
        return (not is_occ_available()
                and get_ocp_install_state()["state"] != "running")

    def invoke(self, context, event):
        # Confirm first -- it's a large download and runs in the background.
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text=t("ocp_confirm1"), icon="IMPORT")
        col.label(text=t("ocp_confirm2"))
        col.label(text=t("ocp_confirm3"))

    def execute(self, context):
        from .step_import import start_ocp_install, get_ocp_install_state

        if not start_ocp_install():
            self.report({"WARNING"}, t("ocp_installing"))
            return {"CANCELLED"}

        # Redraw the panel while the background install runs.
        def _tick():
            wm = bpy.context.window_manager
            for win in wm.windows:
                for area in win.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
            return None if get_ocp_install_state()["state"] in ("done", "error") else 0.5

        if not bpy.app.timers.is_registered(_tick):
            bpy.app.timers.register(_tick, first_interval=0.5)
        self.report({"INFO"}, t("ocp_installing"))
        return {"FINISHED"}


class FTB_OT_ImportStep(bpy.types.Operator, ImportHelper):
    """Import STEP/STP file. Re-importing the same filename updates existing objects"""
    bl_idname = "ftb.import_step"
    bl_label = "Import STEP File"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.step;*.stp;*.STEP;*.STP",
        options={"HIDDEN"},
    )

    quality: EnumProperty(
        name="Quality",
        description="Tessellation quality for the imported STEP geometry",
        items=[
            ("low",    "Low",    "Rough, fast — quick layout check"),
            ("medium", "Medium", "Default quality — general work"),
            ("high",   "High",   "Precise — render-ready"),
            ("ultra",  "Ultra",  "Highest quality, slow — final output"),
        ],
        default="medium",
    )

    def execute(self, context):
        from .step_import import (is_occ_available, import_step_file,
                                  get_deflection_for_preset,
                                  find_existing_objects_for_step)

        if not is_occ_available():
            self.report({"ERROR"}, t("step_occ_missing"))
            return {"CANCELLED"}

        filepath = self.filepath
        if not os.path.isfile(filepath):
            self.report({"ERROR"}, f"File not found: {filepath}")
            return {"CANCELLED"}

        from pathlib import Path
        step_filename = Path(filepath).stem
        step_count, bridge_count = find_existing_objects_for_step(step_filename)

        if bridge_count > 0:
            bpy.ops.ftb.import_step_confirm('INVOKE_DEFAULT',
                                             filepath=filepath,
                                             quality=self.quality,
                                             step_count=step_count,
                                             bridge_count=bridge_count)
            return {"FINISHED"}

        lin, ang = get_deflection_for_preset(self.quality)
        result = import_step_file(filepath, linear_deflection=lin,
                                  angular_deflection=ang, operator=self)

        if "error" in result:
            self.report({"ERROR"}, result["error"])
            return {"CANCELLED"}

        filename = os.path.basename(filepath)
        self.report({"INFO"}, t("step_import_started",
                                file=filename, total=result["total"]))
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "quality")

        from .step_import import is_occ_available
        if not is_occ_available():
            box = layout.box()
            box.alert = True
            box.label(text=t("step_occ_missing_short"), icon="ERROR")


# The three STEP operators only exist where the STEP reader ships. Registering
# them in the extensions-platform build would leave buttons that raise
# ImportError the moment their poll() or draw() ran -- a dead control is worse
# than an absent one.
_STEP_CLASSES = [
    FTB_OT_ImportStepConfirm,
    FTB_OT_InstallStepSupport,
    FTB_OT_ImportStep,
]


def _step_classes():
    import importlib.util
    if importlib.util.find_spec(f"{__package__}.step_import") is None:
        return []
    return _STEP_CLASSES


OPERATOR_CLASSES = [
    FTB_OT_Connect,
    FTB_OT_Disconnect,
    FTB_OT_RequestSync,
    *_step_classes(),
    FTB_OT_ClearAll,
    FTB_OT_SelectFusionObjects,
    FTB_OT_ToggleHiddenBodies,
    FTB_OT_RotateX90,
    FTB_OT_RotateY90,
    FTB_OT_RotateZ90,
    FTB_OT_ResetRotation,
    FTB_OT_SelectByFaceID,
    FTB_OT_SelectByFaceIDEdge,
    FTB_OT_MergeUVSeams,
    FTB_OT_PaintFaces,
]
