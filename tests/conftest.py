"""Pytest configuration for headless unit tests.

Only *pure* helpers are tested here — functions with no Blender (`bpy`) or
Fusion (`adsk`) runtime dependency. `fusion_addin/exporter.py` imports `adsk`
behind a guarded `try/except ImportError`, so it imports cleanly without Fusion
installed; we add that folder to `sys.path` for a direct `import exporter`.
"""
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_ROOT)

sys.path.insert(0, os.path.join(_PROJECT, "fusion_addin"))

# Before exporter is imported: it resolves its log path at import time and would
# otherwise append to the log in the user's Documents. That file is read when
# diagnosing real syncs, and a test run's fake appearance names showing up in it
# is noise in the middle of the evidence.
os.environ.setdefault(
    "FTB_LOG_PATH",
    os.path.join(tempfile.gettempdir(), "ftb_test_log.txt"),
)

# Files that must run INSIDE Blender, not under pytest. They are named test_*.py
# so they read like tests and are easy to find, which also means pytest tries to
# collect them and dies importing `bpy`. Launch them with:
#
#   blender --background --factory-startup --python tests/<name>.py
#
# Keep this list in step with the README's Tests section.
collect_ignore = [
    "test_preservation_blender.py",
    "test_joint_sides_blender.py",
    "test_appearance_blender.py",
    "test_file_load_blender.py",
]
