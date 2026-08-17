"""
Fusion to Blender - STEP File Import

Imports STEP/STP files directly into Blender using OpenCascade (OCP).
Supports update-on-reimport: if objects from the same STEP filename
already exist in the scene, their geometry is updated instead of
creating duplicates.

Dependencies:
    cadquery-ocp (pip install cadquery-ocp)
    — or —
    OCP (pip install OCP)
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
import sys
import site
import traceback
from pathlib import Path

import numpy as np

# ── Ensure user site-packages is on path (pip --user installs go here) ───────
_user_site = site.getusersitepackages()
if _user_site and _user_site not in sys.path:
    sys.path.append(_user_site)


# ── OCC backend detection ────────────────────────────────────────────────────

def _get_occ():
    """Try to import OpenCascade Python bindings (OCP 7.9+). Returns module dict or None."""
    try:
        from OCP.STEPControl import STEPControl_Reader
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE
        from OCP.BRep import BRep_Tool
        from OCP.TopLoc import TopLoc_Location
        from OCP.TopoDS import TopoDS   # OCP 7.9: class with static methods
        mods = {
            "STEPControl_Reader": STEPControl_Reader,
            "IFSelect_RetDone": IFSelect_RetDone,
            "BRepMesh_IncrementalMesh": BRepMesh_IncrementalMesh,
            "TopExp_Explorer": TopExp_Explorer,
            "TopAbs_SOLID": TopAbs_SOLID,
            "TopAbs_FACE": TopAbs_FACE,
            "BRep_Tool": BRep_Tool,
            "TopLoc_Location": TopLoc_Location,
            "TopoDS": TopoDS,
        }
        # XDE (Extended Data Exchange) for reading shape names — optional
        try:
            from OCP.STEPCAFControl import STEPCAFControl_Reader
            from OCP.TDocStd import TDocStd_Document
            from OCP.XCAFDoc import XCAFDoc_DocumentTool
            from OCP.TDF import TDF_LabelSequence
            from OCP.TCollection import TCollection_ExtendedString
            from OCP.XCAFApp import XCAFApp_Application
            from OCP.TDataStd import TDataStd_Name
            mods["has_xde"] = True
            mods["STEPCAFControl_Reader"] = STEPCAFControl_Reader
            mods["TDocStd_Document"] = TDocStd_Document
            mods["XCAFDoc_DocumentTool"] = XCAFDoc_DocumentTool
            mods["TDF_LabelSequence"] = TDF_LabelSequence
            mods["XCAFApp_Application"] = XCAFApp_Application
            mods["TCollection_ExtendedString"] = TCollection_ExtendedString
            mods["TDataStd_Name"] = TDataStd_Name
        except ImportError:
            mods["has_xde"] = False
        return mods
    except ImportError:
        return None


_occ_available_cache = None


def is_occ_available(force: bool = False) -> bool:
    """Check if OpenCascade Python bindings are available (cached).

    Called from the panel draw, so the result is cached to avoid retrying a
    failing import on every redraw. A freshly pip-installed OCP only becomes
    importable after a Blender restart, so the cache never goes stale mid-session.
    """
    global _occ_available_cache
    if force or _occ_available_cache is None:
        _occ_available_cache = _get_occ() is not None
    return _occ_available_cache


# ── STEP support installer (F033): pip-install cadquery-ocp into Blender ──────
# OpenCascade (OCP) is a few-hundred-MB binary, far too large to bundle in the
# add-on. Direct STEP import needs it; the core Fusion→Blender bridge does not.
# We install it with `--user` (no admin rights) using Blender's OWN bundled
# Python, so the version matches and the add-on's user-site path pick-up works.
_ocp_install = {"state": "idle", "msg": ""}   # state: idle|running|done|error


def get_ocp_install_state() -> dict:
    return _ocp_install


def _blender_python_exe():
    """Locate Blender's bundled Python interpreter (Win/Mac/Linux)."""
    import glob
    prefix = sys.prefix  # Blender's python dir, e.g. <blender>/<ver>/python
    if os.name == "nt":
        cands = [os.path.join(prefix, "bin", "python.exe")]
    else:
        cands = sorted(glob.glob(os.path.join(prefix, "bin", "python3.*")))
        cands += [os.path.join(prefix, "bin", "python3"),
                  os.path.join(prefix, "bin", "python")]
    for c in cands:
        if os.path.isfile(c):
            return c
    exe = sys.executable  # last resort (only if it's actually python)
    if exe and os.path.basename(exe).lower().startswith("python"):
        return exe
    return None


