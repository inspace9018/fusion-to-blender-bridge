# extensions.blender.org 제출 — 준비물과 붙여넣을 내용

> 빌드: `python build_extension.py` → `build/fusion_to_blender_bridge-1.0.1.zip` (163 KB)
> Blender 자체 검증(`--command extension validate`) 통과.
> 실제 설치 검증: 격리 Blender 에 깔아 켜고 24항목 확인 (2026-08-28).

> **제출 기록 (2026-09-29):** 심사 대기열에 제출함. 상태 Awaiting Review.
> 관리 페이지: https://extensions.blender.org/add-ons/fusion-to-blender-bridge/manage/

---

## 1. 제출 전 확인

| 심사 항목 | 상태 |
|---|---|
| GPL-3.0-or-later | ✅ `LICENSE` 동봉, 파일마다 고지 |
| 동봉한 남의 코드 고지 | ✅ `NOTICE` §3 — websockets (BSD 3-Clause) |
| 자체 업데이터 없음 | ✅ 없음 (플랫폼이 담당) |
| 런타임 pip 설치 없음 | ✅ STEP 리더 제외로 사라짐 |
| `sys.path` 조작 없음 | ✅ 같은 이유 |
| `addons[__name__]` 오용 없음 | ✅ |
| `bl_ext` 하드코딩 없음 | ✅ |
| 자기 디렉터리에 쓰기 없음 | ✅ |
| 권한 선언 | 없음 — 인터넷·파일 접근을 하지 않음 |
| Blender 안에서 실제 동작 | ✅ 아래 참조 |

## 1-2. 먼저 알아야 할 것 — 이 플랫폼이 받아줄지가 불확실하다

