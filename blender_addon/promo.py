"""
Paid-companion teaser panel (GitHub build only).

Left out of the extensions.blender.org package by build_extension.py: that
platform does not allow a Blender UI element to promote a commercial version
(ToS 6.1 / 6.3). ui.py registers the panel only if this module is present.
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

import bpy
from . import i18n
from .i18n import t

i18n._STRINGS.update({
    # ── ID Studio teaser (paid companion add-on) ─────────────────────────────
    "ids_teaser_audience":  {"ko": "제품 디자이너를 위한 렌더 스튜디오",
                             "en": "A render studio for product designers"},
    "ids_feat_cameras":     {"ko": "제품 카메라 세트 · 샷 프레이밍",
                             "en": "Product camera sets & shot framing"},
    "ids_feat_lights":      {"ko": "스튜디오 조명 + 섀도 캐처·백드롭",
                             "en": "Studio lights + shadow catcher & backdrop"},
    "ids_feat_cmf":         {"ko": "CMF 베리에이션 (컬러·소재·마감)",
                             "en": "CMF variants (colour · material · finish)"},
    "ids_feat_matrix":      {"ko": "Matrix 배치 렌더 — 컬렉션×카메라×CMF",
                             "en": "Matrix batch render — collection × camera × CMF"},
    "ids_get_button":       {"ko": "ID Studio 보러 가기  →",
                             "en": "Get ID Studio  →"},
    "ids_tagline":          {"ko": "싱크한 모델을 완성된 제품샷으로.",
                             "en": "From synced model to finished product shots."},
})

# ─── ID Studio upsell teaser (auto-hides once the paid add-on is installed) ───
# Hidden until ID Studio is actually for sale: flip PRO_TEASER_ENABLED to True
# at launch (and set PRO_BUY_URL to the real store page) to show it.
PRO_TEASER_ENABLED = False
PRO_BUY_URL = ""  # TODO: set to the real ID Studio store page before enabling the teaser


def _pro_installed() -> bool:
    """True if ID Studio for Blender is installed, so we don't nag buyers."""
    if hasattr(bpy.types, "FTB_PT_IDStudioTools"):
        return True
    try:
        for name in bpy.context.preferences.addons.keys():
            if "id_studio_for_blender" in name:
                return True
    except Exception:
        pass
    return False


class FTB_PT_ProPanel(bpy.types.Panel):
    bl_idname   = "FTB_PT_pro_panel"
    bl_label    = "ID Studio for Blender"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "Fusion 360"
    bl_options     = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return PRO_TEASER_ENABLED and not _pro_installed()

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text=t("ids_teaser_audience"), icon="FUND")
        col = box.column(align=True)
        col.label(text=t("ids_feat_cameras"), icon="OUTLINER_OB_CAMERA")
        col.label(text=t("ids_feat_lights"), icon="LIGHT_AREA")
        col.label(text=t("ids_feat_cmf"), icon="MATERIAL")
        col.label(text=t("ids_feat_matrix"), icon="RENDER_ANIMATION")
        row = layout.row()
        row.scale_y = 1.3
        row.operator("wm.url_open", text=t("ids_get_button"),
                     icon="FUND").url = PRO_BUY_URL
        layout.label(text=t("ids_tagline"))


PROMO_PANEL_CLASSES = [FTB_PT_ProPanel]