def _run_pip_install_ocp():
    import subprocess
    py = _blender_python_exe()
    if not py:
        _ocp_install.update(state="error", msg="Blender Python not found")
        return
    # Best-effort: make sure pip exists (no-op on builds that already ship it).
    try:
        subprocess.run([py, "-m", "ensurepip", "--default-pip"],
                       capture_output=True, text=True, timeout=180)
    except Exception:
        pass
    base = [py, "-m", "pip", "install", "--user", "cadquery-ocp"]
    # Some setups break PyPI's TLS verification — Blender's bundled Python can
    # ship without a CA bundle, or an SSL-inspecting proxy / VPN / security
    # suite re-signs the connection — giving "CERTIFICATE_VERIFY_FAILED" and a
    # bogus "No matching distribution found". Retry against the official PyPI
    # hosts marked trusted so the install still goes through there.
    trusted = ["--trusted-host", "pypi.org",
               "--trusted-host", "files.pythonhosted.org",
               "--trusted-host", "pypi.python.org"]
    try:
        last = ""
        for cmd in (base, base + trusted):
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if p.returncode == 0:
                _ocp_install.update(state="done", msg="installed")
                return
            last = p.stderr or p.stdout or ""
            # Only the trusted-host retry can help a TLS-verify failure; for any
            # other error, stop rather than retry pointlessly.
            if "CERTIFICATE_VERIFY" not in last and "SSLError" not in last:
                break
            print("[FusionBridge STEP] pip TLS verify failed — "
                  "retrying with trusted PyPI hosts")
        lines = last.strip().splitlines()
        _ocp_install.update(state="error", msg=(lines[-1] if lines else "pip failed"))
        print("[FusionBridge STEP] pip install failed:\n", last)
    except Exception as e:
        _ocp_install.update(state="error", msg=str(e))
        print("[FusionBridge STEP] OCP install error:", e)


def start_ocp_install() -> bool:
    """Kick off the OCP install in a background thread. Returns False if busy."""
    import threading
    if _ocp_install["state"] == "running":
        return False
    _ocp_install.update(state="running", msg="")
    threading.Thread(target=_run_pip_install_ocp, daemon=True,
                     name="FTB-OCP-install").start()
    return True


# ── STEP Parsing ─────────────────────────────────────────────────────────────

