"""Expected geometry is deliberately independent of candidate parameters/checks."""

from math import cos, sin, radians, sqrt
from ...paths import WORKFLOW_ROOT


PROMPTS = {
    "square-mount": "Create a 60 x 60 x 4 mm plate with four diameter 3.5 mm through-holes at (plus/minus 15.5, plus/minus 15.5) mm. Bottom is Z=0. A centered 42.3 x 42.3 x 40 mm motor envelope starts at Z=4 mm; a 4 x 20 x 10 mm cable keepout starts at X=25.15 mm, Y=-10 mm, Z=4 mm. Minimum motor-to-keepout clearance is 3 mm. These are illustrative interface dimensions, not a NEMA certification.",
    "circular-plate": "Create a circular diameter 70 mm, thickness 8 mm plate, bottom Z=0. Add a centered diameter 20 mm through-bore and six diameter 5.5 mm through-holes on a centered diameter 50 mm bolt circle; first hole on +X. Keep the parametric source editable.",
    "flange": "Create an illustrative flange: outside diameter 70 mm, flange thickness 8 mm, concentric hub diameter 36 mm with overall height 18 mm, and diameter 20 mm through-bore. Six diameter 5.5 mm holes lie on a diameter 50 mm bolt circle, first on +X. This is not a pressure-rated part.",
    "enclosure": "Create a base and lid with usable cavity 60 x 40 x 20 mm, explicitly excluding the 2.4 mm floor. Walls and lid are 2.4 mm; skirt depth is 3 mm, skirt wall 2 mm, skirt clearance 0.30 mm per side. Bottom is Z=0; centered XY. This nominal fit allowance is not physically validated.",
}


def requirement(req_id, binding, *, expected=None, minimum=None, maximum=None,
                unit="mm", tolerance=0.01, mandatory=True):
    criteria = {}
    if expected is not None:
        criteria.update(expected=expected, absolute_tolerance=tolerance)
    if minimum is not None:
        criteria["minimum"] = minimum
    if maximum is not None:
        criteria["maximum"] = maximum
    return {"id": req_id, "description": req_id.replace(".", " "), "mandatory": mandatory,
            "evidence_kind": "geometry-derived", "prompt_ref": "prompt.txt", "unit": unit,
            "binding": binding, "criteria": criteria}


def bbox(req_id, component, axis, value, quantity="size"):
    return requirement(req_id, {"type": "bbox", "component": component, "axis": axis, "quantity": quantity}, expected=value)


def cylinders(component, points, diameter, extent, *, prefix="holes", count=None):
    # Broad enough to detect wrong diameters, narrow enough to exclude a central bore.
    selector = {"radius_min_mm": 0.5, "radius_max_mm": 4.0, "axis_direction": [0, 0, 1]}
    reqs = [requirement(prefix + ".count", {"type": "hole-pattern", "component": component,
                         "selector": selector, "value_path": "count"}, expected=count or len(points), unit=None, tolerance=0)]
    for index, (x, y) in enumerate(points):
        local = {**selector, "axis_location_mm": [x, y, 0], "location_tolerance_mm": 0.01}
        for suffix, path, value, unit in (("diameter", "diameter_mm", diameter, "mm"),
                                          ("extent", "extent_mm", extent, "mm"),
                                          ("full", "angular_span_deg", 360, "deg")):
            reqs.append(requirement(f"{prefix}.h{index}.{suffix}", {"type": "cylinder", "component": component,
                                    "selector": local, "value_path": path}, expected=value, unit=unit))
    return reqs


def central_bore(component, extent):
    return [requirement("bore." + suffix, {"type": "cylinder", "component": component,
             "selector": {"axis_direction": [0, 0, 1], "axis_location_mm": [0, 0, 0],
                          "location_tolerance_mm": 0.01, "concavity": "concave"}, "value_path": path}, expected=value, unit=unit)
            for suffix, path, value, unit in (("diameter", "diameter_mm", 20, "mm"),
                                             ("extent", "extent_mm", extent, "mm"),
                                             ("full", "angular_span_deg", 360, "deg"))]


