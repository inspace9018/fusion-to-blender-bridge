"""
Fusion to Blender - Lighting Presets for Industrial Design
Studio lighting setups that auto-scale to product bounding box.
"""

# Fusion to Blender Lite
# Copyright (C) 2026 inspace
#
# This file is part of Fusion to Blender Lite.
#
# Fusion to Blender Lite is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.

import bpy
import mathutils


PRESETS = {
    "3point": {
        "lights": [
            {
                "name": "Key", "type": "AREA", "energy": 500, "size": 2.0,
                "color": (1.0, 0.98, 0.95),
                "offset": (1.5, -1.5, 1.8),  # multiplied by bbox_radius
                "track": True,
            },
            {
                "name": "Fill", "type": "AREA", "energy": 200, "size": 3.0,
                "color": (0.9, 0.95, 1.0),
                "offset": (-2.0, -0.8, 1.2),
                "track": True,
            },
            {
                "name": "Rim", "type": "AREA", "energy": 400, "size": 1.5,
                "color": (1.0, 1.0, 1.0),
                "offset": (0.0, 2.0, 1.5),
                "track": True,
            },
        ],
    },
    "product": {
        "lights": [
            {
                "name": "Key", "type": "AREA", "energy": 400, "size": 4.0,
                "color": (1.0, 0.99, 0.96),
                "offset": (1.2, -1.8, 1.5),
                "track": True,
            },
            {
                "name": "Fill", "type": "AREA", "energy": 300, "size": 5.0,
                "color": (0.92, 0.96, 1.0),
                "offset": (-2.0, -0.5, 1.0),
                "track": True,
            },
            {
                "name": "Top", "type": "AREA", "energy": 200, "size": 6.0,
                "color": (1.0, 1.0, 1.0),
                "offset": (0.0, 0.0, 3.0),
                "track": True,
            },
            {
                "name": "Edge", "type": "AREA", "energy": 250, "size": 1.0,
                "color": (1.0, 1.0, 1.0),
                "offset": (2.5, 1.0, 0.5),
                "track": True,
            },
        ],
    },
    "dramatic": {
        "lights": [
            {
                "name": "Key", "type": "AREA", "energy": 800, "size": 1.0,
                "color": (1.0, 0.95, 0.9),
                "offset": (1.8, -1.2, 2.0),
                "track": True,
            },
            {
                "name": "Accent", "type": "SPOT", "energy": 300, "size": 0.5,
                "color": (0.85, 0.92, 1.0),
                "offset": (-1.0, 2.0, 0.8),
                "track": True,
                "spot_size": 0.6,
            },
        ],
    },
    "minimal": {
        "lights": [
            {
                "name": "Key", "type": "AREA", "energy": 600, "size": 3.0,
                "color": (1.0, 1.0, 1.0),
                "offset": (1.5, -1.5, 2.0),
                "track": True,
            },
        ],
    },
}


def compute_fusion_bbox():
    """Compute bounding box center and radius of all Fusion objects."""
    fusion_objs = [o for o in bpy.data.objects
                   if "fusion_id" in o and o.type == 'MESH' and not o.hide_viewport]
    if not fusion_objs:
        fusion_objs = [o for o in bpy.data.objects
                       if "fusion_id" in o and o.type == 'MESH']
    if not fusion_objs:
        return mathutils.Vector((0, 0, 0)), 1.0

    all_min = mathutils.Vector((float('inf'),) * 3)
    all_max = mathutils.Vector((float('-inf'),) * 3)

    for obj in fusion_objs:
        bb = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
        for v in bb:
            for i in range(3):
                if v[i] < all_min[i]:
                    all_min[i] = v[i]
                if v[i] > all_max[i]:
                    all_max[i] = v[i]

    center = (all_min + all_max) / 2.0
    radius = max((all_max - all_min).length / 2.0, 0.01)
    return center, radius


def create_lights_for_preset(preset_key, concept_name, collection):
    """Create lights in the given collection based on the preset.
    Returns list of created light objects.
    """
    preset = PRESETS.get(preset_key)
    if not preset:
        return []

    center, radius = compute_fusion_bbox()
    scale = max(radius, 0.1)

    created = []
    for spec in preset["lights"]:
        light_name = f"{spec['name']}_{concept_name}"

        light_data = bpy.data.lights.new(name=light_name, type=spec["type"])
        light_data.energy = spec["energy"] * (scale ** 2)
        light_data.color = spec["color"]

        if spec["type"] == "AREA":
            light_data.shape = 'RECTANGLE'
            light_data.size = spec["size"] * scale
            light_data.size_y = spec["size"] * scale * 0.7
        elif spec["type"] == "SPOT":
            light_data.spot_size = spec.get("spot_size", 0.8)
            light_data.shadow_soft_size = spec.get("size", 0.5) * scale

        light_obj = bpy.data.objects.new(name=light_name, object_data=light_data)

        offset = mathutils.Vector(spec["offset"]) * scale
        light_obj.location = center + offset

        if spec.get("track"):
            constraint = light_obj.constraints.new(type='TRACK_TO')
            target_empty_name = f"_ftb_target_{concept_name}"
            target = bpy.data.objects.get(target_empty_name)
            if target is None:
                target = bpy.data.objects.new(target_empty_name, None)
                target.location = center
                target.empty_display_size = 0.01
                target.hide_viewport = True
                collection.objects.link(target)
            constraint.target = target
            constraint.track_axis = 'TRACK_NEGATIVE_Z'
            constraint.up_axis = 'UP_Y'

        collection.objects.link(light_obj)
        created.append(light_obj)

    return created


def remove_lights_from_collection(collection):
    """Remove all light objects and target empties from a concept collection."""
    to_remove = []
    for obj in collection.objects:
        if obj.type == 'LIGHT' or obj.name.startswith("_ftb_target_"):
            to_remove.append(obj)
    for obj in to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)
