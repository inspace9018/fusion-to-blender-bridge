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

## 2. 상세 페이지 — 그대로 붙여넣기

등록 폼의 각 칸에 아래를 그대로 넣습니다. 마크다운이 렌더링되며,
탭(About / What's New / Permissions / Reviews / Version History)은 자동으로 생깁니다.
Permissions 탭은 매니페스트에서 만들어지고, 우리는 선언한 권한이 없어 비어 있게 됩니다.

### Tagline — 64자 제한

```
Keep your Blender materials when the CAD model changes
```

<sub>54자. 목록 카드에서 제품명 바로 아래 한 줄로 뜹니다.</sub>

---

### About

````markdown
Model in Fusion 360, press **Sync** in Blender, and the geometry updates while
everything you built around it stays put. Your materials, your modifiers, your
light links, and the Sharp, Seam, Crease and Bevel Weight you marked by hand.

The usual CAD-to-Blender loop is export STEP, import, reapply materials, then do
it all again at the next revision. This removes the loop. You set up the look
once and it survives every change to the part.

## Features

- One-click sync of the entire Fusion model
- Materials, modifiers and light links you set up in Blender survive every re-sync
- Hand-marked Sharp, Seam, Crease and Bevel Weight survive too
- Fusion's component hierarchy arrives as Blender collections
- Four mesh quality presets, from a quick layout check to a final render
- Show or hide Fusion-hidden bodies instantly, with no re-sync
- Custom split normals, so curved CAD surfaces read correctly
- Interface follows Blender's language (English and Korean)

## Requirements

- **Fusion 360.** This is a bridge. It needs Fusion running on the same computer
- **The free Fusion add-in**, installed once from the project page below
- Blender 4.2 or newer

## Setup

1. Download the Fusion add-in from the [project page](https://github.com/inspace9018/fusion-to-blender-bridge/releases/latest) and run the installer
2. In Fusion: **Utilities → Add-Ins → fusion_to_blender_addon_fusion → Run**
3. In Blender: **N-panel → Fusion 360 tab → Sync**

That is the whole setup. The add-on connects to Fusion on this computer
(127.0.0.1). It never reaches the internet and stores nothing outside Blender.

## What it does not do

**Fusion Appearances are not imported.** This moves geometry. The look is yours
to author in Blender. That is deliberate rather than a limitation: a look you
build in Blender survives the next twenty CAD revisions, which is not true of
anything that re-imports materials each time.

**Opening .step and .stp files without Fusion** is not part of this package. It
needs a CAD kernel far larger than this platform allows, so it lives in the build
on the project page. The add-on's preferences tell you where to find it.

## Docs & Support

Full documentation, the Fusion add-in, and the STEP-capable build are all on the
[project page](https://github.com/inspace9018/fusion-to-blender-bridge).

Found a bug or want a feature? Open an
[issue](https://github.com/inspace9018/fusion-to-blender-bridge/issues). It gets
read.
````

---

### What's New — v1.0.0

````markdown
First public release.

- One-click sync from Fusion 360, with the whole component hierarchy
- Your Blender materials, modifiers and light links survive every re-sync
- Hand-marked Sharp / Seam / Crease / Bevel Weight survive too
- Four mesh quality presets
- Instant show/hide of bodies hidden in Fusion
- English / Korean interface
````

---

### 나머지 칸

| 칸 | 값 |
|---|---|
| Website | `https://github.com/inspace9018/fusion-to-blender-bridge` |
| Tags | `Import-Export`, `Pipeline` (매니페스트와 동일) |
| License | `GPL-3.0-or-later` (매니페스트와 동일) |

---

## 3. 이 문구가 이렇게 쓰인 이유

**Fusion 애드인이 따로 필요하다는 사실을 Requirements 에 올려 두었다.**
묻히면 안 되는 정보다. Blender 안에서 설치한 사람이 "아무것도 안 되는데" 로
끝나면 별 하나짜리 후기가 남는다. 심사자도 자기완결성 항목에서 이걸 본다.

**"하지 않는 일" 을 숨기지 않았다.** Fusion 재질이 안 넘어온다는 사실은 어차피
5분이면 들킨다. 먼저 말하고, 왜 그게 오히려 이 도구의 요점인지까지 적었다.

**STEP 이 왜 없는지도 적었다.** 그걸 찾으러 온 사람이 "이 도구는 못 하는구나" 로
끝나지 않도록. 애드온 설정 화면에도 같은 안내가 들어가 있다.

**첫 문단에 기능 나열을 하지 않았다.** 첫 두 문장은 사용자가 겪는 반복 작업과
그것이 사라진다는 약속이고, 목록은 그 뒤다.