def _read_step_xde(filepath: str, occ):
    """Read STEP file using XDE (Extended Data Exchange) to get shape names.

    Returns list of (name, shape) tuples with proper STEP entity names.
    """
    try:
        from OCP.TDocStd import TDocStd_Document
        from OCP.XCAFApp import XCAFApp_Application
        from OCP.XCAFDoc import XCAFDoc_DocumentTool
        from OCP.TDF import TDF_LabelSequence, TDF_Label
        from OCP.TDataStd import TDataStd_Name
        from OCP.TCollection import TCollection_ExtendedString
        from OCP.STEPCAFControl import STEPCAFControl_Reader
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_SOLID
        from OCP.TopoDS import TopoDS
    except ImportError:
        return None

    try:
        # Create XDE application and document
        app = XCAFApp_Application.GetApplication_s()
        doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
        app.InitDocument(doc)

        # Read STEP with name support
        reader = STEPCAFControl_Reader()
        reader.SetNameMode(True)
        status = reader.ReadFile(filepath)
        if status != occ["IFSelect_RetDone"]:
            return None
        if not reader.Transfer(doc):
            return None

        shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
        labels = TDF_LabelSequence()
        shape_tool.GetFreeShapes(labels)
        print(f"[FusionBridge STEP] {labels.Size()} top-level free shape(s) in file")

        solids = []
        seen_names = {}  # track duplicates

        def _get_label_name(label) -> str:
            """Extract the name attribute from an XDE label.

            Guards against native crashes (EXCEPTION_ACCESS_VIOLATION in
            TDataStd_GenericExtString::Restore) by pre-checking attribute
            existence before retrieval.
            """
            try:
                if label is None or label.IsNull():
                    return ""
                # Pre-check: only call FindAttribute when the attribute GUID exists.
                # IsAttribute() is a lightweight check that avoids triggering
                # Restore() on potentially corrupt attribute data.
                attr_id = TDataStd_Name.GetID_s()
                try:
                    if not label.IsAttribute(attr_id):
                        return ""
                except AttributeError:
                    # OCP version may not expose IsAttribute — skip the guard
                    pass
                name_attr = TDataStd_Name()
                if label.FindAttribute(attr_id, name_attr):
                    raw = name_attr.Get()
                    if raw is not None:
                        return raw.ToExtString()
            except Exception:
                pass
            return ""

        def _dedup_name(name: str) -> str:
            """Ensure unique body names by appending _N suffix."""
            if name in seen_names:
                seen_names[name] += 1
                return f"{name}_{seen_names[name]}"
            seen_names[name] = 0
            return name

        def _collect_solids(label, accum_loc=None):
            """Recursively collect solids from XDE label tree, composing each
            assembly reference's own placement along the way.

            Only extracts solids from 'simple shapes' (leaf nodes).
            Assemblies/compounds are recursed into via components, not explored directly.

            A component reference (ref_label) carries a TopLoc_Location that
            places THIS INSTANCE within its parent assembly -- e.g. the same
            shared part used twice at two different spots both point at the
            same referred/native-definition label, sitting at that part's own
            local origin. The old code jumped straight to GetReferredShape_s
            and dropped ref_label's placement entirely, so every part was
            emitted at its raw native-CAD position instead of its assembled
            position -- parts landed scattered around the scene origin
            instead of composed into the assembly (this is what made STEP
            imports fall apart compared to single-body files, or other CAD
            tools that do apply the reference placement). accum_loc carries
            the composed placement down the recursion and gets baked onto the
            leaf shape via .Located() before solids are extracted from it.
            """
            if label is None or label.IsNull():
                return
            name = _get_label_name(label)
            shape = shape_tool.GetShape_s(label)
            if shape is None or shape.IsNull():
                return

            # Check if this label has components (= assembly/compound)
            comp = TDF_LabelSequence()
            has_components = shape_tool.GetComponents_s(label, comp)

            if has_components and comp.Size() > 0:
                # This is an assembly — recurse into components, don't explore here
                for j in range(comp.Size()):
                    ref_label = comp.Value(j + 1)
                    try:
                        ref_loc = shape_tool.GetLocation_s(ref_label)
                    except Exception:
                        ref_loc = None
                    if accum_loc is not None and ref_loc is not None:
                        child_loc = accum_loc.Multiplied(ref_loc)
                    else:
                        child_loc = ref_loc if ref_loc is not None else accum_loc
                    if shape_tool.IsReference_s(ref_label):
                        referred = TDF_Label()
                        shape_tool.GetReferredShape_s(ref_label, referred)
                        _collect_solids(referred, child_loc)
                    else:
                        _collect_solids(ref_label, child_loc)
            else:
                # Simple shape (leaf) — bake the accumulated assembly placement
                # onto it, then extract solids.
                shape_to_use = shape
                if accum_loc is not None:
                    try:
                        shape_to_use = shape.Located(accum_loc)
                        t = accum_loc.Transformation().TranslationPart()
                        print(f"[FusionBridge STEP] leaf '{name}': placement applied, "
                              f"translation=({t.X():.2f}, {t.Y():.2f}, {t.Z():.2f}) mm")
                    except Exception:
                        traceback.print_exc()
                else:
                    print(f"[FusionBridge STEP] leaf '{name}': NO accumulated placement "
                          f"(top-level free shape or missing GetLocation_s)")
                try:
                    from OCP.BRepBndLib import BRepBndLib
                    from OCP.Bnd import Bnd_Box
                    bbox = Bnd_Box()
                    BRepBndLib.Add_s(shape_to_use, bbox)
                    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
                    print(f"[FusionBridge STEP] leaf '{name}': final bbox center="
                          f"({(xmin+xmax)/2:.2f}, {(ymin+ymax)/2:.2f}, {(zmin+zmax)/2:.2f}) mm")
                except Exception:
                    pass

                explorer = TopExp_Explorer(shape_to_use, TopAbs_SOLID)
                solid_idx = 0
                while explorer.More():
                    solid = TopoDS.Solid_s(explorer.Current())
                    solid_idx += 1
                    if solid_idx == 1 and name:
                        solid_name = name
                    else:
                        solid_name = f"{name}_{solid_idx}" if name else f"Body_{len(solids)+1}"
                    solids.append((_dedup_name(solid_name), solid))
                    explorer.Next()

                # NOTE: Sub-shape labels (faces/edges with color attributes) are
                # NOT recursed into. They don't contain additional solids and
                # accessing their attributes can trigger native crashes
                # (EXCEPTION_ACCESS_VIOLATION in TKLCAF) on some STEP files.

        for i in range(labels.Size()):
            _collect_solids(labels.Value(i + 1))

        return solids if solids else None
    except Exception:
        traceback.print_exc()
        return None


