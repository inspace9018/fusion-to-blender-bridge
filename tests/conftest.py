"""Pytest configuration for headless unit tests.

Only *pure* helpers are tested here — functions with no Blender (`bpy`) or
Fusion (`adsk`) runtime dependency. `fusion_addin/exporter.py` imports `adsk`
behind a guarded `try/except ImportError`, so it imports cleanly without Fusion
installed; we add that folder to `sys.path` for a direct `import exporter`.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_ROOT)

sys.path.insert(0, os.path.join(_PROJECT, "fusion_addin"))
