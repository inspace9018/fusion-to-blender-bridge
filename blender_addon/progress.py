"""
Fusion to Blender - Viewport GPU progress bar overlay
Draws progress directly at the bottom-left of the 3D viewport during sync.
Always visible without opening the N-panel.
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

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader

try:
    from .i18n import t as _t
except Exception:
    def _t(key, **kw): return key

_handle = None

_state = {
    "active":  False,
    "current": 0,
    "total":   1,
    "label":   "",
}

# Blender 3.x: 'UNIFORM_COLOR' / Blender 2.9x: '2D_UNIFORM_COLOR'
try:
    gpu.shader.from_builtin('UNIFORM_COLOR')
    _SHADER = 'UNIFORM_COLOR'
except Exception:
    _SHADER = '2D_UNIFORM_COLOR'


def set_progress(current: int, total: int, label: str = ""):
    _state["active"]  = total > 0
    _state["current"] = current
    _state["total"]   = max(1, total)
    _state["label"]   = label


def clear_progress():
    _state["active"] = False


def _draw_callback():
    if not _state["active"]:
        return

    region = bpy.context.region
    if region is None:
        return

    rw = region.width

    current = _state["current"]
    total   = _state["total"]
    pct     = min(1.0, current / total)
    label   = _state["label"] or _t(
        "syncing", current=current, total=total, pct=int(pct * 100)
    )

    # ── Layout ────────────────────────────────────────────────────────────────
    margin = 16
    bar_h  = 26
    bar_w  = min(440, rw - margin * 2)
    bar_x  = margin
    bar_y  = margin
    pad    = 3

    fill_w = max(0.0, (bar_w - pad * 2) * pct)

    # ── GPU drawing ────────────────────────────────────────────────────────────
    shader = gpu.shader.from_builtin(_SHADER)
    gpu.state.blend_set('ALPHA')

    def _rect(x, y, w, h, color):
        verts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        b = batch_for_shader(shader, 'TRI_FAN', {"pos": verts})
        shader.bind()
        shader.uniform_float("color", color)
        b.draw(shader)

    # Background (semi-transparent black)
    _rect(bar_x, bar_y, bar_w, bar_h, (0.07, 0.07, 0.07, 0.88))
    # Blue fill
    if fill_w > 0:
        _rect(bar_x + pad, bar_y + pad,
              fill_w, bar_h - pad * 2,
              (0.18, 0.54, 1.0, 0.95))
    # Border line (light gray)
    border_verts = [
        (bar_x,          bar_y),
        (bar_x + bar_w,  bar_y),
        (bar_x + bar_w,  bar_y + bar_h),
        (bar_x,          bar_y + bar_h),
        (bar_x,          bar_y),
    ]
    b_border = batch_for_shader(shader, 'LINE_STRIP', {"pos": border_verts})
    shader.bind()
    shader.uniform_float("color", (0.4, 0.4, 0.4, 0.7))
    b_border.draw(shader)

    gpu.state.blend_set('NONE')

    # ── Text ──────────────────────────────────────────────────────────────────
    fid = 0
    try:
        blf.enable(fid, blf.SHADOW)
        blf.shadow(fid, 3, 0.0, 0.0, 0.0, 1.0)
        blf.shadow_offset(fid, 1, -1)
    except Exception:
        pass

    try:
        blf.size(fid, 13)  # Blender 4.0+
    except TypeError:
        blf.size(fid, 13, 72)  # Blender 3.x (fontid, size, dpi)
    blf.color(fid, 1.0, 1.0, 1.0, 1.0)
    blf.position(fid, bar_x + 10, bar_y + 6, 0.0)
    blf.draw(fid, label)

    try:
        blf.disable(fid, blf.SHADOW)
    except Exception:
        pass


def register():
    global _handle
    if _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_callback, (), 'WINDOW', 'POST_PIXEL'
        )


def unregister():
    global _handle
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        _handle = None
    _state["active"] = False
