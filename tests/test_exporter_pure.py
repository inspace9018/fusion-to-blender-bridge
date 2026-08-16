"""Unit tests for pure (headless-importable) helpers in fusion_addin/exporter.py.

These functions have no Blender/Fusion runtime dependency, so they can be
verified automatically in CI / locally without either app installed. They cover:

* `_mat4_mul_cm` — the column-major 4x4 matrix multiply that bakes every
  occurrence's world transform. A silent regression corrupts object placement.
* occurrence-name normalization (`_strip_occ_*`, `_normalize_path`) — the logic
  that derives object identity / collection paths. A regression here can merge
  or lose objects across files (cf. bug F050).
"""
import exporter


# ── _mat4_mul_cm: column-major 4x4 matrix multiply ────────────────────────────
IDENT = [1.0, 0.0, 0.0, 0.0,
         0.0, 1.0, 0.0, 0.0,
         0.0, 0.0, 1.0, 0.0,
         0.0, 0.0, 0.0, 1.0]


def _translation(tx, ty, tz):
    """Column-major translation matrix (translation lives in the last column)."""
    return [1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            tx,  ty,  tz,  1.0]


def test_mat4_identity_is_neutral():
    m = _translation(2.0, -3.0, 4.0)
    assert exporter._mat4_mul_cm(IDENT, m) == m
    assert exporter._mat4_mul_cm(m, IDENT) == m


def test_mat4_translations_compose():
    a = _translation(1.0, 2.0, 3.0)
    b = _translation(10.0, 20.0, 30.0)
    assert exporter._mat4_mul_cm(a, b) == _translation(11.0, 22.0, 33.0)


def test_mat4_matches_numpy_reference():
    """Cross-check against a numpy column-major matrix product."""
    import numpy as np

    a = [float(i) for i in range(16)]
    b = [float(i) * 0.5 - 2.0 for i in range(16)]
    # order="F" reads the flat list column-major: M[i, j] == flat[i + j*4],
    # exactly how _mat4_mul_cm stores its operands and result.
    A = np.array(a).reshape(4, 4, order="F")
    B = np.array(b).reshape(4, 4, order="F")
    expected = (A @ B).reshape(-1, order="F")

    result = exporter._mat4_mul_cm(a, b)
    assert np.allclose(result, expected)


# ── Occurrence-name normalization ─────────────────────────────────────────────
def test_strip_occ_version_keeps_instance():
    assert exporter._strip_occ_version("External1 v16:1") == "External1:1"


def test_strip_occ_version_no_instance():
    assert exporter._strip_occ_version("Part v3") == "Part"


def test_strip_occ_version_passthrough_when_no_version():
    assert exporter._strip_occ_version("NoVersion:2") == "NoVersion:2"


def test_strip_occ_all_removes_version_and_instance():
    assert exporter._strip_occ_all("External1 v16:1") == "External1"
    assert exporter._strip_occ_all("Part:2") == "Part"
    assert exporter._strip_occ_all("Comp v5") == "Comp"


def test_normalize_path_strip_instance():
    assert exporter._normalize_path("Asm v2:1+Sub v3:2", strip_instance=True) == "Asm/Sub"


def test_normalize_path_keep_instance():
    assert exporter._normalize_path("Asm v2:1+Sub v3:2", strip_instance=False) == "Asm:1/Sub:2"


def test_normalize_path_empty_is_empty():
    assert exporter._normalize_path("") == ""
    assert exporter._normalize_path("   ") == ""
