"""
Fusion to Blender - Internationalization (i18n) for Fusion 360 Add-in
Language is stored in a module-level variable, changeable via Settings dialog.
Supported: English (default), Korean (ko).
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

# Module-level language setting ("auto", "en", "ko")
_language = "auto"

_STRINGS = {
    # ── Tab / Panel ──────────────────────────────────────────────────────────
    "tab_name":             {"ko": "Fusion to Blender",   "en": "Fusion to Blender"},
    "panel_name":           {"ko": "Fusion to Blender",   "en": "Fusion to Blender"},

    # ── Commands ─────────────────────────────────────────────────────────────
    "start_server":         {"ko": "서버 시작",            "en": "Start Server"},
    "start_server_desc":    {"ko": "Blender 연결용 WebSocket 서버를 시작합니다",
                             "en": "Start WebSocket server for Blender connection"},
    "stop_server":          {"ko": "서버 중지",            "en": "Stop Server"},
    "stop_server_desc":     {"ko": "WebSocket 서버를 중지합니다",
                             "en": "Stop WebSocket server"},
    "settings":             {"ko": "서버 설정",            "en": "Server Settings"},
    "settings_desc":        {"ko": "포트 및 옵션 설정",     "en": "Port and option settings"},
    "privacy":              {"ko": "개인정보처리방침",     "en": "Privacy Policy"},
    "privacy_desc":         {"ko": "이 애드인이 무엇을 읽고 무엇을 남기는지",
                             "en": "What this add-in reads, and what it leaves on your machine"},

    # ── Blender 애드온 꺼내기 ────────────────────────────────────────────────
    # 이 항목들은 Blender 애드온 zip 이 애드인 옆에 같이 설치된 배포판에서만
    # 화면에 나타난다. 무료 설치기는 Blender 쪽을 직접 깔아 주므로 zip 이 없고,
    # 버튼도 만들어지지 않는다.
    "get_blender":          {"ko": "Blender 애드온 꺼내기",
                             "en": "Get Blender Add-on"},
    "get_blender_desc":     {"ko": "Blender 에 설치할 애드온 파일을 원하는 위치에 저장합니다",
                             "en": "Save the Blender add-on file somewhere you can find it"},
    "get_blender_missing":  {"ko": "Blender 애드온 파일을 찾지 못했습니다.\n"
                                   "구매하신 다운로드에서 직접 꺼내 주세요.",
                             "en": "Could not find the Blender add-on file.\n"
                                   "Please take it from your original download."},
    "get_blender_saved":    {"ko": "저장했습니다:\n{path}\n\n"
                                   "Blender 에서:\n"
                                   "Edit > Preferences > Add-ons > Install from Disk\n"
                                   "→ 이 파일을 고르고 체크박스를 켜세요.",
                             "en": "Saved to:\n{path}\n\n"
                                   "In Blender:\n"
                                   "Edit > Preferences > Add-ons > Install from Disk\n"
                                   "→ choose this file, then tick it to enable."},

    # ── Nav Toolbar ──────────────────────────────────────────────────────────
    "nav_srv_on":           {"ko": "● 서버 실행 중",       "en": "● Server Running"},
    "nav_srv_on_desc":      {"ko": "서버 실행 중 — 클릭하면 중지",
                             "en": "Server is running — click to stop"},
    "nav_srv_off":          {"ko": "○ 서버 중지됨",        "en": "○ Server Stopped"},
    "nav_srv_off_desc":     {"ko": "서버 중지됨 — 클릭하면 시작",
                             "en": "Server is stopped — click to start"},

    # ── Settings Dialog ──────────────────────────────────────────────────────
    "port_label":           {"ko": "WebSocket 포트",       "en": "WebSocket Port"},
    "include_hidden":       {"ko": "숨김 Body 포함",       "en": "Include Hidden Bodies"},
    "allow_remote":         {"ko": "원격(LAN) 연결 허용",   "en": "Allow remote (LAN) connections"},
    "allow_remote_desc":    {"ko": "기본값은 이 PC(localhost)에서만 연결됩니다. 켜면 같은 네트워크의 다른 기기(다른 PC의 Blender)도 연결할 수 있지만, 방화벽 허용이 필요하고 열려 있는 모델이 네트워크에 노출됩니다. 신뢰된 네트워크에서만 사용하세요.",
                             "en": "By default only this PC (localhost) can connect. Enabling this lets other devices on your network (Blender on another PC) connect too, but it requires a firewall allow and exposes the open model to the network. Use only on trusted networks."},
    "language":             {"ko": "언어",                 "en": "Language"},

    # ── Messages ─────────────────────────────────────────────────────────────
    "server_stopped_msg":   {"ko": "서버가 중지되었습니다.",  "en": "Server has been stopped."},
    "streamed_msg":         {"ko": "{count}개 오브젝트 전송 완료 (품질={preset})",
                             "en": "Streamed {count} objects (quality={preset})"},
    "joints_sent":          {"ko": "{count}개 조인트 전송됨",
                             "en": "{count} joint(s) sent"},
    "action_failed":        {"ko": "작업을 완료하지 못했습니다:\n{detail}",
                             "en": "The action could not be completed:\n{detail}"},
}


def _get_locale() -> str:
    """Return 'ko' or 'en' based on module-level _language setting."""
    global _language
    if _language == "ko":
        return "ko"
    elif _language == "en":
        return "en"
    # "auto" — try to detect from Fusion locale
    try:
        import adsk.core
        app = adsk.core.Application.get()
        prefs = app.preferences
        lang = prefs.generalPreferences.userLanguage
        # Fusion UserLanguage enum: Korean = 11
        if lang == 11:
            return "ko"
    except Exception:
        pass
    return "en"


def set_language(lang: str):
    """Set language: 'auto', 'en', or 'ko'."""
    global _language
    _language = lang


def get_language() -> str:
    """Get current language setting."""
    return _language


def t(key: str, **kwargs) -> str:
    """Get translated string by key. Supports format kwargs."""
    entry = _STRINGS.get(key)
    if entry is None:
        return key

    locale = _get_locale()
    text = entry.get(locale, entry.get("en", key))

    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text
