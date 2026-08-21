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


# ── Telling a painted face from an inherited one ─────────────────────────────
# The fakes above hand back appearance=None for an unpainted face. Real Fusion
# does not: face.appearance is resolved through the override chain, so an
# untouched face answers with the body's own appearance. The tests passed for
# as long as the feature was broken because the fake was more polite than
# Fusion is, so these use the honest shape.

def _entry(name, color=None):
    d = {"name": name}
    if color:
        d["color"] = color
    return d


def test_faces_that_only_inherit_send_nothing():
    """The common case: one colour, hundreds of faces, no payload.

    Every face reporting the body's appearance is what Fusion actually does.
    Before the comparison existed this produced a table entry per face, and
    the Blender side then repainted every polygon from it.
    """
    body = _entry("Plastic - Matte (Black)", [0.1, 0.1, 0.1, 1.0])
    faces = [dict(body) for _ in range(300)]
    assert exporter.build_face_appearance_payload(faces, body) is None


def test_the_one_painted_face_survives_the_filter():
    body = _entry("Plastic - Matte (Black)", [0.1, 0.1, 0.1, 1.0])
    painted = _entry("Panel Blue", [0.0, 0.2, 0.9, 1.0])
    faces = [dict(body), painted, dict(body), dict(body)]
    table, index = exporter.build_face_appearance_payload(faces, body)
    assert len(table) == 1 and table[0]["name"] == "Panel Blue", table
    assert index == [-1, 0, -1, -1], index


def test_an_occurrence_colour_is_not_overwritten_by_the_component_one():
    """The bug this filter exists for.

    _body_appearance resolves the occurrence override; the faces report the
    component's. Sending those faces made the Blender side repaint the whole
    body in the component's colour, so a part coloured per-instance in Fusion
    arrived the wrong colour -- the colour feature losing colour.
    """
    occurrence = _entry("Anodised Red", [0.8, 0.1, 0.1, 1.0])
    component = _entry("Aluminium", [0.7, 0.7, 0.7, 1.0])
    faces = [dict(component) for _ in range(12)]
    built = exporter.build_face_appearance_payload(faces, occurrence)
    assert built is not None, "a genuinely different face appearance must survive"
    table, index = built
    assert all(i == 0 for i in index), index
    # ...and the body keeps its own: nothing here rewrites result["appearance"].
    assert table[0]["name"] == "Aluminium"


def test_two_finishes_on_one_body_keep_both():
    body = _entry("Stainless Steel - Polished", [0.8, 0.8, 0.8, 1.0])
    satin = _entry("Stainless Steel - Satin", [0.6, 0.6, 0.6, 1.0])
    faces = [dict(body), satin, satin, dict(body)]
    table, index = exporter.build_face_appearance_payload(faces, body)
    assert [e["name"] for e in table] == ["Stainless Steel - Satin"], table
    assert index == [-1, 0, 0, -1], index


def test_a_body_with_no_appearance_at_all_still_gets_its_faces():
    painted = _entry("Panel Blue", [0.0, 0.2, 0.9, 1.0])
    table, index = exporter.build_face_appearance_payload([None, painted], None)
    assert index == [-1, 0], index
    assert len(table) == 1


# ── Appearances live on the instance, not on the component ───────────────────
# Bodies are read from occ.component.bRepBodies, so face.appearance answers with
# the COMPONENT's colour. Painting a face while working in the assembly stores
# the appearance on the occurrence's proxy face instead, and reading the
# component face cannot see it -- which is most of what people actually do.

class _FakeFaceList:
    def __init__(self, faces):
        self._faces = faces
        self.count = len(faces)

    def item(self, i):
        return self._faces[i]


class _FakeProxyBody:
    def __init__(self, faces):
        self.faces = _FakeFaceList(faces)


class _FakeBodyWithProxy(_FakeBody):
    """A body whose proxy faces carry paint the component's faces do not."""

    def __init__(self, faces, proxy_faces):
        super().__init__(faces)
        self._proxy = _FakeProxyBody(proxy_faces)
        self.proxy_requested_for = None

    def createForAssemblyContext(self, occurrence):
        self.proxy_requested_for = occurrence
        return self._proxy


def test_no_occurrence_means_no_proxy_lookup():
    body = _FakeBody([_FakeFace(0)])
    assert exporter._appearance_faces(body, None) is None


def test_the_instance_faces_are_used_when_there_is_an_occurrence():
    painted = _FakeAppearance("Grip Orange")
    body = _FakeBodyWithProxy(
        [_FakeFace(0), _FakeFace(10)],                       # component: bare
        [_FakeFace(0), _FakeFace(10, painted)],              # instance: painted
    )
    faces = exporter._appearance_faces(body, occurrence="Occ:1")
    assert faces is not None and body.proxy_requested_for == "Occ:1"

    exporter.reset_appearance_budget()
    *_, appearances = exporter._calc_per_face_mesh(body, 0.02, 0.26, faces)
    assert appearances[0] is None, appearances
    assert appearances[1] and appearances[1]["name"] == "Grip Orange", appearances
    # ...and reading the component's faces instead finds nothing, which is the
    # bug this exists to stop.
    exporter.reset_appearance_budget()
    *_, plain = exporter._calc_per_face_mesh(body, 0.02, 0.26)
    assert plain == [None, None], plain


def test_a_proxy_with_a_different_face_count_is_refused():
    """Colour on the wrong face is worse than colour on none.

    The two lists are matched by position, so a proxy that does not enumerate
    the same faces would paint by coincidence.
    """
    body = _FakeBodyWithProxy([_FakeFace(0), _FakeFace(10)], [_FakeFace(0)])
    assert exporter._appearance_faces(body, occurrence="Occ:1") is None


