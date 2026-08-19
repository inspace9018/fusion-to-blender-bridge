"""Opening a .blend must not sever the link to Fusion.

    "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" \
        --background --factory-startup --python tests/test_file_load_blender.py

The bug this pins down was reported as "Sync freezes at Fusion Computing".
Blender registers a timer to drain what the socket thread receives, and loading
a .blend removes every registered timer without telling anyone. The socket kept
running, the panel still said Connected, and Fusion's own log showed it exporting
all 16 bodies -- but nothing on the Blender side was reading the answers, so the
request timed out after 90 seconds. Disconnecting and reconnecting cured it,
which is why it looked random.
"""
import os
import sys
import threading
import time
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bpy  # noqa: E402

import blender_addon  # noqa: E402
from blender_addon import state  # noqa: E402

# bpy.app.timers compares by identity, so every check here must use the client's
# ONE held reference. Reading client._process_queue afresh builds a new bound
# method and is_registered would answer False even when the timer is running --
# a test that fails against correct code.

_results = []


def say(msg):
    print(msg, flush=True)


def chk(label, cond, extra=""):
    _results.append((label, bool(cond)))
    say(f"[{'PASS' if cond else 'FAIL'}] {label}{('  ' + str(extra)) if extra else ''}")


blender_addon.register()
client = state.get_client()

_stop = threading.Event()


def _idle():
    _stop.wait(60)


# ── 0. The premise: Blender really does drop timers on file load ─────────────
# Asserted rather than assumed, because the whole fix rests on it and a future
# Blender could change it.
say("\n=== 0. loading a file removes timers ===")
try:
    canary = lambda: 0.1          # noqa: E731
    bpy.app.timers.register(canary, first_interval=0.1)
    was = bpy.app.timers.is_registered(canary)
    bpy.ops.wm.read_homefile(use_empty=True)
    chk("a plain timer is registered before the load", was)
    chk("and gone after it", not bpy.app.timers.is_registered(canary))
except Exception:
    traceback.print_exc()
    chk("section 0", False, "raised")


# ── 1. The drain comes back ──────────────────────────────────────────────────
say("\n=== 1. the queue drain survives a file load ===")
try:
    worker = threading.Thread(target=_idle, daemon=True)
    worker.start()
    client._thread = worker            # stand in for a live socket thread
    client._timer_registered = False
    client._register_timer()
    chk("the drain is running before the load",
        bpy.app.timers.is_registered(client._queue_timer))

    bpy.ops.wm.read_homefile(use_empty=True)
    chk("the drain is back after the load",
        bpy.app.timers.is_registered(client._queue_timer))
except Exception:
    traceback.print_exc()
    chk("section 1", False, "raised")


# ── 2. It comes back every time, not just once ───────────────────────────────
say("\n=== 2. and again on the next file ===")
try:
    for i in range(3):
        bpy.ops.wm.read_homefile(use_empty=True)
    chk("still draining after three loads",
        bpy.app.timers.is_registered(client._queue_timer))
except Exception:
    traceback.print_exc()
    chk("section 2", False, "raised")


# ── 3. A dead socket does not get a zombie timer ─────────────────────────────
# Without this the add-on would leave a timer running forever after the user
# disconnects and then opens a file.
say("\n=== 3. no drain when there is no connection ===")
try:
    _stop.set()
    worker.join(timeout=5)
    client._timer_registered = False
    try:
        bpy.app.timers.unregister(client._queue_timer)
    except Exception:
        pass
    bpy.ops.wm.read_homefile(use_empty=True)
    chk("nothing is re-registered for a dead socket thread",
        not bpy.app.timers.is_registered(client._queue_timer))
except Exception:
    traceback.print_exc()
    chk("section 3", False, "raised")


failed = [l for l, ok in _results if not ok]
say(f"\n{len(_results) - len(failed)} passed, {len(failed)} failed")
for l in failed:
    say("   FAILED: " + l)
say("RESULT: " + ("ALL PASS" if not failed else "FAILED"))
os._exit(1 if failed else 0)
