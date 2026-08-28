# Fusion 360 → Blender Bridge

<p align="center">
  <img src="docs/demo.gif" alt="Fusion 360 to Blender Bridge Demo" width="720">
</p>

<p align="center">
  <a href="../../releases/latest"><img src="https://img.shields.io/github/v/release/inspace9018/fusion-to-blender-bridge?label=release&color=success&logo=github" alt="Release"></a>
  <img src="https://img.shields.io/github/last-commit/inspace9018/fusion-to-blender-bridge?label=updated&color=informational&logo=github" alt="Last updated">
  <img src="https://img.shields.io/badge/Blender-4.2%20%E2%80%93%205.0-orange?logo=blender&logoColor=white" alt="Blender 4.2 – 5.0">
  <img src="https://img.shields.io/badge/Fusion_360-supported-blue?logo=autodesk&logoColor=white" alt="Fusion 360">
  <img src="https://img.shields.io/badge/license-GPL--3.0--or--later-lightgrey" alt="GPL-3.0-or-later">
  <a href="https://ko-fi.com/inspace9018gmailcom"><img src="https://img.shields.io/badge/Support-Ko--fi-FF5E5B?logo=ko-fi&logoColor=white" alt="Ko-fi"></a>
</p>

<p align="center">
  <b>Blender에서 입힌 재질을, 모델을 고쳐도 다시 입히지 마세요.</b><br>
  제품 디자이너를 위한 원클릭 동기화 — Fusion에서 형상만 새로 오고,<br>
  Blender에 세팅해 둔 Material · Modifier · Light Link · 손으로 찍은 엣지 표시는 그 자리에 남습니다.<br>
  <sub>내보내기·재질 다시 입히기 같은 반복 작업 없이, 모델을 고치면 Blender에서 Sync 한 번.</sub>
</p>

<p align="center">
  <a href="../../releases/latest"><b>⬇️ 다운로드</b></a>&ensp;·&ensp;<a href="#한국어">한국어</a>&ensp;·&ensp;<a href="#english">English</a>&ensp;·&ensp;<a href="../../">⭐ Star</a>
</p>

---

# 한국어

## 왜 이 도구가 필요한가요?

> Fusion 360에서 모델링 → STEP/OBJ 내보내기 → Blender 임포트 → 재질 다시 적용...
>
> **이 반복 작업이 버튼 하나로 끝납니다.**

Fusion에서 모델을 수정하고 Blender에서 **Sync** 한 번 누르면, 형상만 바뀌고 Material·Modifier·Light Link는 그대로 살아있습니다.

> ### 🎯 한 줄로 정확히
>
> **이 도구가 지키는 재질은 "Blender에서 당신이 입힌 재질"입니다.**
> Fusion에서 모델을 몇 번을 고쳐 와도, Blender에 세팅해 둔 셰이더·모디파이어·라이트 링크가
> 그 자리에 남습니다. 렌더 세팅을 처음부터 다시 하지 않아도 됩니다.
>
> **Fusion의 Appearance(외형)는 가져오지 않습니다.** 이 도구는 형상만 옮깁니다 —
> 룩은 Blender에서 만드는 것이 전제입니다. Fusion에서 색을 칠하고 Sync해도 Blender에는
> 나타나지 않습니다. 정상 동작입니다.

## 핵심 기능

| | 기능 | 설명 |
|:---:|------|------|
| 🔄 | **원클릭 동기화** | 버튼 하나로 Fusion 모델 전체를 Blender로 |
| 🎨 | **Blender 재질 보존** | Blender에서 입힌 Material · Modifier · Light Link가 재동기화에도 그대로 |
| 📁 | **컬렉션 자동 구성** | Fusion 컴포넌트 계층 → Blender Collection |
| 🎛️ | **메시 품질 선택** | Low / Medium / High 3단계 |
| 👁️ | **숨김 Body 토글** | 재동기화 없이 즉시 표시/숨기기 |
| 🌐 | **한/영 자동 전환** | Blender 시스템 언어 감지 (직접 고르려면 애드온 설정에서) |
| ✏️ | **엣지 표시 보존** | 손으로 찍은 Sharp · Seam · Crease · Bevel Weight가 재동기화에도 유지 |
| 📐 | **STEP 임포트** | Fusion 없이 `.step` / `.stp` 파일 열기 (최초 1회 STEP 지원 설치 필요) |

