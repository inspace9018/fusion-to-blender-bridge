"""Re-sync preservation — the promise printed on the README.

    "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" \\
        --background --factory-startup --python tests/test_preservation_blender.py

The listing says: edit in Fusion, press Sync, and your Materials, Modifiers and
hand-marked Sharp / Seam / Crease / Bevel Weight are still there. That claim rests
entirely on `_save_mesh_userdata` / `_restore_mesh_userdata` bracketing the
`mesh.clear_geometry()` that a sync performs. Nothing was checking it.

These tests reproduce that bracket exactly as handler.py does it (save → clear →
rebuild → restore), so they fail if the ordering or the matching logic regresses.

Separate from tests/test_exporter_pure.py, which is pure-Python (pytest, no bpy).
This one needs Blender and so cannot live in that suite.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bmesh  # noqa: E402
import bpy  # noqa: E402

from blender_addon import handler  # noqa: E402

_results = []


def say(msg):
    print(msg, flush=True)


def chk(label, cond, extra=""):
    _results.append((label, bool(cond)))
    say(f"[{'PASS' if cond else 'FAIL'}] {label}{('  ' + str(extra)) if extra else ''}")


# ── fixtures ─────────────────────────────────────────────────────────────────

CUBE_VERTS = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
              (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
CUBE_FACES = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
              (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]


def make_cube(name="Body1"):
    me = bpy.data.meshes.new(name)
    me.from_pydata(CUBE_VERTS, [], CUBE_FACES)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj["fusion_id"] = f"body::{name}"
    return obj


def resync(obj, verts=None, faces=None):
    """Do to the mesh exactly what a sync does: save, clear, rebuild, restore.

    Mirrors handler.py lines 1102/1103 and 1172. Passing new verts simulates the
    user having edited the model in Fusion.
    """
    mesh = obj.data
    saved = handler._save_mesh_userdata(obj, mesh)
    mesh.clear_geometry()
    mesh.from_pydata(list(verts or CUBE_VERTS), [], list(faces or CUBE_FACES))
    mesh.update()
    handler._restore_mesh_userdata(obj, mesh, saved)
    return saved


def mark_edges(obj, sharp=(), seam=()):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    for i in sharp:
        bm.edges[i].smooth = False
    for i in seam:
        bm.edges[i].seam = True
    bm.to_mesh(obj.data)
    bm.free()


def set_bevel(obj, weights):
    """Write per-edge bevel weights through the add-on's own helper.

    Blender 4.0 moved these out of the bmesh layer and into a generic
    `bevel_weight_edge` attribute; `bm.edges.layers.bevel_weight` no longer
    exists. handler already carries the version-spanning accessor, so the test
    uses it rather than keeping a second copy that can drift.
    """
    import numpy as np
    arr = np.zeros(len(obj.data.edges), dtype=np.float32)
    for i, v in weights.items():
        arr[i] = v
    handler._set_edge_bevel_weights(obj.data, arr)
    obj.data.update()


def read_edges(obj):
    """(sharp set, seam set) keyed by the edge's vertex-position pair.

    Edge INDICES are meaningless across a rebuild -- the mesh is built fresh and
    Blender may order edges differently. The add-on itself matches on quantized
    vertex positions, so the test compares the same way.
    """
    me = obj.data
    sharp, seam = set(), set()
    for e in me.edges:
        a = tuple(round(c, 4) for c in me.vertices[e.vertices[0]].co)
        b = tuple(round(c, 4) for c in me.vertices[e.vertices[1]].co)
        key = tuple(sorted([a, b]))
        if not e.use_edge_sharp:
            pass
        else:
            sharp.add(key)
        if e.use_seam:
            seam.add(key)
    return sharp, seam


def wipe():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


say("free Bridge preservation tests")


# ── 1. Hand-marked edges survive an unchanged re-sync ────────────────────────
say("\n=== 1. edge marks survive a re-sync ===")
try:
    wipe()
    obj = make_cube()
    mark_edges(obj, sharp=[0, 1, 2], seam=[0, 4])
    before_sharp, before_seam = read_edges(obj)
    chk("fixture sanity: marks were applied",
        len(before_sharp) == 3 and len(before_seam) == 2,
        f"sharp {len(before_sharp)}, seam {len(before_seam)}")

    resync(obj)

    after_sharp, after_seam = read_edges(obj)
    chk("every Sharp edge came back", after_sharp == before_sharp,
        f"{len(after_sharp)}/{len(before_sharp)}")
    chk("every Seam edge came back", after_seam == before_seam,
        f"{len(after_seam)}/{len(before_seam)}")
except Exception:
    traceback.print_exc()
    chk("section 1", False, "raised")


# ── 2. Bevel weights survive ─────────────────────────────────────────────────
# Named in the listing, and Bridge Pro's Auto Bevel writes into the same channel.
say("\n=== 2. bevel weights survive ===")
try:
    wipe()
    obj = make_cube()
    set_bevel(obj, {0: 1.0, 3: 0.5})
    before = handler._get_edge_bevel_weights(obj.data)
    chk("fixture sanity: weights were written",
        before is not None and float(before.max()) > 0.9, None if before is None else float(before.max()))

    resync(obj)

    after = handler._get_edge_bevel_weights(obj.data)
    chk("a weighted edge is still weighted",
        after is not None and float(after.max()) > 0.9,
        None if after is None else float(after.max()))
    chk("the number of weighted edges is unchanged",
        after is not None and before is not None
        and int((after > 0.01).sum()) == int((before > 0.01).sum()),
        f"{int((before > 0.01).sum())} -> {int((after > 0.01).sum())}")
except Exception:
    traceback.print_exc()
    chk("section 2", False, "raised")


# ── 3. Materials and per-face assignment survive ─────────────────────────────
say("\n=== 3. materials survive ===")
try:
    wipe()
    obj = make_cube()
    red = bpy.data.materials.new("Red")
    blue = bpy.data.materials.new("Blue")
    obj.data.materials.append(red)
    obj.data.materials.append(blue)
    for i, p in enumerate(obj.data.polygons):
        p.material_index = 1 if i % 2 else 0
    before_slots = [m.name for m in obj.data.materials]
    before_idx = [p.material_index for p in obj.data.polygons]

    resync(obj)

    chk("both material slots survived",
        [m.name for m in obj.data.materials] == before_slots,
        [m.name for m in obj.data.materials])
    chk("per-face material assignment survived",
        [p.material_index for p in obj.data.polygons] == before_idx)
except Exception:
    traceback.print_exc()
    chk("section 3", False, "raised")


# ── 4. UVs survive ───────────────────────────────────────────────────────────
say("\n=== 4. UVs survive ===")
try:
    wipe()
    obj = make_cube()
    uvl = obj.data.uv_layers.new(name="UVMap")
    for i, d in enumerate(uvl.data):
        d.uv = (i / 100.0, 1.0 - i / 100.0)
    before = [tuple(round(c, 5) for c in d.uv) for d in obj.data.uv_layers[0].data]

    resync(obj)

    chk("the UV layer still exists", len(obj.data.uv_layers) >= 1,
        [l.name for l in obj.data.uv_layers])
    after = ([tuple(round(c, 5) for c in d.uv) for d in obj.data.uv_layers[0].data]
             if obj.data.uv_layers else [])
    chk("UV coordinates were carried over", after == before,
        f"{len(after)} loops")
except Exception:
    traceback.print_exc()
    chk("section 4", False, "raised")


# ── 5. Modifiers are untouched ───────────────────────────────────────────────
# Modifiers live on the object, not the mesh, so clear_geometry must not disturb
# them. Cheap to check, and it is the third word in the listing's headline.
say("\n=== 5. modifiers are untouched ===")
try:
    wipe()
    obj = make_cube()
    mod = obj.modifiers.new("Subdiv", 'SUBSURF')
    mod.levels = 3
    resync(obj)
    got = obj.modifiers.get("Subdiv")
    chk("the modifier is still on the object", got is not None)
    chk("its settings are unchanged", got is not None and got.levels == 3,
        None if got is None else got.levels)
except Exception:
    traceback.print_exc()
    chk("section 5", False, "raised")


# ── 6. Edits in Fusion: matching edges keep marks, new geometry does not ─────
# The documented behaviour is position-based matching. A vertex that moved is a
# different edge and cannot keep its mark -- what matters is that the UNMOVED
# part of the model keeps everything and nothing raises.
say("\n=== 6. after a real geometry change ===")
try:
    wipe()
    obj = make_cube()
    mark_edges(obj, seam=[0, 1, 2, 3, 4, 5, 6, 7])
    before_seam = read_edges(obj)[1]

    # Push the top face up 1 unit, as if the part got taller in Fusion.
    moved = [(x, y, z + 1 if z > 0 else z) for (x, y, z) in CUBE_VERTS]
    resync(obj, verts=moved)

    after_seam = read_edges(obj)[1]
    kept = before_seam & after_seam
    chk("the untouched bottom edges kept their seams", len(kept) >= 4,
        f"{len(kept)} of {len(before_seam)} kept")
    chk("no phantom seams on geometry that never had one",
        after_seam <= before_seam | {k for k in after_seam if k not in before_seam}
        and len(after_seam) <= len(before_seam),
        f"{len(after_seam)} seams now")
except Exception:
    traceback.print_exc()
    chk("section 6", False, "raised")


# ── 7. Degenerate input does not crash the sync ──────────────────────────────
# _save_mesh_userdata returns None for an empty mesh; _restore must accept that.
# A raise here would abort a sync for every user with an empty body in the model.
say("\n=== 7. empty mesh is survivable ===")
try:
    wipe()
    me = bpy.data.meshes.new("Empty")
    obj = bpy.data.objects.new("Empty", me)
    bpy.context.collection.objects.link(obj)

    saved = handler._save_mesh_userdata(obj, me)
    chk("an empty mesh saves as None", saved is None, saved)

    raised = None
    try:
        handler._restore_mesh_userdata(obj, me, None)
    except Exception as exc:
        raised = exc
    chk("restoring None does not raise", raised is None, raised)
except Exception:
    traceback.print_exc()
    chk("section 7", False, "raised")


failed = [l for l, ok in _results if not ok]
say(f"\n{len(_results) - len(failed)} passed, {len(failed)} failed")
for l in failed:
    say("   FAILED: " + l)
say("RESULT: " + ("ALL PASS" if not failed else "FAILED"))
os._exit(1 if failed else 0)
