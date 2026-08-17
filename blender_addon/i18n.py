"""
Fusion to Blender - Internationalization (i18n)
Auto-detects Blender's system language and returns the appropriate string.
Supported: English (default), Korean (ko_KR).
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

_STRINGS = {
    # ── Connection ────────────────────────────────────────────────────────────
    "connected":            {"ko": "● 연결됨",           "en": "● Connected"},
    "not_connected":        {"ko": "○ 연결 안 됨",       "en": "○ Not Connected"},
    "server":               {"ko": "서버",               "en": "Server"},
    "disconnect":           {"ko": "연결 해제",          "en": "Disconnect"},
    "cancel":               {"ko": "취소",               "en": "Cancel"},
    "connecting":           {"ko": "↻  연결 시도 중...", "en": "↻  Connecting..."},
    # ── First-use hint (EU04) ─────────────────────────────────────────────────
    "hint_step1":           {"ko": "1) Fusion 360에서 애드인 Run",
                             "en": "1) Run the add-in in Fusion 360"},
    "hint_step2":           {"ko": "2) 아래 Sync 누르기 (연결은 자동)",
                             "en": "2) Press Sync below (connects automatically)"},
    # ── Connection failure hints (EU05) ───────────────────────────────────────
    "err_refused":          {"ko": "Fusion 애드인이 실행 중인지 확인하세요 (Run)",
                             "en": "Check the Fusion add-in is running (Run)"},
    "err_timeout":          {"ko": "Fusion 애드인이 응답하지 않습니다 — Fusion에서 Run 상태인지, 포트 9080이 막혀 있지 않은지 확인하세요",
                             "en": "The Fusion add-in isn't answering — check it is Run in Fusion and that port 9080 isn't blocked"},
    "err_unreachable":      {"ko": "이 컴퓨터의 Fusion에 연결할 수 없습니다 — 애드인을 Run 하셨나요?",
                             "en": "Can't reach Fusion on this machine — did you Run the add-in?"},
    "err_invalid":          {"ko": "연결 주소가 잘못되었습니다 — Blender를 다시 시작해 주세요",
                             "en": "The connection address is wrong — restart Blender"},
    "reconnect_countdown":  {"ko": "↻  {cd:.0f}초 후 재연결...",
                             "en": "↻  Reconnect in {cd:.0f}s..."},

    # ── Mesh Quality ──────────────────────────────────────────────────────────
    "mesh_quality":         {"ko": "메시 품질",          "en": "Mesh Quality"},
    "surface_tol":          {"ko": "곡면 오차",          "en": "Surface Tol."},
    "normal_angle":         {"ko": "법선 각도",          "en": "Normal Angle"},
    "surface_tol_mm":       {"ko": "곡면 오차 (mm):",    "en": "Surface Tol. (mm):"},
    "normal_angle_deg":     {"ko": "법선 각도 (°):",     "en": "Normal Angle (°):"},

    # ── Coordinate System ─────────────────────────────────────────────────────
    "coord_system":         {"ko": "좌표계",             "en": "Coordinate System"},
    "coord_hint":           {"ko": "  객체들이 눕거나 거꾸로면 토글",
                             "en": "  Toggle if objects appear sideways or upside down"},

    # ── Import Options ────────────────────────────────────────────────────────
    "import_options":       {"ko": "임포트 옵션",        "en": "Import Options"},
    "hide_hidden":          {"ko": "숨김 Body 숨기기 (현재: 표시)",
                             "en": "Hide Hidden Bodies (Current: Shown)"},
    "show_hidden":          {"ko": "숨김 Body 표시하기 (현재: 숨김)",
                             "en": "Show Hidden Bodies (Current: Hidden)"},
    "root_empty":           {"ko": "최상위 Empty parent", "en": "Top-level Empty Parent"},
    "update_transforms":    {"ko": "Transform 갱신",     "en": "Update Transforms"},
    "auto_update_col":      {"ko": "Collection 자동 갱신", "en": "Auto Update Collections"},

    # ── Sync ──────────────────────────────────────────────────────────────────
    "sync":                 {"ko": "동기화",             "en": "Sync"},
    "idle":                 {"ko": "대기 중",            "en": "Idle"},
    "complete":             {"ko": "완료",               "en": "Complete"},

    # ── Object Management ─────────────────────────────────────────────────────
    "object_mgmt":          {"ko": "오브젝트 관리",      "en": "Object Management"},
    "update_transforms_l":  {"ko": "Transform 업데이트", "en": "Update Transforms"},
    "auto_update_col_l":    {"ko": "컬렉션 자동 업데이트", "en": "Auto Update Collections"},
    "preserving_col":       {"ko": "  컬렉션/Parent 변경 보존 중",
                             "en": "  Preserving Collection/Parent changes"},
    "fusion_obj_count":     {"ko": "씬 내 Fusion 오브젝트: {count}개",
                             "en": "Fusion objects in scene: {count}"},
    "select_fusion":        {"ko": "Fusion 오브젝트 선택", "en": "Select Fusion Objects"},
    "delete_all":           {"ko": "전체 삭제",          "en": "Delete All"},

    # ── Rotation ──────────────────────────────────────────────────────────────
    "rotation_correction":  {"ko": "선택 회전 보정 ({n}개)",
                             "en": "Rotation Correction ({n})"},
    "rotation_hint":        {"ko": "  90° 단위 회전, 재싱크에도 유지됨",
                             "en": "  90° step rotation, persists through re-sync"},
    "reset_rotation":       {"ko": "회전 초기화",        "en": "Reset Rotation"},
    "current_rot":          {"ko": "  현재: X={rx:g}°  Y={ry:g}°  Z={rz:g}°",
                             "en": "  Current: X={rx:g}°  Y={ry:g}°  Z={rz:g}°"},

    # ── Sync options ────────────────────────────────────────────────────────────
    "auto_mark_sync":       {"ko": "동기화 시 자동 Mark", "en": "Auto Mark on Sync"},
    "bridge_not_ready":     {"ko": "브리지가 아직 준비되지 않았습니다",
                             "en": "the bridge is not ready yet"},

    # ── Mesh Utilities ────────────────────────────────────────────────────────
    "mesh_utilities":       {"ko": "메시 유틸리티",      "en": "Mesh Utilities"},
    "edge_marking":         {"ko": "Edge 마킹",         "en": "Edge Marking"},
    "smart_normal":         {"ko": "Smart (노말 기반)",  "en": "Smart (Normal-based)"},
    "face_selection":       {"ko": "Face 선택",          "en": "Face Selection"},
    "select_fusion_face":   {"ko": "Fusion Face 선택",   "en": "Select Fusion Face"},
    "select_face_edge":     {"ko": "Fusion Face 경계 Edge 선택",
                             "en": "Select Fusion Face Boundary Edges"},
    "other":                {"ko": "기타",               "en": "Other"},

    # ── Status Messages ───────────────────────────────────────────────────────
    "syncing":              {"ko": "동기화 중...  {current} / {total}   ({pct} %)",
                             "en": "Syncing...  {current} / {total}   ({pct} %)"},
    "sync_starting":        {"ko": "동기화 시작... {cur}/{total}",
                             "en": "Sync starting... {cur}/{total}"},
    "sync_progress":        {"ko": "동기화 중... {cur}/{total}",
                             "en": "Syncing... {cur}/{total}"},
    "sync_done":            {"ko": "완료: {count}개  ({ts})",
                             "en": "Done: {count}  ({ts})"},
    "sync_done_with_errors": {"ko": "완료 (오류 {errors}건): {count}개  ({ts})",
                              "en": "Done (errors: {errors}): {count}  ({ts})"},
    "fusion_computing":     {"ko": "Fusion 계산 중...",  "en": "Fusion computing..."},
    "sync_no_answer":       {"ko": "Fusion이 응답하지 않습니다 — 애드인 실행과 디자인 열림을 확인하세요",
                             "en": "No answer from Fusion -- check the add-in is running and a design is open"},
    "sync_refused":         {"ko": "Fusion이 동기화를 못 했습니다: {reason}",
                             "en": "Fusion could not sync: {reason}"},
    "fusion_mesh_wait":     {"ko": "Fusion 메시 계산 중...  잠시 기다려 주세요",
                             "en": "Fusion mesh calculation in progress...  please wait"},
    "reconnect_delay":      {"ko": "{delay:.0f}초 후 재연결 시도...",
                             "en": "Reconnecting in {delay:.0f}s..."},
    "sync_interrupted":     {"ko": "⚠ 싱크 중단됨 ({cur}/{total})  — Sync 버튼으로 재시도",
                             "en": "⚠ Sync interrupted ({cur}/{total})  — press Sync to retry"},
    "sync_error_body":      {"ko": "⚠ 오류 {errors}건 발생  — 콘솔 확인",
                             "en": "⚠ {errors} error(s) during sync  — check console"},

    # ── Operator Reports ──────────────────────────────────────────────────────
    "connecting_to":        {"ko": "Fusion 360 서버 {server}에 연결 중...",
                             "en": "Connecting to Fusion 360 server {server}..."},
    "disconnected":         {"ko": "연결이 해제되었습니다", "en": "Disconnected"},
    "sync_requested":       {"ko": "동기화 요청 (preset={preset}, hidden_mode={mode})",
                             "en": "Sync requested (preset={preset}, hidden_mode={mode})"},
    "connecting_then_sync": {"ko": "{server}에 연결 후 자동으로 동기화합니다...",
                             "en": "Connecting to {server}, then syncing automatically..."},
    "sync_after_connect":   {"ko": "연결되는 대로 동기화합니다...",
                             "en": "Will sync as soon as connected..."},
    "all_deleted":          {"ko": "Fusion 360 오브젝트가 모두 삭제되었습니다",
                             "en": "All Fusion 360 objects have been deleted"},
    "obj_selected":         {"ko": "{count}개의 Fusion 오브젝트가 선택되었습니다",
                             "en": "{count} Fusion object(s) selected"},
    "hidden_shown":         {"ko": "숨김 Body 표시 ON",  "en": "Hidden Bodies: Shown"},
    "hidden_hidden":        {"ko": "숨김 Body 숨김 (OFF)", "en": "Hidden Bodies: Hidden"},
    "rotated":              {"ko": "{n}개 객체 {axis}축 +90° 회전",
                             "en": "{n} object(s) rotated +90° on {axis} axis"},
    "rotation_reset":       {"ko": "{n}개 객체 회전 초기화",
                             "en": "{n} object(s) rotation reset"},
    "no_face_groups":       {"ko": "Face group 정보 없음", "en": "No face group data"},
    "no_faces_selected":    {"ko": "선택된 face 없음",   "en": "No faces selected"},
    "faces_selected":       {"ko": "{n}개 BRep Face 선택됨",
                             "en": "{n} BRep Face(s) selected"},
    "edges_selected":       {"ko": "{n}개 경계 edge 선택됨",
                             "en": "{n} boundary edge(s) selected"},
    "edges_marked":         {"ko": "{n}개 edge 마킹됨",  "en": "{n} edge(s) marked"},
    "face_groups_colored":  {"ko": "{n}개 face group 색상 적용",
                             "en": "{n} face group(s) colored"},
    "no_face_groups_obj":   {"ko": "{name}: face group 없음",
                             "en": "{name}: No face groups"},

    # ── Joint / Motion Link ──────────────────────────────────────────────────
    "joints_processed":     {"ko": "{count}개 조인트 처리됨",
                             "en": "{count} joint(s) processed"},
    "joint_collection":     {"ko": "Fusion 360 조인트",     "en": "Fusion 360 Joints"},

    # ── Operator Labels & Descriptions ────────────────────────────────────────
    "op_connect_desc":      {"ko": "Fusion 360 브리지 서버에 연결합니다",
                             "en": "Connect to Fusion 360 bridge server"},
    "op_disconnect_desc":   {"ko": "연결 및 자동 재연결을 중단합니다",
                             "en": "Stop connection and auto-reconnect"},
    "op_sync_desc":         {"ko": "현재 품질 설정으로 Fusion 360에 전체 동기화를 요청합니다",
                             "en": "Request full sync from Fusion 360 with current quality settings"},
    "op_clear_label":       {"ko": "Fusion 오브젝트 전체 삭제",
                             "en": "Delete All Fusion Objects"},
    "op_clear_desc":        {"ko": "Blender 씬에서 Fusion 360 오브젝트를 모두 삭제합니다",
                             "en": "Delete all Fusion 360 objects from the Blender scene"},
    "op_select_label":      {"ko": "Fusion 오브젝트 선택",
                             "en": "Select Fusion Objects"},
    "op_select_desc":       {"ko": "Fusion 360에서 임포트된 모든 오브젝트를 선택합니다",
                             "en": "Select all objects imported from Fusion 360"},
    "op_toggle_desc":       {"ko": "Fusion 360 에서 숨긴 occurrence/body 의 Blender 표시 토글",
                             "en": "Toggle visibility of Fusion 360 hidden occurrences/bodies in Blender"},

    # ── STEP Import ──────────────────────────────────────────────────────────
    "import_step":          {"ko": "STEP 파일 임포트",     "en": "Import STEP File"},
    "step_imported":        {"ko": "{file}: {total}개 Body 임포트 완료 (신규 {created}, 업데이트 {updated})",
                             "en": "{file}: {total} bodies imported ({created} new, {updated} updated)"},
    "step_import_started":  {"ko": "{file}: {total}개 Body 임포트 시작...",
                             "en": "{file}: importing {total} bodies..."},
    "step_import_done":     {"ko": "STEP 완료: {count}개 Body ({ts})",
                             "en": "STEP done: {count} bodies ({ts})"},
    "step_existing_title":  {"ko": "기존 오브젝트 발견",
                             "en": "Existing Objects Found"},
    "step_existing_step":   {"ko": "STEP 임포트 오브젝트: {count}개",
                             "en": "STEP imported objects: {count}"},
    "step_existing_bridge": {"ko": "Fusion Bridge 오브젝트: {count}개",
                             "en": "Fusion Bridge objects: {count}"},
    "step_update_confirm":  {"ko": "기존 오브젝트를 업데이트합니다. OK를 누르세요.",
                             "en": "Existing objects will be updated. Press OK."},
    "step_occ_missing":     {"ko": "OpenCascade (OCP) 미설치. Blender Python에서 설치:\n"
                                   "  <blender>/python/bin/python -m pip install cadquery-ocp",
                             "en": "OpenCascade (OCP) not found. Install in Blender Python:\n"
                                   "  <blender>/python/bin/python -m pip install cadquery-ocp"},
    "step_occ_missing_short": {"ko": "OCP 미설치 — cadquery-ocp 필요",
                               "en": "OCP not installed — cadquery-ocp required"},
    # ── STEP support installer button (F033) ──────────────────────────────────
    "ocp_hint1":            {"ko": ".step 파일을 직접 열려면 STEP 지원이 필요합니다",
                             "en": "Opening .step files directly needs STEP support"},
    "ocp_hint2":            {"ko": "(핵심 동기화에는 불필요)",
                             "en": "(not needed for the core sync)"},
    "ocp_install_btn":      {"ko": "STEP 지원 설치",        "en": "Install STEP Support"},
    "ocp_confirm1":         {"ko": "OpenCascade(약 수백 MB)를 내려받아 설치합니다.",
                             "en": "Downloads & installs OpenCascade (~hundreds of MB)."},
    "ocp_confirm2":         {"ko": "인터넷이 필요하며 몇 분 걸릴 수 있습니다.",
                             "en": "Needs internet; may take a few minutes."},
    "ocp_confirm3":         {"ko": "백그라운드로 진행되며, 끝나면 Blender를 재시작하세요.",
                             "en": "Runs in the background; restart Blender when done."},
    "ocp_installing":       {"ko": "STEP 지원 설치 중... (몇 분 소요)",
                             "en": "Installing STEP support... (a few minutes)"},
    "ocp_running_note":     {"ko": "백그라운드 진행 중 — 작업 계속 가능",
                             "en": "Running in background — you can keep working"},
    "ocp_done_restart":     {"ko": "STEP 지원 설치 완료 — Blender 재시작",
                             "en": "STEP support installed — restart Blender"},
    "ocp_failed":           {"ko": "STEP 지원 설치 실패",   "en": "STEP support install failed"},
    "ocp_retry":            {"ko": "다시 시도",             "en": "Retry"},

    # ── Shot List ────────────────────────────────────────────────────────────
    "shot_created":         {"ko": "Shot '{name}' 생성됨", "en": "Shot '{name}' created"},
    "shot_removed":         {"ko": "Shot 삭제됨",       "en": "Shot removed"},
    "camera":               {"ko": "카메라",             "en": "Camera"},
    "lights":               {"ko": "조명",              "en": "Lights"},
    "shot_hint":            {"ko": "+로 Shot을 추가하세요. 카메라가 자동 생성됩니다.",
                             "en": "Press + to add a shot. A camera is created automatically."},
    "shot_no_camera":       {"ko": "카메라 없음",        "en": "No camera"},
    "visibility":           {"ko": "가시성",             "en": "Visibility"},
    "save_visibility":      {"ko": "현재 저장",         "en": "Save Current"},
    "restore_visibility":   {"ko": "저장 복원",         "en": "Restore Saved"},
    "visibility_saved":     {"ko": "{count}개 컬렉션 가시성 저장됨",
                             "en": "{count} collection(s) visibility saved"},
    "visibility_hint":      {"ko": "  Outliner에서 가시성 조절 후 Save",
                             "en": "  Adjust visibility in Outliner, then Save"},
    "color_variations":     {"ko": "컬러 배리에이션",   "en": "Color Variations"},
    "enable_color_overrides": {"ko": "컬러 오버라이드 활성화",
                               "en": "Enable Color Overrides"},
    "add_color_override":   {"ko": "선택에서 오버라이드 추가",
                             "en": "Add Override from Selection"},
    "apply_colors":         {"ko": "컬러 적용",         "en": "Apply Colors"},
    "color_override_added": {"ko": "{obj} [{slot}] 컬러 오버라이드 추가됨",
                             "en": "Color override added for {obj} [{slot}]"},
    "render_shot":          {"ko": "렌더",              "en": "Render"},
    "batch_render":         {"ko": "전체 렌더",         "en": "Batch All"},
    "batch_complete":       {"ko": "{count}개 Shot 렌더 완료",
                             "en": "{count} shot(s) rendered"},
    "generate_views":       {"ko": "표준 뷰 생성",          "en": "Generate Standard Views"},
    "views_generated":      {"ko": "{count}개 표준 뷰 생성됨",
                             "en": "{count} standard view(s) generated"},
    "template_hint":        {"ko": "  변수: {project} {shot} {date} {time} {index}",
                             "en": "  Variables: {project} {shot} {date} {time} {index}"},

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
}


def _get_locale() -> str:
    """Return 'ko' or 'en' based on addon preference, falling back to Blender system language."""
    # 1) Check addon preference (manual override)
    try:
        prefs = bpy.context.preferences.addons.get(__package__)
        if prefs and hasattr(prefs, 'preferences'):
            lang = getattr(prefs.preferences, 'ftb_language', 'auto')
            if lang == 'ko':
                return 'ko'
            elif lang == 'en':
                return 'en'
            # 'auto' falls through to system detection
    except Exception:
        pass
    # 2) Auto-detect from Blender system language
    try:
        locale = bpy.app.translations.locale
        if locale and locale.startswith("ko"):
            return "ko"
    except Exception:
        pass
    return "en"


def t(key: str, **kwargs) -> str:
    """Get translated string by key. Supports format kwargs.

    Usage:
        t("connected")                    -> "● Connected" or "● 연결됨"
        t("fusion_obj_count", count=42)   -> "Fusion objects in scene: 42"
    """
    entry = _STRINGS.get(key)
    if entry is None:
        return key  # Fallback: return the key itself

    locale = _get_locale()
    text = entry.get(locale, entry.get("en", key))

    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text