2026-08-10 자 [이용약관](https://extensions.blender.org/terms-of-service/)을 우리
물건에 그대로 대보면, **거절 사유가 될 만한 조항이 두 개** 있다. 예전 심사
지침의 "localhost is fine" 한 줄만 보고 괜찮다고 적어 두었던 것은 지금 약관으로는
근거가 부족하다.

| 조항 | 원문 요지 | 우리 경우 |
|---|---|---|
| **5.2** | 확장은 "다른 데서 내려받아야 하는 외부 구성요소를 요구해서는 안 된다 — 그 기능이 선택적이더라도" | ❗ Fusion 애드인을 GitHub 에서 따로 받아 깔아야 **아무 기능도** 동작하지 않는다 |
| **3.10** | "추가 구매·외부 서비스 가입·결제·키" 가 기능을 막아서는 안 된다 | ❗ Fusion 360 은 상용이고, 무료 개인용도 Autodesk 계정 가입이 필요하다 |
| 6.3 | Blender UI 안에서 업데이트·상용판·다른 확장을 홍보하면 안 된다 | ⚠️ 설정 화면의 "STEP 되는 빌드 받으러 가기" 안내와, 꺼져 있는 유료판 티저 패널이 걸린다 |
| 1.3 | 동봉한 남의 코드의 저작권자를 매니페스트에 적어야 한다 | ✅ 고침 — websockets 저작권자를 `copyright` 에 추가했다 |

**전례 (2026-09-29 확인, 플랫폼 API 전체 목록 기준):**

| 확장 | 우리와 같은 점 | 승인 |
|---|---|---|
| Darkly | 외부 앱을 GitHub 에서 따로 받아 localhost 로 통신 (5.2) | 2026-07-14 |
| NodeFlow Importer | 유료 외부 서비스·계정이 있어야 쓸모가 있음 (3.10) — **개정 약관 이후** | 2026-08-29 |
| Retro Console Lite | 상세 페이지에 "More features in the full version" + Superhive 링크, 이름에 Lite | 2025-07 |
| AutoCam Free | 상세 페이지에 Gumroad 링크, 변경 로그에 Pro edition 언급 | 2025-06 |

**그래서:** 3.10 은 NodeFlow 로 방어된다. 5.2 는 Darkly 로 방어되지만 우리 애드인이
"같은 프로젝트의 구성요소" 로 읽힐 여지는 남는다. Fusion 애드인을 zip 에 동봉하면 5.2 는
풀리지만, 무료 사용자가 설치 가이드 페이지(= 전환 페이지)를 반드시 거치는 흐름이 사라지므로
**동봉하지 않는다.** 심사에서 요구할 때만 동봉으로 후퇴한다.

**반영한 것 (2026-09-29):**
- 이름 `Fusion to Blender Lite` → `Fusion Bridge Lite` — 2.1 "Blender" 는 이름에 쓸 수 없다
- 유료판 티저 패널을 `promo.py` 로 분리, 확장 zip 에서 제외 (6.1 / 6.3)
- 콘솔 메시지의 "Bridge Pro" 언급 제거
- 설정 화면의 "GitHub 에서 받기" 버튼 제거 → "Setup guide & docs (opens browser)" 버튼 (4.4)
- 연결 안 됨 상태에 "Fusion add-in setup (opens browser)" 버튼 추가 — 새 사용자가 막히는 바로 그 자리
- `website` → 설치 가이드 페이지 `https://inspace9018.github.io/fusion-to-blender-bridge/`

---

### 실제 설치 검증 (2026-08-28)

빌드한 zip 을 격리한 Blender 5.0.1 에 실제로 설치해 켜고, 설정 화면이 무엇을
그리는지까지 확인했다 — **24/24**.

- 켜지고 꺼진다 (등록·해제 모두 오류 없음)
- 사이드바 패널 제목이 `Fusion to Blender Lite  v1.0`
- 설정 화면에 언어·자동연결 두 항목과 **개인정보처리방침 링크**가 나온다
- STEP 리더가 빠졌음을 스스로 알고, 안내문을 대신 띄운다
- STEP 관련 오퍼레이터 3개가 **등록되지 않는다** (죽은 버튼이 남지 않는다)
- 연결·해제·전체 동기화·선택 동기화·숨김 토글 오퍼레이터가 모두 등록된다

> **이 검증이 잡아낸 것.** 이전 버전은 확장으로 깔면 *켜지지도 않았다*. 확장은
> 애드온 이름이 `bl_ext.user_default.<id>` 라서, 이름을 첫 점에서 자르던 코드가
> 설정을 통째로 등록하지 않았고 `bl_info` 를 읽던 자리에서 그대로 멈췄다.
> 커밋 `a7146af` 에서 고쳤다. **zip 만 검증하고 설치는 하지 않으면 이 부류는
> 절대 안 잡힌다** — `extension validate` 는 TOML 만 본다.

---

## 2. 상세 페이지 — 그대로 붙여넣기

등록 폼의 각 칸에 아래를 그대로 넣습니다. 마크다운이 렌더링되며,
탭(About / What's New / Permissions / Reviews / Version History)은 자동으로 생깁니다.
Permissions 탭은 매니페스트에서 만들어지고, 우리는 선언한 권한이 없어 비어 있게 됩니다.

### Name

```
Fusion Bridge Lite
```

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
- **Sync Selected** — pick a few objects and pull fresh geometry for just those.
  Fix one part in a 500-object assembly without waiting for the other 499
- Materials, modifiers and light links you set up in Blender survive every re-sync
- Hand-marked Sharp, Seam, Crease and Bevel Weight survive too
- Fusion's component hierarchy arrives as Blender collections
- Three mesh quality presets, from a quick layout check to a final render
- Show or hide Fusion-hidden bodies instantly, with no re-sync
- Custom split normals, so curved CAD surfaces read correctly
- Interface follows Blender's language (English and Korean)

## Requirements

- **Fusion 360.** This is a bridge. It needs Fusion running on the same computer
- **The free Fusion add-in**, installed once from the setup guide linked below
- Blender 4.2 or newer

## Setup

1. Download the Fusion add-in from the [setup guide](https://inspace9018.github.io/fusion-to-blender-bridge/) and run the installer inside the zip
2. In Fusion: **Utilities → Add-Ins → fusion_to_blender_addon_fusion → Run**
3. In Blender: **N-panel → Fusion 360 tab → Sync**

That is the whole setup. The add-on connects to Fusion on this computer
(127.0.0.1). It never reaches the internet and stores nothing outside Blender.

## What it does not do

**Fusion Appearances are not imported.** This version moves geometry, and the
look is yours to author in Blender. Whatever you build there survives every
re-sync.

**Opening .step and .stp files without Fusion** is not part of this package. It
needs a CAD kernel far larger than this platform allows. The
[setup guide](https://inspace9018.github.io/fusion-to-blender-bridge/) says
where the build that has it lives.

## Privacy

Nothing is collected and nothing is sent anywhere. The full policy — what is
read, what is written to your own disk, and how to remove it — is linked from
the add-on's preferences and published at
[PRIVACY.md](https://github.com/inspace9018/fusion-to-blender-bridge/blob/main/PRIVACY.md).

## Docs & Support

The [setup guide](https://inspace9018.github.io/fusion-to-blender-bridge/) has
the Fusion add-in download and the three setup steps. Source code is on
[GitHub](https://github.com/inspace9018/fusion-to-blender-bridge).

Found a bug or want a feature? Open an
[issue](https://github.com/inspace9018/fusion-to-blender-bridge/issues). It gets
read.

More features in the full version:
[Fusion to Blender Bridge Pro](https://superhivemarket.com/products/fusion-to-blender-bridge)
````

---

### What's New — v1.0.1

````markdown
First release on this platform.

- One-click sync from Fusion 360, with the whole component hierarchy
- **Sync Selected** — re-pull geometry for just the objects you picked, and
  leave the rest of the scene untouched
- Your Blender materials, modifiers and light links survive every re-sync
- Hand-marked Sharp / Seam / Crease / Bevel Weight survive too
- Three mesh quality presets
- Instant show/hide of bodies hidden in Fusion
- English / Korean interface
````

<sub>플랫폼에는 처음 올리는 것이라 "First release on this platform" 이라고 적었습니다.
GitHub 쪽 버전 이력과 번호를 맞추기 위해 1.0.0 이 아니라 1.0.1 로 시작합니다.</sub>

---

### 이미지 (extension/listing/)

| 칸 | 파일 | 규격 |
|---|---|---|
| Icon | `icon.png` | 256×256, 투명 배경 |
| Featured image | `featured.png` | 1920×1080 |
| Preview 1 | `featured.png` | 1920×1080 |
| Preview 2 | `howto.png` | 1920×1080 |

규격은 승인된 확장(Darkly, Retro Console Lite, AutoCam Free)의 실제 이미지에서 확인했다
(아이콘 128·256 정사각, 미리보기 16:9 → 1920×1080 썸네일 생성). Pro 화면이 보이는
루트 `demo.gif` 는 6.2 때문에 쓰지 않는다. Blender·Autodesk 로고 없음 (2.2 / 2.4).

### 나머지 칸

| 칸 | 값 |
|---|---|
| Website | `https://inspace9018.github.io/fusion-to-blender-bridge/` (매니페스트와 동일) |
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

**유료판은 맨 끝 한 줄, 기능 나열 없이.** 6.2 는 상세 페이지에서 플랫폼 버전에 없는
기능을 보여주는 것을 막는다. 유료판이 있다는 사실과 링크는 Retro Console Lite·AutoCam Free
전례대로 허용된다. Pro 기능 비교는 설치 가이드 페이지가 맡는다.

**"재질을 안 가져오는 게 의도" 라는 문장은 뺐다.** 무료 사용자에게 Pro 의 핵심 기능이
필요 없다고 설득하는 문장이었다.
