"""
Unified installer bundle packager.
Run: python build_installer.py
Output: fusion_to_blender_bridge_installer.zip

The bundle contains BOTH add-ons plus the cross-platform installer scripts:
    fusion_to_blender_bridge_installer/
        install.bat            (Windows)
        install.command        (macOS, executable)
        README.txt
        fusion_to_blender_addon_fusion/   (Fusion 360 add-in)
        fusion_to_blender_addon_blender/  (Blender add-on)

install.bat / install.command copy those two folders into the right place
(Fusion AddIns + Blender scripts/addons) with an Install/Update/Uninstall menu.
"""
import os
import zipfile

TOP = "fusion_to_blender_bridge_installer"
OUTPUT_ZIP = "fusion_to_blender_bridge_installer.zip"

# (source dir on disk, folder name inside the bundle)
ADDONS = [
    ("fusion_addin",  "fusion_to_blender_addon_fusion"),
    ("blender_addon", "fusion_to_blender_addon_blender"),
]
INSTALLER_FILES = ["installer/install.bat", "installer/install.command", "installer/README.txt"]

EXCLUDE_DIRS = {"__pycache__", ".DS_Store", "Thumbs.db", ".vscode"}
EXEC_FILES = (".command", ".sh")
# Installer artifacts must NOT be copied inside the add-on folders — the unified
# installer at the bundle root is the single entry point. (Keeps Fusion's AddIns
# folder clean: just the add-in, no stray install scripts.)
EXCLUDE_ADDON_FILES = {"install.bat", "install.command", "install.sh", "README.txt"}


def _line_endings_for(path, data):
    """What .gitattributes declares, enforced at package time.

    Not trusted from the working copy: the file on disk drifts, and it had --
    install.command was carrying CRLF, so its shebang ended in a carriage
    return and macOS answered "bad interpreter". A packager that copies bytes
    verbatim ships that every time.
    """
    data = data.replace(b"\r\n", b"\n")
    if path.endswith((".bat", "README.txt")):
        data = data.replace(b"\n", b"\r\n")
    return data


def _add_file(zf, disk_path, arcname):
    if disk_path.endswith(EXEC_FILES):
        with open(disk_path, "rb") as fh:
            data = _line_endings_for(disk_path, fh.read())
        zi = zipfile.ZipInfo(arcname)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o755 << 16   # keep the executable bit on macOS
        zf.writestr(zi, data)
    elif disk_path.endswith((".bat", "README.txt")):
        with open(disk_path, "rb") as fh:
            zf.writestr(arcname, _line_endings_for(disk_path, fh.read()))
    else:
        zf.write(disk_path, arcname)


def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, OUTPUT_ZIP)
    count = 0

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Installer scripts + readme at the bundle root
        for rel in INSTALLER_FILES:
            disk = os.path.join(script_dir, rel)
            if not os.path.isfile(disk):
                print(f"Error: missing {rel}")
                return
            _add_file(zf, disk, f"{TOP}/{os.path.basename(rel)}")
            count += 1

        # GPL 요건: 배포물에 라이선스 전문이 함께 있어야 한다.
        # 통합 설치본은 두 애드온을 함께 담으므로 번들 루트에 한 벌 둔다.
        for name in ("LICENSE", "NOTICE"):
            path = os.path.join(script_dir, name)
            if os.path.exists(path):
                _add_file(zf, path, f"{TOP}/{name}")
                count += 1
            else:
                print(f"Warning: {name} not found — the bundle will ship without it.")

        # Both add-ons
        for src_dir, bundle_name in ADDONS:
            src_path = os.path.join(script_dir, src_dir)
            if not os.path.isdir(src_path):
                print(f"Error: {src_dir}/ not found")
                return
            for root, dirs, files in os.walk(src_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for file in files:
                    if file.endswith((".pyc", ".pyo")):
                        continue
                    if file in EXCLUDE_ADDON_FILES:
                        continue
                    disk = os.path.join(root, file)
                    rel = os.path.relpath(disk, src_path).replace("\\", "/")
                    _add_file(zf, disk, f"{TOP}/{bundle_name}/{rel}")
                    count += 1

    size_kb = os.path.getsize(output_path) / 1024
    print(f"Built {OUTPUT_ZIP}  ({count} files, {size_kb:.0f} KB)")


if __name__ == "__main__":
    build()
