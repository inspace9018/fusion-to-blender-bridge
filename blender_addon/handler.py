"""
Fusion to Blender - Scene Handler (Blender side)
Core logic: update Blender scene with mesh data received from Fusion 360.
Materials, Modifiers, and Light Links live at the Object level, so replacing only Mesh data preserves them automatically.
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

import array as _arr
import base64
import json
import math
import re
import time
import traceback
from collections import deque

import bpy
import mathutils

from .i18n import t
from . import hooks

try:
    from . import progress as _progress
except Exception:
    _progress = None


def _prog(method, *args, **kwargs):
    """Safely call a method on the _progress module."""
    if _progress is None:
        return
    try:
        getattr(_progress, method)(*args, **kwargs)
    except Exception:
        pass


def _push_undo(label: str = "Fusion 360 Sync"):
    """Push an undo step on sync completion (Ctrl+Z to revert entire sync result)."""
    try:
        bpy.ops.ed.undo_push(message=label)
    except Exception:
        pass


_BATCH_SIZE = 8        # objects to process per timer tick
_REDRAW_INTERVAL = 0.08  # streaming redraw throttle (seconds)

# Fusion 360 3D environment is Z-up (same as Blender).
# Meshes arrive in Fusion world coordinates, so no extra rotation needed = identity matrix.
# Two coordinate transform matrices for Fusion mesh -> Blender.
# Scene property `ftb_up_axis` ("Y" or "Z") selects which one to use.
#   "Y": Fusion mesh is Y-up -> Rx(+90 deg) to convert to Z-up
#   "Z": Fusion mesh is already Z-up -> identity
# Convention may differ per file/body, so it is exposed as a Scene toggle.
_RX_90 = mathutils.Matrix([
    [1,  0,  0,  0],
    [0,  0, -1,  0],
    [0,  1,  0,  0],
    [0,  0,  0,  1],
])
_IDENTITY = mathutils.Matrix.Identity(4)


def _global_axis_matrix() -> mathutils.Matrix:
    """Return coordinate transform matrix based on the Scene's ftb_up_axis setting."""
    try:
        up = bpy.context.scene.ftb_up_axis
    except Exception:
        up = "Z"
    return _RX_90 if up == "Y" else _IDENTITY

# Compiled regexes (called repeatedly)
_RE_SUFFIX  = re.compile(r'\.\d+$')        # Blender duplicate suffix ".001" etc.
_RE_VER_REM = re.compile(r'\s+v\d+(?::\d+)?')
_RE_INST_REM = re.compile(r':\d+')


# ─── Search utilities ─────────────────────────────────────────────────────────
def find_object_by_fusion_id(fusion_id: str):
    for obj in bpy.data.objects:
        if obj.get("fusion_id") == fusion_id:
            return obj
    return None


# Top-level collection that Fusion-synced geometry lands in. Named "Product" so
# it lines up with the render/studio collection convention (Product/Camera/Staging).
ROOT_COLLECTION_NAME = "Product"


# ─── Collection utilities ─────────────────────────────────────────────────────
def get_or_create_collection(component_path: str,
                             root_name: str = ROOT_COLLECTION_NAME) -> bpy.types.Collection:
    """Component path -> collection (created if missing). "A/B" -> root > A > B.

    root_name is the top-level wrapper (default "Product" for the Fusion
    bridge). Pass an empty string to place the path directly under the scene --
    used by direct STEP import so it does NOT create a "Product" collection.
    """
    if root_name:
        root_col = bpy.data.collections.get(root_name)
        if root_col is None:
            root_col = bpy.data.collections.new(root_name)
            bpy.context.scene.collection.children.link(root_col)
    else:
        root_col = bpy.context.scene.collection

    if not component_path:
        return root_col

    parts = [p.strip() for p in component_path.replace("\\", "/").split("/") if p.strip()]
    if not parts:
        return root_col

    current = root_col
    for part in parts:
        # Check if current already has a child with this name
        existing_child = None
        for c in current.children:
            if c.name == part or re.sub(r'\.\d+$', '', c.name) == part:
                existing_child = c
                break

        if existing_child is not None:
            current = existing_child
        else:
            # Always create a NEW collection instead of reusing a global one.
            # bpy.data.collections.get(part) would find collections from OTHER
            # design trees (e.g. reusing "SF50-A" from a previous sync when
            # building "SF50-B/SF50-A"), causing cross-design contamination.
            child = bpy.data.collections.new(part)
            try:
                current.children.link(child)
            except RuntimeError:
                pass  # Already linked
            current = child

    return current


def link_object_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection):
    """Link object to specified collection (unlinking from previous ones)."""
    if collection in obj.users_collection:
        return  # Already in the target collection
    try:
        for col in list(obj.users_collection):
            col.objects.unlink(obj)
        collection.objects.link(obj)
    except RuntimeError:
        pass


# ── Design-root Empty parent helper ───────────────────────────────────────────
# Create a single Empty named after the design root (e.g. PB10) and parent all bodies to it.
# The component field has root_name prepended as the first segment by the exporter,
# so component.split('/')[0] becomes the design root name.
_RE_INSTANCE_NUM = re.compile(r':\d+$')


def _design_root_name(component_path: str) -> str:
    """First segment of component_path (= design root, e.g. 'PB10')."""
    if not component_path:
        return ""
    parts = [p for p in component_path.replace("\\", "/").split("/") if p]
    if not parts:
        return ""
    return _RE_INSTANCE_NUM.sub('', parts[0]).strip()


def _get_or_create_root_empty(root_name: str):
    """Create/retrieve an Empty named after the design root, inside the design root's collection."""
    if not root_name:
        return None
    empty_name = f"{root_name}_origin"
    existing = bpy.data.objects.get(empty_name)
    if existing is not None and existing.type == 'EMPTY':
        return existing
    try:
        empty = bpy.data.objects.new(empty_name, None)
        empty.empty_display_type = 'PLAIN_AXES'
        empty.empty_display_size = 1.0
        empty["ftb_root_empty"] = root_name
        col = get_or_create_collection(root_name)
        try:
            col.objects.link(empty)
        except Exception:
            pass
        return empty
    except Exception:
        traceback.print_exc()
        return None


def _parent_to_root_empty(obj: bpy.types.Object, component_path: str):
    """Parent obj to the design-root Empty (preserving world coordinates).
    First segment of component_path is the design root name.
    """
    try:
        root_name = _design_root_name(component_path)
        if not root_name:
            return
        empty = _get_or_create_root_empty(root_name)
        if empty is None or empty is obj:
            return
        if obj.parent is empty:
            return
        world_mat = obj.matrix_world.copy()
        obj.parent = empty
        try:
            obj.matrix_parent_inverse = empty.matrix_world.inverted()
        except Exception:
            obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        obj.matrix_world = world_mat
    except Exception:
        traceback.print_exc()


def _find_collection_by_path(col_path: str, root_col_name: str = ROOT_COLLECTION_NAME):
    """Look up a collection by component path format ('PB10/PM1893D/FILTERSCREEN_ASM')."""
    if not col_path:
        return None
    root = bpy.data.collections.get(root_col_name)
    if root is None:
        return None
    parts = [p for p in col_path.replace("\\", "/").split("/") if p]
    if not parts:
        return root
    current = root
    for part in parts:
        nxt = None
        for child in current.children:
            if child.name == part:
                nxt = child
                break
        if nxt is None:
            # Handle Blender duplicate avoidance ".001" suffix
            for child in current.children:
                base = re.sub(r'\.\d+$', '', child.name)
                if base == part:
                    nxt = child
                    break
        if nxt is None:
            return None
        current = nxt
    return current


def _find_layer_collection(view_layer, target_col):
    """Find the LayerCollection corresponding to target_col in the ViewLayer's layer_collection tree."""
    def _walk(lc):
        if lc.collection is target_col:
            return lc
        for child in lc.children:
            found = _walk(child)
            if found:
                return found
        return None
    try:
        return _walk(view_layer.layer_collection)
    except Exception:
        return None


def _is_show_hidden() -> bool:
    """Value of Scene's ftb_show_hidden_bodies toggle (default False = keep hidden)."""
    try:
        return bool(getattr(bpy.context.scene, "ftb_show_hidden_bodies", False))
    except Exception:
        return False


def _apply_obj_hidden(obj: bpy.types.Object, fusion_hidden: bool):
    """Set object's hide_viewport / hide_render according to the toggle + fusion_hidden.

    If show_hidden=True, display even when fusion_hidden.
    If show_hidden=False, hide only when fusion_hidden=True.
    """
    should_hide = bool(fusion_hidden) and not _is_show_hidden()
    try:
        obj.hide_viewport = should_hide
        obj.hide_render = should_hide
    except Exception:
        pass


def _apply_col_hidden(col, fusion_hidden: bool):
    """Apply collection's exclude_from_view_layer (checkbox) across all view layers.

    User requirement: when hiding collections, use exclude_from_view_layer instead of
    enable_in_viewport (hide_viewport). Since exclude is a LayerCollection property,
    we find and set it for each view layer.
    """
    should_exclude = bool(fusion_hidden) and not _is_show_hidden()
    try:
        for view_layer in bpy.context.scene.view_layers:
            lc = _find_layer_collection(view_layer, col)
            if lc is not None:
                try:
                    lc.exclude = should_exclude
                except Exception as e:
                    print(f"[FusionBridge] Failed to set collection exclude on '{col.name}': {e}")
                    pass
    except Exception:
        pass


def _refresh_hidden_state():
    """Called when ftb_show_hidden_bodies toggle changes -- reapply visibility state
    of all Fusion objects/collections to match the current toggle. Applies immediately without re-sync.
    """
    # objects
    for obj in bpy.data.objects:
        if obj.get("ftb_body_hidden"):
            _apply_obj_hidden(obj, True)
    # collections
    for col in bpy.data.collections:
        if col.get("ftb_collection_hidden"):
            _apply_col_hidden(col, True)


# ─── Compatibility wrapper (maintain legacy call paths) ───────────────────────
def _apply_hidden_state(obj: bpy.types.Object, fusion_hidden: bool):
    """Legacy code compatibility. Handles body-level hide."""
    if fusion_hidden:
        obj["ftb_body_hidden"] = True
    elif "ftb_body_hidden" in obj:
        del obj["ftb_body_hidden"]
    _apply_obj_hidden(obj, fusion_hidden)


def _apply_hidden_collections(hidden_paths: set):
    """Mark collections for the given component path set as hidden and apply immediately."""
    if not hidden_paths:
        print("[FusionBridge] HIDE-COL: no hidden ancestor paths this sync "
              "(nothing to hide)")
        return
    # First clear existing marks
    for col in bpy.data.collections:
        if col.get("ftb_collection_hidden"):
            try:
                del col["ftb_collection_hidden"]
            except Exception:
                pass
            _apply_col_hidden(col, False)
    # Apply new marks
    print(f"[FusionBridge] HIDE-COL: {len(hidden_paths)} path(s) to hide: "
          f"{sorted(hidden_paths)}")
    for path in hidden_paths:
        col = _find_collection_by_path(path)
        if col is None:
            print(f"[FusionBridge] HIDE-COL  ✗ path NOT FOUND in 'Product' "
                  f"tree: '{path}'")
            continue
        col["ftb_collection_hidden"] = True
        _apply_col_hidden(col, True)
        # Read back the resulting exclude state to confirm it actually took
        try:
            states = []
            for vl in bpy.context.scene.view_layers:
                lc = _find_layer_collection(vl, col)
                states.append("?" if lc is None else str(lc.exclude))
            print(f"[FusionBridge] HIDE-COL  ✓ '{path}' → collection '{col.name}' "
                  f"exclude={states}")
        except Exception:
            pass


