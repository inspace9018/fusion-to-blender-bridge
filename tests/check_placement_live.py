"""Are the parts where Fusion put them? Syncs three times and measures.

Run inside Blender, with Fusion open on a design and the add-in running:

    blender --python tests/check_placement_live.py

Not a unit test -- it needs a live Fusion on the other end of the socket, which
is exactly why it exists. Nothing headless could have found what it found: the
joint pass was parenting bodies against matrices the depsgraph had not caught up
with, so parts landed 8.75 mm out of place while every suite stayed green. Two
of the three affected parts silently corrected themselves on a later sync and
one never did, which is why it syncs more than once and compares.

The measurement has a real ground truth rather than a guess. Fusion bakes world
coordinates into the vertices it sends, so the only correct world matrix for a
body is the axis conversion; anything else is displacement, in millimetres.

Also prints what Fusion reported for each body's face appearances, because
"this body has no painted face" and "we never managed to look" arrive looking
identical, and the difference is the whole diagnosis when a colour goes missing.
"""
import json
import sys
import traceback

import bpy
import mathutils

# Tolerated slop. Anything above this is a real displacement -- the numbers seen
# in practice were whole millimetres, not rounding.
TOLERANCE_MM = 0.001
SYNCS = 3


def log(m):
    print(m, flush=True)


def _handler():
    """The bridge's handler module, whichever add-on is providing it."""
    for name in ("bridge_pro.core.handler", "fusion_to_blender_addon_blender.handler"):
        mod = sys.modules.get(name)
        if mod is not None:
            return mod
    raise SystemExit("neither add-on is loaded -- enable it and run again")


def bodies():
    return [o for o in bpy.data.objects if o.type == 'MESH' and "fusion_id" in o]


def placement(tag) -> float:
    axis = _handler()._global_axis_matrix()
    log(f"\n===== PLACEMENT {tag} =====")
    log(f"{'body':<16}{'gap (mm)':>10}  parent chain")
    worst = 0.0
    for obj in sorted(bodies(), key=lambda o: o.name):
        local = sum((mathutils.Vector(c) for c in obj.bound_box),
                    mathutils.Vector()) / 8.0
        gap = ((obj.matrix_world @ local) - (axis @ local)).length * 1000.0
        worst = max(worst, gap)
        chain, parent = [], obj.parent
        while parent is not None and len(chain) < 5:
            chain.append(parent.name)
            parent = parent.parent
        log(f"{obj.name:<16}{gap:>10.4f}  {' < '.join(chain) or '(none)'}"
            f"{'  <-- OFF' if gap > TOLERANCE_MM else ''}")
    log(f"worst gap: {worst:.4f} mm")
    return worst


def per_face(tag):
    log(f"\n===== FACE APPEARANCES {tag} =====")
    for obj in sorted(bodies(), key=lambda o: o.name):
        table = index = ()
        try:
            faces = json.loads(obj.get("ftb_appearance") or "{}").get("faces") or {}
            table, index = faces.get("table") or (), faces.get("index") or ()
        except Exception:
            pass
        inherited = sum(1 for v in index if v < 0)
        part = (obj.get("fusion_component", "") or "").split("/")[-1]
        log(f"{part[:24]:<25} painted={len(index) - inherited:<5} "
            f"inherited={inherited:<5} slots={len(obj.data.materials):<3} "
            f"used={len({p.material_index for p in obj.data.polygons}):<3} "
            f"{[e.get('name') for e in table if isinstance(e, dict)][:3]}")
    log("Fusion's own side of this is in the add-in's log: look for the "
        "[APPEARANCE] line naming each body and how many distinct face "
        "appearances it answered with.")


STATE = {"done": 0, "ticks": 0, "worst": 0.0}


def connect():
    try:
        bpy.ops.ftb.connect()
    except Exception:
        traceback.print_exc()
    return None


def request():
    scene = bpy.context.scene
    for flag in ("bpro_material_on_sync", "bpro_joints_on_sync", "bpro_mark_on_sync"):
        try:
            setattr(scene, flag, True)
        except Exception:
            pass                      # free add-on alone: those settings are Pro's
    try:
        bpy.ops.ftb.request_sync()
        log(f"\n>>> sync {STATE['done'] + 1} of {SYNCS}")
    except Exception:
        traceback.print_exc()
    return None


def watch():
    STATE["ticks"] += 1
    if getattr(bpy.context.scene, "ftb_is_syncing", False) and STATE["ticks"] < 150:
        return 1.0
    if STATE["ticks"] < 5:
        return 1.0

    STATE["done"] += 1
    tag = f"after sync {STATE['done']}"
    STATE["worst"] = max(STATE["worst"], placement(tag))
    per_face(tag)

    if STATE["done"] < SYNCS:
        STATE["ticks"] = 0
        bpy.app.timers.register(request, first_interval=1.0)
        return 1.0

    ok = STATE["worst"] <= TOLERANCE_MM
    log(f"\n{'PASS' if ok else 'FAIL'}: worst displacement over {SYNCS} syncs "
        f"was {STATE['worst']:.4f} mm")
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(connect, first_interval=1.5)
bpy.app.timers.register(request, first_interval=4.0)
bpy.app.timers.register(watch, first_interval=6.0)
