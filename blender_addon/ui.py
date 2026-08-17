"""
Fusion to Blender - Blender UI Panel
N-panel > Fusion 360 tab
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

import bpy
from . import state
from .i18n import t

_get_client = state.get_client

# Preset value display (for UI reference)
# Note: Fusion 360 API limitations:
#   - surfaceTolerance  (surface tolerance) -- supported ✓
#   - normalTolerance   (normal angle)      -- supported ✓ (ignored if unsupported in some versions)
#   - maximumEdgeLength (max edge length)   -- not supported by API ✗
PRESET_INFO = {
    "low":    ("0.5 mm", "30°"),
    "medium": ("0.2 mm", "15°"),
    "high":   ("0.05 mm", "8°"),
    "ultra":  ("0.01 mm", "4°"),
}


def _panel_title() -> str:
    """"Fusion to Blender Lite  v1.0" -- the version read, never typed.

    It was typed, and it drifted: the panel still said v1.4 after the add-on was
    renumbered to 1.0.0, which is the version a user reads first and the one that
    ends up in every screenshot. Reading it from bl_info costs nothing and cannot
    go stale.
    """
    try:
        from . import bl_info
        return "Fusion to Blender Lite  v{}.{}".format(*bl_info["version"][:2])
    except Exception:
        return "Fusion to Blender Lite"


class FTB_PT_MainPanel(bpy.types.Panel):
    bl_idname   = "FTB_PT_main_panel"
    bl_label    = _panel_title()
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "Fusion 360"

    def _draw_step_support(self, layout):
        """The STEP reader's install prompt -- only in builds that ship it.

        `step_import` is left out of the extensions-platform zip (see
        __init__.has_step_support), so this whole section has to disappear
        without a trace rather than raise on a missing import.
        """
        try:
            from .step_import import is_occ_available, get_ocp_install_state
        except ImportError:
            return

        ocp = get_ocp_install_state()
        ocp_state = ocp["state"]
        if is_occ_available() and ocp_state not in ("running", "done", "error"):
            return

        layout.separator(factor=0.4)
        sbox = layout.box()
        if ocp_state == "running":
            sbox.label(text=t("ocp_installing"), icon="SORTTIME")
            note = sbox.column(align=True); note.scale_y = 0.7
            note.label(text=t("ocp_running_note"))
        elif ocp_state == "done":
            sbox.label(text=t("ocp_done_restart"), icon="CHECKMARK")
        elif ocp_state == "error":
            r = sbox.row(); r.alert = True
            r.label(text=t("ocp_failed"), icon="ERROR")
            msg = ocp.get("msg", "")
            if msg:
                m = sbox.column(align=True); m.scale_y = 0.7
                m.label(text=msg[:60])
            sbox.operator("ftb.install_step_support", text=t("ocp_retry"), icon="IMPORT")
        else:
            head = sbox.column(align=True); head.scale_y = 0.8
            head.label(text=t("ocp_hint1"), icon="INFO")
            head.label(text=t("ocp_hint2"))
            sbox.operator("ftb.install_step_support",
                          text=t("ocp_install_btn"), icon="IMPORT")

    def draw(self, context):
        layout = self.layout
        scene  = context.scene
        client = _get_client()

        # ── Progress bar (always visible) ────────────────────────────────────
        is_syncing   = getattr(scene, "ftb_is_syncing", False)
        is_error     = getattr(scene, "ftb_sync_error", False)
        status       = getattr(scene, "ftb_sync_status", "Idle")
        progress_val = getattr(scene, "ftb_sync_progress", 0.0)

        prog_box = layout.box()
        if is_syncing:
            # Blender 4.1+: indicator_factor  /  3.4~4.0: factor
            try:
                prog_box.progress(indicator_factor=progress_val, text=status)
            except TypeError:
                try:
                    prog_box.progress(factor=progress_val, text=status)
                except Exception:
                    prog_box.label(text=status, icon="SORTTIME")
        elif is_error:
            row = prog_box.row()
            row.alert = True
            row.label(text=status, icon="CANCEL")
        else:
            row = prog_box.row()
            # Default property value is "Idle" (English); translate for display
            display_status = t("idle") if status == "Idle" else status
            is_done = status != "Idle" and status != ""
            row.label(text=display_status, icon="CHECKMARK" if is_done else "TIME")
        layout.separator(factor=0.3)

        # ── Connection status ─────────────────────────────────────────────────
        conn_box = layout.box()
        if client and client.connected:
            row = conn_box.row()
            row.label(text=t("connected"), icon="CHECKMARK")
            row.label(text=client.server)
            conn_box.operator("ftb.disconnect", text=t("disconnect"), icon="UNLINKED")

        elif client and client._should_reconnect:
            row = conn_box.row()
            cd = client.reconnect_countdown
            if cd > 0:
                row.label(text=t("reconnect_countdown", cd=cd), icon="TIME")
            else:
                row.label(text=t("connecting"), icon="TIME")
            # EU05: if a previous attempt failed, show why + how to fix it.
            err = getattr(client, "connect_error", None)
            if err in ("refused", "timeout", "unreachable", "invalid"):
                hint = conn_box.column(align=True)
                hint.scale_y = 0.75
                hint.alert = True
                hint.label(text=t(f"err_{err}"), icon="ERROR")
            conn_box.operator("ftb.disconnect", text=t("cancel"), icon="X")

        else:
            conn_box.label(text=t("not_connected"), icon="CANCEL")
            # No address field: the bridge only talks to Fusion on this machine,
            # so there is nothing here for anyone to get right or wrong.
            conn_box.operator("ftb.connect", text="Connect", icon="LINKED")
            # EU04: first-use hint -- with auto-connect/auto-sync this is all it takes.
            hint = conn_box.column(align=True)
            hint.scale_y = 0.7
            hint.label(text=t("hint_step1"), icon="INFO")
            hint.label(text=t("hint_step2"), icon="BLANK1")

        layout.separator(factor=0.5)

        # ── Mesh Quality ─────────────────────────────────────────────────────
        q_box = layout.box()
        col = q_box.column(align=True)
        col.label(text=t("mesh_quality"), icon="MESH_DATA")
        col.separator(factor=0.3)
        col.prop(scene, "ftb_mesh_preset", text="")

        preset = scene.ftb_mesh_preset

        if preset != "custom":
            # Preset value info
            info = PRESET_INFO.get(preset, ("—", "—"))
            info_col = q_box.column(align=True)
            info_col.scale_y = 0.75
            info_col.label(text=f"  {t('surface_tol')}:  {info[0]}", icon="DOT")
            info_col.label(text=f"  {t('normal_angle')}:  {info[1]}", icon="DOT")
        else:
            # Custom parameter input
            custom_col = q_box.column(align=True)
            custom_col.separator(factor=0.5)

            row = custom_col.row(align=True)
            row.label(text=t("surface_tol_mm"))
            row = custom_col.row(align=True)
            row.prop(scene, "ftb_surface_tol_mm", text="")

            custom_col.separator(factor=0.3)
            row = custom_col.row(align=True)
            row.label(text=t("normal_angle_deg"))
            row = custom_col.row(align=True)
            row.prop(scene, "ftb_normal_tol_deg", text="")

            # maximumEdgeLength removed -- not supported by Fusion 360 API

        layout.separator(factor=0.5)

        # ── Coordinate System toggle ──────────────────────────────────────────
        axis_box = layout.box()
        axis_box.label(text=t("coord_system"), icon="ORIENTATION_GLOBAL")
        axis_box.prop(scene, "ftb_up_axis", text="Fusion Up")
        axis_note = axis_box.column(align=True)
        axis_note.scale_y = 0.7
        axis_note.label(text=t("coord_hint"), icon="INFO")

        # ── Import Options ────────────────────────────────────────────────────
        opt_box = layout.box()
        opt_box.label(text=t("import_options"), icon="IMPORT")
        # Hidden Body toggle -- operator button (immediate hide/show without re-sync)
        # Button label/icon changes based on current state.
        is_showing_hidden = getattr(scene, "ftb_show_hidden_bodies", False)
        hide_row = opt_box.row()
        hide_row.scale_y = 1.2
        if is_showing_hidden:
            hide_row.operator("ftb.toggle_hidden_bodies",
                              text=t("hide_hidden"),
                              icon="HIDE_OFF")
        else:
            hide_row.operator("ftb.toggle_hidden_bodies",
                              text=t("show_hidden"),
                              icon="HIDE_ON")
        opt_box.prop(scene, "ftb_create_root_empty", text=t("root_empty"))
        opt_box.prop(scene, "ftb_update_transforms", text=t("update_transforms"))
        opt_box.prop(scene, "ftb_update_collections", text=t("auto_update_col"))

        layout.separator(factor=0.3)

        # ── Sync button + status ─────────────────────────────────────────────
        sync_row = layout.row()
        sync_row.scale_y = 1.5
        sync_row.operator("ftb.request_sync", text=t("sync"), icon="FILE_REFRESH")

        # ── STEP support (OCP) installer -- shown only while relevant (F033) ───
        # Absent entirely in the extensions-platform build; see
        # __init__.has_step_support() for why. Nothing below should run then.
        self._draw_step_support(layout)

        # ── Language selector ────────────────────────────────────────────────
        layout.separator(factor=0.5)
        try:
            prefs = context.preferences.addons.get(__package__)
            if prefs:
                lang_row = layout.row(align=True)
                lang_row.label(text="", icon="WORLD")
                lang_row.prop(prefs.preferences, "ftb_language", text="")
        except Exception:
            pass


class FTB_PT_ManagePanel(bpy.types.Panel):
    bl_idname   = "FTB_PT_manage_panel"
    bl_label    = "Object Management"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "Fusion 360"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene  = context.scene

        layout.prop(scene, "ftb_update_transforms", text=t("update_transforms_l"))
        layout.prop(scene, "ftb_update_collections", text=t("auto_update_col_l"))

        # Collection preservation notice
        if not getattr(scene, "ftb_update_collections", False):
            note = layout.column(align=True)
            note.scale_y = 0.75
            note.label(text=t("preserving_col"), icon="LOCKED")

        layout.separator(factor=0.5)

        fusion_count = sum(1 for obj in bpy.data.objects if "fusion_id" in obj.keys())
        layout.label(text=t("fusion_obj_count", count=fusion_count), icon="OBJECT_DATA")

        layout.separator(factor=0.5)
        layout.operator("ftb.select_fusion_objects",
                        text=t("select_fusion"), icon="RESTRICT_SELECT_OFF")
        layout.operator("ftb.clear_all", text=t("delete_all"), icon="TRASH")

        # ── Manual rotation for selected objects (stand up sideways sub-assemblies) ──
        sel_fusion = [o for o in context.selected_objects if "fusion_id" in o]
        if sel_fusion:
            layout.separator(factor=0.5)
            box = layout.box()
            box.label(text=t("rotation_correction", n=len(sel_fusion)), icon="EMPTY_AXIS")

            note = box.column(align=True)
            note.scale_y = 0.75
            note.label(text=t("rotation_hint"))

            row = box.row(align=True)
            row.operator("ftb.rotate_x_90", text="X +90°")
            row.operator("ftb.rotate_y_90", text="Y +90°")
            row.operator("ftb.rotate_z_90", text="Z +90°")
            box.operator("ftb.reset_rotation", text=t("reset_rotation"), icon="LOOP_BACK")

            # Current rotation display
            if len(sel_fusion) == 1:
                obj = sel_fusion[0]
                rx = obj.get('ftb_rot_x_deg', 0)
                ry = obj.get('ftb_rot_y_deg', 0)
                rz = obj.get('ftb_rot_z_deg', 0)
                if rx or ry or rz:
                    info = box.column(align=True)
                    info.scale_y = 0.75
                    info.label(text=t("current_rot", rx=rx, ry=ry, rz=rz))


class FTB_PT_UtilitiesPanel(bpy.types.Panel):
    bl_idname   = "FTB_PT_utilities_panel"
    bl_label    = "Mesh Utilities"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "Fusion 360"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        # ── Auto Mark Edges ──────────────────────────────────────────────
        box = layout.box()
        box.label(text=t("edge_marking"), icon="EDGESEL")
        col = box.column(align=True)
        op = col.operator("mesh.ftb_auto_mark_edges", text="Auto Mark Edges",
                          icon="MOD_EDGESPLIT")
        scene = context.scene
        row = box.row(align=True)
        row.prop(scene, "ftb_mark_sharp", text="Sharp")
        row.prop(scene, "ftb_mark_seam", text="Seam")
        box.prop(scene, "ftb_mark_smart", text=t("smart_normal"))
        # Sync rebuilds the mesh and wipes marks, so offer the same "keep it applied"
        # toggle Auto Bevel already has.
        box.prop(scene, "ftb_auto_mark_on_sync", text=t("auto_mark_sync"))

        layout.separator(factor=0.3)

        # ── Face Selection ────────────────────────────────────────────────
        box = layout.box()
        box.label(text=t("face_selection"), icon="FACESEL")
        col = box.column(align=True)
        col.operator("mesh.ftb_select_by_face_id",
                     text=t("select_fusion_face"), icon="FACE_MAPS")
        col.operator("mesh.ftb_select_by_face_id_edge",
                     text=t("select_face_edge"), icon="EDGESEL")

        layout.separator(factor=0.3)

        # ── Other utilities ───────────────────────────────────────────────
        box = layout.box()
        box.label(text=t("other"), icon="TOOL_SETTINGS")
        box.operator("mesh.ftb_merge_uv_seams",
                     text="Merge UV Seams", icon="UV")
        box.operator("mesh.ftb_paint_faces",
                     text="Paint Fusion Faces", icon="BRUSH_DATA")


# ─── ID Studio upsell teaser (auto-hides once the paid add-on is installed) ───
# Hidden until ID Studio is actually for sale: flip PRO_TEASER_ENABLED to True
# at launch (and set PRO_BUY_URL to the real store page) to show it.
PRO_TEASER_ENABLED = False
PRO_BUY_URL = "https://gumroad.com/"  # TODO: set to the real ID Studio store page


def _pro_installed() -> bool:
    """True if ID Studio for Blender is installed, so we don't nag buyers."""
    if hasattr(bpy.types, "FTB_PT_IDStudioTools"):
        return True
    try:
        for name in bpy.context.preferences.addons.keys():
            if "id_studio_for_blender" in name:
                return True
    except Exception:
        pass
    return False


class FTB_PT_ProPanel(bpy.types.Panel):
    bl_idname   = "FTB_PT_pro_panel"
    bl_label    = "ID Studio for Blender"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "Fusion 360"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return PRO_TEASER_ENABLED and not _pro_installed()

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text=t("ids_teaser_audience"), icon="FUND")
        col = box.column(align=True)
        col.label(text=t("ids_feat_cameras"), icon="OUTLINER_OB_CAMERA")
        col.label(text=t("ids_feat_lights"), icon="LIGHT_AREA")
        col.label(text=t("ids_feat_cmf"), icon="MATERIAL")
        col.label(text=t("ids_feat_matrix"), icon="RENDER_ANIMATION")
        row = layout.row()
        row.scale_y = 1.3
        row.operator("wm.url_open", text=t("ids_get_button"),
                     icon="FUND").url = PRO_BUY_URL
        layout.label(text=t("ids_tagline"))


PANEL_CLASSES = [
    FTB_PT_MainPanel,
    FTB_PT_ManagePanel,
    FTB_PT_UtilitiesPanel,
    FTB_PT_ProPanel,
]
