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


# ── mesh quality knobs ───────────────────────────────────────────────────────
# Fusion left to itself meshes a cylindrical wall with triangles spanning the
# whole part -- measured at 7924:1 on a real body -- and Auto Bevel tears gashes
# down one of those. maxAspectRatio is the setting that stops it at the source,
# and it was never being set.
class _Calc:
    """Accepts every setting, like a current Fusion."""
    def __init__(self):
        self.applied = {}

    def __setattr__(self, name, value):
        if name == "applied":
            object.__setattr__(self, name, value)
        else:
            self.applied[name] = value


class _OldCalc(_Calc):
    """Refuses the newer settings, like an older Fusion."""
    def __setattr__(self, name, value):
        if name in ("normalTolerance", "maxAspectRatio"):
            raise AttributeError(name)
        super().__setattr__(name, value)


def test_all_three_quality_knobs_are_set():
    calc = exporter._apply_mesh_quality(_Calc(), 0.001, 0.07)
    assert calc.applied["surfaceTolerance"] == 0.001
    assert calc.applied["normalTolerance"] == 0.07
    assert calc.applied["maxAspectRatio"] == exporter._MAX_ASPECT_RATIO


def test_a_fusion_without_them_still_exports():
    """A missing setting must not cost the user their geometry."""
    calc = exporter._apply_mesh_quality(_OldCalc(), 0.001, 0.07)
    assert calc.applied["surfaceTolerance"] == 0.001
    assert "maxAspectRatio" not in calc.applied


def test_the_limit_is_loose_enough_to_be_safe():
    """Too tight multiplies the triangle count on every body."""
    assert 3.0 <= exporter._MAX_ASPECT_RATIO <= 10.0


# ── _calc_per_face_mesh's arity, and the call site that unpacks it ────────────
# This is not a made-up worry. A seventh value (per-face appearances) was added
# to the return without updating the unpack in export_body. Every body then
# raised ValueError inside export_body's broad except, came back as None, and
# the sync arrived EMPTY -- with the only evidence in Fusion's own console.
# The arity is a contract between two places in one file; pin it.
import ast
import inspect
import os


def _exporter_source():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "fusion_addin", "exporter.py")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _returned_lengths(tree, func_name):
    """How many values each `return` in `func_name` yields, tuples only."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Tuple):
                    out.append(len(sub.value.elts))
    return out


def test_calc_per_face_mesh_returns_one_shape():
    lengths = _returned_lengths(ast.parse(_exporter_source()), "_calc_per_face_mesh")
    assert lengths, "no tuple returns found -- did the function get renamed?"
    assert len(set(lengths)) == 1, f"return paths disagree: {lengths}"


def test_export_body_unpacks_exactly_what_it_gets():
    tree = ast.parse(_exporter_source())
    returned = set(_returned_lengths(tree, "_calc_per_face_mesh"))

    unpacked = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        call = node.value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "_calc_per_face_mesh"):
            continue
        for target in node.targets:
            if isinstance(target, (ast.Tuple, ast.List)):
                unpacked.append(len(target.elts))

    assert unpacked, "nobody calls _calc_per_face_mesh -- did it get renamed?"
    assert set(unpacked) == returned, (
        f"unpacked {unpacked} but the function returns {sorted(returned)}")


# ── _calc_per_face_mesh actually running, with stand-in Fusion objects ────────
# The AST checks above pin the shape. This one runs the code: a face whose own
# appearance differs from the body's has to come back in the per-face list, in
# the same order as the face groups, or the colours land on the wrong faces.
class _FakeMesh:
    def __init__(self, base):
        self.nodeCoordinatesAsDouble = [float(base), 0.0, 0.0,
                                        float(base) + 1, 0.0, 0.0,
                                        float(base) + 1, 1.0, 0.0]
        self.normalVectorsAsDouble = [0.0, 0.0, 1.0] * 3
        self.nodeIndices = [0, 1, 2]


class _FakeCalc:
    def __init__(self, base):
        self._base = base
        self.setQuality = lambda *a, **k: None

    def calculate(self):
        return _FakeMesh(self._base)


class _FakeMeshManager:
    def __init__(self, base):
        self._base = base

    def createMeshCalculator(self):
        return _FakeCalc(self._base)


class _FakeAppearance:
    def __init__(self, name):
        self.name = name
        self.id = name
        self.appearanceProperties = []


class _FakeFace:
    def __init__(self, base, appearance=None):
        self.meshManager = _FakeMeshManager(base)
        self.appearance = appearance
        self.entityToken = f"tok{base}"


class _FakeFaces:
    def __init__(self, faces):
        self._faces = faces
        self.count = len(faces)

    def item(self, i):
        return self._faces[i]


class _FakeBody:
    def __init__(self, faces):
        self.faces = _FakeFaces(faces)
        self.name = "FakeBody"


def test_per_face_appearances_line_up_with_face_groups():
    exporter.reset_appearance_budget()
    painted = _FakeAppearance("Panel Blue")
    body = _FakeBody([_FakeFace(0), _FakeFace(10, painted), _FakeFace(20)])

    result = exporter._calc_per_face_mesh(body, 0.02, 0.26)
    coords, normals, indices, groups, ids, keys, appearances = result

    assert len(groups) == 6, groups            # three faces, start+count each
    assert len(appearances) == 3, appearances
    assert appearances[0] is None and appearances[2] is None, appearances
    assert appearances[1] and appearances[1].get("name") == "Panel Blue", appearances[1]


def test_a_body_with_no_painted_faces_reports_none_throughout():
    exporter.reset_appearance_budget()
    body = _FakeBody([_FakeFace(0), _FakeFace(10)])
    *_, appearances = exporter._calc_per_face_mesh(body, 0.02, 0.26)
    assert appearances == [None, None], appearances
