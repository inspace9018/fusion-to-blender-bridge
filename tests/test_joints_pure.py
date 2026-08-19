"""export_joints: where each joint's pivot and axis actually come from.

Runs headless with stand-in objects rather than Fusion, because the thing under
test is which API property gets asked for and in what order -- and that is
exactly what went wrong in the field. A real 16-body assembly synced with its
single revolute joint pinned at (0, 0, 0): the code read only
`geometryOrOriginOne`, an as-built joint does not have it, and every fallback
below that discarded the real pivot.

The stand-ins deliberately expose ONE property each, so a test can only pass if
the exporter reached for that specific one.
"""
import math

import exporter


class Pt:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Vec:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Geo:
    """A JointGeometry: a pivot, and optionally a primary axis."""
    def __init__(self, origin_cm, axis=None):
        self.origin = Pt(*origin_cm)
        if axis is not None:
            self.primaryAxisVector = Vec(*axis)


class Motion:
    def __init__(self, joint_type=1, rotation_axis=None, slide_dir=None):
        self.jointType = joint_type
        if rotation_axis is not None:
            self.rotationAxisVector = Vec(*rotation_axis)
        if slide_dir is not None:
            self.slideDirectionVector = Vec(*slide_dir)


class Occ:
    """An occurrence sitting at a known world position, untransformed otherwise."""
    def __init__(self, path, xyz_cm=(0.0, 0.0, 0.0)):
        self.fullPathName = path
        self.assemblyContext = None
        self.transform = _Xform(xyz_cm)


class _Xform:
    """Fusion's Matrix3D.asArray() is ROW-major, so the translation sits in the
    last column (indices 3, 7, 11). Getting this backwards in the stub made the
    test fail against correct code -- worth stating rather than just fixing."""
    def __init__(self, xyz_cm):
        self._m = [1.0, 0.0, 0.0, xyz_cm[0],
                   0.0, 1.0, 0.0, xyz_cm[1],
                   0.0, 0.0, 1.0, xyz_cm[2],
                   0.0, 0.0, 0.0, 1.0]

    def asArray(self):
        return list(self._m)


class Joint:
    def __init__(self, name, motion, occ_one=None, occ_two=None, **geometry):
        self.name = name
        self.jointMotion = motion
        self.entityToken = name + "-token"
        self.occurrenceOne = occ_one
        self.occurrenceTwo = occ_two
        self.isSuppressed = False
        self.healthState = 0
        for key, value in geometry.items():
            setattr(self, key, value)


class Design:
    def __init__(self, joints=(), as_built=()):
        self.rootComponent = type("Root", (), {
            "allJoints": list(joints),
            "allAsBuiltJoints": list(as_built),
        })()


def _one(design):
    out = exporter.export_joints(design)
    assert len(out) == 1, out
    return out[0]


def _close(got, want, tol=1e-9):
    return all(abs(a - b) < tol for a, b in zip(got, want))


# ── the pivot ────────────────────────────────────────────────────────────────
def test_regular_joint_takes_its_pivot_from_geometry_one():
    j = Joint("Rev", Motion(1), geometryOrOriginOne=Geo((1.0, 2.0, 3.0)))
    # Fusion works in centimetres; Blender in metres.
    assert _close(_one(Design(joints=[j]))["origin"], [0.01, 0.02, 0.03])


def test_regular_joint_falls_through_to_geometry_two():
    """One side can be an origin-less construction; the other still knows."""
    j = Joint("Rev", Motion(1), geometryOrOriginTwo=Geo((4.0, 0.0, 0.0)))
    assert _close(_one(Design(joints=[j]))["origin"], [0.04, 0.0, 0.0])


def test_as_built_joint_pivot_comes_from_its_own_geometry():
    """The field bug: as-built joints carry `geometry`, not `geometryOrOriginOne`,
    so reading only the latter pinned them to the world origin."""
    j = Joint("AsBuilt", Motion(1), geometry=Geo((5.0, 6.0, 7.0)))
    assert _close(_one(Design(as_built=[j]))["origin"], [0.05, 0.06, 0.07])


def test_pivot_falls_back_to_the_moving_occurrence():
    j = Joint("Rigid", Motion(0), occ_two=Occ("Comp:1", (10.0, 0.0, 0.0)))
    assert _close(_one(Design(joints=[j]))["origin"], [0.1, 0.0, 0.0])


def test_pivot_of_last_resort_is_the_origin():
    j = Joint("Bare", Motion(1))
    assert _close(_one(Design(joints=[j]))["origin"], [0.0, 0.0, 0.0])


# ── the axis ─────────────────────────────────────────────────────────────────
def test_axis_comes_from_geometry_when_present():
    j = Joint("Rev", Motion(1), geometryOrOriginOne=Geo((0, 0, 0), axis=(1.0, 0.0, 0.0)))
    assert _close(_one(Design(joints=[j]))["axis"], [1.0, 0.0, 0.0])


def test_revolute_axis_comes_from_the_motion_when_no_geometry_was_picked():
    """An as-built hinge has no picked geometry but always knows what it turns
    about. Defaulting to world Z instead put the hinge on the wrong plane."""
    j = Joint("AsBuilt", Motion(1, rotation_axis=(0.0, 1.0, 0.0)))
    assert _close(_one(Design(as_built=[j]))["axis"], [0.0, 1.0, 0.0])


def test_slider_direction_comes_from_the_motion():
    j = Joint("Slide", Motion(2, slide_dir=(0.0, 0.0, -1.0)))
    assert _close(_one(Design(joints=[j]))["axis"], [0.0, 0.0, -1.0])


def test_axis_of_last_resort_is_world_up():
    j = Joint("Bare", Motion(0))
    assert _close(_one(Design(joints=[j]))["axis"], [0.0, 0.0, 1.0])


# ── the pieces around it still work ──────────────────────────────────────────
def test_joint_type_and_connected_parts_survive():
    j = Joint("Rev", Motion(1),
              occ_one=Occ("Base:1"), occ_two=Occ("Arm:1"),
              geometryOrOriginOne=Geo((0, 0, 0)))
    got = _one(Design(joints=[j]))
    assert got["joint_type"] == "Revolute"
    assert got["occ_one"] == "Base:1"
    assert got["occ_two"] == "Arm:1"


def test_a_suppressed_joint_is_not_exported():
    j = Joint("Off", Motion(1), geometryOrOriginOne=Geo((0, 0, 0)))
    j.isSuppressed = True
    assert exporter.export_joints(Design(joints=[j])) == []
