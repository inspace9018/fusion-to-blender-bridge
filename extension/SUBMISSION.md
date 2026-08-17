# extensions.blender.org 제출 — 준비물과 붙여넣을 내용

> 빌드: `python build_extension.py` → `build/fusion_to_blender_bridge-1.0.0.zip` (161 KB)
> Blender 자체 검증(`--command extension validate`) 통과.

---

## 1. 제출 전 확인 (코드 쪽은 끝남)

| 심사 항목 | 상태 |
|---|---|
| GPL-3.0-or-later | ✅ `LICENSE` 동봉, 파일마다 고지 |
| 자체 업데이터 없음 | ✅ 없음 (플랫폼이 담당) |
| 런타임 pip 설치 없음 | ✅ STEP 리더 제외로 사라짐 |
| `sys.path` 조작 없음 | ✅ 같은 이유 |
| `addons[__name__]` 오용 없음 | ✅ |
| `bl_ext` 하드코딩 없음 | ✅ |
| 자기 디렉터리에 쓰기 없음 | ✅ |
| 권한 선언 | 없음 — 인터넷·파일 접근을 하지 않음 |
| Blender 안에서 실제 동작 | ✅ 격리 설치 후 14항목 확인 |

**유일하게 남은 판단 항목:** 자기완결성(self-contained). 이 애드온은 같은 컴퓨터의
Fusion 360 애드인과 `127.0.0.1:9080` 으로 통신한다. 심사 지침은 외부 *서버* 의존을
금지하면서 **"localhost is fine"** 이라고 적고 있고, 별도로 *"추가 소프트웨어가 필요하고
동봉할 수 없다면 사용자가 실행하면 된다"* 고도 적고 있다. 우리가 정확히 그 형태다.
확신이 서지 않으면 `#extension-moderators` 에 먼저 묻는 편이 빠르다.

---

## 2. 등록 양식에 붙여넣을 것

### Tagline (한 줄, 64자 이내)

```
Keep your Blender materials when the CAD model changes
```

### Description

```
Fusion to Blender Bridge keeps your Blender work alive across CAD revisions.

Model in Fusion 360, press Sync in Blender, and the geometry updates while the
materials, modifiers, light links and hand-marked Sharp / Seam / Crease / Bevel
Weight you set up in Blender stay exactly where they were. No STEP export, no
re-import, no rebuilding your shading every time the part changes.

WHAT IT DOES
• One-click sync of the whole Fusion model
• Your Blender materials, modifiers and light links survive every re-sync
• Hand-marked edges survive too
• Fusion's component hierarchy becomes Blender collections
• Four mesh quality presets, from quick layout to final render
• Show or hide Fusion-hidden bodies instantly, without re-syncing
• Interface follows Blender's language (English / Korean)

WHAT IT DOES NOT DO
Fusion Appearances are not imported. This moves geometry; the look is yours to
author in Blender — which is the whole point, since that look then survives
every later CAD edit.

HOW IT CONNECTS
Fusion 360 and Blender run on the same computer. The add-on talks to the Fusion
add-in over 127.0.0.1 only. It never reaches the internet, reads no files of its
own, and has no updater — Blender handles updates.

SETUP
1. Install the free Fusion 360 add-in from the project page (link below)
2. Run it in Fusion (Utilities → Add-Ins)
3. In Blender: N-panel → Fusion 360 tab → Sync

Opening .step / .stp files directly, without Fusion, needs a CAD kernel too
large for this platform's size limit. That version is on the project page.

Requires Fusion 360 (any current version).
```

### Website
```
https://github.com/inspace9018/fusion-to-blender-bridge
```

### Tags
`Import-Export`, `Pipeline`  ← 매니페스트와 동일

### License
`GPL-3.0-or-later` ← 매니페스트와 동일

---

## 3. 사용자님이 하셔야 하는 것

**계정** — Blender ID 로 extensions.blender.org 로그인.

**이미지** — 심사에서 *"Check the overall quality of the images"* 를 봅니다.
지침이 **무거운 GIF 를 쓰지 말라**고 명시하므로 `docs/demo.gif`(27MB) 는 그대로 쓰면
안 됩니다. 정지 이미지 3~4장을 권합니다:

1. Blender 뷰포트에 Fusion 모델이 올라온 화면 + 오른쪽 N 패널이 보이게
2. 재질을 입힌 상태 → Fusion 에서 고친 뒤 Sync → 재질이 그대로인 before/after
3. 컬렉션 구조(아웃라이너)가 Fusion 컴포넌트 계층과 같은 모습
4. (선택) 품질 프리셋 비교

**제출** — https://extensions.blender.org/submit/ 에 위 zip 업로드.

---

## 4. 승인 후

버전을 올릴 때는 `blender_addon/__init__.py` 의 `bl_info["version"]` 만 고치면
`build_extension.py` 가 매니페스트를 맞춰 줍니다. 둘이 어긋날 수 없습니다.