def _read_step_basic(filepath: str, occ):
    """Read STEP file using basic STEPControl_Reader (no names).

    Returns list of (name, shape) tuples with generic names.
    """
    reader = occ["STEPControl_Reader"]()
    status = reader.ReadFile(filepath)
    if status != occ["IFSelect_RetDone"]:
        raise RuntimeError(f"Failed to read STEP file: {filepath}")

    reader.TransferRoots()
    n_shapes = reader.NbShapes()
    if n_shapes == 0:
        raise RuntimeError(f"No shapes found in STEP file: {filepath}")

    solids = []
    global_solid_idx = 0
    for i in range(1, n_shapes + 1):
        shape = reader.Shape(i)
        explorer = occ["TopExp_Explorer"](shape, occ["TopAbs_SOLID"])
        found = False
        while explorer.More():
            solid = occ["TopoDS"].Solid_s(explorer.Current())
            global_solid_idx += 1
            solids.append((f"Body_{global_solid_idx}", solid))
            found = True
            explorer.Next()
        if not found:
            global_solid_idx += 1
            solids.append((f"Body_{global_solid_idx}", shape))

    return solids


def _read_step_file(filepath: str, occ):
    """Read a STEP file and return a list of (name, shape) tuples.

    Tries XDE reader first (for named shapes), falls back to basic reader.
    """
    # Try XDE first for named shapes
    if occ.get("has_xde"):
        try:
            result = _read_step_xde(filepath, occ)
            if result:
                print(f"[FusionBridge STEP] XDE reader: {len(result)} bodies with names")
                return result
        except Exception:
            traceback.print_exc()

    # Fall back to basic reader
    return _read_step_basic(filepath, occ)


