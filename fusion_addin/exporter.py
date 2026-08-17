"""
Fusion to Blender - Geometry Exporter (Fusion 360 side)

Coordinate system strategy:
- Fusion 360 3D environment is Z-up (same as Blender).
- Map the top-level file's TOP direction (= Fusion world +Z) to Blender Z.
- Always obtain local mesh via MeshCalculator and bake the accumulated world_transform.
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

import array as _array
import base64
import hashlib
import math
import os
import re
import time
import traceback

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    pass

CM_TO_M = 0.01

_IDENTITY_16 = [1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0]


# ── File logging (fallback for when Fusion console is not visible) ────────────
def _log_file_path() -> str:
    candidates = []
    home = os.environ.get('USERPROFILE') or os.path.expanduser('~')
    if home:
        candidates.append(os.path.join(home, 'Documents', 'fusion_bridge_log.txt'))
        candidates.append(os.path.join(home, 'fusion_bridge_log.txt'))
    tmp = os.environ.get('TEMP') or os.environ.get('TMP')
    if tmp:
        candidates.append(os.path.join(tmp, 'fusion_bridge_log.txt'))
    candidates.append(os.path.abspath('fusion_bridge_log.txt'))
    for p in candidates:
        try:
            d = os.path.dirname(p)
            if not d or os.path.isdir(d):
                return p
        except Exception:
            continue
    return 'fusion_bridge_log.txt'


_LOG_PATH = _log_file_path()


def _log(msg: str):
    """Log to both Fusion console and file."""
    print(msg)
    try:
        with open(_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _mat4_mul_cm(a: list, b: list) -> list:
    """Column-major 4x4 matrix multiplication."""
    r = [0.0] * 16
    for i in range(4):
        for j in range(4):
            for k in range(4):
                r[i + j * 4] += a[i + k * 4] * b[k + j * 4]
    return r


# ── Occurrence name normalization ─────────────────────────────────────────────
_RE_VER_INST = re.compile(r'\s+v\d+(?=:\d+|$)')
_RE_VER_ANY  = re.compile(r'\s+v\d+(?::\d+)?')
_RE_INST_END = re.compile(r':\d+$')
_RE_PATH_SEP = re.compile(r'[+/]')


def _strip_occ_version(seg: str) -> str:
    """Strip version only, keep instance. "External1 v16:1" -> "External1:1" """
    return _RE_VER_INST.sub('', seg).strip()


def _strip_occ_all(seg: str) -> str:
    """Strip both version and instance (for collection names)."""
    seg = _RE_VER_ANY.sub('', seg)
    seg = _RE_INST_END.sub('', seg)
    return seg.strip()


def _normalize_path(full_path: str, strip_instance: bool = True) -> str:
    if not full_path:
        return ""
    fn = _strip_occ_all if strip_instance else _strip_occ_version
    parts = _RE_PATH_SEP.split(full_path)
    return '/'.join(fn(p) for p in parts if p.strip())


# ── Quality presets ───────────────────────────────────────────────────────────
MESH_PRESETS = {
    "low":    (0.05,  0.52),
    "medium": (0.02,  0.26),
    "high":   (0.005, 0.14),
    "ultra":  (0.001, 0.07),
}


def _get_quality_params(quality: dict) -> tuple:
    """quality dict -> (surface_cm, normal_rad). Custom parameters take priority."""
    if not quality:
        return MESH_PRESETS["medium"]

    preset = quality.get("preset", "medium")
    s, n = MESH_PRESETS.get(preset, MESH_PRESETS["medium"])

    if "surface_tolerance_mm" in quality:
        s = quality["surface_tolerance_mm"] / 10.0
    if "normal_tolerance_deg" in quality:
        n = math.radians(quality["normal_tolerance_deg"])
    return s, n


def _flatten_transform(transform) -> list:
    """occurrence.transform -> column-major 4x4 flat list.

    Attempt A: getAsCoordinateSystem() -- build directly from axis vectors, no format ambiguity.
    Attempt B: asArray() -- Fusion API returns row-major -> always transpose.
               (Still row-major even for pure rotations, so no conditional transpose.)
    Attempt C: Extract translation only, rotation = identity.
    """
    # Attempt A: getAsCoordinateSystem()
    # Returns: (ok, origin:Point3D, xAxis:Vector3D, yAxis:Vector3D, zAxis:Vector3D)
    try:
        result = transform.getAsCoordinateSystem()
        if isinstance(result, tuple) and len(result) >= 5:
            ok, origin, xa, ya, za = result[0], result[1], result[2], result[3], result[4]
            if ok and origin is not None and xa is not None and ya is not None and za is not None:
                return [
                    xa.x, xa.y, xa.z, 0.0,
                    ya.x, ya.y, ya.z, 0.0,
                    za.x, za.y, za.z, 0.0,
                    origin.x, origin.y, origin.z, 1.0,
                ]
    except Exception:
        pass

    # Attempt B: asArray() -- row-major -> column-major transpose
    try:
        arr = transform.asArray()
        if arr is not None:
            raw = list(arr)
            if len(raw) == 16:
                return [raw[r * 4 + c] for c in range(4) for r in range(4)]
    except Exception:
        pass

    # Attempt C: translation only
    try:
        t = transform.translation
        if t is not None:
            return [1.0, 0.0, 0.0, 0.0,
                    0.0, 1.0, 0.0, 0.0,
                    0.0, 0.0, 1.0, 0.0,
                    t.x, t.y, t.z, 1.0]
    except Exception:
        pass

    _log("[FLATTEN] All methods failed, returning identity")
    return list(_IDENTITY_16)


def _occ_world_xform(occ) -> list:
    """Compose an occurrence's ancestor chain (assemblyContext) into a world/root
    space transform. occ.transform is local to the occurrence's immediate
    parent context (same as the body-export assembly walk found), so this
    walks assemblyContext up to the root and composes parent_world @ local at
    each level -- the same order export_design's recursive walk uses for body
    world_transform.
    """
    chain = []
    cur = occ
    depth = 0
    while cur is not None and depth < 64:
        chain.append(cur)
        try:
            cur = cur.assemblyContext
        except Exception:
            cur = None
        depth += 1
    world = list(_IDENTITY_16)
    for anc in reversed(chain):
        try:
            local = _flatten_transform(anc.transform)
        except Exception:
            local = list(_IDENTITY_16)
        world = _mat4_mul_cm(world, local)
    return world


def _det3x3(m: list) -> float:
    return (m[0]  * (m[5] * m[10] - m[9] * m[6])
            - m[4] * (m[1] * m[10] - m[9] * m[2])
            + m[8] * (m[1] * m[6]  - m[5] * m[2]))


def _body_visible(body) -> bool:
    try:
        return body.isLightBulbOn
    except AttributeError:
        try:
            return body.isVisible
        except Exception:
            return True


def _occ_lightbulb_on(occ) -> bool:
    try:
        return occ.isLightBulbOn
    except AttributeError:
        try:
            return occ.isVisible
        except Exception:
            return True


def _calc_local_mesh(body, surface_cm: float, normal_rad: float):
    calc = body.meshManager.createMeshCalculator()
    calc.surfaceTolerance = surface_cm
    try:
        calc.normalTolerance = normal_rad
    except AttributeError:
        pass
    return calc.calculate()


# Sent for a face whose entityToken could not be read. Not an error: some faces
# (and some Fusion versions) simply do not hand one out. Consumers must treat 0
# as "this face has no identity I can trust across syncs" and fall back to
# position-based behaviour, rather than treating all such faces as the same one.
FACE_KEY_NONE = 0


def _face_key(face, fallback_index: int) -> int:
    """A 64-bit identity for a BRep face that is meant to survive CAD edits.

    face.entityToken is Fusion's own handle for the face -- it is what stays the
    same when the face is unchanged but the model around it moved. It is a long
    opaque string, so it is hashed: the raw token is never needed downstream,
    only the ability to say "same face as last time".

    Hashing, not truncating: tokens share long common prefixes, so a prefix
    would collide constantly. sha1's first 8 bytes give ~1e-11 collision odds
    for a 10,000-face body, which is far below the odds of Fusion reissuing the
    token in the first place.

    IMPORTANT: a stable key is not the same as a stable face. Fusion reissues
    tokens for some operations, and this function cannot tell. Treat it as "the
    best identity available", and measure the real stability per operation
    before relying on it.
    """
    try:
        token = face.entityToken
    except Exception:
        token = None
    if not token:
        return FACE_KEY_NONE
    digest = hashlib.sha1(token.encode("utf-8")).digest()[:8]
    key = int.from_bytes(digest, "big", signed=True)
    # 0 is reserved for "no identity"; nudge the ~1-in-1e19 token that hashes
    # there so it does not silently claim to be unidentifiable.
    return key if key != FACE_KEY_NONE else 1


def _calc_per_face_mesh(body, surface_cm: float, normal_rad: float):
    """Per-BRepFace tessellation -> combined mesh + face group info.

    Plasticity approach: tessellate each face independently and record loop ranges.
    Used for face group-based sharp/seam edge marking in Blender.

    See _face_key() for what makes face_keys different from face_ids.

    Returns: (coords, normals, indices, face_groups, face_ids, face_keys)
      face_groups: [start_0, count_0, start_1, count_1, ...]  (loop units)
      face_ids:    [id_0, id_1, ...]  (position in body.faces -- see below)
      face_keys:   [key_0, key_1, ...]  (stable identity, 64-bit, see below)

    face_ids is the face's POSITION in body.faces, so it changes the moment the
    model gains or loses a face: add one fillet and every id after it shifts by
    one. It is fine for grouping loops within a single sync, which is all it was
    ever used for, and useless for recognising "the same face" after a CAD edit.

    face_keys is derived from face.entityToken, which is Fusion's own identity
    for the face and is meant to survive edits. Anything that has to remember a
    decision about a specific face across syncs must key off this, not face_ids.

    Whether entityToken really survives a given edit is Fusion's business and is
    not guaranteed for every operation -- measure it (see the face-key stability
    check in Bridge Pro) rather than assuming it.
    """
    all_coords = []
    all_normals = []
    all_indices = []
    face_groups = []
    face_ids = []
    face_keys = []
    vert_offset = 0
    loop_offset = 0

    try:
        faces = body.faces
    except Exception:
        mesh = _calc_local_mesh(body, surface_cm, normal_rad)
        return (list(mesh.nodeCoordinatesAsDouble),
                list(mesh.normalVectorsAsDouble),
                list(mesh.nodeIndices), [], [], [])

    for fi in range(faces.count):
        try:
            face = faces.item(fi)
            calc = face.meshManager.createMeshCalculator()
            calc.surfaceTolerance = surface_cm
            try:
                calc.normalTolerance = normal_rad
            except AttributeError:
                pass
            fm = calc.calculate()

            coords = fm.nodeCoordinatesAsDouble
            norms = fm.normalVectorsAsDouble
            idxs = fm.nodeIndices

            n_verts = len(coords) // 3
            n_loops = len(idxs)

            all_coords.extend(coords)
            all_normals.extend(norms)
            for idx in idxs:
                all_indices.append(idx + vert_offset)

            face_groups.append(loop_offset)
            face_groups.append(n_loops)
            face_ids.append(fi)
            face_keys.append(_face_key(face, fi))

            vert_offset += n_verts
            loop_offset += n_loops
        except Exception as e:
            _log(f"[FusionBridge] Failed to tessellate face {fi} of body '{getattr(body, 'name', '?')}': {e}")
            continue

    if not all_coords:
        mesh = _calc_local_mesh(body, surface_cm, normal_rad)
        return (list(mesh.nodeCoordinatesAsDouble),
                list(mesh.normalVectorsAsDouble),
                list(mesh.nodeIndices), [], [], [])

    return all_coords, all_normals, all_indices, face_groups, face_ids, face_keys


# ── Auto-orient: automatic rotation correction for tall lying objects ────────
# Analyze each occurrence's world bbox; if the dominant axis is not Z,
# rotate around the bbox center to stand it up. Flat objects (PCB, plate) are not corrected.
_ORIENT_DOMINANCE_RATIO = 1.4


def _component_local_bbox(component):
    """Combine bounding boxes of all bodies in the component (local coordinates)."""
    minx = miny = minz = float('inf')
    maxx = maxy = maxz = float('-inf')
    found = False
    try:
        for body in component.bRepBodies:
            try:
                bb = body.boundingBox
                if bb is None:
                    continue
                minx = min(minx, bb.minPoint.x); maxx = max(maxx, bb.maxPoint.x)
                miny = min(miny, bb.minPoint.y); maxy = max(maxy, bb.maxPoint.y)
                minz = min(minz, bb.minPoint.z); maxz = max(maxz, bb.maxPoint.z)
                found = True
            except Exception:
                pass
    except Exception:
        pass
    return (minx, maxx, miny, maxy, minz, maxz) if found else None


def _transform_bbox(local_bbox, tw):
    """Transform local bbox 8 corners by world transform -> world bbox."""
    minx, maxx, miny, maxy, minz, maxz = local_bbox
    wminx = wminy = wminz = float('inf')
    wmaxx = wmaxy = wmaxz = float('-inf')
    for x in (minx, maxx):
        for y in (miny, maxy):
            for z in (minz, maxz):
                wx = tw[0]*x + tw[4]*y + tw[8]*z  + tw[12]
                wy = tw[1]*x + tw[5]*y + tw[9]*z  + tw[13]
                wz = tw[2]*x + tw[6]*y + tw[10]*z + tw[14]
                if wx < wminx: wminx = wx
                if wx > wmaxx: wmaxx = wx
                if wy < wminy: wminy = wy
                if wy > wmaxy: wmaxy = wy
                if wz < wminz: wminz = wz
                if wz > wmaxz: wmaxz = wz
    return (wminx, wmaxx, wminy, wmaxy, wminz, wmaxz)


def _merge_bbox(a, b):
    """Merge two (minx,maxx,miny,maxy,minz,maxz) bboxes into a larger bbox."""
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), max(a[1], b[1]),
            min(a[2], b[2]), max(a[3], b[3]),
            min(a[4], b[4]), max(a[5], b[5]))


def _subtree_local_bbox(component, parent_in_subtree=None):
    """Return the combined bbox of all bodies in the component's subtree,
    in the component-local frame. (Used to determine the overall orientation
    of a root-level wrapper subtree like PM1893D at once.)

    parent_in_subtree: accumulated transform from the subtree-internal parent
    to this component. Identity on initial call (component's own frame is the basis).
    """
    if parent_in_subtree is None:
        parent_in_subtree = list(_IDENTITY_16)

    result = None
    direct = _component_local_bbox(component)
    if direct is not None:
        result = _merge_bbox(result, _transform_bbox(direct, parent_in_subtree))

    try:
        for occ in component.occurrences:
            try:
                child_local = _flatten_transform(occ.transform)
                child_in_subtree = _mat4_mul_cm(parent_in_subtree, child_local)
                child_bbox = _subtree_local_bbox(occ.component, child_in_subtree)
                if child_bbox is not None:
                    result = _merge_bbox(result, child_bbox)
            except Exception:
                pass
    except Exception:
        pass

    return result


def _strip_rotation(xform: list) -> list:
    """Keep translation only, rotation = identity, as a 4x4 column-major matrix.

    Strips rotation from top-level occurrences (direct children of root) so their
    children display in the component-local frame as-is. Fixes the issue where
    wrapper assemblies like PM1893D have unintended rotations (e.g. Rx(-90deg))
    at root, causing children to arrive lying down.
    """
    return [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        xform[12], xform[13], xform[14], 1.0,
    ]


def _has_rotation(xform: list, tol: float = 1e-6) -> bool:
    """Check whether xform's rotation part differs from identity."""
    return (abs(xform[0] - 1.0) > tol or abs(xform[5] - 1.0) > tol
            or abs(xform[10] - 1.0) > tol
            or abs(xform[1]) > tol or abs(xform[2]) > tol
            or abs(xform[4]) > tol or abs(xform[6]) > tol
            or abs(xform[8]) > tol or abs(xform[9]) > tol)


def _auto_orient_correction(world_bbox):
    """Analyze world bbox -> return correction matrix and label.

    Y-dominant (Y > 1.4*Z and Y > 1.4*X): Rx(+90deg) (Y->Z) rotation around bbox center
    X-dominant (X > 1.4*Z and X > 1.4*Y): Ry(-90deg) (X->Z) rotation around bbox center
    Otherwise (Z-dominant or no dominance): identity
    """
    if world_bbox is None:
        return list(_IDENTITY_16), 'identity'
    wminx, wmaxx, wminy, wmaxy, wminz, wmaxz = world_bbox
    dx, dy, dz = wmaxx - wminx, wmaxy - wminy, wmaxz - wminz
    r = _ORIENT_DOMINANCE_RATIO

    # Y-dominant case: Rx(+90deg) around bbox center (cy, cz)
    if dy > r * dz and dy > r * dx:
        cy = (wminy + wmaxy) * 0.5
        cz = (wminz + wmaxz) * 0.5
        # Rx(+90°) around (y=cy, z=cz):
        #   x' = x
        #   y' = -z + (cy + cz)
        #   z' =  y + (cz - cy)
        return [
            1.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, -1.0, 0.0, 0.0,
            0.0, cy + cz, cz - cy, 1.0,
        ], 'Y->Z'

    # X-dominant case: Ry(-90deg) around bbox center (cx, cz)
    if dx > r * dz and dx > r * dy:
        cx = (wminx + wmaxx) * 0.5
        cz = (wminz + wmaxz) * 0.5
        # Ry(-90°) around (x=cx, z=cz):
        #   x' = -z + (cx + cz)
        #   y' =  y
        #   z' =  x + (cz - cx)
        return [
            0.0, 0.0, 1.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            -1.0, 0.0, 0.0, 0.0,
            cx + cz, 0.0, cz - cx, 1.0,
        ], 'X->Z'

    return list(_IDENTITY_16), 'identity'


def export_body(body, occurrence=None, quality: dict = None,
                world_transform: list = None, explicit_path: str = None,
                root_name: str = "") -> dict | None:
    """BRepBody -> dict.

    Always obtains local coordinate mesh via MeshCalculator and bakes world_transform.
    If world_transform=None, identity is used (= local is world, for root bodies).

    explicit_path: full path from root accumulated during recursive traversal.
    Used instead of occurrence.fullPathName when provided, because occ.fullPathName
    obtained via component.occurrences may be a sub-assembly local path.

    root_name (kwargs): design.rootComponent.name. Prepended to component_name
    so that the design name (e.g. "PB10") is included in the Blender collection tree.
    Must be explicitly combined because occurrence.fullPathName does not include
    the root component.
    """
    try:
        name = body.name

        # ── Component path ─────────────────────────────────────────────────
        component_name = ""
        norm_inst_path = ""

        if explicit_path is not None:
            component_name = _normalize_path(explicit_path, strip_instance=True)
            norm_inst_path = _normalize_path(explicit_path, strip_instance=False)
        elif occurrence is not None:
            try:
                raw_path = occurrence.fullPathName
                component_name = _normalize_path(raw_path, strip_instance=True)
                norm_inst_path = _normalize_path(raw_path, strip_instance=False)
            except Exception:
                try:
                    fallback_comp = _strip_occ_all(body.parentComponent.name)
                    # Avoid duplication with root_name prepend below:
                    # if parentComponent IS the root, leave empty.
                    stripped_root = _strip_occ_all(root_name) if root_name else ""
                    if fallback_comp and fallback_comp != stripped_root:
                        component_name = fallback_comp
                except Exception:
                    pass
        else:
            # Root-level body (no occurrence). parentComponent.name is the root
            # component itself — will be added via root_name prepend below,
            # so leave component_name empty to avoid duplication ("A/A").
            pass

        # Prepend design root component name (e.g. "PB10" + "/" + ...)
        # so the top-level document name is included in the Blender collection tree.
        if root_name:
            stripped_root = _strip_occ_all(root_name)
            if stripped_root:
                if component_name:
                    component_name = f"{stripped_root}/{component_name}"
                else:
                    component_name = stripped_root

        # ── fusion_id ─────────────────────────────────────────────────────
        try:
            token = body.entityToken
            if not token:
                token = name or f"unnamed_{id(body)}"
        except Exception:
            token = name or f"unnamed_{id(body)}"
        fusion_id = f"{norm_inst_path}::{token}" if norm_inst_path else token

        # ── Mesh (per-face tessellation -> includes face group info) ─────
        surface_cm, normal_rad = _get_quality_params(quality)
        node_coords, node_normals, tri_indices, face_groups, face_ids, face_keys = \
            _calc_per_face_mesh(body, surface_cm, normal_rad)

        # ── world_transform bake ──────────────────────────────────────────
        cm = CM_TO_M
        n_verts = len(node_coords)
        n_norms = len(node_normals)

        tw = world_transform if world_transform is not None else _IDENTITY_16
        t0, t4, t8,  t12 = tw[0], tw[4], tw[8],  tw[12]
        t1, t5, t9,  t13 = tw[1], tw[5], tw[9],  tw[13]
        t2, t6, t10, t14 = tw[2], tw[6], tw[10], tw[14]
        reflected = _det3x3(tw) < 0
        # Reflected instance: flipping winding alone corrects face normal direction.
        # Normal vectors naturally reflect to the correct direction with just the
        # 3x3 transform applied. Additional sign inversion (nsign) would cause
        # double inversion, making normals point inward, so it is not applied.

        vert_arr = _array.array('f', [0.0]) * n_verts
        for i in range(0, n_verts, 3):
            x = node_coords[i]
            y = node_coords[i + 1]
            z = node_coords[i + 2]
            vert_arr[i]     = (t0 * x + t4 * y + t8  * z + t12) * cm
            vert_arr[i + 1] = (t1 * x + t5 * y + t9  * z + t13) * cm
            vert_arr[i + 2] = (t2 * x + t6 * y + t10 * z + t14) * cm

        norm_arr = _array.array('f', [0.0]) * n_norms
        for i in range(0, n_norms, 3):
            nx = node_normals[i]
            ny = node_normals[i + 1]
            nz = node_normals[i + 2]
            norm_arr[i]     = t0 * nx + t4 * ny + t8  * nz
            norm_arr[i + 1] = t1 * nx + t5 * ny + t9  * nz
            norm_arr[i + 2] = t2 * nx + t6 * ny + t10 * nz

        if reflected:
            idx_arr = _array.array('i')
            for i in range(0, len(tri_indices), 3):
                idx_arr.append(tri_indices[i])
                idx_arr.append(tri_indices[i + 2])
                idx_arr.append(tri_indices[i + 1])
        else:
            idx_arr = _array.array('i', tri_indices)

        fg_arr = _array.array('i', face_groups) if face_groups else _array.array('i')
        fi_arr = _array.array('i', face_ids) if face_ids else _array.array('i')
        # 'q' = signed 64-bit, matching _face_key. Byte order follows the host,
        # exactly like the vertex/index arrays above -- the protocol has always
        # assumed both ends are little-endian, and every platform Fusion runs on
        # is.
        fk_arr = _array.array('q', face_keys) if face_keys else _array.array('q')

        result = {
            "fusion_id":     fusion_id,
            "instance_path": norm_inst_path,
            "name":          name,
            "component":     component_name,
            "transform":     list(_IDENTITY_16),  # world bake complete
            "vertices_b64":  base64.b64encode(vert_arr.tobytes()).decode('ascii'),
            "normals_b64":   base64.b64encode(norm_arr.tobytes()).decode('ascii'),
            "indices_b64":   base64.b64encode(idx_arr.tobytes()).decode('ascii'),
            "vertex_count":  n_verts // 3,
            "face_count":    len(idx_arr) // 3,
            "surface_tol_m": surface_cm * CM_TO_M,
        }
        if len(fg_arr):
            result["face_groups_b64"] = base64.b64encode(fg_arr.tobytes()).decode('ascii')
            result["face_ids_b64"]    = base64.b64encode(fi_arr.tobytes()).decode('ascii')
            if len(fk_arr):
                result["face_keys_b64"] = base64.b64encode(fk_arr.tobytes()).decode('ascii')
        return result
    except Exception:
        traceback.print_exc()
        return None


# ── Visibility helpers ────────────────────────────────────────────────────────
def _build_hidden_occ_paths(root) -> set:
    """fullPathName set for occurrences that are hidden in Fusion.

    An occurrence counts as hidden when its own light bulb is off
    (isLightBulbOn == False) OR its effective visibility is off
    (isVisible == False). The isVisible fallback matters for proxy
    occurrences inside an external reference (xref): toggling the eye in the
    parent document is not always reflected in the proxy's isLightBulbOn, but
    it IS reflected in isVisible. Both values are logged so the cause stays
    auditable in fusion_bridge_log.txt.
    """
    hidden = set()
    n_total = 0
    n_bulb_off = 0
    n_vis_off = 0
    samples = []
    try:
        for occ in root.allOccurrences:
            try:
                n_total += 1
                try:
                    bulb = bool(occ.isLightBulbOn)
                except Exception:
                    bulb = True
                try:
                    vis = bool(occ.isVisible)
                except Exception:
                    vis = True
                if not bulb:
                    n_bulb_off += 1
                if not vis:
                    n_vis_off += 1
                if (not bulb) or (not vis):
                    hidden.add(occ.fullPathName)
                    if len(samples) < 8:
                        samples.append(f"{occ.fullPathName} [bulb={bulb} vis={vis}]")
            except Exception:
                pass
    except Exception:
        pass
    try:
        _log(f"[HIDE-DETECT] occurrences={n_total} bulb_off={n_bulb_off} "
             f"vis_off={n_vis_off} -> hidden={len(hidden)}")
        for s in samples:
            _log(f"[HIDE-DETECT]   {s}")
    except Exception:
        pass
    return hidden


def _is_ancestor_hidden(occ_path: str, hidden_paths: set) -> bool:
    if not hidden_paths:
        return False
    if occ_path in hidden_paths:
        return True
    for hp in hidden_paths:
        if occ_path.startswith(hp + '+') or occ_path.startswith(hp + '/'):
            return True
    return False


def _count_visible_bodies(root, include_hidden: bool) -> int:
    count = 0
    hidden_paths = set() if include_hidden else _build_hidden_occ_paths(root)

    try:
        for body in root.bRepBodies:
            if include_hidden or _body_visible(body):
                count += 1
    except Exception:
        pass

    try:
        for occ in root.allOccurrences:
            try:
                if not include_hidden and _is_ancestor_hidden(occ.fullPathName, hidden_paths):
                    continue
                for body in occ.component.bRepBodies:
                    if include_hidden or _body_visible(body):
                        count += 1
            except Exception:
                pass
    except Exception:
        pass

    return max(count, 1)


# ── Main export ──────────────────────────────────────────────────────────────
def export_design(design, quality: dict = None, include_hidden: bool = False,
                  progress_cb=None, body_callback=None) -> list:
    """Export all visible bodies via recursive traversal.

    Paths:
      1. root.bRepBodies -> root bodies (world = identity)
      2. component.occurrences recursive -> accurate world transform via local transform accumulation

    Key design: occ.fullPathName obtained via component.occurrences may not return
    the full path from root in a sub-assembly context.
    Therefore _walk_assembly accumulates the full path directly as
    parent_full_path + "+" + occ.name. This path is used consistently for
    dedup keys, collection placement, and logging.

    The flat fallback only handles external references (xref) etc. that are not
    reachable via component.occurrences. When comparing with recursive_visited,
    normalized paths with versions stripped are used to prevent mismatches due to
    format differences (presence/absence of version).
    """
    results = []
    seen_ids = set()

    _log(f"[FusionBridge] === Export start === (quality={quality}, "
         f"include_hidden={include_hidden})")

    try:
        root = design.rootComponent

        total_bodies = _count_visible_bodies(root, include_hidden) if progress_cb else 0
        processed = [0]

        def _tick():
            processed[0] += 1
            if progress_cb:
                try:
                    progress_cb(processed[0], total_bodies)
                except Exception:
                    pass

        if progress_cb:
            try:
                progress_cb(0, total_bodies)
            except Exception:
                pass

        body_hidden_count = [0]
        dedup_collision_count = [0]
        occ_count = [0]
        skipped_hidden = [0]

        # design root component name (e.g. "PB10") -- prepended as top-level
        # folder in the Blender collection tree. Not included in
        # occurrence.fullPathName, so must be passed explicitly.
        try:
            design_root_name = root.name or ""
        except Exception:
            design_root_name = ""
        _log(f"[FusionBridge] design root name: '{design_root_name}'")

        stripped_root_name = _strip_occ_all(design_root_name) if design_root_name else ""

        # Build hidden occurrence paths for ancestor-hidden checks.
        # ALWAYS build this set, even when include_hidden=True. Reason: Blender
        # always requests include_hidden=True (it imports everything and hides
        # locally), so it still needs hidden_ancestor metadata to collection-hide
        # the right occurrences. The flat fallback — which handles external
        # references (xrefs) unreachable via component.occurrences — relies on
        # this set for ancestor-hidden detection. Leaving it empty made hidden
        # sub-assemblies inside an xref (e.g. a lightbulb-off FL25CR_030001_ASM
        # under an xref'd MF20-... parent) export as fully visible in Blender.
        hidden_paths = _build_hidden_occ_paths(root)
        _log(f"[FusionBridge] hidden occurrences detected (bulb-off or invisible): "
             f"{len(hidden_paths)}"
             + ("  e.g. " + " | ".join(list(hidden_paths)[:5]) if hidden_paths else ""))
        # Normalized form of the authoritative hidden set (version stripped, instance
        # kept), for matching against the recursive walk's accumulated full_path. The
        # recursive walk descends into an xref's INTERNAL definition, whose occurrences
        # don't carry the parent document's hide override — so the only reliable signal
        # there is membership in this set (built from root.allOccurrences, which does).
        hidden_paths_norm = {_normalize_path(p, strip_instance=False) for p in hidden_paths}

        def _make_component_path(occ_full_path: str) -> str:
            """occurrence fullPathName -> component path (root prepend, instance stripped).
            Format matching Blender's component_name.
            """
            normalized = _normalize_path(occ_full_path, strip_instance=True)
            if stripped_root_name:
                return f"{stripped_root_name}/{normalized}" if normalized else stripped_root_name
            return normalized

        def _emit(body, occurrence, world_xform, explicit_path=None,
                  body_hidden=False, hidden_ancestor_path=""):
            """Process one body -> check seen_ids -> export -> callback/results.

            body_hidden: body itself has isLightBulbOn=False in Fusion
                         (part-level hide). Maps to hide_viewport in Blender.
            hidden_ancestor_path: normalized component path of the closest-to-root
                         hidden ancestor occurrence (assembly)
                         (e.g. "PB10/PM1893D/FILTERSCREEN_ASM").
                         In Blender, only that collection is hidden;
                         child bodies are not individually hidden.
            """
            try:
                try:
                    token = body.entityToken
                    if not token:
                        token = body.name or f"unnamed_{id(body)}"
                except Exception:
                    token = body.name or f"unnamed_{id(body)}"

                norm_path = ""
                if explicit_path is not None:
                    norm_path = _normalize_path(explicit_path, strip_instance=False)
                elif occurrence is not None:
                    try:
                        norm_path = _normalize_path(occurrence.fullPathName, strip_instance=False)
                    except Exception:
                        pass

                dedup_key = f"{norm_path}::{token}"
                if dedup_key in seen_ids:
                    dedup_collision_count[0] += 1
                    return
                seen_ids.add(dedup_key)

                data = export_body(body, occurrence=occurrence, quality=quality,
                                   world_transform=world_xform,
                                   explicit_path=explicit_path,
                                   root_name=design_root_name)
                if data:
                    if body_hidden:
                        data['body_hidden'] = True
                    if hidden_ancestor_path:
                        data['hidden_ancestor'] = hidden_ancestor_path
                    if body_callback:
                        try:
                            body_callback(data)
                        except Exception:
                            traceback.print_exc()
                    else:
                        results.append(data)
            except Exception:
                traceback.print_exc()
            finally:
                _tick()

        # ── Root correction cache ─────────────────────────────────────────────
        # Cache per-root correction values so flat fallback's non-top-level
        # occurrences receive the same root strip+orient as the recursive walk.
        # key: root occurrence fullPathName (e.g. "PM1893D v3:1")
        # value: (stripped_local_xform, subtree_correction_matrix)
        root_corrections = {}
        occ_by_path_for_correction = {}
        try:
            for o in root.allOccurrences:
                try:
                    occ_by_path_for_correction[o.fullPathName] = o
                except Exception:
                    pass
        except Exception:
            pass

        def _get_root_effective(root_occ_name: str):
            """Return the effective transform with strip+correction applied for a root occurrence."""
            if root_occ_name in root_corrections:
                return root_corrections[root_occ_name]
            anc = occ_by_path_for_correction.get(root_occ_name)
            if anc is None:
                root_corrections[root_occ_name] = list(_IDENTITY_16)
                return root_corrections[root_occ_name]
            local = _flatten_transform(anc.transform)
            if _has_rotation(local):
                local = _strip_rotation(local)
            try:
                subtree_bbox = _subtree_local_bbox(anc.component)
                if subtree_bbox is not None:
                    correction, label = _auto_orient_correction(subtree_bbox)
                    if label != 'identity':
                        local = _mat4_mul_cm(local, correction)
            except Exception:
                pass
            root_corrections[root_occ_name] = local
            return local

        def _world_xform_via_path(full_path: str):
            """Follow the segments of fullPathName, applying root strip+orient,
            and return the accumulated world transform. Ensures flat fallback's
            non-top-level occurrences receive the same root correction as the recursive walk.
            """
            parts = _RE_PATH_SEP.split(full_path)
            world = list(_IDENTITY_16)
            for i in range(len(parts)):
                prefix_plus = '+'.join(parts[:i+1])
                prefix_slash = '/'.join(parts[:i+1])
                anc = (occ_by_path_for_correction.get(prefix_plus)
                       or occ_by_path_for_correction.get(prefix_slash))
                if anc is None:
                    continue
                if i == 0:
                    seg_local = _get_root_effective(prefix_plus
                        if prefix_plus in occ_by_path_for_correction
                        else prefix_slash)
                else:
                    seg_local = _flatten_transform(anc.transform)
                world = _mat4_mul_cm(world, seg_local)
            return world

        # ── Root-level bodies (world = identity) ────────────────────────────
        try:
            for body in root.bRepBodies:
                visible = _body_visible(body)
                if not include_hidden and not visible:
                    body_hidden_count[0] += 1
                    try:
                        _log(f"[BODY-SKIP-HIDDEN] root body name='{body.name}'")
                    except Exception:
                        pass
                    continue
                _emit(body, occurrence=None, world_xform=None,
                      body_hidden=(not visible))
        except Exception:
            traceback.print_exc()

        # ── Recursive traversal: accumulate local transforms via component.occurrences
        # component.occurrences returns only direct children and .transform is always
        # the local transform relative to the parent component.
        #
        # Note: occ.fullPathName obtained via component.occurrences may not return
        # the full path from root in a sub-assembly context.
        # Accumulate paths directly as parent_full_path + "+" + occ.name.
        recursive_visited = set()  # stores normalized full paths

        def _walk_assembly(component, parent_world, parent_full_path="", depth=0,
                           ancestor_hidden_path=""):
            try:
                occs = list(component.occurrences)
            except Exception:
                return

            for occ in occs:
                try:
                    occ_count[0] += 1
                    occ_name = ""
                    try:
                        occ_name = occ.name  # e.g. "PM1893D v1:1", "PCBA:1"
                    except Exception:
                        pass

                    # Build full path from root to this occ directly
                    full_path = (parent_full_path + "+" + occ_name) if parent_full_path else occ_name
                    # Store normalized path in visited set (for flat fallback comparison)
                    norm_full_path = _normalize_path(full_path, strip_instance=False)
                    recursive_visited.add(norm_full_path)

                    # Track occurrence visibility state.
                    #   - ancestor_hidden_path: topmost hidden ancestor path.
                    #     If already set, keep as-is (topmost takes priority).
                    #     If not yet set and this occ is hidden, use this occ's path.
                    #   - Body hide is determined solely by body itself (isLightBulbOn).
                    #     Even if occurrence is hidden, child bodies are not individually
                    #     hidden (instead hidden_ancestor_path is passed -> collection-level hide).
                    # Hidden iff this occurrence's root-context path is in the
                    # authoritative hidden set. That set is built from
                    # root.allOccurrences, which carries the parent document's hide
                    # override even for proxies inside an xref — whereas the occ
                    # object we hold here came from the xref's INTERNAL definition
                    # and reports isLightBulbOn/isVisible from the xref's own
                    # (unhidden) state. Matching by normalized path is the only
                    # reliable signal (this is why the direct bulb/visible checks
                    # found 0 while root.allOccurrences found 87). Fall back to the
                    # direct checks for non-xref trees.
                    occ_hidden = norm_full_path in hidden_paths_norm
                    if not occ_hidden:
                        try:
                            occ_hidden = (not bool(occ.isLightBulbOn)) or (not bool(occ.isVisible))
                        except Exception:
                            occ_hidden = not _occ_lightbulb_on(occ)
                    if ancestor_hidden_path:
                        my_hidden_ancestor = ancestor_hidden_path
                    elif occ_hidden:
                        my_hidden_ancestor = _make_component_path(full_path)
                    else:
                        my_hidden_ancestor = ""

                    if not include_hidden:
                        if occ_hidden or ancestor_hidden_path:
                            skipped_hidden[0] += 1
                            continue

                    local_xform = _flatten_transform(occ.transform)

                    # Use original transform as-is. The previously applied strip-rotation
                    # and subtree-orient introduced (cy+cz, cz-cy) translation in
                    # bbox-center-based rotation for top-level occurrences like PM1893D,
                    # causing relative coordinates to misalign with other top-level
                    # occurrences (front_1 etc.). Since Fusion's PB10 view is the
                    # user's intended final arrangement, bake that transform directly.

                    world_xform = _mat4_mul_cm(parent_world, local_xform)
                    emit_xform = world_xform

                    try:
                        for body in occ.component.bRepBodies:
                            body_visible_flag = _body_visible(body)
                            body_directly_hidden = not body_visible_flag
                            # Skip decision: if include_hidden=False, skip when
                            # directly hidden or ancestor hidden
                            if not include_hidden and (body_directly_hidden or my_hidden_ancestor):
                                body_hidden_count[0] += 1
                                try:
                                    _log(f"[BODY-SKIP-HIDDEN] '{full_path}' body='{body.name}'")
                                except Exception:
                                    pass
                                continue
                            # Only direct hide is passed as body_hidden.
                            # Ancestor hide is passed separately via hidden_ancestor_path
                            # -> only the collection is hidden in Blender.
                            _emit(body, occ, emit_xform, explicit_path=full_path,
                                  body_hidden=body_directly_hidden,
                                  hidden_ancestor_path=my_hidden_ancestor)
                    except Exception:
                        traceback.print_exc()

                    _walk_assembly(occ.component, world_xform, full_path, depth + 1,
                                   my_hidden_ancestor)
                except Exception:
                    traceback.print_exc()

        _walk_assembly(root, list(_IDENTITY_16), "")

        recursive_count = occ_count[0]

        # ── Fallback: only process occurrences missed by component.occurrences recursion
        # External references (xref) etc. may be missing from component.occurrences.
        # Compare with recursive_visited using normalized paths with versions stripped
        # to absorb format differences like "PM1893D v1:1+PCBA:1" vs "PM1893D:1+PCBA:1".
        flat_only_count = 0
        try:
            for occ in root.allOccurrences:
                try:
                    fp = occ.fullPathName
                    norm_fp = _normalize_path(fp, strip_instance=False)
                    if norm_fp in recursive_visited:
                        continue
                    flat_only_count += 1
                    occ_count[0] += 1

                    # Separate occurrence + ancestor hidden.
                    # ancestor_hidden_path: use that path if ancestor is hidden (for collection hide).
                    # body_directly_hidden: body's own hide state (for object hide).
                    occ_visible = _occ_lightbulb_on(occ)
                    flat_ancestor_hidden_path = ""
                    try:
                        if _is_ancestor_hidden(fp, hidden_paths):
                            # Find the first hidden ancestor prefix and convert to path
                            for hp in hidden_paths:
                                if fp == hp or fp.startswith(hp + '+') or fp.startswith(hp + '/'):
                                    flat_ancestor_hidden_path = _make_component_path(hp)
                                    break
                    except Exception:
                        pass
                    if not occ_visible and not flat_ancestor_hidden_path:
                        flat_ancestor_hidden_path = _make_component_path(fp)
                    if not include_hidden and (not occ_visible or flat_ancestor_hidden_path):
                        skipped_hidden[0] += 1
                        continue

                    # Two paths for flat fallback:
                    #   1) top-level occurrence: apply strip+orient directly (same as
                    #      depth=0 in recursive walk)
                    #   2) non-top-level (descendant of root missing from
                    #      component.occurrences xref): must accumulate root correction
                    #      along the path for consistency with siblings processed by
                    #      recursive walk
                    # Use original transform as-is (strip / subtree-orient removed).
                    # See recursive walk comments for detailed reasoning.
                    world_xform = _flatten_transform(occ.transform)

                    emit_xform = world_xform

                    try:
                        for body in occ.component.bRepBodies:
                            body_visible_flag = _body_visible(body)
                            body_directly_hidden = not body_visible_flag
                            if not include_hidden and (body_directly_hidden or flat_ancestor_hidden_path):
                                body_hidden_count[0] += 1
                                try:
                                    _log(f"[BODY-SKIP-HIDDEN-FLAT] '{fp}' body='{body.name}'")
                                except Exception:
                                    pass
                                continue
                            # Only direct hide as body_hidden, ancestor hide via separate path
                            _emit(body, occ, emit_xform,
                                  body_hidden=body_directly_hidden,
                                  hidden_ancestor_path=flat_ancestor_hidden_path)
                    except Exception:
                        traceback.print_exc()
                except Exception:
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()

        _log(f"[FusionBridge] Export: recursive_occ={recursive_count}, "
             f"flat_fallback={flat_only_count}, "
             f"occ_hidden_skipped={skipped_hidden[0]}, "
             f"body_hidden_skipped={body_hidden_count[0]}, "
             f"dedup_collisions={dedup_collision_count[0]}, "
             f"emitted_unique={len(seen_ids)}")

        # Missing body diagnostics: directly count total bodies in design (root + all occurrences).
        # Compare with emitted unique count to identify gaps beyond visibility/skip reasons.
        try:
            total_design_bodies = 0
            try:
                total_design_bodies += len(list(root.bRepBodies))
            except Exception:
                pass
            try:
                for o in root.allOccurrences:
                    try:
                        total_design_bodies += len(list(o.component.bRepBodies))
                    except Exception:
                        pass
            except Exception:
                pass
            diff = total_design_bodies - len(seen_ids)
            _log(f"[FusionBridge] Total design bodies: {total_design_bodies}, "
                 f"emitted: {len(seen_ids)}, missing: {diff} "
                 f"(missing = hidden_skipped + dedup + duplicate_proxy_pairs)")
        except Exception:
            pass

        _log(f"[FusionBridge] Log file: {_LOG_PATH}")

    except Exception:
        traceback.print_exc()

    return results


def export_joints(design) -> list:
    """Export all joints and as-built joints from the design.

    Returns a list of joint dicts, each containing:
      - joint_id:      unique identifier (entityToken or name)
      - name:          joint name
      - joint_type:    string ('Revolute', 'Slider', 'Cylindrical', 'Pin', 'Planar', 'Ball', 'Rigid')
      - origin:        [x, y, z] in meters (Blender units)
      - axis:          [x, y, z] normalized direction vector
      - occ_one:       occurrence 1 path (normalized)
      - occ_two:       occurrence 2 path (normalized)
      - limits:        dict with min/max rotation (deg) and/or translation (m)
    """
    results = []
    if design is None:
        return results

    root = design.rootComponent

    _JOINT_TYPE_MAP = {
        0: "Rigid",
        1: "Revolute",
        2: "Slider",
        3: "Cylindrical",
        4: "Pin",
        5: "Planar",
        6: "Ball",
    }

    def _process_joint(joint, is_as_built=False):
        try:
            # Skip suppressed or errored joints
            try:
                if hasattr(joint, 'isSuppressed') and joint.isSuppressed:
                    return
            except Exception:
                pass
            try:
                if hasattr(joint, 'healthState'):
                    hs = joint.healthState
                    # HealthState 0=OK, >0=warning/error
                    if hs and hs > 1:
                        return
            except Exception:
                pass

            name = joint.name or "Joint"

            # Joint type
            try:
                jtype = _JOINT_TYPE_MAP.get(int(joint.jointMotion.jointType), "Unknown")
            except Exception:
                jtype = "Unknown"

            # Joint ID
            try:
                jid = joint.entityToken
                if not jid:
                    jid = name
            except Exception:
                jid = name

            # Connected occurrences (needed below as an origin/axis fallback too)
            occ_one_obj = None
            occ_two_obj = None
            occ_one = ""
            occ_two = ""
            try:
                occ_one_obj = joint.occurrenceOne
                if occ_one_obj:
                    occ_one = _normalize_path(occ_one_obj.fullPathName, strip_instance=False)
            except Exception:
                pass
            try:
                occ_two_obj = joint.occurrenceTwo
                if occ_two_obj:
                    occ_two = _normalize_path(occ_two_obj.fullPathName, strip_instance=False)
            except Exception:
                pass

            # Origin and axis from joint geometry. geometryOrOriginOne is only
            # populated for joints created from explicit geometry selections --
            # AsBuiltJoints (captured from the occurrences' current relative
            # position, no geometry picked) generally do not expose it, so the
            # old bare try/except silently left every as-built joint's Empty at
            # world origin (0,0,0), rotating around the wrong pivot entirely.
            origin = None
            axis = None
            try:
                geo = joint.geometryOrOriginOne
                if geo is not None:
                    try:
                        pt = geo.origin
                        if pt is not None:
                            origin = [pt.x * CM_TO_M, pt.y * CM_TO_M, pt.z * CM_TO_M]
                    except Exception:
                        pass
                    try:
                        ax = geo.primaryAxisVector
                        if ax is not None:
                            axis = [ax.x, ax.y, ax.z]
                    except Exception:
                        pass
            except Exception:
                pass

            if origin is None:
                # Fall back to the moving occurrence's own world position --
                # not exact for every joint type, but far closer to the real
                # pivot than the world origin, and exact for Rigid joints
                # (which need no axis, just the right parenting).
                fallback_occ = occ_two_obj or occ_one_obj
                if fallback_occ is not None:
                    try:
                        world = _occ_world_xform(fallback_occ)
                        origin = [world[12] * CM_TO_M, world[13] * CM_TO_M, world[14] * CM_TO_M]
                        _log(f"[JOINT] '{name}' (as_built={is_as_built}): "
                             f"geometryOrOriginOne unavailable, using occurrence "
                             f"world position as origin fallback")
                    except Exception:
                        traceback.print_exc()
                if origin is None:
                    origin = [0.0, 0.0, 0.0]
                    _log(f"[JOINT] '{name}': no origin available, defaulting to (0,0,0)")
            if axis is None:
                axis = [0.0, 0.0, 1.0]

            # Limits
            limits = {}
            try:
                motion = joint.jointMotion
                if jtype == "Revolute" or jtype == "Cylindrical":
                    try:
                        rl = motion.rotationLimits
                        if rl.isMinimumValueEnabled:
                            limits["rot_min"] = math.degrees(rl.minimumValue)
                        if rl.isMaximumValueEnabled:
                            limits["rot_max"] = math.degrees(rl.maximumValue)
                    except Exception:
                        pass
                if jtype == "Slider" or jtype == "Cylindrical":
                    try:
                        sl = motion.slideLimits
                        if sl.isMinimumValueEnabled:
                            limits["slide_min"] = sl.minimumValue * CM_TO_M
                        if sl.isMaximumValueEnabled:
                            limits["slide_max"] = sl.maximumValue * CM_TO_M
                    except Exception:
                        pass
            except Exception:
                pass

            results.append({
                "joint_id": jid,
                "name": name,
                "joint_type": jtype,
                "origin": origin,
                "axis": axis,
                "occ_one": occ_one,
                "occ_two": occ_two,
                "limits": limits,
                "is_as_built": is_as_built,
            })
        except Exception:
            traceback.print_exc()

    # Standard joints
    try:
        for joint in root.allJoints:
            _process_joint(joint, is_as_built=False)
    except Exception:
        pass

    # As-built joints
    try:
        for joint in root.allAsBuiltJoints:
            _process_joint(joint, is_as_built=True)
    except Exception:
        pass

    _log(f"[FusionBridge] Exported {len(results)} joints")
    return results


def build_delete_message(fusion_id: str) -> dict:
    return {"type": "object_delete", "fusion_id": fusion_id}