def test_a_body_that_cannot_make_a_proxy_falls_back_quietly():
    class _NoProxy(_FakeBody):
        def createForAssemblyContext(self, occurrence):
            raise RuntimeError("not in an assembly context")

    body = _NoProxy([_FakeFace(0)])
    assert exporter._appearance_faces(body, occurrence="Occ:1") is None


def test_export_body_actually_asks_for_the_instance_faces():
    """The parts are tested; this pins that they are wired together.

    Disconnecting the call site -- passing None where _appearance_faces(...)
    belongs -- left every other test in this file green, because they exercise
    _appearance_faces and _calc_per_face_mesh separately and nothing looked at
    the one line that joins them. The feature would have been dead again with a
    full green suite, which is how it got here the first time.
    """
    tree = ast.parse(_exporter_source())
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_calc_per_face_mesh"):
            continue
        args = node.args
        assert len(args) >= 4, (
            "_calc_per_face_mesh is called without the appearance faces, so "
            "face colours are read from the component instead of the instance"
        )
        passed = args[3]
        assert isinstance(passed, ast.Call) and getattr(
            passed.func, "id", "") == "_appearance_faces", (
            f"4th argument is {ast.dump(passed)[:60]}..., not _appearance_faces(...)"
        )
        return
    raise AssertionError("_calc_per_face_mesh is never called -- was it renamed?")


def test_the_four_ways_of_not_looking_are_counted_separately():
    """"No painted faces" and "we never managed to look" must not be one silence.

    _appearance_faces gives up for four different reasons and returns the same
    None for all of them. Every bug found in this feature hid in exactly that
    kind of shared silence, so each reason is counted and reported.
    """
    exporter.reset_appearance_budget()

    class _NoProxy(_FakeBody):
        def createForAssemblyContext(self, occurrence):
            raise RuntimeError("nope")

    exporter._appearance_faces(_FakeBody([_FakeFace(0)]), None)
    exporter._appearance_faces(_NoProxy([_FakeFace(0)]), "Occ:1")
    exporter._appearance_faces(
        _FakeBodyWithProxy([_FakeFace(0), _FakeFace(10)], [_FakeFace(0)]), "Occ:1")
    exporter._appearance_faces(
        _FakeBodyWithProxy([_FakeFace(0)], [_FakeFace(0)]), "Occ:1")

    assert exporter._instance_faces == {
        "no_occurrence": 1, "unavailable": 1, "count_mismatch": 1, "used": 1,
    }, exporter._instance_faces


def test_the_report_says_when_the_instance_could_not_be_read():
    exporter.reset_appearance_budget()
    said = []
    original = exporter._log
    exporter._log = said.append
    try:
        exporter._appearance_faces(_FakeBodyWithProxy([_FakeFace(0)], [_FakeFace(0)]),
                                   "Occ:1")
        exporter._appearance_faces(_FakeBody([_FakeFace(0)]), None)
        exporter.log_instance_face_report()
    finally:
        exporter._log = original
    joined = " ".join(said)
    assert "1/2 bodies read face colours from the instance" in joined, said
    assert "not in an assembly" in joined, said
    assert "fell back to the component" in joined, said


def test_the_report_stays_quiet_when_nothing_happened():
    exporter.reset_appearance_budget()
    said = []
    original = exporter._log
    exporter._log = said.append
    try:
        exporter.log_instance_face_report()
    finally:
        exporter._log = original
    assert said == [], said


def test_each_body_says_what_fusion_answered_for_its_faces():
    """Printed even when every face agrees -- that is the interesting case.

    "This body has no painted face" is a finding. Without it written down it
    reads exactly like not having looked, and telling those apart is the whole
    job when someone reports a colour that did not come through.
    """
    said = []
    original = exporter._log
    exporter._log = said.append
    try:
        exporter.log_body_face_appearances(
            _FakeBody([]),
            {"name": "Plastic - Matte (Black)"},
            [{"name": "Plastic - Matte (Black)"}] * 103,
        )
    finally:
        exporter._log = original
    line = " ".join(said)
    assert "faces=103" in line and "distinct=1" in line, said
    assert "'Plastic - Matte (Black)'x103" in line, said


def test_a_painted_face_shows_up_by_name_in_the_line():
    said = []
    original = exporter._log
    exporter._log = said.append
    try:
        exporter.log_body_face_appearances(
            _FakeBody([]),
            {"name": "Plastic - Matte (Black)"},
            [{"name": "Plastic - Matte (Black)"}] * 12 + [{"name": "Button Red"}],
        )
    finally:
        exporter._log = original
    line = " ".join(said)
    assert "distinct=2" in line and "'Button Red'x1" in line, said


class _FakeOccurrence:
    def __init__(self, referenced):
        self.isReferencedComponent = referenced


def test_the_line_says_whether_the_part_came_from_another_document():
    """A linked part is the first thing suspected when a colour goes missing.

    Measured here rather than assumed: the only body in the test design whose
    face appearances DO come through is a linked one, so "linked" is not the
    blocker -- and the line has to be able to say so.
    """
    for referenced, word in ((True, "linked"), (False, "local")):
        said = []
        original = exporter._log
        exporter._log = said.append
        try:
            exporter.log_body_face_appearances(
                _FakeBody([]), {"name": "Black"}, [{"name": "Black"}],
                _FakeOccurrence(referenced))
        finally:
            exporter._log = original
        assert word in " ".join(said), (referenced, said)


def test_a_root_body_has_no_occurrence_and_says_nothing_either_way():
    said = []
    original = exporter._log
    exporter._log = said.append
    try:
        exporter.log_body_face_appearances(_FakeBody([]), {"name": "Black"},
                                           [{"name": "Black"}])
    finally:
        exporter._log = original
    line = " ".join(said)
    assert "linked" not in line and "local" not in line, said
