"""Extension points other add-ons can subscribe to.

Why this exists
---------------
Auto Bevel used to live inside this add-on and was called directly from the
sync path. It moved to Bridge Pro, but the work it did still has to happen at
exactly the same moment: right after a body's geometry has been rebuilt from
Fusion's buffers and before the next body arrives. Sync destroys and rebuilds
the mesh (clear_geometry), so anything that derives edge data has to run there
or it derives from a mesh that is about to be thrown away.

Without a published hook, an add-on wanting that moment has only bad options:
monkey-patch a private function, or poll on a timer and hope. Both break
silently whenever this file changes. So the moment is a hook instead.

Contract
--------
- A callback receives the Blender object whose geometry was just rebuilt.
- It runs inside the sync loop, once per body. Keep it cheap.
- A callback that raises is reported and then IGNORED FOR THE REST OF THE
  SYNC. One misbehaving add-on must not turn a 300-body sync into 300
  tracebacks, and must never abort the sync itself -- the user's model
  arriving intact matters more than any extension.
- Order is registration order. Do not depend on it.

Subscribers must unregister in their own unregister(), because this add-on can
be disabled and re-enabled independently of them.
"""

# Fusion to Blender Bridge
# Copyright (C) 2026 inspace
#
# This file is part of Fusion to Blender Bridge.
#
# Fusion to Blender Bridge is free software: you can redistribute it and/or modify it
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

import traceback

# Callables taking a single argument: the object whose geometry was rebuilt.
_post_body_sync = []

# Callables taking the list of objects the sync touched, run once at the end.
#
# Why a second hook: anything using bpy.ops -- unwrapping, for instance -- must
# not run inside the streaming loop. Ops need mode switches and a selection, and
# doing that per body while meshes are still arriving is both slow and a good way
# to corrupt the sync. The end of the sync is the first safe moment.
_post_sync = []

# Callbacks that raised during the current sync. Cleared at each sync start.
_muted = set()


def register_post_body_sync(fn):
    """Subscribe to "a body's geometry was just rebuilt during sync"."""
    if fn not in _post_body_sync:
        _post_body_sync.append(fn)
    return fn


def unregister_post_body_sync(fn):
    """Unsubscribe. Safe to call when not subscribed."""
    if fn in _post_body_sync:
        _post_body_sync.remove(fn)
    _muted.discard(fn)


def clear_mutes():
    """Give every callback a fresh chance. Called at the start of a sync."""
    _muted.clear()


def run_post_body_sync(obj):
    """Run subscribers for one rebuilt object. Never raises."""
    for fn in tuple(_post_body_sync):
        if fn in _muted:
            continue
        try:
            fn(obj)
        except Exception:
            _muted.add(fn)
            print(f"[FusionBridge] post-body-sync hook {getattr(fn, '__qualname__', fn)!r} "
                  f"raised; muted for the rest of this sync")
            traceback.print_exc()


def register_post_sync(fn):
    """Subscribe to "the sync finished". Receives the list of synced objects."""
    if fn not in _post_sync:
        _post_sync.append(fn)
    return fn


def unregister_post_sync(fn):
    if fn in _post_sync:
        _post_sync.remove(fn)


def run_post_sync(objects):
    """Run end-of-sync subscribers. Never raises.

    Not muted like the per-body hook: this runs once, so a failure cannot
    snowball, and swallowing it silently would hide the whole feature failing.
    """
    for fn in tuple(_post_sync):
        try:
            fn(list(objects))
        except Exception:
            print(f"[FusionBridge] post-sync hook {getattr(fn, '__qualname__', fn)!r} raised")
            traceback.print_exc()