def _tessellate_shape(shape, occ, linear_deflection=0.1, angular_deflection=0.5):
    """Tessellate a TopoDS_Shape and return (vertices, indices, normals).

    Returns:
        vertices: np.array of shape (N, 3) float32
        indices: np.array of shape (M*3,) int32  (triangle indices)
        normals: np.array of shape (N, 3) float32
    """
    from OCP.TopAbs import TopAbs_REVERSED

    # Mesh the shape
    occ["BRepMesh_IncrementalMesh"](shape, linear_deflection, False, angular_deflection, True)

    all_verts = []
    all_indices = []
    vert_offset = 0

    # Iterate faces — collect positions + winding only (normals computed below).
    explorer = occ["TopExp_Explorer"](shape, occ["TopAbs_FACE"])
    while explorer.More():
        face = occ["TopoDS"].Face_s(explorer.Current())
        loc = occ["TopLoc_Location"]()
        triangulation = occ["BRep_Tool"].Triangulation_s(face, loc)

        if triangulation is None:
            explorer.Next()
            continue

        n_nodes = triangulation.NbNodes()
        n_tris = triangulation.NbTriangles()

        trsf = loc.Transformation()
        is_reversed = face.Orientation() == TopAbs_REVERSED

        # Vertices (OCC 1-based), baked into world space
        for i in range(1, n_nodes + 1):
            pnt = triangulation.Node(i)
            pnt.Transform(trsf)
            all_verts.append([pnt.X(), pnt.Y(), pnt.Z()])

        # Triangles — flip winding for reversed faces (matches STEPper)
        for i in range(1, n_tris + 1):
            tri = triangulation.Triangle(i)
            n1, n2, n3 = tri.Get()
            if is_reversed:
                all_indices.extend([n1 - 1 + vert_offset, n3 - 1 + vert_offset, n2 - 1 + vert_offset])
            else:
                all_indices.extend([n1 - 1 + vert_offset, n2 - 1 + vert_offset, n3 - 1 + vert_offset])

        vert_offset += n_nodes
        explorer.Next()

    if not all_verts:
        return None, None, None

    # ── Normals from GEOMETRY (no fragile/version-specific OCC normal API) ───
    # BRepMesh usually omits node normals, so the old code fell back to [0,0,1]
    # for every vertex → dark/inside-out. Build smooth per-vertex normals from
    # the triangle geometry (area-weighted), then orient them OUTWARD via the
    # mesh's signed volume (robust for closed solids and thin shells).
    vertices = np.array(all_verts, dtype=np.float64)
    tris = np.array(all_indices, dtype=np.int64).reshape(-1, 3)
    v0 = vertices[tris[:, 0]]
    v1 = vertices[tris[:, 1]]
    v2 = vertices[tris[:, 2]]
    face_n = np.cross(v1 - v0, v2 - v0)            # area-weighted face normals
    vnorm = np.zeros_like(vertices)
    np.add.at(vnorm, tris[:, 0], face_n)
    np.add.at(vnorm, tris[:, 1], face_n)
    np.add.at(vnorm, tris[:, 2], face_n)
    lens = np.linalg.norm(vnorm, axis=1, keepdims=True)
    lens[lens < 1e-12] = 1.0
    vnorm /= lens
    signed_vol6 = float(np.einsum('ij,ij->', v0, np.cross(v1, v2)))  # 6x signed volume
    if signed_vol6 < 0.0:
        vnorm = -vnorm
    print(f"[FusionBridge STEP] geom-normals: verts={len(vertices)} "
          f"tris={len(tris)} vol6={signed_vol6:.3e} "
          f"{'(flipped outward)' if signed_vol6 < 0 else '(outward)'}")

    vertices = vertices.astype(np.float32)
    indices = np.array(all_indices, dtype=np.int32)
    normals = vnorm.astype(np.float32)

    return vertices, indices, normals


# ── Unit conversion ─────────────────────────────────────────────────────────
# STEP files store geometry in mm (ISO 10303 default).
# Blender works in meters. Same convention as the Fusion exporter (cm→m).
MM_TO_M = 0.001


