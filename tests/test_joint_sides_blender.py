"""Which side of a joint the Empty is allowed to move.

    "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" \
        --background --factory-startup --python tests/test_joint_sides_blender.py

The case this exists for came from a real assembly. A revolute joint between a
body inside Component2 and its parent Component1 was reported as:

    occ_one='Component1:1/Component2:1'  occ_two='Component1:1'

and the code moved occ_two -- so turning the hinge moved all 9 bodies of
Component1 instead of the single body it is attached to. Nothing raised; the
Empty was built, the parenting "succeeded", and only looking at the outliner
showed it.

Fixtures are built by hand rather than synced, because what is under test is the
choice of side, and a real sync would need Fusion running.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bpy  # noqa: E402

from blender_addon.handler import SceneHandler  # noqa: E402

_results = []


def say(msg):
    print(msg, flush=True)


def chk(label, cond, extra=""):
    _results.append((label, bool(cond)))
    say(f"[{'PASS' if cond else 'FAIL'}] {label}{('  ' + str(extra)) if extra else ''}")


def wipe():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def body(name, instance):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    obj["fusion_id"] = name
    obj["fusion_instance"] = instance
    obj["fusion_component"] = instance
    bpy.context.scene.collection.objects.link(obj)
    return obj


def joint_empty(jid):
    e = bpy.data.objects.new("J_" + jid, None)
    e["ftb_joint_id"] = jid
    bpy.context.scene.collection.objects.link(e)
    return e


def run(jdata):
    """Build the empty, link, and return the objects parented under it."""
    e = joint_empty(jdata["joint_id"])
    SceneHandler()._link_joints_to_bodies([jdata], {jdata["joint_id"]: e})
    return sorted(o.name for o in bpy.data.objects if o.parent is e)


# ── 1. The real assembly: a child pivots against its parent ──────────────────
say("\n=== 1. a body inside Component2, hinged to Component1 ===")
try:
    wipe()
    for i in range(8):
        body(f"C1_Body{i}", "Component1:1")
    body("C2_Body1", "Component1:1/Component2:1")
    moved = run({"joint_id": "rev18", "name": "Revolute 18",
                 "occ_one": "Component1:1/Component2:1",
                 "occ_two": "Component1:1"})
    chk("only the Component2 body moves", moved == ["C2_Body1"], moved)
    chk("Component1's own 8 bodies stay put", len(moved) == 1, f"{len(moved)} moved")
except Exception:
    traceback.print_exc()
    chk("section 1", False, "raised")


# ── 2. The same joint with the sides reported the other way round ────────────
# Whichever label Fusion puts on them, a side that CONTAINS the other cannot be
# the one that moves -- it would carry its own reference along with it.
say("\n=== 2. sides swapped: the container must not be the mover ===")
try:
    wipe()
    for i in range(8):
        body(f"C1_Body{i}", "Component1:1")
    body("C2_Body1", "Component1:1/Component2:1")
    moved = run({"joint_id": "rev18b", "name": "Revolute 18 flipped",
                 "occ_one": "Component1:1",
                 "occ_two": "Component1:1/Component2:1"})
    chk("still only the contained body moves", moved == ["C2_Body1"], moved)
except Exception:
    traceback.print_exc()
    chk("section 2", False, "raised")


# ── 3. Two siblings: no containment, so Fusion's order decides ───────────────
say("\n=== 3. two sibling components ===")
try:
    wipe()
    body("Arm_Body", "Arm:1")
    body("Base_Body", "Base:1")
    moved = run({"joint_id": "rev2", "name": "Arm hinge",
                 "occ_one": "Arm:1", "occ_two": "Base:1"})
    chk("the first-named side is the one that moves", moved == ["Arm_Body"], moved)
except Exception:
    traceback.print_exc()
    chk("section 3", False, "raised")


# ── 4. Nested instances of the mover come along ──────────────────────────────
# A hinge on an arm has to carry whatever is mounted further down the arm.
say("\n=== 4. everything below the mover moves with it ===")
try:
    wipe()
    body("Arm_Body", "Arm:1")
    body("Hand_Body", "Arm:1/Hand:1")
    body("Base_Body", "Base:1")
    moved = run({"joint_id": "rev3", "name": "Shoulder",
                 "occ_one": "Arm:1", "occ_two": "Base:1"})
    chk("the arm and the hand move together",
        moved == ["Arm_Body", "Hand_Body"], moved)
    chk("the base does not", "Base_Body" not in moved, moved)
except Exception:
    traceback.print_exc()
    chk("section 4", False, "raised")


failed = [l for l, ok in _results if not ok]
say(f"\n{len(_results) - len(failed)} passed, {len(failed)} failed")
for l in failed:
    say("   FAILED: " + l)
say("RESULT: " + ("ALL PASS" if not failed else "FAILED"))
os._exit(1 if failed else 0)
