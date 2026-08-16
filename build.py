"""
Blender Add-on ZIP 패키징 스크립트
실행: python build.py
결과: fusion_to_blender_addon_blender.zip (Blender 설치용)

Blender ZIP 규칙:
  ZIP 내부에 최상위 폴더가 있어야 하며, __init__.py는 그 안에 있어야 함.
  소스는 blender_addon/ 에 있지만 ZIP 안에서는
  fusion_to_blender_addon_blender/ 이름으로 패키징된다.
"""
import os
import zipfile

SRC_DIR = "blender_addon"
ZIP_ADDON_NAME = "fusion_to_blender_addon_blender"
OUTPUT_ZIP = "fusion_to_blender_addon_blender.zip"

EXCLUDE = {"__pycache__", ".DS_Store", "Thumbs.db", "*.pyc", "speedups.c"}


def should_exclude(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDE or part.endswith(".pyc"):
            return True
    return False


def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(script_dir, SRC_DIR)
    output_path = os.path.join(script_dir, OUTPUT_ZIP)

    if not os.path.isdir(src_path):
        print(f"Error: {SRC_DIR}/ folder not found.")
        return

    count = 0
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE]
            for file in files:
                file_path = os.path.join(root, file)
                rel = os.path.relpath(file_path, src_path).replace("\\", "/")
                if should_exclude(rel):
                    continue
                arcname = f"{ZIP_ADDON_NAME}/{rel}"
                zf.write(file_path, arcname)
                count += 1

        # GPL 요건: 배포물에 라이선스 전문이 함께 있어야 한다.
        # NOTICE 는 코드(GPL)와 마케팅 에셋(All rights reserved)의 경계를 알린다.
        for name in ("LICENSE", "NOTICE"):
            path = os.path.join(script_dir, name)
            if os.path.exists(path):
                zf.write(path, f"{ZIP_ADDON_NAME}/{name}")
                count += 1
            else:
                print(f"Warning: {name} not found — the zip will ship without it.")

    size_kb = os.path.getsize(output_path) / 1024
    print(f"Built {OUTPUT_ZIP}  ({count} files, {size_kb:.0f} KB)")


if __name__ == "__main__":
    build()