def _read_step_length_unit(filepath: str, occ):
    """Try to detect the length unit from STEP file header.

    Returns scale factor to convert to meters.
    Most STEP files use mm (returns 0.001). Falls back to mm if undetectable.
    """
    try:
        from OCP.STEPControl import STEPControl_Reader
        from OCP.IFSelect import IFSelect_RetDone

        reader = STEPControl_Reader()
        status = reader.ReadFile(filepath)
        if status != IFSelect_RetDone:
            return MM_TO_M

        ws = reader.WS()
        model = ws.Model()
        if model is None:
            return MM_TO_M

        n_ents = model.NbEntities()
        for i in range(1, n_ents + 1):
            try:
                ent = model.Entity(i)
                type_name = ent.DynamicType().Name()
                if "length_measure" in type_name.lower() or "si_unit" in type_name.lower():
                    pass
            except Exception:
                continue
    except Exception:
        pass
    return MM_TO_M


# ── Blender Integration ──────────────────────────────────────────────────────

def _find_existing_step_objects(step_filename: str) -> dict:
    """Find all Blender objects previously imported from the same STEP file.

    Returns dict: body_name -> bpy.types.Object
    """
    import bpy
    existing = {}
    for obj in bpy.data.objects:
        if obj.get("ftb_step_file") == step_filename:
            body_name = obj.get("ftb_step_body", "")
            if body_name:
                existing[body_name] = obj
    return existing


def find_existing_objects_for_step(step_filename: str) -> tuple:
    """Check if objects from the same STEP filename exist in the scene.

    Looks for both STEP-imported objects (ftb_step_file) and
    Fusion bridge objects (fusion_component matching the filename).

    Returns (step_count, bridge_count).
    """
    import bpy
    step_count = 0
    bridge_count = 0
    fname_lower = step_filename.lower()
    for obj in bpy.data.objects:
        if obj.get("ftb_step_file", "").lower() == fname_lower:
            step_count += 1
        elif (obj.get("fusion_id", "")
              and not obj.get("ftb_step_file")
              and fname_lower in obj.get("fusion_component", "").lower()):
            bridge_count += 1
    return step_count, bridge_count


def _build_mesh_data(vertices, indices, normals):
    """Convert numpy arrays to the dict format expected by update_mesh_geometry."""
    import base64

    v_b64 = base64.b64encode(vertices.astype(np.float32).tobytes()).decode()
    i_b64 = base64.b64encode(indices.astype(np.int32).tobytes()).decode()
    n_b64 = base64.b64encode(normals.astype(np.float32).tobytes()).decode()

    return {
        "vertices_b64": v_b64,
        "indices_b64": i_b64,
        "normals_b64": n_b64,
    }


def _get_or_create_step_root_empty(step_filename: str, collection):
    """Create/retrieve root Empty inside the STEP file's collection."""
    import bpy

    empty_name = f"{step_filename}_origin"
    existing = bpy.data.objects.get(empty_name)
    if existing is not None and existing.type == 'EMPTY':
        return existing
    empty = bpy.data.objects.new(empty_name, None)
    empty.empty_display_type = 'PLAIN_AXES'
    empty.empty_display_size = 1.0
    empty["ftb_root_empty"] = step_filename
    try:
        collection.objects.link(empty)
    except Exception:
        pass
    return empty


def _parent_to_step_empty(obj, step_filename: str, collection):
    """Parent obj to the STEP root Empty (inside the same collection)."""
    import mathutils

    empty = _get_or_create_step_root_empty(step_filename, collection)
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


# ── Batched STEP importer (timer-based, like Fusion bridge) ─────────────────

_STEP_BATCH_SIZE = 4

_step_import_state = None


class _StepImportState:
    """Holds state for a running batched STEP import."""

    def __init__(self, solids, step_filename, collection_path, existing,
                 occ, linear_deflection, angular_deflection, operator):
        self.solids = solids
        self.step_filename = step_filename
        self.collection_path = collection_path
        self.existing = existing
        self.occ = occ
        self.linear_deflection = linear_deflection
        self.angular_deflection = angular_deflection
        self.operator = operator

        self.total = len(solids)
        self.cursor = 0
        self.created = 0
        self.updated = 0
        self.errors = []