# ─── Mesh update ──────────────────────────────────────────────────────────────
def _b64_f32(s: str) -> _arr.array:
    return _arr.array('f', base64.b64decode(s))


def _b64_i32(s: str) -> _arr.array:
    return _arr.array('i', base64.b64decode(s))


def _b64_i64(s: str) -> _arr.array:
    """Signed 64-bit array. Used for BRep face keys (exporter._face_key)."""
    return _arr.array('q', base64.b64decode(s))


# ─── Edge bevel weight access (Blender 4.x attribute API + legacy) ────────────
def _get_edge_bevel_weights(mesh):
    """Per-edge bevel weights as a float32 array, or None when unavailable.

    Blender 4.0+ stores edge bevel weights in the generic 'bevel_weight_edge'
    attribute; older versions expose edge.bevel_weight directly.
    """
    import numpy as np

    n_edges = len(mesh.edges)
    if n_edges == 0:
        return None
    attr = mesh.attributes.get("bevel_weight_edge")
    if attr is not None and attr.domain == 'EDGE' and attr.data_type == 'FLOAT':
        buf = np.empty(n_edges, dtype=np.float32)
        attr.data.foreach_get("value", buf)
        return buf
    try:
        return np.array([e.bevel_weight for e in mesh.edges], dtype=np.float32)
    except (AttributeError, TypeError):
        return None


def _set_edge_bevel_weights(mesh, weights):
    """Write per-edge bevel weights (counterpart of _get_edge_bevel_weights)."""
    try:
        attr = mesh.attributes.get("bevel_weight_edge")
        if attr is None:
            attr = mesh.attributes.new("bevel_weight_edge", 'FLOAT', 'EDGE')
        if attr is not None and attr.domain == 'EDGE' and attr.data_type == 'FLOAT':
            attr.data.foreach_set("value", weights)
            return
    except Exception:
        pass
    try:
        for i, w in enumerate(weights):
            if w > 0:
                mesh.edges[i].bevel_weight = float(w)
    except (AttributeError, TypeError):
        pass


def _save_vertex_groups(obj, mesh):
    """Vertex group names + per-vertex weights.

    mesh.clear_geometry() destroys the groups themselves, not just the weights
    (verified), and a modifier bound to one keeps pointing at the now-missing name --
    a Mask modifier silently masks the whole object away. So they have to be saved
    and rebuilt like UVs and colours are.

    Returns [(name, {vert_index: weight}), ...] in object order, or [] when there are
    none -- which is the common case, and costs nothing.
    """
    if obj is None or not obj.vertex_groups:
        return []
    names = [g.name for g in obj.vertex_groups]
    per_group = [dict() for _ in names]
    n_groups = len(names)
    for vi, v in enumerate(mesh.vertices):
        for ge in v.groups:
            gi = ge.group
            if 0 <= gi < n_groups:
                per_group[gi][vi] = ge.weight
    return list(zip(names, per_group))


def _apply_vertex_groups(obj, pairs):
    """Rebuild vertex groups from [(name, {vert_index: weight}), ...].

    Weights are bucketed by value because VertexGroup.add() takes one weight for a
    list of indices -- a weight-painted mesh has few distinct values, so this is a
    handful of calls instead of one per vertex.
    """
    for name, weights in pairs:
        vg = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
        buckets = {}
        for vi, w in weights.items():
            buckets.setdefault(round(float(w), 6), []).append(vi)
        for w, idxs in buckets.items():
            try:
                vg.add(idxs, w, 'REPLACE')
            except Exception:
                pass


