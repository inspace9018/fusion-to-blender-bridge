"""Reading a Fusion appearance into something Blender can use.

Fusion appearances are Autodesk material definitions, not PBR materials, and
their property names differ per definition family. There is no schema to read,
so the exporter searches by keyword -- which means the searching itself is the
thing worth testing, with stand-ins named the way real appearances are.
"""
import exporter


class Color:
    def __init__(self, r, g, b, opacity=255):
        self.red, self.green, self.blue, self.opacity = r, g, b, opacity


class Prop:
    def __init__(self, name, value, prop_id=None):
        self.name = name
        self.id = prop_id or name
        self.value = value


class Appearance:
    def __init__(self, name, *props):
        self.name = name
        self.appearanceProperties = list(props)


class Body:
    def __init__(self, appearance=None, component_appearance=None):
        self.appearance = appearance
        if component_appearance is not None:
            self.parentComponent = type("C", (), {
                "material": type("M", (), {"appearance": component_appearance})()
            })()


class Occ:
    def __init__(self, appearance=None):
        self.appearance = appearance


def test_a_named_colour_property_wins():
    a = Appearance("Paint - Red",
                   Prop("Reflectivity", 0.4),
                   Prop("Surface Color", Color(255, 0, 0)))
    got = exporter._appearance_to_dict(a)
    assert got["name"] == "Paint - Red"
    assert got["color"][:3] == [1.0, 0.0, 0.0]


def test_any_colour_is_used_when_none_is_named_as_the_base():
    a = Appearance("Odd", Prop("Fleck", Color(0, 0, 255)))
    assert exporter._appearance_to_dict(a)["color"][:3] == [0.0, 0.0, 1.0]


def test_the_named_one_wins_even_when_another_colour_comes_first():
    a = Appearance("Flecked",
                   Prop("Fleck Color", Color(0, 255, 0)),
                   Prop("albedo", Color(255, 255, 255)))
    assert exporter._appearance_to_dict(a)["color"][:3] == [1.0, 1.0, 1.0]


def test_opacity_becomes_alpha():
    a = Appearance("Glass", Prop("Color", Color(255, 255, 255, opacity=51)))
    assert abs(exporter._appearance_to_dict(a)["color"][3] - 0.2) < 1e-6


def test_roughness_is_read_directly():
    a = Appearance("Matte", Prop("Roughness", 0.8))
    assert exporter._appearance_to_dict(a)["roughness"] == 0.8


def test_glossiness_is_inverted_into_roughness():
    """Autodesk stores shininess the other way round from Blender."""
    a = Appearance("Shiny", Prop("Glossiness", 0.9))
    assert abs(exporter._appearance_to_dict(a)["roughness"] - 0.1) < 1e-6


def test_metallic_is_read():
    a = Appearance("Steel", Prop("Metalness", 1.0))
    assert exporter._appearance_to_dict(a)["metallic"] == 1.0


def test_a_missing_property_is_omitted_not_defaulted():
    """A roughness Fusion never specified must not arrive as 0.0 -- that would
    make every unspecified surface a mirror."""
    got = exporter._appearance_to_dict(Appearance("Plain", Prop("Color", Color(1, 2, 3))))
    assert "roughness" not in got and "metallic" not in got


def test_a_name_alone_is_still_worth_sending():
    """It lets the Blender side share one material per appearance."""
    assert exporter._appearance_to_dict(Appearance("Anodised")) == {"name": "Anodised"}


def test_nothing_at_all_returns_nothing():
    assert exporter._appearance_to_dict(None) is None
    assert exporter._appearance_to_dict(Appearance("")) is None


# ── which appearance actually shows on the body ──────────────────────────────
def test_the_body_beats_the_occurrence():
    body = Body(appearance=Appearance("Body Red", Prop("Color", Color(255, 0, 0))))
    occ = Occ(appearance=Appearance("Occ Blue", Prop("Color", Color(0, 0, 255))))
    assert exporter._body_appearance(body, occ)["name"] == "Body Red"


def test_the_occurrence_is_used_when_the_body_has_none():
    """Painting a whole occurrence is how assemblies actually get coloured."""
    body = Body(appearance=None)
    occ = Occ(appearance=Appearance("Occ Blue", Prop("Color", Color(0, 0, 255))))
    assert exporter._body_appearance(body, occ)["name"] == "Occ Blue"


def test_the_component_material_is_the_last_resort():
    body = Body(appearance=None,
                component_appearance=Appearance("ABS", Prop("Color", Color(200, 200, 200))))
    assert exporter._body_appearance(body, None)["name"] == "ABS"


# ── reading them cannot be allowed to stall a sync ───────────────────────────
# The first real run froze at "Fusion Computing...". Autodesk appearances are
# not cheap property lookups -- reading one can make Fusion resolve a material
# library -- and this was reading one per body.
class CountingAppearance(Appearance):
    """Counts how many times its properties are actually walked."""
    reads = 0

    @property
    def appearanceProperties(self):
        CountingAppearance.reads += 1
        return self._props

    def __init__(self, name, *props):
        self.name = name
        self._props = list(props)


class SlowAppearance(Appearance):
    """Stands in for an appearance that takes real time to read."""
    def __init__(self, name, seconds):
        self.name = name
        self._seconds = seconds

    @property
    def appearanceProperties(self):
        import time as _t
        _t.sleep(self._seconds)
        return []


def test_one_appearance_is_read_once_however_many_bodies_share_it():
    exporter.reset_appearance_budget()
    CountingAppearance.reads = 0
    shared = CountingAppearance("Aluminium", Prop("Color", Color(200, 200, 200)))
    for _ in range(16):
        exporter._body_appearance(Body(appearance=shared), None)
    assert CountingAppearance.reads == 1, CountingAppearance.reads


def test_the_cache_is_cleared_between_syncs():
    """A recolour in Fusion has to reach the next sync."""
    exporter.reset_appearance_budget()
    CountingAppearance.reads = 0
    shared = CountingAppearance("Aluminium", Prop("Color", Color(200, 200, 200)))
    exporter._body_appearance(Body(appearance=shared), None)
    exporter.reset_appearance_budget()
    exporter._body_appearance(Body(appearance=shared), None)
    assert CountingAppearance.reads == 2, CountingAppearance.reads


def test_slow_appearances_stop_being_read_rather_than_stalling_the_sync():
    """Colour is what gets dropped -- never the geometry Sync was pressed for."""
    exporter.reset_appearance_budget()
    budget = exporter._APPEARANCE_BUDGET_S
    # Distinct names, so the cache cannot absorb them.
    for i in range(6):
        exporter._body_appearance(Body(appearance=SlowAppearance(f"Slow{i}", budget / 2)), None)
    # Two reads is already the budget; anything past that must be refused.
    assert exporter._appearance_spent[0] >= budget
    CountingAppearance.reads = 0
    exporter._body_appearance(Body(appearance=CountingAppearance("Late", Prop("Color", Color(1, 2, 3)))), None)
    assert CountingAppearance.reads == 0