def _step_batch_tick():
    """Timer callback: tessellate + create _STEP_BATCH_SIZE bodies per tick."""
    global _step_import_state
    st = _step_import_state
    if st is None:
        return None

    import bpy
    from .handler import (update_mesh_geometry, update_transform,
                          get_or_create_collection)

    try:
        _progress = None
        try:
            from . import progress as _progress
        except Exception:
            pass

        end = min(st.cursor + _STEP_BATCH_SIZE, st.total)

        for i in range(st.cursor, end):
            body_name, shape = st.solids[i]
            try:
                vertices, indices, normals = _tessellate_shape(
                    shape, st.occ, st.linear_deflection, st.angular_deflection)

                if vertices is None:
                    st.errors.append(f"{body_name}: tessellation produced no geometry")
                    continue

                # mm → m conversion
                vertices *= MM_TO_M

                mesh_data = _build_mesh_data(vertices, indices, normals)
                mesh_data["name"] = body_name
                mesh_data["component"] = st.step_filename
                mesh_data["fusion_id"] = f"step::{st.step_filename}::{body_name}"
                mesh_data["instance_path"] = ""

                existing_obj = st.existing.get(body_name)

                if existing_obj is not None:
                    update_mesh_geometry(existing_obj, mesh_data)
                    existing_obj["fusion_id"] = mesh_data["fusion_id"]
                    existing_obj["fusion_doc"] = f"step::{st.step_filename}"
                    existing_obj["ftb_step_file"] = st.step_filename
                    existing_obj["ftb_step_body"] = body_name
                    st.updated += 1
                    print(f"[FusionBridge STEP] Updated: {body_name}")
                else:
                    mesh = bpy.data.meshes.new(body_name)
                    obj = bpy.data.objects.new(body_name, mesh)

                    # Direct STEP import: place under the scene, NOT inside a
                    # "Product" collection (that wrapper is for the bridge).
                    col = get_or_create_collection(st.collection_path, root_name="")
                    col.objects.link(obj)

                    obj["fusion_id"] = mesh_data["fusion_id"]
                    obj["fusion_component"] = st.step_filename
                    obj["fusion_instance"] = ""
                    obj["fusion_doc"] = f"step::{st.step_filename}"
                    obj["ftb_step_file"] = st.step_filename
                    obj["ftb_step_body"] = body_name

                    update_mesh_geometry(obj, mesh_data)
                    update_transform(obj, [])

                    if getattr(bpy.context.scene, "ftb_create_root_empty", True):
                        _parent_to_step_empty(obj, st.step_filename, col)

                    st.created += 1
                    print(f"[FusionBridge STEP] Created: {body_name}")

            except Exception as e:
                st.errors.append(f"{body_name}: {e}")
                traceback.print_exc()

        st.cursor = end

        # Progress update
        pct = int(st.cursor / max(1, st.total) * 100)
        status = f"STEP Import  {st.cursor} / {st.total}  ({pct} %)"
        try:
            for w in bpy.context.window_manager.windows:
                w.scene.ftb_sync_status = status
                w.scene.ftb_sync_progress = st.cursor / max(1, st.total)
                w.scene.ftb_is_syncing = True
        except Exception:
            pass
        if _progress:
            try:
                _progress.set_progress(st.cursor, st.total, status)
            except Exception:
                pass

        # Redraw viewports
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
        except Exception:
            pass

        # Check if done
        if st.cursor >= st.total:
            import time
            ts = time.strftime("%H:%M:%S")
            print(f"[FusionBridge STEP] Import complete: "
                  f"{st.created} created, {st.updated} updated, "
                  f"{len(st.errors)} errors")

            # Clear progress overlay first
            if _progress:
                try:
                    _progress.clear_progress()
                except Exception:
                    pass

            # Clear syncing state
            try:
                from .i18n import t
                for w in bpy.context.window_manager.windows:
                    w.scene.ftb_is_syncing = False
                    w.scene.ftb_sync_progress = 0.0
                    w.scene.ftb_sync_status = t("step_import_done",
                                                 count=st.created + st.updated,
                                                 ts=ts)
            except Exception:
                pass

            # Redraw to remove progress bar
            try:
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == "VIEW_3D":
                            area.tag_redraw()
            except Exception:
                pass

            try:
                bpy.ops.ed.undo_push(message=f"Import STEP: {st.step_filename}")
            except Exception:
                pass

            _step_import_state = None
            return None

        return 0.0  # re-fire immediately (Blender yields to UI between ticks)

    except Exception:
        traceback.print_exc()
        # Ensure progress bar is cleared on error
        if _progress:
            try:
                _progress.clear_progress()
            except Exception:
                pass
        try:
            for w in bpy.context.window_manager.windows:
                w.scene.ftb_is_syncing = False
                w.scene.ftb_sync_progress = 0.0
        except Exception:
            pass
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
        except Exception:
            pass
        _step_import_state = None
        return None