def _save_mesh_userdata(obj, mesh):
    """Save UV, vertex colour, edge mark, material and vertex group data before the
    geometry clear that a sync does."""
    import numpy as np

    n_verts = len(mesh.vertices)
    n_loops = len(mesh.loops)
    if n_verts == 0 or n_loops == 0:
        return None

    # Vertex positions
    vert_co = np.empty(n_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", vert_co)
    vert_co = vert_co.reshape(-1, 3)

    # Loop → vertex mapping
    loop_verts = np.empty(n_loops, dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_verts)

    # Polygon data (for seam-aware UV matching)
    n_polys = len(mesh.polygons)
    poly_loop_starts = np.empty(n_polys, dtype=np.int32)
    poly_loop_totals = np.empty(n_polys, dtype=np.int32)
    mesh.polygons.foreach_get("loop_start", poly_loop_starts)
    mesh.polygons.foreach_get("loop_total", poly_loop_totals)

    # UV layers
    uv_data = {}
    uv_active = ""
    try:
        if mesh.uv_layers and mesh.uv_layers.active:
            uv_active = mesh.uv_layers.active.name
    except Exception:
        pass
    for uvl in mesh.uv_layers:
        try:
            buf = np.empty(n_loops * 2, dtype=np.float32)
            uvl.data.foreach_get("uv", buf)
            uv_data[uvl.name] = buf.reshape(-1, 2)
        except Exception:
            pass

    # Edge marks (sharp, seam, crease, bevel weight)
    n_edges = len(mesh.edges)
    edge_data = {}
    if n_edges > 0:
        # Read edge vertex indices
        edge_verts = np.empty(n_edges * 2, dtype=np.int32)
        mesh.edges.foreach_get("vertices", edge_verts)
        edge_verts = edge_verts.reshape(-1, 2)

        # Read edge flags
        edge_sharp = np.empty(n_edges, dtype=np.bool_)
        edge_seam = np.empty(n_edges, dtype=np.bool_)
        mesh.edges.foreach_get("use_edge_sharp", edge_sharp)
        mesh.edges.foreach_get("use_seam", edge_seam)

        # Read crease (Blender 4.0+ uses mesh attributes, legacy uses edge.crease)
        edge_crease = None
        try:
            if hasattr(mesh, 'edge_creases') and mesh.edge_creases:
                # Blender 4.0+: crease is a separate attribute
                edge_crease = np.empty(n_edges, dtype=np.float32)
                mesh.edge_creases.foreach_get("value", edge_crease)
            else:
                # Try legacy API
                edge_crease = np.array([mesh.edges[i].crease for i in range(n_edges)],
                                       dtype=np.float32)
        except Exception:
            pass

        # Read bevel weight (Blender 4.x 'bevel_weight_edge' attribute / legacy)
        edge_bevel = _get_edge_bevel_weights(mesh)

        # Check if any edge has user-set data (skip saving if all default)
        has_any_marks = (edge_sharp.any() or edge_seam.any()
                         or (edge_crease is not None and np.any(edge_crease > 0))
                         or (edge_bevel is not None and np.any(edge_bevel > 0)))

        if has_any_marks:
            # Build edge key: sorted quantized vertex positions -> (sharp, seam, crease, bevel)
            q = np.round(vert_co * 1e6).astype(np.int64)
            edge_data["keys"] = []  # list of ((x1,y1,z1),(x2,y2,z2))
            edge_data["sharp"] = edge_sharp
            edge_data["seam"] = edge_seam
            edge_data["crease"] = edge_crease
            edge_data["bevel"] = edge_bevel
            for ei in range(n_edges):
                v0, v1 = int(edge_verts[ei, 0]), int(edge_verts[ei, 1])
                k0 = (int(q[v0, 0]), int(q[v0, 1]), int(q[v0, 2]))
                k1 = (int(q[v1, 0]), int(q[v1, 1]), int(q[v1, 2]))
                # Sort so (A,B) == (B,A)
                edge_data["keys"].append((k0, k1) if k0 <= k1 else (k1, k0))

    # Material indices per polygon (face → material slot assignment)
    mat_indices = None
    if n_polys > 0:
        mat_idx_buf = np.empty(n_polys, dtype=np.int32)
        mesh.polygons.foreach_get("material_index", mat_idx_buf)
        # Only save if any face uses a non-zero material slot
        if mat_idx_buf.any():
            mat_indices = mat_idx_buf
            # Build face keys for position-based matching:
            # For each polygon, create a frozenset of quantized vertex positions
            q = np.round(vert_co * 1e6).astype(np.int64)
            mat_face_keys = []
            for pi in range(n_polys):
                ls = int(poly_loop_starts[pi])
                lt = int(poly_loop_totals[pi])
                verts_in_face = set()
                for li in range(ls, ls + lt):
                    vi = int(loop_verts[li])
                    verts_in_face.add((int(q[vi, 0]), int(q[vi, 1]), int(q[vi, 2])))
                mat_face_keys.append(frozenset(verts_in_face))
        else:
            mat_face_keys = None
    else:
        mat_face_keys = None

    # Vertex colors (support both legacy vertex_colors and Blender 4.0+ color_attributes)
    vcol_data = {}
    vcol_active = ""
    vcol_source = "vertex_colors"  # track which API was used
    try:
        if hasattr(mesh, 'vertex_colors') and mesh.vertex_colors and len(mesh.vertex_colors) > 0:
            if mesh.vertex_colors.active:
                vcol_active = mesh.vertex_colors.active.name
            for vcl in mesh.vertex_colors:
                try:
                    buf = np.empty(n_loops * 4, dtype=np.float32)
                    vcl.data.foreach_get("color", buf)
                    vcol_data[vcl.name] = buf.reshape(-1, 4)
                except Exception as e:
                    print(f"[FusionBridge] Failed to read vertex color layer '{vcl.name}' on '{mesh.name}': {e}")
        elif hasattr(mesh, 'color_attributes') and mesh.color_attributes and len(mesh.color_attributes) > 0:
            vcol_source = "color_attributes"
            if mesh.color_attributes.active_color:
                vcol_active = mesh.color_attributes.active_color.name
            for ca in mesh.color_attributes:
                try:
                    if ca.domain == 'CORNER' and ca.data_type in ('FLOAT_COLOR', 'BYTE_COLOR'):
                        buf = np.empty(n_loops * 4, dtype=np.float32)
                        ca.data.foreach_get("color", buf)
                        vcol_data[ca.name] = buf.reshape(-1, 4)
                except Exception as e:
                    print(f"[FusionBridge] Failed to read color attribute '{ca.name}' on '{mesh.name}': {e}")
    except Exception:
        pass

    return {
        "vert_co": vert_co,
        "loop_verts": loop_verts,
        "poly_loop_starts": poly_loop_starts,
        "poly_loop_totals": poly_loop_totals,
        "uv_data": uv_data,
        "uv_active": uv_active,
        "vcol_data": vcol_data,
        "vcol_active": vcol_active,
        "vcol_source": vcol_source,
        "edge_data": edge_data,
        "mat_indices": mat_indices,
        "mat_face_keys": mat_face_keys,
        "vgroups": _save_vertex_groups(obj, mesh),
        "n_verts": n_verts,
        "n_loops": n_loops,
    }


def _restore_vcol_layers(mesh, vcol_data: dict, vcol_source: str,
                         pre_mapped: bool = False):
    """Restore vertex color layers using the correct API.

    vcol_source: 'vertex_colors' or 'color_attributes'
    pre_mapped: if True, values in vcol_data are already n_new_loops-sized arrays
                ready to foreach_set. Otherwise they are raw old data to copy.
    """
    if not vcol_data:
        return
    for vc_name, colors in vcol_data.items():
        try:
            if vcol_source == "color_attributes" and hasattr(mesh, 'color_attributes'):
                vcl = mesh.color_attributes.get(vc_name)
                if vcl is None:
                    vcl = mesh.color_attributes.new(
                        name=vc_name, type='FLOAT_COLOR', domain='CORNER')
                vcl.data.foreach_set("color", colors.ravel())
            else:
                # Legacy vertex_colors API
                if hasattr(mesh, 'vertex_colors'):
                    vcl = mesh.vertex_colors.get(vc_name)
                    if vcl is None:
                        vcl = mesh.vertex_colors.new(name=vc_name)
                    vcl.data.foreach_set("color", colors.ravel())
        except Exception:
            traceback.print_exc()


def _restore_active_layers(mesh, saved: dict, vcol_source: str):
    """Restore active UV and vertex color layer selections."""
    try:
        uv_active = saved.get("uv_active", "")
        if uv_active and uv_active in {u.name for u in mesh.uv_layers}:
            mesh.uv_layers.active = mesh.uv_layers[uv_active]
    except Exception:
        pass

    vcol_active = saved.get("vcol_active", "")
    if not vcol_active:
        return
    try:
        if vcol_source == "color_attributes" and hasattr(mesh, 'color_attributes'):
            if vcol_active in {c.name for c in mesh.color_attributes}:
                mesh.color_attributes.active_color = mesh.color_attributes[vcol_active]
        elif hasattr(mesh, 'vertex_colors') and mesh.vertex_colors:
            if vcol_active in {v.name for v in mesh.vertex_colors}:
                mesh.vertex_colors.active = mesh.vertex_colors[vcol_active]
    except Exception:
        pass


def _restore_edge_marks(mesh, saved):
    """Restore edge sharp/seam/crease/bevel marks after geometry rebuild.

    Uses vertex position pairs as edge identifiers. Old edges are looked up
    by sorted quantized positions of their two vertices. If a matching new
    edge exists, the marks are transferred.
    """
    import numpy as np

    edge_data = saved.get("edge_data")
    if not edge_data or "keys" not in edge_data:
        return

    n_new_edges = len(mesh.edges)
    if n_new_edges == 0:
        return

    old_keys = edge_data["keys"]
    old_sharp = edge_data["sharp"]
    old_seam = edge_data["seam"]
    old_crease = edge_data.get("crease")
    old_bevel = edge_data.get("bevel")

    # Build lookup: old edge key → old edge index
    old_edge_map = {}
    for ei, key in enumerate(old_keys):
        old_edge_map[key] = ei

    # Get new vertex positions (quantized)
    n_new_verts = len(mesh.vertices)
    new_co = np.empty(n_new_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", new_co)
    new_co = new_co.reshape(-1, 3)
    new_q = np.round(new_co * 1e6).astype(np.int64)

    # Get new edge vertex indices
    new_edge_verts = np.empty(n_new_edges * 2, dtype=np.int32)
    mesh.edges.foreach_get("vertices", new_edge_verts)
    new_edge_verts = new_edge_verts.reshape(-1, 2)

    # Match new edges to old edges and apply marks
    new_sharp = np.zeros(n_new_edges, dtype=np.bool_)
    new_seam = np.zeros(n_new_edges, dtype=np.bool_)
    new_crease = np.zeros(n_new_edges, dtype=np.float32) if old_crease is not None else None
    new_bevel = np.zeros(n_new_edges, dtype=np.float32) if old_bevel is not None else None

    matched = 0
    for ei in range(n_new_edges):
        v0 = int(new_edge_verts[ei, 0])
        v1 = int(new_edge_verts[ei, 1])
        k0 = (int(new_q[v0, 0]), int(new_q[v0, 1]), int(new_q[v0, 2]))
        k1 = (int(new_q[v1, 0]), int(new_q[v1, 1]), int(new_q[v1, 2]))
        key = (k0, k1) if k0 <= k1 else (k1, k0)

        old_ei = old_edge_map.get(key)
        if old_ei is not None:
            matched += 1
            new_sharp[ei] = old_sharp[old_ei]
            new_seam[ei] = old_seam[old_ei]
            if new_crease is not None and old_crease is not None:
                new_crease[ei] = old_crease[old_ei]
            if new_bevel is not None and old_bevel is not None:
                new_bevel[ei] = old_bevel[old_ei]

    # Apply if any marks found
    if new_sharp.any():
        mesh.edges.foreach_set("use_edge_sharp", new_sharp)
    if new_seam.any():
        mesh.edges.foreach_set("use_seam", new_seam)

    # Crease (Blender 4.0+ attribute API vs legacy)
    if new_crease is not None and np.any(new_crease > 0):
        try:
            if hasattr(mesh, 'edge_creases'):
                # Blender 4.0+: create crease layer if needed
                if not mesh.edge_creases:
                    mesh.use_customdata_edge_crease = True
                if mesh.edge_creases:
                    mesh.edge_creases.foreach_set("value", new_crease)
            else:
                for i in range(n_new_edges):
                    if new_crease[i] > 0:
                        mesh.edges[i].crease = float(new_crease[i])
        except Exception as e:
            print(f"[FusionBridge] Failed to restore edge creases on '{mesh.name}': {e}")
            pass

    # Bevel weight (Blender 4.x 'bevel_weight_edge' attribute / legacy)
    if new_bevel is not None and np.any(new_bevel > 0):
        _set_edge_bevel_weights(mesh, new_bevel)

    if matched > 0:
        print(f"[FusionBridge] Edge marks restored: {matched}/{n_new_edges} edges matched")


def _restore_material_indices(mesh, saved):
    """Restore per-face material_index after geometry rebuild.

    Uses frozenset of quantized vertex positions as face keys to match
    old polygons to new polygons, then copies material_index.
    """
    import numpy as np

    mat_indices = saved.get("mat_indices")
    mat_face_keys = saved.get("mat_face_keys")
    if mat_indices is None or mat_face_keys is None:
        return

    n_new_polys = len(mesh.polygons)
    if n_new_polys == 0:
        return

    # Tier 1: same polygon count -- direct copy
    if len(mat_indices) == n_new_polys:
        # Quick check: also verify topology matches (same vert/loop counts)
        old_n_verts = saved.get("n_verts", -1)
        old_n_loops = saved.get("n_loops", -1)
        if old_n_verts == len(mesh.vertices) and old_n_loops == len(mesh.loops):
            mesh.polygons.foreach_set("material_index", mat_indices)
            print(f"[FusionBridge] Material indices restored: direct copy ({n_new_polys} faces)")
            return

    # Tier 2: position-based matching
    # Build new face keys
    n_new_verts = len(mesh.vertices)
    new_co = np.empty(n_new_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", new_co)
    new_co = new_co.reshape(-1, 3)
    new_q = np.round(new_co * 1e6).astype(np.int64)

    n_new_loops = len(mesh.loops)
    new_loop_verts = np.empty(n_new_loops, dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", new_loop_verts)

    new_poly_starts = np.empty(n_new_polys, dtype=np.int32)
    new_poly_totals = np.empty(n_new_polys, dtype=np.int32)
    mesh.polygons.foreach_get("loop_start", new_poly_starts)
    mesh.polygons.foreach_get("loop_total", new_poly_totals)

    # Build lookup: old face key → material_index
    old_face_map = {}
    for pi, key in enumerate(mat_face_keys):
        # If multiple old faces share same vertex set (unlikely but possible),
        # keep the first one
        if key not in old_face_map:
            old_face_map[key] = int(mat_indices[pi])

    # Match new faces
    new_mat_idx = np.zeros(n_new_polys, dtype=np.int32)
    matched = 0
    for pi in range(n_new_polys):
        ls = int(new_poly_starts[pi])
        lt = int(new_poly_totals[pi])
        verts_in_face = set()
        for li in range(ls, ls + lt):
            vi = int(new_loop_verts[li])
            verts_in_face.add((int(new_q[vi, 0]), int(new_q[vi, 1]), int(new_q[vi, 2])))
        face_key = frozenset(verts_in_face)
        mat = old_face_map.get(face_key)
        if mat is not None:
            new_mat_idx[pi] = mat
            matched += 1

    if new_mat_idx.any():
        mesh.polygons.foreach_set("material_index", new_mat_idx)

    if matched > 0:
        print(f"[FusionBridge] Material indices restored: {matched}/{n_new_polys} faces matched")


def _restore_mesh_userdata(obj, mesh, saved):
    """Restore UV, vertex color, edge mark, and material index data after geometry rebuild."""
    import numpy as np

    if saved is None:
        return
    has_uv = bool(saved["uv_data"])
    has_vcol = bool(saved["vcol_data"])
    has_edges = bool(saved.get("edge_data"))
    has_mats = saved.get("mat_indices") is not None
    has_vgroups = bool(saved.get("vgroups"))
    if not has_uv and not has_vcol and not has_edges and not has_mats and not has_vgroups:
        return

    n_new_verts = len(mesh.vertices)
    n_new_loops = len(mesh.loops)
    if n_new_verts == 0 or n_new_loops == 0:
        return

    old_co = saved["vert_co"]
    old_loop_verts = saved["loop_verts"]

    vcol_source = saved.get("vcol_source", "vertex_colors")

    # ── Tier 1: Direct copy if topology unchanged ────────────────────
    if (saved["n_verts"] == n_new_verts and saved["n_loops"] == n_new_loops):
        for uv_name, old_uvs in saved["uv_data"].items():
            uvl = mesh.uv_layers.get(uv_name)
            if uvl is None:
                uvl = mesh.uv_layers.new(name=uv_name)
            uvl.data.foreach_set("uv", old_uvs.ravel())
        _restore_vcol_layers(mesh, saved["vcol_data"], vcol_source)
        _restore_active_layers(mesh, saved, vcol_source)
        # Edge marks: direct copy if edge count also unchanged
        _restore_edge_marks(mesh, saved)
        # Material indices per face
        _restore_material_indices(mesh, saved)
        # Vertex groups: same vertex count, so the indices still line up
        if has_vgroups:
            _apply_vertex_groups(obj, saved["vgroups"])
        mesh.update()
        return

    # ── Tier 2: Position-based matching ──────────────────────────────
    # Quantize old vertex positions (1µm)
    old_q = np.round(old_co * 1e6).astype(np.int64)
    old_pos_map = {}  # (x,y,z) -> old_vert_idx
    for i in range(len(old_q)):
        key = (int(old_q[i, 0]), int(old_q[i, 1]), int(old_q[i, 2]))
        if key not in old_pos_map:
            old_pos_map[key] = i

    # New vertex positions
    new_co = np.empty(n_new_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", new_co)
    new_co = new_co.reshape(-1, 3)
    new_q = np.round(new_co * 1e6).astype(np.int64)

    # Build new_vert → old_vert mapping
    new_to_old_vert = np.full(n_new_verts, -1, dtype=np.int32)
    for i in range(n_new_verts):
        key = (int(new_q[i, 0]), int(new_q[i, 1]), int(new_q[i, 2]))
        old_idx = old_pos_map.get(key, -1)
        if old_idx >= 0:
            new_to_old_vert[i] = old_idx

    # Build old_vert → list of old loops
    old_vert_to_loops = {}
    for li in range(len(old_loop_verts)):
        vi = int(old_loop_verts[li])
        if vi not in old_vert_to_loops:
            old_vert_to_loops[vi] = []
        old_vert_to_loops[vi].append(li)

    # New loop→vertex
    new_loop_verts = np.empty(n_new_loops, dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", new_loop_verts)

    # Build new polygon data for context-aware matching
    n_new_polys = len(mesh.polygons)
    new_poly_starts = np.empty(n_new_polys, dtype=np.int32)
    new_poly_totals = np.empty(n_new_polys, dtype=np.int32)
    mesh.polygons.foreach_get("loop_start", new_poly_starts)
    mesh.polygons.foreach_get("loop_total", new_poly_totals)

    # Build loop→polygon index for new mesh
    new_loop_to_poly = np.zeros(n_new_loops, dtype=np.int32)
    for pi in range(n_new_polys):
        ls = int(new_poly_starts[pi])
        lt = int(new_poly_totals[pi])
        new_loop_to_poly[ls:ls+lt] = pi

    # Build old loop→polygon index
    old_n_polys = len(saved["poly_loop_starts"])
    old_loop_to_poly = np.zeros(len(old_loop_verts), dtype=np.int32)
    for pi in range(old_n_polys):
        ls = int(saved["poly_loop_starts"][pi])
        lt = int(saved["poly_loop_totals"][pi])
        old_loop_to_poly[ls:ls+lt] = pi

    # For each new loop, find the best matching old loop
    # Strategy: prefer old loops whose neighboring vertices also match
    new_to_old_loop = np.full(n_new_loops, -1, dtype=np.int32)
    for new_li in range(n_new_loops):
        new_vi = int(new_loop_verts[new_li])
        old_vi = int(new_to_old_vert[new_vi])
        if old_vi < 0:
            continue
        old_loops = old_vert_to_loops.get(old_vi)
        if not old_loops:
            continue
        if len(old_loops) == 1:
            new_to_old_loop[new_li] = old_loops[0]
        else:
            # Multiple old loops for same vertex (UV seam) -- pick best by
            # checking if neighboring loop vertices also match
            new_pi = int(new_loop_to_poly[new_li])
            new_ps = int(new_poly_starts[new_pi])
            new_pt = int(new_poly_totals[new_pi])
            # Collect new polygon's vertex set (mapped to old verts)
            new_poly_old_verts = set()
            for li in range(new_ps, new_ps + new_pt):
                ov = int(new_to_old_vert[int(new_loop_verts[li])])
                if ov >= 0:
                    new_poly_old_verts.add(ov)

            best = old_loops[0]
            best_score = -1
            for ol in old_loops:
                # Score: count how many verts in old polygon also appear
                # in the new polygon's mapped vert set
                old_pi = int(old_loop_to_poly[ol])
                ops = int(saved["poly_loop_starts"][old_pi])
                opt = int(saved["poly_loop_totals"][old_pi])
                score = 0
                for oli in range(ops, ops + opt):
                    if int(old_loop_verts[oli]) in new_poly_old_verts:
                        score += 1
                if score > best_score:
                    best_score = score
                    best = ol
            new_to_old_loop[new_li] = best

    # Apply UV data
    for uv_name, old_uvs in saved["uv_data"].items():
        uvl = mesh.uv_layers.get(uv_name)
        if uvl is None:
            uvl = mesh.uv_layers.new(name=uv_name)
        new_uvs = np.zeros((n_new_loops, 2), dtype=np.float32)
        valid = new_to_old_loop >= 0
        new_uvs[valid] = old_uvs[new_to_old_loop[valid]]
        uvl.data.foreach_set("uv", new_uvs.ravel())

    # Apply vertex colors (Tier 2: position-based)
    if saved["vcol_data"]:
        mapped_vcol = {}
        for vc_name, old_cols in saved["vcol_data"].items():
            new_cols = np.ones((n_new_loops, 4), dtype=np.float32)  # default white
            valid = new_to_old_loop >= 0
            new_cols[valid] = old_cols[new_to_old_loop[valid]]
            mapped_vcol[vc_name] = new_cols
        _restore_vcol_layers(mesh, mapped_vcol, vcol_source, pre_mapped=True)

    # Restore active layers
    _restore_active_layers(mesh, saved, vcol_source)

    # Edge marks: position-based restoration
    _restore_edge_marks(mesh, saved)

    # Material indices per face: position-based restoration
    _restore_material_indices(mesh, saved)

    # Vertex groups: remap each old vertex's weight onto the new vertex that landed in
    # the same place. Vertices with no match keep no weight -- same rule the UV and
    # colour paths use. The group is recreated either way, so a modifier bound to it
    # still resolves even where the geometry moved.
    if has_vgroups:
        remapped = []
        for name, old_weights in saved["vgroups"]:
            new_weights = {}
            for new_vi in range(n_new_verts):
                old_vi = int(new_to_old_vert[new_vi])
                if old_vi >= 0 and old_vi in old_weights:
                    new_weights[new_vi] = old_weights[old_vi]
            remapped.append((name, new_weights))
        _apply_vertex_groups(obj, remapped)

    # Finalize -- ensure edge marks & material indices are committed
    mesh.update()

    # Note: vertex group weights are stored on Object, not Mesh. They survive
    # clear_geometry but their per-vertex weights are lost if vert count changes.
    # This is a Blender limitation.


def update_mesh_geometry(obj: bpy.types.Object, data: dict):
    """Replace only the object's Mesh data -- Plasticity safe_mesh_import_data pattern."""
    try:
        _update_mesh_geometry_impl(obj, data)
    except Exception:
        # On individual body failure, log and continue
        name = data.get("name", "?")
        print(f"[FusionBridge] !! ERROR processing body '{name}': ")
        traceback.print_exc()


def _update_mesh_geometry_impl(obj: bpy.types.Object, data: dict):
    """Internal implementation -- Plasticity safe_mesh_import_data pattern."""
    import numpy as np

    # ── Data decoding ──────────────────────────────────────────────────────
    if "vertices_b64" in data:
        raw_verts = _b64_f32(data["vertices_b64"])
        raw_idx   = _b64_i32(data["indices_b64"])
        nb64      = data.get("normals_b64", "")
        raw_norms = _b64_f32(nb64) if nb64 else _arr.array('f')
    else:
        raw_verts = data.get("vertices", [])
        raw_idx   = data.get("indices", [])
        raw_norms = data.get("normals", [])

    if not len(raw_verts) or not len(raw_idx):
        return

    # Validate data sizes before clearing geometry
    if len(raw_verts) % 3 != 0:
        print(f"[FusionBridge] WARN vertex count not divisible by 3, truncating")
        raw_verts = raw_verts[:len(raw_verts) - len(raw_verts) % 3]
    if len(raw_idx) % 3 != 0:
        print(f"[FusionBridge] WARN index count not divisible by 3, truncating")
        raw_idx = raw_idx[:len(raw_idx) - len(raw_idx) % 3]
    if not len(raw_verts) or not len(raw_idx):
        return

    if not isinstance(obj.data, bpy.types.Mesh):
        return

    if obj.mode == "EDIT":
        try:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    mesh: bpy.types.Mesh = obj.data
    # ── Save user mesh data for restoration ──────────────────────────
    _saved_userdata = _save_mesh_userdata(obj, mesh)
    mesh.clear_geometry()

    # ── numpy array conversion ─────────────────────────────────────────────
    verts_np   = np.frombuffer(raw_verts, dtype=np.float32).reshape(-1, 3).copy()
    indices_np = np.frombuffer(raw_idx,   dtype=np.int32).copy()

    # Validate index range
    if len(indices_np) > 0 and indices_np.max() >= len(verts_np):
        indices_np = np.clip(indices_np, 0, len(verts_np) - 1)

    has_normals = len(raw_norms) >= 9
    normals_np  = (np.frombuffer(raw_norms, dtype=np.float32)
                   .reshape(-1, 3).copy()) if has_normals else None

    # ── vertex dedup (1 um quantization) ───────────────────────────────────
    quantized = np.round(verts_np * 1e6).astype(np.int64)
    qview = quantized.view(
        np.dtype([('x', np.int64), ('y', np.int64), ('z', np.int64)])
    ).ravel()
    _, unique_idx, inverse = np.unique(qview, return_index=True,
                                       return_inverse=True)
    unique_verts = verts_np[unique_idx]
    new_indices  = inverse[indices_np].astype(np.int32)

    # ── Remove degenerate triangles ────────────────────────────────────────
    tris  = new_indices.reshape(-1, 3)
    valid = ((tris[:, 0] != tris[:, 1]) &
             (tris[:, 1] != tris[:, 2]) &
             (tris[:, 0] != tris[:, 2]))
    has_degen = not valid.all()

    if has_degen:
        loop_keep    = np.repeat(valid, 3)
        final_idx    = tris[valid].ravel()
        orig_loop_ix = indices_np[loop_keep]
    else:
        final_idx    = new_indices
        orig_loop_ix = indices_np

    n_loops = len(final_idx)
    n_faces = n_loops // 3

    # ── Build Blender mesh ────────────────────────────────────────────────
    mesh.vertices.add(len(unique_verts))
    mesh.vertices.foreach_set("co", unique_verts.ravel())

    mesh.loops.add(n_loops)
    mesh.loops.foreach_set("vertex_index", final_idx)

    mesh.polygons.add(n_faces)
    mesh.polygons.foreach_set("loop_start",
                              np.arange(0, n_loops, 3, dtype=np.int32))
    mesh.polygons.foreach_set("loop_total",
                              np.full(n_faces, 3, dtype=np.int32))

    # ── face group data ───────────────────────────────────────────────────
    fg_b64 = data.get("face_groups_b64", "")
    fi_b64 = data.get("face_ids_b64", "")
    fk_b64 = data.get("face_keys_b64", "")
    groups    = list(_b64_i32(fg_b64)) if fg_b64 else []
    face_ids  = list(_b64_i32(fi_b64)) if fi_b64 else []
    # Absent when the Fusion add-in predates face keys. Everything still works;
    # only cross-sync face identity is unavailable.
    face_keys = list(_b64_i64(fk_b64)) if fk_b64 else []

    _safe_mesh_import_data(mesh, orig_loop_ix, normals_np,
                           groups, face_ids, has_normals, face_keys)

    # ── Restore user data (UV, vertex colors) ─────────────────────────
    _restore_mesh_userdata(obj, mesh, _saved_userdata)

    obj["fusion_id"]        = data.get("fusion_id", "")
    obj["fusion_component"] = data.get("component", "")
    obj["fusion_instance"]  = data.get("instance_path", "")


def _store_face_keys(mesh, keys):
    """Persist 64-bit BRep face keys on the mesh.

    Blender's ID-property integer arrays are 32-bit, so a 64-bit key cannot be
    stored directly, and storing it as a float would silently lose the low bits
    (doubles carry 53). So each key is kept as its two 32-bit halves, in the
    order the machine writes them -- reassembled by reading the pairs back as
    int64. Layout: 2 ints per face, [half, half, half, half, ...].
    """
    if not keys:
        mesh["ftb_face_keys"] = []
        return
    try:
        packed = _arr.array('i', _arr.array('q', keys).tobytes())
        mesh["ftb_face_keys"] = list(packed)
    except Exception:
        traceback.print_exc()
        mesh["ftb_face_keys"] = []


def face_keys_of(mesh):
    """The 64-bit face keys stored on a mesh, one per face group.

    Empty when the Fusion add-in is older than face keys, or when the mesh did
    not come from Fusion. A key of 0 means that face had no usable entityToken:
    it is NOT an identity, and two faces both keyed 0 are not the same face.
    """
    packed = list(mesh.get("ftb_face_keys", []))
    if not packed or len(packed) % 2:
        return []
    try:
        return list(_arr.array('q', _arr.array('i', packed).tobytes()))
    except Exception:
        return []


def _safe_mesh_import_data(mesh, indices, normals_np, groups, face_ids,
                           has_normals, face_keys=None):
    """Same normals + face group pipeline as Plasticity safe_mesh_import_data()."""
    import numpy as np

    face_keys = face_keys or []

    if len(mesh.polygons) == 0:
        mesh.update()
        mesh["ftb_face_groups"] = []
        mesh["ftb_face_ids"]    = []
        _store_face_keys(mesh, [])
        return

    original_polygon_count = len(mesh.polygons)

    # ── per-loop normals → temp attribute ─────────────────────────────────
    loop_normals = None
    if has_normals and normals_np is not None and len(indices) > 0:
        # Index range check -- guard against missing Fusion face data
        max_idx = int(np.max(indices)) if len(indices) > 0 else 0
        if max_idx >= len(normals_np):
            print(f"[FusionBridge] WARN normals index OOB: max_idx={max_idx}, "
                  f"normals_len={len(normals_np)}, clipping")
            safe_idx = np.clip(indices, 0, len(normals_np) - 1)
        else:
            safe_idx = indices
        loop_normals = np.ascontiguousarray(
            normals_np[safe_idx], dtype=np.float32)
        nlen = np.linalg.norm(loop_normals, axis=1, keepdims=True)
        nlen = np.where(nlen < 1e-8, 1.0, nlen)
        loop_normals = loop_normals / nlen

        if "_ftb_tmp_normals" in mesh.attributes:
            mesh.attributes.remove(mesh.attributes["_ftb_tmp_normals"])
        mesh.attributes.new("_ftb_tmp_normals", 'FLOAT_VECTOR', 'CORNER')
        mesh.attributes["_ftb_tmp_normals"].data.foreach_set(
            "vector", loop_normals.ravel())

    # ── face group → temp attribute ───────────────────────────────────────
    if groups and face_ids and len(groups) >= 2:
        if "_ftb_tmp_gidx" in mesh.attributes:
            mesh.attributes.remove(mesh.attributes["_ftb_tmp_gidx"])
        mesh.attributes.new("_ftb_tmp_gidx", 'INT', 'FACE')
        pg = np.zeros(len(mesh.polygons), dtype=np.int32)
        n_groups = len(face_ids)
        g_idx   = 0
        g_start = groups[0]
        g_count = groups[1]
        for poly in mesh.polygons:
            while (g_idx + 1 < n_groups
                   and poly.loop_start >= g_start + g_count
                   and (g_idx + 1) * 2 + 1 < len(groups)):
                g_idx += 1
                g_start = groups[g_idx * 2]
                g_count = groups[g_idx * 2 + 1]
            pg[poly.index] = min(g_idx, n_groups - 1)
        mesh.attributes["_ftb_tmp_gidx"].data.foreach_set("value", pg)

    # ── mesh.update() -- Blender may remove degenerate polygons ────────────
    mesh.update()

    collapsed = original_polygon_count - len(mesh.polygons)

    # ── Flat shading (Fusion CAD model default) ────────────────────────────
    mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))

    # ── Apply custom normals (same as Plasticity) ─────────────────────────
    if loop_normals is not None:
        if hasattr(mesh, "use_auto_smooth"):
            mesh.use_auto_smooth = True
        try:
            if collapsed == 0:
                mesh.normals_split_custom_set(loop_normals.tolist())
            else:
                buf = np.empty(len(mesh.loops) * 3, dtype=np.float32)
                mesh.attributes["_ftb_tmp_normals"].data.foreach_get(
                    "vector", buf)
                mesh.normals_split_custom_set(
                    buf.reshape(-1, 3).tolist())
        except Exception:
            traceback.print_exc()
        try:
            mesh.attributes.remove(mesh.attributes["_ftb_tmp_normals"])
        except Exception:
            pass

    # ── Restore face groups (same as Plasticity) ──────────────────────────
    if groups and face_ids:
        try:
            if collapsed == 0:
                mesh["ftb_face_groups"] = groups
                mesh["ftb_face_ids"]    = face_ids
                _store_face_keys(mesh, face_keys)
            else:
                pg_buf = np.empty(len(mesh.polygons), dtype=np.int32)
                mesh.attributes["_ftb_tmp_gidx"].data.foreach_get(
                    "value", pg_buf)
                g_out  = []
                fi_out = []
                fk_out = []
                cur_gi = None
                cur_s  = 0
                cur_c  = 0

                def _close_group(gi):
                    """Emit the group that just ended, carrying its face's key.

                    Groups are re-derived here because Blender dropped degenerate
                    polygons, so the surviving groups must keep pointing at the
                    CAD faces they came from -- otherwise a key would end up
                    naming the wrong face, which is worse than having no key.
                    """
                    fi_out.append(face_ids[gi] if gi < len(face_ids) else gi)
                    fk_out.append(face_keys[gi] if gi < len(face_keys) else 0)

                for poly, gi in zip(mesh.polygons, pg_buf):
                    gi = int(gi)
                    if cur_gi is None or gi != cur_gi:
                        if cur_gi is not None:
                            g_out.extend([cur_s, cur_c])
                            _close_group(cur_gi)
                        cur_gi = gi
                        cur_s  = poly.loop_start
                        cur_c  = 0
                    cur_c += poly.loop_total
                if cur_gi is not None:
                    g_out.extend([cur_s, cur_c])
                    _close_group(cur_gi)
                mesh["ftb_face_groups"] = g_out
                mesh["ftb_face_ids"]    = fi_out
                _store_face_keys(mesh, fk_out if face_keys else [])
        except Exception:
            traceback.print_exc()
        try:
            mesh.attributes.remove(mesh.attributes["_ftb_tmp_gidx"])
        except Exception:
            pass
    else:
        mesh["ftb_face_groups"] = []
        mesh["ftb_face_ids"]    = []
        _store_face_keys(mesh, [])

    mesh.update()
    mesh.validate(clean_customdata=False)


def _user_rotation_matrix(obj) -> mathutils.Matrix:
    """Manual rotation hint stored on the object (in degrees) -> 4x4 rotation matrix.

    Per-object correction applied on top of the Fusion coordinate transform (Rx 90 deg).
    Used to correct sub-assemblies modeled in non-standard orientations.
    """
    rx = obj.get('ftb_rot_x_deg', 0.0)
    ry = obj.get('ftb_rot_y_deg', 0.0)
    rz = obj.get('ftb_rot_z_deg', 0.0)
    if not (rx or ry or rz):
        return mathutils.Matrix.Identity(4)
    mat = mathutils.Matrix.Identity(4)
    if rx:
        mat = mat @ mathutils.Matrix.Rotation(math.radians(rx), 4, 'X')
    if ry:
        mat = mat @ mathutils.Matrix.Rotation(math.radians(ry), 4, 'Y')
    if rz:
        mat = mat @ mathutils.Matrix.Rotation(math.radians(rz), 4, 'Z')
    return mat


def update_transform(obj: bpy.types.Object, transform: list):
    """Fusion mesh coordinates -> Blender world coordinates.

    matrix_world = _user_rotation_matrix(obj) @ _global_axis_matrix()
      - _global_axis_matrix: Scene's ftb_up_axis toggle ("Y"/"Z")
      - _user_rotation_matrix: per-object manual rotation hint (optional)
    """
    try:
        obj.matrix_world = _user_rotation_matrix(obj) @ _global_axis_matrix()
    except Exception:
        pass


# ─── Component path normalization (for comparison) ────────────────────────────
# ── Fusion appearance: carried, not applied ───────────────────────────────────
# The Fusion add-in sends each body's appearance (name, colour, roughness,
# metallic). Turning that into a Blender material belongs to Bridge Pro, so this
# side only carries it: the payload is parked on the object and the post-body
# hook fires right after, which is where Pro picks it up.
#
# Why park it on the object rather than hand it to the hook: the hook's contract
# is "here is the object whose geometry was just rebuilt", and a released version
# of this add-on is already out with that signature. Widening it would break Pro
# builds compiled against either side of the change, silently -- the callback
# would raise, be muted, and the feature would simply stop with no error anyone
# would connect to it.
APPEARANCE_KEY = "ftb_appearance"


def _stash_appearance(obj, appearance, face_table=None, face_index=None):
    """Park the body's appearance -- and any per-face ones -- on the object.

    Stored as JSON text. Blender's ID properties can hold nested data, but the
    exact shape Fusion sends varies by appearance family and a round-trip
    through a dict-like property drops types quietly; text comes back the same
    way it went in.

    Per-face appearances ride in the same payload under "faces": a small table
    of the distinct ones plus an index per CAD face (-1 meaning "the body's").
    Fusion lets you paint a single face, and that is how a logo panel, a grip
    or a two-tone housing is coloured.
    """
    try:
        payload = None
        if appearance and isinstance(appearance, dict):
            payload = dict(appearance)
        if face_table and face_index:
            payload = payload or {}
            payload["faces"] = {"table": face_table, "index": list(face_index)}
        if payload:
            obj[APPEARANCE_KEY] = json.dumps(payload)
        elif APPEARANCE_KEY in obj:
            # Fusion no longer reports one for this body. Leaving the old value
            # would have Pro repaint a colour the design does not have any more.
            del obj[APPEARANCE_KEY]
    except Exception:
        traceback.print_exc()


def _norm_component(comp: str) -> str:
    """Comparison key: remove version/instance, lowercase.
    "External1 v16:1/SubComp:2" -> "external1/subcomp"
    """
    comp = _RE_VER_REM.sub('', comp)
    comp = _RE_INST_REM.sub('', comp)
    return comp.lower().strip()


# ─── SceneHandler ─────────────────────────────────────────────────────────────
class SceneHandler:
    """Manages all Fusion objects in the Blender scene."""

    def __init__(self):
        self._id_to_obj_name: dict[str, str] = {}
        self.update_transforms = True
        self.preserve_materials = True

        # Batch sync (full_sync fallback)
        self._pending_queue: deque = deque()
        self._sync_total: int = 0
        self._sync_processed: int = 0

        # Streaming sync
        self._streaming_sync: bool = False
        self._streaming_seen_fids: set = set()
        self._streaming_prev_fids: set = set()
        self._last_redraw_time: float = 0.0
        # Hidden ancestor collection paths found during this sync
        self._sync_hidden_collection_paths: set = set()
        # Error tracking for current sync
        self._sync_error_count: int = 0
        # Per-document scope (F050): set on sync_start, stamped on every object
        self._sync_doc: str = ""

    # ── Cache management ───────────────────────────────────────────────────────
    def _rebuild_cache(self):
        # Doc-scoped (F050): only THIS sync's document. Fusion can hand out
        # IDENTICAL entityTokens across different files, so an unscoped
        # fid->object map lets one file's body resolve (via _get_obj) to another
        # file's object and overwrite it. Excluding other-document objects keeps
        # them separate. (Empty _sync_doc / legacy objects fall back to global.)
        self._id_to_obj_name = {
            obj.get("fusion_id"): obj.name
            for obj in bpy.data.objects
            if obj.get("fusion_id") and self._doc_ok(obj)
        }

    def _get_obj(self, fusion_id: str):
        name = self._id_to_obj_name.get(fusion_id)
        if name:
            obj = bpy.data.objects.get(name)
            if obj and obj.get("fusion_id") == fusion_id:
                return obj
        # Cache miss -> rebuild
        self._rebuild_cache()
        name = self._id_to_obj_name.get(fusion_id)
        return bpy.data.objects.get(name) if name else None

    def _doc_ok(self, obj) -> bool:
        """True if obj may belong to the current sync's document -- same doc, or
        either side unstamped (legacy objects are soft-migrated on first match).
        When this sync carries no doc id, scoping is disabled (old behavior)."""
        if obj is None:
            return False
        d = getattr(self, "_sync_doc", "")
        od = obj.get("fusion_doc", "")
        return (not d) or (not od) or (od == d)

    # ── Message dispatch ────────────────────────────────────────────────────
    def handle_message(self, msg: dict):
        msg_type = msg.get("type")

        if msg_type == "sync_start":
            self.on_sync_start(msg)
        elif msg_type == "sync_end":
            self.on_sync_end(msg)
        elif msg_type == "object_add":
            obj = msg.get("object", {})
            if self._streaming_sync:
                self.on_streaming_add(obj)
            else:
                self.on_object_add(obj)
        elif msg_type == "joints_data":
            self.on_joints_data(msg)
        elif msg_type == "full_sync":
            self.on_full_sync(msg)
        elif msg_type == "object_update":
            self.on_object_update(msg.get("object", {}))
        elif msg_type == "object_delete":
            self.on_object_delete(msg.get("fusion_id", ""))
        elif msg_type == "_waiting_fusion":
            _prog("set_progress", 0, 1, t("fusion_mesh_wait"))
            self._set_status(t("fusion_computing"))
            self._set_syncing(True)
            self._tag_redraw()
        elif msg_type == "sync_error":
            self.on_sync_error(msg)
        elif msg_type == "_connection_lost":
            self.disarm_sync_watchdog()
            self._on_connection_lost()
        else:
            print(f"[FusionBridge] Unknown message type: {msg_type}")

    # ── UI state helpers ───────────────────────────────────────────────────────
    def _set_status(self, text: str):
        try:
            for w in bpy.context.window_manager.windows:
                w.scene.ftb_sync_status = text
        except Exception:
            pass

    def _set_progress(self, value: float):
        try:
            v = min(1.0, max(0.0, value))
            for w in bpy.context.window_manager.windows:
                w.scene.ftb_sync_progress = v
        except Exception:
            pass

    def _set_syncing(self, value: bool):
        try:
            for w in bpy.context.window_manager.windows:
                w.scene.ftb_is_syncing = value
                if not value:
                    w.scene.ftb_sync_progress = 0.0
        except Exception:
            pass

    def _set_error(self, value: bool):
        try:
            for w in bpy.context.window_manager.windows:
                w.scene.ftb_sync_error = value
        except Exception:
            pass

    def _tag_redraw(self):
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
        except Exception:
            pass

    # ── Sync watchdog ──────────────────────────────────────────────────────────
    # Pressing Sync puts the panel into "Fusion computing..." immediately, then
    # waits for sync_start. If Fusion never answers -- the add-in is stopped, is
    # an old version, threw before it could reply, or has no design open -- there
    # was nothing to end that wait, and the panel sat there forever with no way
    # to tell a slow sync from a dead one. So the wait is now bounded.
    #
    # The timeout is generous on purpose: counting bodies in a large assembly
    # genuinely takes many seconds before the first message goes out, and firing
    # early would be worse than not firing at all.
    SYNC_ANSWER_TIMEOUT_S = 90.0

    def arm_sync_watchdog(self):
        """Start waiting for Fusion's first reply. Call right after requesting."""
        self._awaiting_sync_start = True
        if bpy.app.timers.is_registered(self._sync_watchdog):
            bpy.app.timers.unregister(self._sync_watchdog)
        bpy.app.timers.register(self._sync_watchdog,
                                first_interval=self.SYNC_ANSWER_TIMEOUT_S)

    def disarm_sync_watchdog(self):
        self._awaiting_sync_start = False

    def _sync_watchdog(self):
        if not getattr(self, "_awaiting_sync_start", False):
            return None                      # answered in time; nothing to do
        self._awaiting_sync_start = False
        print("[FusionBridge] Fusion did not answer the sync request within "
              f"{self.SYNC_ANSWER_TIMEOUT_S:.0f}s. Check Fusion's add-in is "
              f"running (Utilities > Add-Ins) and that a design is open.")
        self._set_error(True)
        self._set_status(t("sync_no_answer"))
        self._set_syncing(False)
        _prog("clear_progress")
        self._tag_redraw()
        return None

    def on_sync_error(self, msg: dict):
        """Fusion reached us but could not run the sync, and said why."""
        self.disarm_sync_watchdog()
        reason = str(msg.get("reason", "")) or "unknown"
        print(f"[FusionBridge] Fusion refused the sync: {reason}")
        self._streaming_sync = False
        self._set_error(True)
        self._set_status(t("sync_refused", reason=reason[:80]))
        self._set_syncing(False)
        _prog("clear_progress")
        self._tag_redraw()

    def _on_connection_lost(self):
        """Called when the WebSocket connection drops unexpectedly.
        Resets any in-progress streaming sync so the UI doesn't hang
        and the user can request a fresh sync after reconnection.
        """
        if self._streaming_sync:
            print(f"[FusionBridge] Connection lost during streaming sync "
                  f"({self._sync_processed}/{self._sync_total} received) — resetting")
            self._streaming_sync = False
            self._set_error(True)
            self._set_status(t("sync_interrupted",
                               cur=self._sync_processed,
                               total=self._sync_total))
            self._set_syncing(False)
            _prog("clear_progress")
            self._tag_redraw()

    # ── Batch timer ────────────────────────────────────────────────────────────
    def _process_batch(self):
        """Timer callback: process _BATCH_SIZE objects per tick."""
        try:
            if not self._pending_queue:
                ts = time.strftime("%H:%M:%S")
                self._set_status(t("sync_done", count=self._sync_total, ts=ts))
                self._set_syncing(False)
                _prog("clear_progress")
                self._tag_redraw()
                print(f"[FusionBridge] Sync complete: {self._sync_total} objects")
                _push_undo(f"Fusion 360 Sync ({self._sync_total} objects)")
                return None

            for _ in range(min(_BATCH_SIZE, len(self._pending_queue))):
                obj_data = self._pending_queue.popleft()
                fid = obj_data.get("fusion_id")
                if not fid:
                    self._sync_processed += 1
                    continue
                try:
                    if self._get_obj(fid):
                        self.on_object_update(obj_data)
                    else:
                        self.on_object_add(obj_data)
                except Exception:
                    traceback.print_exc()
                self._sync_processed += 1

            total = max(1, self._sync_total)
            pct = int(self._sync_processed / total * 100)
            self._set_status(t("sync_progress", cur=self._sync_processed, total=self._sync_total))
            self._set_progress(self._sync_processed / total)
            _prog("set_progress", self._sync_processed, self._sync_total,
                  f"Fusion → Blender  {self._sync_processed} / {self._sync_total}  ({pct} %)")
            self._tag_redraw()

            return 0.0

        except Exception:
            traceback.print_exc()
            _prog("clear_progress")
            return None

    # ── Streaming sync ─────────────────────────────────────────────────────────
    def on_sync_start(self, msg: dict):
        total = msg.get("object_count", 0)
        self._streaming_sync = True
        self._streaming_seen_fids = set()
        self._sync_total = max(1, total)
        self._sync_processed = 0
        self._sync_error_count = 0
        self._last_redraw_time = 0.0
        # Reset hidden ancestor collection tracking
        self._sync_hidden_collection_paths = set()
        # Track fids already claimed by remap in this sync (prevent cross-component collisions)
        self._streaming_claimed_fids: set = set()
        # Clear any previous error state
        self._set_error(False)

        # Design-root scoping: only delete bodies belonging to THIS design at
        # sync_end. Without this, switching designs (SF50-A → SF50-B) would
        # delete all old bodies from the previous design.
        #
        # Strategy: collect ALL prev_fids now, and auto-detect design root(s)
        # from the incoming bodies' component paths during streaming. At
        # sync_end, only bodies whose component root matches the detected
        # root(s) are eligible for deletion. Bodies from other designs are
        # left untouched.
        #
        # Also accept explicit design_root from the server (if available)
        # as an authoritative hint.
        self._sync_design_root = msg.get("design_root", "")
        self._sync_doc = msg.get("doc", "")           # F050 per-document scope
        self._streaming_incoming_roots: set = set()   # auto-detected from body data

        # Save previous object list -> determine deletion targets at sync_end
        self._rebuild_cache()
        self._streaming_prev_fids = set(self._id_to_obj_name.keys())

        _prog("set_progress", 0, self._sync_total,
              f"Fusion → Blender  0 / {total}  (0 %)")
        self.disarm_sync_watchdog()          # Fusion answered
        self._set_status(t("sync_starting", cur=0, total=total))
        self._set_syncing(True)
        # A hook muted by an error in the previous sync gets another chance here.
        hooks.clear_mutes()
        self._tag_redraw()
        print(f"[FusionBridge] Streaming sync start: {total} objects expected, "
              f"design_root='{self._sync_design_root}', doc='{self._sync_doc}', "
              f"scene objects={len(self._id_to_obj_name)}")
        # Surface the Fusion add-in's version + what it detected as hidden, so a
        # single Blender console reveals whether the Fusion side actually updated.
        fusion_ver = msg.get("addon_version", "OLD/unknown")
        hidden_count = msg.get("hidden_count", "n/a")
        hidden_sample = msg.get("hidden_sample", [])
        print(f"[FusionBridge] Fusion add-in version={fusion_ver}, "
              f"Fusion-detected hidden occurrences={hidden_count} "
              f"{hidden_sample if hidden_sample else ''}")

    def on_streaming_add(self, data: dict):
        fid = data.get("fusion_id")
        if not fid:
            return

        self._streaming_seen_fids.add(fid)

        # Auto-detect design root from the first path segment of component.
        # e.g. "SF50-B/SF50-A/SubComp" → root = "sf50-b"
        comp = data.get("component", "")
        if comp:
            root_seg = comp.split("/")[0].strip().lower()
            if root_seg:
                self._streaming_incoming_roots.add(root_seg)

        # Handle entityToken change: remap existing object by name+instance
        body_name = data.get("name", "")
        body_comp = data.get("component", "")
        body_inst = data.get("instance_path", "")

        _fast = self._get_obj(fid) if fid in self._id_to_obj_name else None
        if _fast is not None and self._doc_ok(_fast):
            # Same entityToken AND same document = same body → claim as-is.
            # The doc check is essential: Fusion can hand out IDENTICAL tokens to
            # bodies in different files (observed), so the token alone is not a
            # cross-file-unique identity (F050).
            self._streaming_claimed_fids.add(fid)
            action = "EXISTING"
        else:
            existing = self._find_by_name_component(
                body_name, body_comp, body_inst,
                exclude_fids=self._streaming_claimed_fids,
            )
            if existing:
                old_fid = existing.get("fusion_id", "")
                old_comp = existing.get("fusion_component", "")
                old_inst = existing.get("fusion_instance", "")
                # Log the object's current collections + fid change too: a REMAP
                # that pulls an object OUT of another file's collection is the
                # cross-file body-name collision (F050) and is otherwise silent.
                try:
                    _cols = ", ".join(c.name for c in existing.users_collection)
                except Exception:
                    _cols = "?"
                print(f"[FusionBridge] REMAP '{body_name}': "
                      f"old_comp='{old_comp}' old_inst='{old_inst}' "
                      f"old_fid='{old_fid[:24]}' in[{_cols}] → "
                      f"new_comp='{body_comp}' new_inst='{body_inst}' "
                      f"new_fid='{fid[:24]}'")
                if old_fid and old_fid != fid:
                    self._id_to_obj_name.pop(old_fid, None)
                    self._streaming_prev_fids.discard(old_fid)
                    self._streaming_claimed_fids.discard(old_fid)
                existing["fusion_id"] = fid
                self._id_to_obj_name[fid] = existing.name
                self._streaming_claimed_fids.add(fid)
                action = "REMAPPED"
            else:
                action = "NEW"

        try:
            if self._get_obj(fid):
                self.on_object_update(data)
            else:
                self.on_object_add(data)
        except Exception:
            self._sync_error_count += 1
            print(f"[FusionBridge] !! Body error #{self._sync_error_count} "
                  f"name='{body_name}' fid='{fid[:40]}':")
            traceback.print_exc()

        # Log first 20 bodies and any Body1-related for diagnosis
        if self._sync_processed < 20 or "body1" in body_name.lower().replace(" ", ""):
            print(f"[FusionBridge] [{self._sync_processed}] {action} "
                  f"name='{body_name}' comp='{body_comp}' "
                  f"inst='{body_inst}' fid='{fid[:40]}..'")

        self._sync_processed += 1

        # Progress bar + redraw throttle
        total = self._sync_total
        pct = int(self._sync_processed / total * 100)
        _prog("set_progress", self._sync_processed, total,
              f"Fusion → Blender  {self._sync_processed} / {total}  ({pct} %)")

        now = time.time()
        if now - self._last_redraw_time > _REDRAW_INTERVAL:
            self._last_redraw_time = now
            self._set_status(t("sync_progress", cur=self._sync_processed, total=total))
            self._tag_redraw()

    def on_sync_end(self, msg: dict):
        self._streaming_sync = False

        # ── Determine which design root(s) this sync covers ──────────────
        # Priority: explicit design_root from server > auto-detected from bodies
        design_roots: set = set()
        if self._sync_design_root:
            design_roots.add(self._sync_design_root.lower())
        if self._streaming_incoming_roots:
            design_roots |= self._streaming_incoming_roots

        # ── Delete previous objects NOT seen in this sync ────────────────
        # Only delete objects whose component root matches the synced design.
        # Bodies from OTHER designs are left untouched.
        unseen = self._streaming_prev_fids - self._streaming_seen_fids
        to_delete: set = set()

        if design_roots:
            for fid in unseen:
                oname = self._id_to_obj_name.get(fid)
                if oname is None:
                    to_delete.add(fid)
                    continue
                obj = bpy.data.objects.get(oname)
                if obj is None:
                    to_delete.add(fid)
                    continue
                comp = obj.get("fusion_component", "")
                comp_root = comp.split("/")[0].strip().lower() if comp else ""
                # Only sweep bodies belonging to THIS document (F050): a body
                # from another file that happens to share the design-root name
                # must not be deleted just because we re-synced a same-named design.
                if comp_root in design_roots and self._doc_ok(obj):
                    to_delete.add(fid)
                # else: body belongs to a different design/document → keep it
        else:
            # No design info at all (shouldn't happen) -- legacy full-replace
            to_delete = unseen

        kept = len(unseen) - len(to_delete)
        kept_details: list = []
        if design_roots:
            for fid in unseen - to_delete:
                oname = self._id_to_obj_name.get(fid, "?")
                obj = bpy.data.objects.get(oname)
                cr = ""
                if obj:
                    c = obj.get("fusion_component", "")
                    cr = c.split("/")[0].strip().lower() if c else "(empty)"
                kept_details.append(f"{oname}[root={cr}]")

        print(f"[FusionBridge] sync_end: incoming_roots={design_roots}, "
              f"unseen={len(unseen)}, deleting={len(to_delete)}, "
              f"keeping={kept}")
        if kept_details:
            # Show up to 30 kept objects for diagnosis
            print(f"[FusionBridge] KEPT from other designs: "
                  f"{', '.join(kept_details[:30])}"
                  f"{'...' if len(kept_details) > 30 else ''}")
        if to_delete:
            del_names = []
            for fid in list(to_delete)[:20]:
                oname = self._id_to_obj_name.get(fid, "?")
                del_names.append(oname)
            print(f"[FusionBridge] DELETING: {', '.join(del_names)}"
                  f"{'...' if len(to_delete) > 20 else ''}")

        for fid in to_delete:
            self.on_object_delete(fid)

        # Collection hide: hide collections whose ancestors are hidden in Fusion
        # Only apply when show_hidden_bodies is OFF (i.e., user wants to respect Fusion hide state)
        try:
            show_hidden = getattr(bpy.context.scene, "ftb_show_hidden_bodies", False)
            print(f"[FusionBridge] HIDE-COL: show_hidden_bodies={show_hidden}, "
                  f"collected hidden ancestor paths={len(self._sync_hidden_collection_paths)}")
            if not show_hidden and self._sync_hidden_collection_paths:
                _apply_hidden_collections(self._sync_hidden_collection_paths)
            elif show_hidden:
                print("[FusionBridge] HIDE-COL: skipped — 'Show Hidden Bodies' "
                      "toggle is ON, so nothing is hidden by design")
        except Exception:
            traceback.print_exc()

        # Diagnostic: print count of Fusion objects in scene and how many are hidden
        try:
            scene_fusion_objs = [o for o in bpy.data.objects if "fusion_id" in o]
            scene_total = len(scene_fusion_objs)
            scene_hidden = sum(1 for o in scene_fusion_objs if o.hide_viewport)
            print(f"[FusionBridge] Scene Fusion objects: {scene_total} "
                  f"(hidden: {scene_hidden}), this sync emitted: "
                  f"{self._sync_processed}")
        except Exception:
            pass

        ts = time.strftime("%H:%M:%S")
        if self._sync_error_count > 0:
            self._set_error(True)
            self._set_status(t("sync_done_with_errors",
                               errors=self._sync_error_count,
                               count=self._sync_processed, ts=ts))
            print(f"[FusionBridge] Streaming sync complete with {self._sync_error_count} "
                  f"error(s): {self._sync_processed} objects")
        else:
            self._set_error(False)
            self._set_status(t("sync_done", count=self._sync_processed, ts=ts))
            print(f"[FusionBridge] Streaming sync complete: {self._sync_processed} objects")

        # Fusion announced a body count at the start. Bodies it then failed to
        # export never arrive and nothing above notices -- the sync just reports
        # a smaller number and looks finished. That is how a plain bug in the
        # exporter (an unpack that stopped matching its function) presented as
        # "no objects come across", with the real traceback sitting unseen in
        # Fusion's own console.
        missing = self._sync_total - self._sync_processed
        if missing > 0:
            self._set_error(True)
            print(f"[FusionBridge] WARNING: Fusion said {self._sync_total} bodies "
                  f"but only {self._sync_processed} arrived; {missing} failed to "
                  f"export. The reason is in Fusion's own text console "
                  f"(Utilities > Add-Ins > Scripts and Add-Ins), not here.")
            self._set_status(t("sync_short", got=self._sync_processed,
                               total=self._sync_total, ts=ts))
        self._set_syncing(False)
        _prog("clear_progress")
        self._tag_redraw()

        # Extensions that need bpy.ops (unwrapping, for one) get their turn here
        # rather than inside the streaming loop -- see hooks.py. Runs before the
        # undo push so whatever they do lands in the same undo step as the sync.
        hooks.run_post_sync(self._synced_objects())

        # Ctrl+Z support: bundle all changes from this sync into a single undo step
        _push_undo(f"Fusion 360 Sync ({self._sync_processed} objects)")

    def _synced_objects(self):
        """The objects this sync created or updated, still present in the file."""
        out = []
        for fid in self._streaming_seen_fids:
            name = self._id_to_obj_name.get(fid)
            obj = bpy.data.objects.get(name) if name else None
            if obj is not None and obj.type == 'MESH':
                out.append(obj)
        return out

    # ── Full sync (legacy fallback) ─────────────────────────────────────────
    def on_full_sync(self, msg: dict):
        objects = msg.get("objects", [])
        print(f"[FusionBridge] Full sync started: {len(objects)} objects")

        incoming_ids = {o.get("fusion_id") for o in objects if o.get("fusion_id")}

        # Step 1: entityToken change remap (name+instance / fallback: name+component)
        self._rebuild_cache()

        # Build lookup maps. instance_path is the primary key (unique per
        # occurrence); component is the fallback for legacy objects.
        # When multiple bodies share the same (name, component) -- common when
        # importing external files whose bodies have identical default names --
        # we store ALL candidate fids so that each old object can claim a
        # distinct new fid without collisions.
        name_inst_to_new_fid: dict[tuple, str] = {}
        name_comp_to_new_fids: dict[tuple, list] = {}
        for o in objects:
            key_inst = (o.get("name", ""), o.get("instance_path", ""))
            name_inst_to_new_fid[key_inst] = o["fusion_id"]
            key_comp = (o.get("name", ""), _norm_component(o.get("component", "")))
            name_comp_to_new_fids.setdefault(key_comp, []).append(o["fusion_id"])

        claimed_fids: set = set()   # track fids already claimed by remap

        remapped = 0
        for old_fid in list(self._id_to_obj_name):
            if old_fid in incoming_ids:
                continue
            obj = self._get_obj(old_fid)
            if obj is None:
                continue
            base_name = _RE_SUFFIX.sub('', obj.name)
            inst_path = obj.get("fusion_instance", "")

            new_fid = name_inst_to_new_fid.get((base_name, inst_path))
            if new_fid is None:
                comp = _norm_component(obj.get("fusion_component", ""))
                # Pick the first unclaimed fid from the candidates list
                for candidate in name_comp_to_new_fids.get((base_name, comp), []):
                    if candidate not in self._id_to_obj_name and candidate not in claimed_fids:
                        new_fid = candidate
                        break

            if new_fid and new_fid not in self._id_to_obj_name and new_fid not in claimed_fids:
                obj["fusion_id"] = new_fid
                self._id_to_obj_name[new_fid] = obj.name
                del self._id_to_obj_name[old_fid]
                claimed_fids.add(new_fid)
                remapped += 1

        if remapped:
            print(f"[FusionBridge] {remapped} object(s) remapped (token changed)")

        # Step 2: delete if still not in incoming after remap
        for fid in list(self._id_to_obj_name):
            if fid not in incoming_ids:
                self.on_object_delete(fid)

        # Step 3: set up batch queue
        self._pending_queue = deque(objects)
        self._sync_total = len(objects)
        self._sync_processed = 0

        self._set_status(t("sync_starting", cur=0, total=self._sync_total))
        self._set_progress(0.0)
        self._set_syncing(True)
        _prog("set_progress", 0, self._sync_total,
              f"Fusion → Blender  0 / {self._sync_total}  (0 %)")
        self._tag_redraw()

        if not bpy.app.timers.is_registered(self._process_batch):
            bpy.app.timers.register(self._process_batch, first_interval=0.0)

    # ── Search object by name+component (handle token changes) ─────────────
    def _find_by_name_component(self, name: str, component: str,
                                instance_path: str = "",
                                exclude_fids: set | None = None):
        """Search for existing object by name + (instance_path or component).

        When instance_path is provided:
          1) First look for an object with exact instance_path match.
          2) If not found, fall back to component matching only for legacy
             objects whose fusion_instance is empty AND whose fusion_component
             matches.

        When multiple candidates share the same (name, component) -- common for
        root-level bodies with identical default names -- return the FIRST
        unclaimed candidate (exclude_fids filters already-claimed objects).
        This pairs old→new bodies in arrival order, preserving materials and
        edge marks even when entityTokens change.

        exclude_fids: set of fusion_ids already claimed in this sync session.
             Objects with these fusion_ids are skipped so each new body claims
             a distinct old object.
        """
        norm_comp = _norm_component(component)
        _excl = exclude_fids or set()

        if instance_path:
            # Pass 1: strict instance_path matching
            for obj in bpy.data.objects:
                if "fusion_id" not in obj:
                    continue
                if obj.get("fusion_id", "") in _excl:
                    continue
                if not self._doc_ok(obj):
                    continue
                if _RE_SUFFIX.sub('', obj.name) != name:
                    continue
                if obj.get("fusion_instance", "") == instance_path:
                    return obj
            # Pass 2: component fallback for legacy objects with empty
            # fusion_instance. Return first unclaimed candidate.
            for obj in bpy.data.objects:
                if "fusion_id" not in obj:
                    continue
                if obj.get("fusion_id", "") in _excl:
                    continue
                if not self._doc_ok(obj):
                    continue
                if _RE_SUFFIX.sub('', obj.name) != name:
                    continue
                if obj.get("fusion_instance", ""):
                    continue   # never match objects belonging to other instances
                if _norm_component(obj.get("fusion_component", "")) == norm_comp:
                    return obj
            return None

        # instance_path not provided (root-level bodies): component matching.
        # Return first unclaimed candidate. Combined with exclude_fids,
        # each same-name body claims a different old object in order.
        for obj in bpy.data.objects:
            if "fusion_id" not in obj:
                continue
            if obj.get("fusion_id", "") in _excl:
                continue
            if not self._doc_ok(obj):
                continue
            if _RE_SUFFIX.sub('', obj.name) != name:
                continue
            if _norm_component(obj.get("fusion_component", "")) == norm_comp:
                return obj
        return None

    # ── Individual object processing ────────────────────────────────────────
    def on_object_update(self, data: dict):
        fid = data.get("fusion_id")
        if not fid:
            return

        obj = self._get_obj(fid)
        if obj is None:
            # Token changed -> retry by name+component
            obj = self._find_by_name_component(
                data.get("name", ""), data.get("component", ""),
                data.get("instance_path", ""),
                exclude_fids=getattr(self, '_streaming_claimed_fids', None),
            )
            if obj:
                old_fid = obj.get("fusion_id", "")
                if old_fid:
                    self._id_to_obj_name.pop(old_fid, None)
                obj["fusion_id"] = fid
                self._id_to_obj_name[fid] = obj.name

        if obj is None:
            self.on_object_add(data)
            return

        # Read the component BEFORE update_mesh_geometry -- it stamps
        # obj["fusion_component"] from this same payload (see _update_mesh_geometry_impl),
        # so asking afterwards always answers "unchanged" and the move below never fires.
        old_component = obj.get("fusion_component", "")

        try:
            update_mesh_geometry(obj, data)
            _stash_appearance(obj, data.get("appearance"),
                              data.get("face_appearances"),
                              data.get("face_appearance_index"))
            hooks.run_post_body_sync(obj)

            # Only update transform when Scene's ftb_update_transforms is true
            should_update_xform = getattr(bpy.context.scene, "ftb_update_transforms", True)
            if should_update_xform:
                update_transform(obj, data.get("transform", []))

            new_component = data.get("component", "")
            should_update_col = getattr(bpy.context.scene, "ftb_update_collections", True)
            if should_update_col and old_component != new_component:
                col = get_or_create_collection(new_component)
                link_object_to_collection(obj, col)

            new_name = data.get("name", "")
            if new_name and obj.name != new_name:
                # Only rename if the target name is not already taken by another
                # object. When two bodies share the same name (e.g. "Body1" in
                # Component1 and Component2), renaming would cause Blender to
                # append ".001" suffix anyway, and could break _id_to_obj_name
                # cache references. Keep the current Blender-assigned name.
                other = bpy.data.objects.get(new_name)
                if other is None or other is obj:
                    obj.name = new_name
                    if obj.data:
                        obj.data.name = new_name

            # Body-level hide (part-level): obj's hide_viewport / hide_render
            body_hidden = data.get("body_hidden", False) or data.get("hidden", False)
            _apply_hidden_state(obj, body_hidden)

            # Ancestor occurrence hide (assembly-level): collection path tracking
            ancestor = data.get("hidden_ancestor", "")
            if ancestor:
                try:
                    self._sync_hidden_collection_paths.add(ancestor)
                except Exception:
                    pass

            # Maintain/update Empty parent (if Scene toggle is on and user hasn't unparented)
            if getattr(bpy.context.scene, "ftb_create_root_empty", True):
                if obj.parent is None or obj.parent.get("ftb_root_empty"):
                    _parent_to_root_empty(obj, data.get("component", ""))

            obj["fusion_doc"] = getattr(self, "_sync_doc", "")
            self._id_to_obj_name[fid] = obj.name
        except Exception:
            traceback.print_exc()

    def on_object_add(self, data: dict):
        fid = data.get("fusion_id")
        if not fid:
            return

        name = data.get("name", "FusionBody")
        component = data.get("component", "")

        try:
            mesh = bpy.data.meshes.new(name)
            obj = bpy.data.objects.new(name, mesh)

            col = get_or_create_collection(component)
            col.objects.link(obj)

            obj["fusion_id"]        = fid
            obj["fusion_component"] = component
            obj["fusion_instance"]  = data.get("instance_path", "")
            obj["fusion_doc"]       = getattr(self, "_sync_doc", "")

            update_mesh_geometry(obj, data)
            _stash_appearance(obj, data.get("appearance"),
                              data.get("face_appearances"),
                              data.get("face_appearance_index"))
            hooks.run_post_body_sync(obj)

            should_update_xform = getattr(bpy.context.scene, "ftb_update_transforms", True)
            if should_update_xform:
                update_transform(obj, data.get("transform", []))

            # Body-level hide (part-level): obj's hide_viewport / hide_render
            body_hidden = data.get("body_hidden", False) or data.get("hidden", False)
            _apply_hidden_state(obj, body_hidden)

            # Ancestor occurrence hide (assembly-level): collection path tracking
            ancestor = data.get("hidden_ancestor", "")
            if ancestor:
                try:
                    self._sync_hidden_collection_paths.add(ancestor)
                except Exception:
                    pass

            # Auto-create/link Empty parent
            if getattr(bpy.context.scene, "ftb_create_root_empty", True):
                _parent_to_root_empty(obj, data.get("component", ""))

            self._id_to_obj_name[fid] = obj.name
        except Exception:
            traceback.print_exc()

    def on_object_delete(self, fusion_id: str):
        if not fusion_id:
            return
        obj = self._get_obj(fusion_id)
        if obj is None:
            return
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
            self._id_to_obj_name.pop(fusion_id, None)
        except Exception:
            traceback.print_exc()

    # ── Joint / Motion Link processing ───────────────────────────────────────
    def on_joints_data(self, msg: dict):
        """Hand Fusion's joints to whoever subscribed.

        Building the Empties and their constraints moved to Bridge Pro: it is
        not geometry, it is what Fusion knows ABOUT the geometry. This side
        keeps receiving the message -- the Fusion add-in sends it either way --
        and passes it on. With nobody subscribed, nothing happens and nothing
        is lost; the bodies are all already in the scene.
        """
        joints = msg.get("joints", [])
        if not joints:
            return
        hooks.run_joints(joints, getattr(self, "_sync_doc", ""))
        self._tag_redraw()

    def clear_all(self):
        """Delete all Fusion objects and joint empties."""
        self._rebuild_cache()
        for fid in list(self._id_to_obj_name):
            self.on_object_delete(fid)
        # Also remove joint empties
        for obj in list(bpy.data.objects):
            if obj.get("ftb_joint_id"):
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception:
                    pass
