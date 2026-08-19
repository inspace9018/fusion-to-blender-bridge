"""Applying a Fusion appearance without ever overwriting the user's own work.

    "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" \
        --background --factory-startup --python tests/test_appearance_blender.py

The bridge's whole promise is that the look you build in Blender survives the
next CAD revision. Importing appearances is worth having only if it cannot break
that, so most of what is checked here is what the feature must NOT do.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bpy  # noqa: E402

from blender_addon import handler  # noqa: E402

_results = []


def say(msg):
    print(msg, flush=True)


def chk(label, cond, extra=""):
    _results.append((label, bool(cond)))
    say(f"[{'PASS' if cond else 'FAIL'}] {label}{('  ' + str(extra)) if extra else ''}")


def wipe():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


def cube(name="Body"):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def base_color(mat):
    node = handler._principled(mat)
    return list(node.inputs["Base Color"].default_value) if node else None


RED = {"name": "Paint - Red", "color": [1.0, 0.0, 0.0, 1.0], "roughness": 0.3}
BLUE = {"name": "Paint - Blue", "color": [0.0, 0.0, 1.0, 1.0]}


# ── 1. A body with no material gets the Fusion one ───────────────────────────
say("\n=== 1. an unpainted body takes the Fusion appearance ===")
try:
    wipe()
    obj = cube()
    handler._apply_appearance(obj, RED)
    chk("a material was assigned", len(obj.data.materials) == 1)
    mat = obj.data.materials[0]
    chk("it is named after the Fusion appearance", mat.name == "Paint - Red", mat.name)
    chk("the colour came across", base_color(mat)[:3] == [1.0, 0.0, 0.0], base_color(mat))
    node = handler._principled(mat)
    chk("so did the roughness", abs(node.inputs["Roughness"].default_value - 0.3) < 1e-6)
    chk("metallic was left alone, not defaulted to 0",
        "metallic" not in RED)
except Exception:
    traceback.print_exc()
    chk("section 1", False, "raised")


# ── 2. The user's own material is never touched ──────────────────────────────
# This is the one that matters. Everything else here could regress and the
# product would still be honest; this one cannot.
say("\n=== 2. a material the user made is left completely alone ===")
try:
    wipe()
    obj = cube()
    mine = bpy.data.materials.new("My Careful Shader")
    mine.use_nodes = True
    handler._principled(mine).inputs["Base Color"].default_value = (0.1, 0.9, 0.2, 1.0)
    obj.data.materials.append(mine)

    handler._apply_appearance(obj, RED)
    chk("still exactly one slot", len(obj.data.materials) == 1)
    chk("still the user's material", obj.data.materials[0] is mine, obj.data.materials[0].name)
    chk("its colour is untouched",
        [round(c, 3) for c in base_color(mine)[:3]] == [0.1, 0.9, 0.2], base_color(mine))
    chk("no Fusion material was created behind their back",
        bpy.data.materials.get("Paint - Red") is None)
except Exception:
    traceback.print_exc()
    chk("section 2", False, "raised")


# ── 3. Recolouring in Fusion reaches a body we painted ───────────────────────
say("\n=== 3. a recolour in Fusion lands on a body we own ===")
try:
    wipe()
    obj = cube()
    handler._apply_appearance(obj, RED)
    handler._apply_appearance(obj, BLUE)
    chk("still one slot", len(obj.data.materials) == 1)
    chk("now the new appearance", obj.data.materials[0].name == "Paint - Blue",
        obj.data.materials[0].name)
    chk("with the new colour",
        base_color(obj.data.materials[0])[:3] == [0.0, 0.0, 1.0])
except Exception:
    traceback.print_exc()
    chk("section 3", False, "raised")


# ── 4. Bodies sharing an appearance share one material ───────────────────────
# They share one in Fusion. If Blender made sixteen copies, recolouring the
# design would mean editing sixteen materials by hand.
say("\n=== 4. one material per appearance, not per body ===")
try:
    wipe()
    a, b, c = cube("A"), cube("B"), cube("C")
    for o in (a, b, c):
        handler._apply_appearance(o, RED)
    chk("all three share one material",
        a.data.materials[0] is b.data.materials[0] is c.data.materials[0])
    chk("only one material exists", len(bpy.data.materials) == 1, len(bpy.data.materials))
except Exception:
    traceback.print_exc()
    chk("section 4", False, "raised")


# ── 5. A name collision with the user's material ─────────────────────────────
say("\n=== 5. the user already has a material of that name ===")
try:
    wipe()
    theirs = bpy.data.materials.new("Paint - Red")
    theirs.use_nodes = True
    handler._principled(theirs).inputs["Base Color"].default_value = (0.0, 1.0, 0.0, 1.0)
    obj = cube()

    handler._apply_appearance(obj, RED)
    chk("theirs was not overwritten",
        [round(v, 3) for v in base_color(theirs)[:3]] == [0.0, 1.0, 0.0], base_color(theirs))
    chk("ours took a neighbouring name",
        obj.data.materials[0] is not theirs, obj.data.materials[0].name)
except Exception:
    traceback.print_exc()
    chk("section 5", False, "raised")


# ── 6. Nothing to apply ──────────────────────────────────────────────────────
say("\n=== 6. a body with no appearance data ===")
try:
    wipe()
    obj = cube()
    handler._apply_appearance(obj, None)
    handler._apply_appearance(obj, {})
    chk("no material, no exception", len(obj.data.materials) == 0)
except Exception:
    traceback.print_exc()
    chk("section 6", False, "raised")


failed = [l for l, ok in _results if not ok]
say(f"\n{len(_results) - len(failed)} passed, {len(failed)} failed")
for l in failed:
    say("   FAILED: " + l)
say("RESULT: " + ("ALL PASS" if not failed else "FAILED"))
os._exit(1 if failed else 0)