def import_step_file(filepath: str, linear_deflection: float = 0.1,
                     angular_deflection: float = 0.5,
                     operator=None) -> dict:
    """Import a STEP file into Blender using batched timer processing.

    Tessellation and mesh creation are spread across multiple timer ticks
    (_STEP_BATCH_SIZE bodies per tick) to keep Blender responsive.

    Coordinates are converted from mm (STEP standard) to meters (Blender).

    Args:
        filepath: Path to the .step/.stp file
        linear_deflection: Tessellation linear tolerance (mm). Lower = finer mesh.
        angular_deflection: Tessellation angular tolerance (rad). Lower = smoother curves.
        operator: Optional bpy.types.Operator for status reports.

    Returns:
        dict with 'total' count (actual results reported via operator when done).
    """
    global _step_import_state
    import bpy

    occ = _get_occ()
    if occ is None:
        return {"error": "OpenCascade (OCP) not found. Install via:\n"
                         "  Blender Python: <blender>/python/bin/python -m pip install cadquery-ocp"}

    filepath = os.path.abspath(filepath)
    step_filename = Path(filepath).stem

    # Phase 1: parse STEP file (blocking but usually fast)
    try:
        solids = _read_step_file(filepath, occ)
    except Exception as e:
        return {"error": str(e)}

    if not solids:
        return {"error": f"No shapes found in STEP file: {filepath}"}

    existing = _find_existing_step_objects(step_filename)
    collection_path = step_filename

    # Phase 2: set up batched import state
    _step_import_state = _StepImportState(
        solids=solids,
        step_filename=step_filename,
        collection_path=collection_path,
        existing=existing,
        occ=occ,
        linear_deflection=linear_deflection,
        angular_deflection=angular_deflection,
        operator=operator,
    )

    print(f"[FusionBridge STEP] Starting batched import: {len(solids)} bodies "
          f"(batch size {_STEP_BATCH_SIZE})")

    # Register timer
    if not bpy.app.timers.is_registered(_step_batch_tick):
        bpy.app.timers.register(_step_batch_tick, first_interval=0.0)

    return {"total": len(solids), "created": 0, "updated": 0, "errors": []}


def get_deflection_for_preset(preset: str) -> tuple:
    """Map mesh quality preset names to (linear_deflection, angular_deflection).

    Returns (linear_mm, angular_rad) matching the Fusion quality presets.
    """
    presets = {
        "low":    (0.5,  0.52),   # ~30°
        "medium": (0.2,  0.26),   # ~15°
        "high":   (0.05, 0.14),   # ~8°
        "ultra":  (0.01, 0.07),   # ~4°
    }
    return presets.get(preset, presets["medium"])
