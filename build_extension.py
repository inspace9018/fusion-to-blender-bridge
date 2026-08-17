"""Build the Blender extension package (extensions.blender.org).

    python build_extension.py [--blender "C:/Program Files/.../blender.exe"]

Different from build.py in two ways that matter:

  * The package is driven by ``blender_manifest.toml``, not ``bl_info`` -- the
    extensions platform reads the manifest, and Blender synthesises a bl_info
    from it for compatibility.
  * ``step_import.py`` is left out. The STEP reader needs a CAD kernel whose
    wheels total ~150 MB per platform (OpenCascade, plus VTK, which its loader
    demands even though nothing here calls it) and which ships its own numpy
    beside Blender's. The platform's limit is 100 MB, and two numpys in one
    process is the worse problem of the two. The add-on notices the module is
    gone and hides every STEP control rather than leaving dead buttons.

The version is read from bl_info so the two builds can never drift apart.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "blender_addon")
EXT = os.path.join(HERE, "extension")
STAGE = os.path.join(HERE, "build", "extension_stage")
OUT = os.path.join(HERE, "build")

# Files that exist in the add-on but must not reach the extensions platform.
EXCLUDE_FILES = {"step_import.py"}
EXCLUDE_DIRS = {"__pycache__"}

DEFAULT_BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"


def addon_version() -> str:
    src = open(os.path.join(SRC, "__init__.py"), encoding="utf-8").read()
    m = re.search(r'"version"\s*:\s*\((\d+),\s*(\d+),\s*(\d+)\)', src)
    if not m:
        raise SystemExit("Could not read version from blender_addon/__init__.py")
    return ".".join(m.groups())


def sync_manifest_version(path: str, version: str):
    """Keep the manifest's version equal to bl_info's, rather than trusting a human."""
    text = open(path, encoding="utf-8").read()
    new = re.sub(r'^version\s*=\s*"[^"]*"',
                 f'version = "{version}"', text, count=1, flags=re.M)
    if new != text:
        open(path, "w", encoding="utf-8").write(new)
        print(f"  manifest version -> {version}")


def stage():
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)

    kept = skipped = 0
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), SRC).replace("\\", "/")
            if fn in EXCLUDE_FILES or fn.endswith(".pyc"):
                print(f"  excluded: {rel}")
                skipped += 1
                continue
            dst = os.path.join(STAGE, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(root, fn), dst)
            kept += 1

    for name in ("LICENSE", "NOTICE"):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(STAGE, name))
            kept += 1
        else:
            print(f"  WARNING: {name} missing -- the package will ship without it")

    shutil.copy2(os.path.join(EXT, "blender_manifest.toml"),
                 os.path.join(STAGE, "blender_manifest.toml"))
    print(f"  staged {kept} file(s), excluded {skipped}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", default=DEFAULT_BLENDER)
    args = ap.parse_args()

    version = addon_version()
    print(f"Fusion to Blender Lite {version} -- extension build")
    sync_manifest_version(os.path.join(EXT, "blender_manifest.toml"), version)
    stage()

    os.makedirs(OUT, exist_ok=True)
    cmd = [args.blender, "--factory-startup", "--command", "extension", "build",
           "--source-dir", STAGE, "--output-dir", OUT]
    print("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # Blender prints a lot of unrelated add-on chatter on startup; only the build
    # lines matter, and a failure has to be loud.
    for line in (proc.stdout + proc.stderr).splitlines():
        if any(k in line.lower() for k in ("error", "warning: ", "created", ".zip", "fail")):
            print("  " + line.strip())
    if proc.returncode != 0:
        raise SystemExit(f"extension build failed (exit {proc.returncode})")

    for fn in sorted(os.listdir(OUT)):
        if fn.endswith(".zip"):
            size = os.path.getsize(os.path.join(OUT, fn)) / 1024
            print(f"  {fn}  ({size:.0f} KB)")


if __name__ == "__main__":
    main()