def get_case(name):
    if name not in PROMPTS:
        raise ValueError(f"unknown benchmark: {name}")
    brief = {"schema": "designworkflow.brief", "schema_version": "1", "id": name, "revision": 1,
             "domain": "simple-enclosure" if name == "enclosure" else "mounting-plate",
             "coordinate_frame": "Centered XY; bottom Z=0; positive Z is height.",
             "printable_components": ["base", "lid"] if name == "enclosure" else ["flange"] if name == "flange" else ["plate"],
             "dimensions": {}, "questions": [], "assumptions": [],
             "physical_validation_gaps": ["Physical fit, process suitability, material capability, and performance have not been tested."],
             "requirements": []}
    reqs = brief["requirements"]
    template = WORKFLOW_ROOT / "templates/mounting-plate"
    values = {}
    if name in {"square-mount", "circular-plate", "flange"}:
        component = "flange" if name == "flange" else "plate"
        size, height = (60, 4) if name == "square-mount" else (70, 18 if name == "flange" else 8)
        reqs += [bbox("plate." + axis.lower(), component, axis, value) for axis, value in (("X", size), ("Y", size), ("Z", height))]
        reqs.append(bbox("plate.bottom", component, "Z", 0, "min"))
        reqs.append(requirement("plate.solids", {"type": "solid-count", "component": component}, expected=1, unit=None, tolerance=0))
        reqs.append(requirement("plate.printable-count", {"type": "printable-count"}, expected=1, unit=None, tolerance=0))
        if name == "square-mount":
            points = [(x, y) for x in (-15.5, 15.5) for y in (-15.5, 15.5)]
            reqs += cylinders(component, points, 3.5, 4)
            pattern_selector = {"radius_min_mm": 0.5, "radius_max_mm": 4.0, "axis_direction": [0, 0, 1]}
            for suffix, value_path, value in (("diameter", "bolt_circle_diameter_mm", 31 * sqrt(2)),
                                              ("center", "centroid_uv_mm", 0),
                                              ("radial", "maximum_radial_residual_mm", 0),
                                              ("angular", "maximum_angular_residual_deg", 0)):
                reqs.append(requirement("pattern." + suffix, {"type": "hole-pattern", "component": component,
                                         "selector": pattern_selector, "value_path": value_path},
                                         expected=value, unit="deg" if suffix == "angular" else "mm"))
            for c, dims in (("motor-envelope", (42.3, 42.3, 40)), ("cable-keepout", (4, 20, 10))):
                reqs += [bbox(c + "." + a.lower(), c, a, v) for a, v in zip("XYZ", dims)]
                reqs.append(bbox(c + ".bottom", c, "Z", 4, "min"))
            # Keepout X is a design variable; minimum distance is normative.
            reqs += [bbox("motor.center-x", "motor-envelope", "X", 0, "center"),
                     bbox("motor.center-y", "motor-envelope", "Y", 0, "center"),
                     bbox("keepout.center-y", "cable-keepout", "Y", 0, "center"),
                     bbox("keepout.start-x", "cable-keepout", "X", 25.15, "min"),
                     requirement("cable.clearance", {"type": "clearance", "components": ["motor-envelope", "cable-keepout"], "value_path": "distance_mm"}, minimum=3),
                     requirement("cable.interference", {"type": "interference", "components": ["motor-envelope", "cable-keepout"]}, maximum=1e-7, unit="mm^3")]
        else:
            points = [(25 * cos(radians(i * 60)), 25 * sin(radians(i * 60))) for i in range(6)]
            reqs += cylinders(component, points, 5.5, 8)
            reqs += central_bore(component, height)
            if name == "circular-plate":
                values = {"size_x": 70.0, "size_y": 70.0, "thickness": 8.0, "circular": True,
                          "pattern": "circle", "hole_count": 6, "hole_diameter": 5.5,
                          "bore_diameter": 20.0, "reference_envelopes": False}
            else:
                template = WORKFLOW_ROOT / "templates/flange"
                # The selected outer convex cylinder independently establishes the hub.
                reqs.append(requirement("hub.diameter", {"type": "cylinder", "component": "flange",
                    "selector": {"concavity": "convex", "radius_min_mm": 17, "radius_max_mm": 19},
                    "value_path": "diameter_mm"}, expected=36))
    else:
        template = WORKFLOW_ROOT / "templates/enclosure"
        reqs += [requirement("assembly.printable-count", {"type": "printable-count"}, expected=2, unit=None, tolerance=0),
                 requirement("assembly.interference", {"type": "interference", "components": ["base", "lid"]}, maximum=1e-5, unit="mm^3")]
        for c, dims in (("base", (64.8, 44.8, 22.4)), ("lid", (64.8, 44.8, 5.4))):
            reqs += [bbox(c + "." + a.lower(), c, a, v) for a, v in zip("XYZ", dims)]
            reqs.append(requirement(c + ".solids", {"type": "solid-count", "component": c}, expected=1, unit=None, tolerance=0))
        # Explicit material chord samples; no claim about global minimum thickness.
        for suffix, component, point, direction, expected in (
            ("floor", "base", [0, 0, 1.2], [0, 0, 1], 2.4),
            ("x-wall", "base", [31.2, 0, 10], [1, 0, 0], 2.4),
            ("y-wall", "base", [0, 21.2, 10], [0, 1, 0], 2.4),
            ("lid", "lid", [0, 0, 23.6], [0, 0, 1], 2.4),
            ("skirt", "lid", [28.7, 0, 21], [1, 0, 0], 2.0)):
            reqs.append(requirement("sample." + suffix, {"type": "thickness", "component": component,
                                     "points_mm": [point], "direction": direction, "value_path": "minimum_mm"}, expected=expected))
        brief["assumptions"].append({"description": "0.30 mm per-side skirt clearance is a nominal allowance, not physically verified; thickness checks cover listed samples only.", "blocking": False})
        reqs.append(requirement("skirt.clearance", {"type": "clearance", "components": ["base", "lid"],
                               "z_slab_mm": [19.5, 22.0], "value_path": "distance_mm"}, expected=0.30))
        reqs.append({"id": "fit.physical", "description": "Physical lid fit", "mandatory": False,
                     "evidence_kind": "external", "prompt_ref": "prompt.txt", "binding": {"type": "physical"}, "criteria": {}})
    brief["dimensions"]["overall-x"] = {"value": 64.8 if name == "enclosure" else 60 if name == "square-mount" else 70,
        "unit": "mm", "source": "calculation" if name == "enclosure" else "user-statement", "prompt_ref": "prompt.txt"}
    return {"prompt": PROMPTS[name], "brief": brief, "template": template, "variant_values": values}
