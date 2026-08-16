"""
Fusion 360 Add-in ZIP 패키징 스크립트
실행: python build_fusion.py
결과: fusion_to_blender_addon_fusion.zip (Fusion 360 설치용)
"""
import os
import zipfile

SRC_DIR = "fusion_addin"
ZIP_ADDON_NAME = "fusion_to_blender_addon_fusion"
OUTPUT_ZIP = "fusion_to_blender_addon_fusion.zip"

EXCLUDE = {"__pycache__", ".DS_Store", "Thumbs.db"}


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
                if file.endswith(".pyc"):
                    continue
                file_path = os.path.join(root, file)
                rel = os.path.relpath(file_path, src_path).replace("\\", "/")
                arcname = f"{ZIP_ADDON_NAME}/{rel}"
                if file.endswith((".command", ".sh")):
                    # Preserve the executable bit so the macOS launcher runs
                    # after extraction (zf.write drops it on Windows hosts).
                    with open(file_path, "rb") as fh:
                        data = fh.read()
                    zi = zipfile.ZipInfo(arcname)
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zi.external_attr = 0o755 << 16
                    zf.writestr(zi, data)
                else:
                    zf.write(file_path, arcname)
                count += 1

        # GPL 요건: 배포물에 라이선스 전문이 함께 있어야 한다.
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