## 🧩 함께 쓰는 도구들

> **브리지는 한 가지만 합니다 — Fusion ↔ Blender 동기화.** 위 표의 기능은 전부 무료이고 계속 무료입니다.
>
> 그 앞뒤를 맡는 유료 애드온이 따로 있습니다. 브리지 없이도, 사지 않아도 브리지는 그대로 완전합니다.
>
> | | 하는 일 | |
> |---|---|:---:|
> | **Bridge** (이 저장소) | Fusion ↔ Blender 동기화와 보존 | **무료** |
> | **[Bridge Pro](https://nexuslabmain.gumroad.com/l/fusion-to-blender-bridge)** | **이 브리지 + Fusion이 아는 것** — 색 · 움직임 · 모서리 · 정밀도 · 토폴로지 | $39 |
>
> Bridge Pro는 이 애드온을 **품고 있는 별도 애드온**입니다. 사면 이걸 지우고 그것 하나만
> 씁니다(설치 프로그램이 알아서 합니다). 둘 다 켜면 모델이 두 번씩 들어옵니다.
>
> ⭐ **Star**를 눌러두시면 새 소식을 가장 먼저 받아보실 수 있어요.

## 설치 (5분)

### 준비물

- **Fusion 360** (최신 버전)
- **Blender 4.2+** (5.0 권장)

### ⭐ 가장 쉬운 방법 — 통합 설치 프로그램 (권장)

Fusion·Blender 애드온을 **한 번에** 설치합니다.

1. [Releases](../../releases)에서 `fusion_to_blender_bridge_installer.zip` 다운로드 후 **압축 해제**
2. 시작 전 **Fusion 360과 Blender를 닫아주세요.**
3. 설치 파일 **더블클릭** → 메뉴에서 **Install** 선택:
   - **Windows:** `install.bat`
   - **Mac:** `install.command` (차단되면 우클릭 → 열기)
4. 끝나면 안내대로: Fusion에서 애드인 **Run**, Blender에서 애드온 **활성화** 후 재시작

> 메뉴에는 **Install / Update·Repair / Uninstall**이 있어, 업데이트·재설치·삭제도 같은 파일로 합니다. 사용자 폴더에만 설치되고(관리자 권한 불필요), 삭제는 두 애드온 폴더만 지웁니다.

아래는 애드온을 따로 설치하고 싶을 때의 수동 방법입니다.

### Step 1 — Fusion 360 Add-in (수동)

1. [Releases](../../releases)에서 `fusion_to_blender_addon_fusion.zip` 다운로드 후 **압축 해제**
2. 압축 푼 폴더 안의 설치 파일을 **더블클릭** — 올바른 위치에 자동 설치됩니다:
   - **Windows:** `install.bat`
   - **Mac:** `install.command` (차단되면 우클릭 → 열기)
3. Fusion 360 → **유틸리티(또는 도구) → Add-Ins → "스크립트 및 추가 기능"** → Add-Ins 탭에서 `fusion_to_blender_addon_fusion` 선택 → **Run**

<details>
<summary>수동 설치 (스크립트를 쓰지 않을 때)</summary>

압축 푼 폴더를 아래 경로에 직접 넣은 뒤 위 3번을 진행하세요. ZIP을 그대로 넣지 말고 반드시 **압축을 풀고** 폴더를 넣으세요.
```
Windows:  %appdata%\Autodesk\Autodesk Fusion 360\API\AddIns\
Mac:      ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/
```
</details>

### Step 2 — Blender Add-on

1. [Releases](../../releases)에서 `fusion_to_blender_addon_blender.zip` 다운로드
2. Blender → **Edit** → **Preferences** → **Add-ons** → **Install from Disk**
3. ZIP 파일 선택 → 설치 → **Fusion to Blender Lite** 활성화
4. 3D Viewport 우측 `N` 키 → **Fusion 360** 탭 확인

## 사용법

```
Step 1    Fusion 360에서 Add-in 실행 (서버 자동 시작)
            ↓
Step 2    Blender N패널 → Fusion 360 탭 → Connect
            ↓
Step 3    품질 프리셋 선택 (Low ~ High)
            ↓
Step 4    Sync 버튼 클릭
            ↓
          ✅ 모델이 Blender에 나타남!
            ↓
Step 5    Fusion에서 모델 수정 → 다시 Sync
            ↓
          ✅ 형상만 새로 오고, Blender 재질은 그대로!
```

## 설정

### 메시 품질

| 프리셋 | 곡면 오차 | 법선 각도 | 추천 용도 |
|:------:|:--------:|:--------:|---------|
| Low | 0.5 mm | 30° | 빠른 레이아웃 확인 |
| **Medium** | **0.2 mm** | **15°** | **일반 작업 (기본값)** |
| High | 0.05 mm | 8° | 렌더링 준비 |

### 임포트 옵션

| 옵션 | 기본값 | 설명 |
|------|:------:|------|
| 숨김 Body 표시 | OFF | Fusion에서 숨긴 Body를 Blender에서도 표시 |
| 최상위 Empty | ON | 서브어셈블리를 Empty로 묶어 함께 이동 |
| Transform 갱신 | ON | 위치/회전/스케일 동기화 |
| Collection 자동 갱신 | OFF | Fusion 계층대로 Collection 재배치 |

## 유틸리티 도구 (Edit Mode)

| 도구 | 기능 |
|------|------|
| **Face 선택 확장** | 같은 BRep Face 전체 선택 |
| **경계 Edge 선택** | Face Group 경계만 선택 |
| **UV Seam 병합** | 불필요한 seam 축소 |
| **Face 페인팅** | Face Group별 랜덤 색상 |

## 네트워크

**이 컴퓨터 안에서만 통신합니다.** Fusion과 Blender가 같은 PC에서 돌아가며,
브리지는 `127.0.0.1:9080`(자기 자신)에만 접속합니다. 인터넷으로 나가지 않고,
바깥에서 들어올 수도 없습니다. 설정할 주소도 없습니다.

> 보안 프로그램이 이 컴퓨터 안의 통신까지 막는 경우, 포트 9080을 허용해 주세요.

<sub>1.0.0부터 다른 PC의 Fusion에 붙는 기능은 없앴습니다. 쓰는 분이 없었고,
그 기능 하나 때문에 인터넷 권한과 방화벽 구멍이 필요했습니다.</sub>

## 문제 해결

<details>
<summary><b>Connect 후 오브젝트가 안 나와요</b></summary>

**Sync** 버튼을 눌러주세요. 연결만으로는 모델이 자동 전송되지 않습니다.
</details>

<details>
<summary><b>연결이 안 돼요</b></summary>

1. Fusion 360에서 Add-in이 **Run** 상태인지 확인 — 대부분 이것입니다
2. Fusion과 Blender가 **같은 PC**에서 돌고 있는지 확인
3. 보안 프로그램이 포트 9080을 막고 있지 않은지 확인
</details>

<details>
<summary><b>동기화가 멈춰요</b></summary>

1. Blender를 완전히 재시작
2. 복잡한 모델은 **Medium** 품질부터 시도
3. High는 처리 시간이 길 수 있습니다
</details>

<details>
<summary><b>메시가 거칠어요</b></summary>

품질 프리셋을 **High**로 변경하세요. 처리 시간이 늘어나지만 곡면이 더 매끄러워집니다.
</details>

<details>
<summary><b>재질이 사라졌어요 / 안 넘어와요</b></summary>

**Fusion에서 입힌 색이 Blender에 안 보이는 경우** — 정상입니다. 이 도구는 형상만 옮기고 Fusion의 Appearance는 가져오지 않습니다. 재질은 Blender에서 한 번 입혀 두시면, 그 뒤로는 모델을 고쳐도 계속 유지됩니다.

**Blender에서 입힌 재질이 동기화 후 사라진 경우** — Fusion에서 Body를 **삭제 후 재생성**하면 고유 ID가 바뀌어 Blender가 새 오브젝트로 인식합니다. 가능하면 Body를 삭제하지 말고 수정하세요.
</details>

---

# English

## Why This Tool?

> Fusion 360 modeling → export STEP/OBJ → import into Blender → reapply materials...
>
> **One button replaces this entire workflow.**

Edit your model in Fusion, hit **Sync** in Blender. The geometry updates. Your Materials, Modifiers and Light Links stay exactly as they were.

> ### 🎯 To be precise
>
> **The materials this protects are the ones YOU built in Blender.**
> Revise the model in Fusion as often as you like. The shaders, modifiers and light
> links you set up in Blender stay put. You never rebuild your render setup.
>
> **Fusion Appearances are not imported.** This tool moves geometry only. The look is
> yours to author in Blender. Painting a body in Fusion and pressing Sync will not
> bring that colour across. That is deliberate, not a fault.

## Key Features

| | Feature | Description |
|:---:|---------|-------------|
| 🔄 | **One-click sync** | Bring your entire Fusion model into Blender |
| 🎨 | **Your Blender look, kept** | Materials, Modifiers and Light Links you set up in Blender survive every re-sync |
| 📁 | **Auto collections** | Fusion component hierarchy → Blender Collections |
| 🎛️ | **Quality presets** | Low / Medium / High mesh quality |
| 👁️ | **Hidden body toggle** | Show/hide instantly without re-syncing |
| 🌐 | **Auto language** | Detects Blender's language (override in the add-on preferences) |
| ✏️ | **Edge marks preserved** | Hand-marked Sharp / Seam / Crease / Bevel Weight survive every re-sync |
| 📐 | **STEP import** | Open `.step` / `.stp` files without Fusion (one-time STEP-support install) |

## 🧩 Tools that work alongside it

> **The bridge does one job: Fusion ↔ Blender sync.** Everything in the table above is free and stays free.
>
> A paid add-on covers what sits either side of it. The bridge is complete without it.
>
> | | What it does | |
> |---|---|:---:|
> | **Bridge** (this repo) | Fusion ↔ Blender sync and preservation | **Free** |
> | **[Bridge Pro](https://nexuslabmain.gumroad.com/l/fusion-to-blender-bridge)** | **This bridge plus everything Fusion knows** — colour, motion, edges, precision, topology | $39 |
>
> Bridge Pro is a separate add-on that *contains* this one. Buying it replaces
> this: the installer removes it for you. Do not enable both -- the model would
> come in twice.
>
> ⭐ **Star** the repo to hear about what comes next.

## Installation (5 min)

### Requirements

- **Fusion 360** (latest version)
- **Blender 4.2+** (5.0 recommended)

### ⭐ Easiest — unified installer (recommended)

Installs **both** the Fusion and Blender add-ons in one go.

1. Download `fusion_to_blender_bridge_installer.zip` from [Releases](../../releases) and **extract it**
2. **Close Fusion 360 and Blender first.**
3. **Double-click** the installer → choose **Install** from the menu:
   - **Windows:** `install.bat`
   - **Mac:** `install.command` (if blocked, right-click → Open)
4. Then follow the on-screen steps: **Run** the add-in in Fusion, **enable** the add-on in Blender and restart.

> The menu also has **Install / Update·Repair / Uninstall**, so updates, reinstalls, and removal all use the same file. It installs only into your user profile (no admin), and uninstall deletes only the two add-on folders.

Below is the manual method if you prefer to install each add-on separately.

### Step 1 — Fusion 360 Add-in (manual)

1. Download `fusion_to_blender_addon_fusion.zip` from [Releases](../../releases) and **extract it**
2. **Double-click** the installer inside the extracted folder. It copies the add-in to the right place automatically:
   - **Windows:** `install.bat`
   - **Mac:** `install.command` (if blocked, right-click → Open)
3. Fusion 360 → **Utilities (or Tools) → Add-Ins → "Scripts and Add-Ins"** → Add-Ins tab → select `fusion_to_blender_addon_fusion` → **Run**

<details>
<summary>Manual install (if you'd rather not run the script)</summary>

Place the extracted folder here, then do step 3 above. Do NOT drop the ZIP in directly. **Extract it first.**
```
Windows:  %appdata%\Autodesk\Autodesk Fusion 360\API\AddIns\
Mac:      ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/
```
</details>

### Step 2 — Blender Add-on

1. Download `fusion_to_blender_addon_blender.zip` from [Releases](../../releases)
2. Blender → **Edit** → **Preferences** → **Add-ons** → **Install from Disk**
3. Select the ZIP → install → enable **Fusion to Blender Lite**
4. Press `N` in 3D Viewport → find the **Fusion 360** tab

## Usage

```
Step 1    Run Add-in in Fusion 360 (server starts automatically)
            ↓
Step 2    Blender N-Panel → Fusion 360 tab → Connect
            ↓
Step 3    Choose quality preset (Low ~ High)
            ↓
Step 4    Click Sync
            ↓
          ✅ Model appears in Blender!
            ↓
Step 5    Edit model in Fusion → Sync again
            ↓
          ✅ Geometry updates; your Blender materials stay!
```

## Settings

### Mesh Quality

| Preset | Surface Tol. | Normal Angle | Best For |
|:------:|:----------:|:----------:|----------|
| Low | 0.5 mm | 30° | Quick layout check |
| **Medium** | **0.2 mm** | **15°** | **General work (default)** |
| High | 0.05 mm | 8° | Render-ready |

### Import Options

| Option | Default | Description |
|--------|:-------:|-------------|
| Show hidden bodies | OFF | Toggle Fusion-hidden bodies in Blender |
| Root Empty parent | ON | Group sub-assemblies under an Empty |
| Update transforms | ON | Sync position, rotation, scale |
| Auto-update collections | OFF | Match Fusion component hierarchy |

## Utility Tools (Edit Mode)

| Tool | Description |
|------|-------------|
| **Expand Face Selection** | Select entire BRep Face group |
| **Select Boundary Edges** | Select face group boundary edges |
| **Merge UV Seams** | Reduce UV seams to boundary-only |
| **Paint Faces** | Random colors per face group |

## Network

**Everything stays on this machine.** Fusion and Blender run on the same PC, and the
bridge only ever connects to `127.0.0.1:9080`, which is itself. Nothing leaves for
the internet, nothing can reach in, and there is no address to configure.

> If security software polices loopback traffic too, allow port 9080.

<sub>Connecting to Fusion on another PC was dropped in 1.0.0. Nobody used it, and it
was the only reason the add-on needed internet permission and a firewall hole.</sub>

## Troubleshooting

<details>
<summary><b>No objects after connecting</b></summary>

Click the **Sync** button. Connecting alone does not transfer data.
</details>

<details>
<summary><b>Can't connect</b></summary>

1. Verify the Fusion 360 Add-in is running. It is almost always this
2. Check Fusion and Blender are on the **same PC**
3. Check security software isn't blocking port 9080
</details>

<details>
<summary><b>Sync stops midway</b></summary>

1. Restart Blender completely
2. Try **Medium** quality first for complex models
3. High quality may take a long time
</details>

<details>
<summary><b>Mesh too rough</b></summary>

Switch to the **High** preset. Slower, but smoother curves.
</details>

<details>
<summary><b>Materials disappeared / didn't come across</b></summary>

**A colour you applied in Fusion doesn't show up in Blender.** That is expected. This tool moves geometry only, and Fusion Appearances are not imported. Author the material once in Blender and it will survive every later edit.

**A material you applied in Blender vanished after a sync.** Deleting and recreating a body in Fusion changes its unique ID, so Blender sees it as a new object. Modify bodies instead of deleting them.
</details>

---

## Changelog

### v1.0.0 (2026-08-17) — 첫 공개 릴리스

**여기가 실제로 쓰시라고 내놓는 첫 버전입니다.**

**하는 일**
- 원클릭 동기화 — Blender에 세팅해 둔 Material · Modifier · Light Link 보존
- **엣지 표시 보존** — 손으로 찍은 Sharp · Seam · Crease · Bevel Weight가 재동기화에도 유지
- 컬렉션 자동 구성 · 메시 품질 3단계 · 숨김 Body 토글 · 한/영 자동 전환
- Edit Mode 유틸리티 — Face 선택 확장, 경계 Edge 선택, UV Seam 병합, Face 페인팅
- STEP 직접 임포트

**라이선스: GPL-3.0-or-later** — 자유롭게 쓰고, 고치고, 상업적으로도 사용할 수 있습니다.
고친 것을 배포한다면 소스도 같은 GPL로 공개해야 합니다. 코드가 아닌 자산(브랜드·데모 영상·리스팅 문구)은
`NOTICE`에 별도로 적었습니다.

**함께 고친 것**
- **STEP 임포트** — 어셈블리 참조의 배치 정보를 버리고 있어 부품들이 원점 주변에 흩어지던 문제 수정.
  단일 Body 파일에서는 멀쩡해 보여 오래 남아 있던 버그입니다


## Project Structure

```
fusion-to-blender-bridge/
│
├── blender_addon/              ← Blender Add-on
│   ├── __init__.py                 Entry point + preferences
│   ├── client.py                   WebSocket client
│   ├── handler.py                  Mesh import pipeline
│   ├── operators.py                Sync, Face Group tools
│   ├── ui.py                       N-Panel UI
│   ├── i18n.py                     Korean / English strings
│   ├── step_import.py              STEP/STP file import (OCP)
│   ├── progress.py                 Viewport progress bar
│   ├── state.py                    Global state
│   └── libs/websockets/            Bundled WebSocket library
│
├── fusion_addin/               ← Fusion 360 Add-in
│   ├── fusion_to_blender_addon_fusion.py        Entry point (name must match folder)
│   ├── fusion_to_blender_addon_fusion.manifest  Add-in manifest (name must match folder)
│   ├── server.py                   WebSocket server
│   ├── exporter.py                 BRep → mesh + face groups
│   ├── i18n.py                     Korean / English strings
│   └── resources/                  Icons
│
├── docs/demo.gif               Demo animation
├── build.py                    Blender ZIP builder
├── build_fusion.py             Fusion ZIP builder
├── LICENSE                     GPL-3.0 전문
└── NOTICE                      코드 외 자산(브랜드·홍보물)의 권리 고지
```

## Technical Details

- **Mesh pipeline** — per-BRep-face tessellation → 1 um vertex dedup → Plasticity-style custom split normals
- **Unit conversion** — Fusion (cm) → Blender (m), automatic x0.01
- **Protocol** — WebSocket + zlib-compressed JSON with Base64 binary mesh data
- **Compression** — server-side zlib level 1 for low-latency streaming

### Tests

Two suites, split by whether they need Blender:

```bash
python -m pytest
```
Pure helpers from `fusion_addin/exporter.py`: matrix maths and occurrence-path
handling. Runs anywhere; no Blender, no Fusion.

```bash
blender --background --factory-startup --python tests/test_preservation_blender.py
```
The re-sync promise: hand-marked Sharp / Seam / Bevel Weight, materials and their
per-face assignment, UVs and modifiers all survive the `clear_geometry()` that a
sync performs. Needs Blender because that logic is `bpy` all the way down.

---

## Support This Project

<p align="center">
  이 프로젝트가 도움이 되었다면 후원을 부탁드립니다!<br>
  If this project helps your workflow, consider supporting it:
</p>

<p align="center">
  <a href="https://ko-fi.com/inspace9018gmailcom"><img src="https://img.shields.io/badge/☕_Buy_me_a_coffee-Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Ko-fi"></a>
</p>

## License

**GPL-3.0-or-later** — 자유롭게 쓰고, 고치고, 상업적으로도 사용할 수 있습니다.
다만 **고친 것을 배포한다면 소스도 같은 GPL로 함께 공개**해야 합니다.

코드가 아닌 것(브랜드명·로고·데모 영상·스토어 리스팅 문구 등)은 GPL 대상이 아닙니다. [`NOTICE`](NOTICE)를 참고하세요.

**GPL-3.0-or-later** — free to use, modify, and use commercially. If you distribute a modified
version, you must release its source under the same license. Non-code assets (brand, demo media,
listing copy) are not covered. See [`NOTICE`](NOTICE).

---

<p align="center">
  <sub><i>Fusion 360 is a trademark of Autodesk, Inc. This project is not affiliated with or endorsed by Autodesk.</i></sub>
</p>
