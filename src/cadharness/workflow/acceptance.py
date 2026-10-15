"""Bind independent brief requirements to existing CAD-Harness checks."""

from dataclasses import replace
from copy import deepcopy

from cadharness import (
    DEFAULT_TOLERANCE, CylinderSelector, EvidenceKind,
    equals_check, range_check, geometry_measurement_check,
    measure_cylindrical_feature, measure_hole_pattern,
    measure_shape_clearance, measure_directional_thickness, interference_check, Component,
)

PREFIX = "workflow."
SUPPORTED = {"bbox", "solid-count", "printable-count", "hole-pattern", "cylinder", "clearance", "interference", "thickness"}


def bind_requirements(document, brief):
    """Return a new CADDocument; candidate checks cannot shadow acceptance checks."""
    if any(check.id.startswith(PREFIX) for check in document.checks):
        raise ValueError("candidate checks use reserved workflow. namespace")
    checks, coverage = [], []
    for req in brief["requirements"]:
        binding = req["binding"]
        kind = binding["type"]
        check_id = PREFIX + req["id"]
        row = {"id": req["id"], "mandatory": req["mandatory"], "description": req["description"],
               "evidence_kind": req["evidence_kind"], "check_id": None,
               "status": "not-yet-verified", "reason": "not evaluated"}
        coverage.append(row)
        if kind not in SUPPORTED or req["evidence_kind"] != "geometry-derived":
            row.update(status="unknown" if kind not in {"external", "physical"} else "not-yet-verified",
                       reason="No supported geometry binding; external/declared evidence is not inferred.")
            continue
        if not any(key in req.get("criteria", {}) for key in ("expected", "minimum", "maximum")):
            raise ValueError(f"{req['id']}: acceptance criteria required")
        components = tuple(binding.get("components", []))
        component = binding.get("component")
        if component:
            components = (component,)
        criteria = req["criteria"]
        common = {"unit": req.get("unit"), "components": components}
        if kind == "interference":
            if len(components) != 2 or set(criteria) != {"maximum"} or req.get("unit") != "mm^3":
                raise ValueError("interference requires two components, maximum, and mm^3")
            check = interference_check(check_id, *components, maximum_volume_mm3=criteria["maximum"], description=req["description"])
        elif kind in {"bbox", "solid-count", "printable-count"}:
            if kind == "bbox":
                if binding.get("axis") not in {"X", "Y", "Z"} or not component:
                    raise ValueError("bbox requires component and X/Y/Z axis")
                axis = binding["axis"]
                quantity = binding.get("quantity", "size")
                if quantity not in {"size", "min", "max", "center"}:
                    raise ValueError("bbox quantity must be size/min/max/center")
                def actual(doc, c=component, a=axis, q=quantity):
                    bbox = doc.components[c].shape.bounding_box()
                    return getattr(bbox.center() if q == "center" else getattr(bbox, q), a)
            elif kind == "solid-count":
                if not component:
                    raise ValueError("solid-count requires component")
                actual = lambda doc, c=component: len(doc.components[c].shape.solids())
            else:
                actual = lambda doc: sum(item.role == "printable-part" for item in doc.components.values())
            args = dict(evidence_kind=EvidenceKind.GEOMETRY, measurement_method="occt-" + kind, **common)
            if "expected" in criteria:
                check = equals_check(check_id, req["description"], actual,
                                     criteria["expected"], absolute_tolerance=criteria.get("absolute_tolerance", 0), **args)
                if "minimum" in criteria or "maximum" in criteria:
                    raise ValueError("scalar equality binding cannot also specify bounds")
            else:
                check = range_check(check_id, req["description"], actual,
                                    **{k: v for k, v in criteria.items() if k != "absolute_tolerance"}, **args)
        else:
            tolerance = DEFAULT_TOLERANCE
            if kind in {"hole-pattern", "cylinder"}:
                if not component:
                    raise ValueError(f"{kind} requires component")
                selector = CylinderSelector(component, **binding.get("selector", {}))
                operation = measure_hole_pattern if kind == "hole-pattern" else measure_cylindrical_feature
                measurement = lambda doc, op=operation, s=selector, mid=check_id: op(doc, mid, s)
                spec = {"selector": selector.to_dict(), "tolerance": tolerance.to_dict()}
                # The core cylinder report has a report-wide mm unit even though
                # angular_span_deg is an angular field. Select that quantity
                # explicitly and retain the complete original report as evidence.
                if kind == "cylinder" and binding.get("value_path") == "angular_span_deg":
                    raw_measurement = measurement
                    def measurement(doc, raw=raw_measurement):
                        result = raw(doc)
                        return replace(result, unit="deg",
                            value={"angular_span_deg": result.value["angular_span_deg"]} if result.status.value == "success" else result.value,
                            diagnostics={**result.diagnostics, "source_measurement": result.to_dict(),
                                         "selected_quantity": "angular_span_deg"})
            elif kind == "clearance":
                if len(components) != 2:
                    raise ValueError("clearance requires two components")
                slab = binding.get("z_slab_mm")
                if slab is not None and (len(slab) != 2 or slab[0] >= slab[1]):
                    raise ValueError("clearance z_slab_mm requires ascending lower/upper planes")
                def measurement(doc, cs=components, mid=check_id, z_slab=slab):
                    if z_slab is not None:
                        # Exclude seated lid contact by clipping actual shapes,
                        # not by reconstructing nominal walls or skirt geometry.
                        from build123d import Box, Pos
                        shapes = [doc.components[c].shape for c in cs]
                        boxes = [shape.bounding_box() for shape in shapes]
                        size_x = max(abs(b.min.X) + abs(b.max.X) for b in boxes) + 2
                        size_y = max(abs(b.min.Y) + abs(b.max.Y) for b in boxes) + 2
                        clip = Pos(0, 0, sum(z_slab) / 2) * Box(2 * size_x, 2 * size_y, z_slab[1] - z_slab[0])
                        clipped = {c: Component(c, deepcopy(doc.components[c].shape) & deepcopy(clip)) for c in cs}
                        doc = replace(doc, components=clipped, checks=())
                    result = measure_shape_clearance(doc, mid, *cs)
                    if z_slab is not None:
                        result = replace(result, diagnostics={**result.diagnostics, "z_slab_mm": z_slab},
                            limitations=(*result.limitations, "Clearance measured only between actual shapes clipped to the specified Z slab."))
                    return result
                spec = {"components": components, "z_slab_mm": slab, "tolerance": tolerance.to_dict()}
            else:
                if not component or not binding.get("points_mm") or not binding.get("direction"):
                    raise ValueError("thickness requires component, points_mm, direction")
                measurement = lambda doc, c=component, b=binding, mid=check_id: measure_directional_thickness(
                    doc, mid, c, b["points_mm"], b["direction"])
                spec = {"points_mm": binding["points_mm"], "direction": binding["direction"],
                        "tolerance": tolerance.to_dict()}
            check = geometry_measurement_check(
                check_id, req["description"], measurement, value_path=binding.get("value_path", ""),
                measurement_spec=spec, **criteria, **common)
        check = replace(check, requirement=replace(check.requirement,
                        origin=req["prompt_ref"], metadata={**check.requirement.metadata,
                        "brief_requirement": req["id"], "binding": binding}))
        checks.append(check)
        row["check_id"] = check_id
    return replace(document, checks=(*document.checks, *checks)), coverage


def update_coverage(coverage, validation):
    results = {item["id"]: item for item in validation["results"]}
    for row in coverage:
        if row["check_id"]:
            result = results[row["check_id"]]
            row.update(status={"pass": "pass", "fail": "fail"}.get(result["status"], "unknown"),
                       reason=result["message"], execution_status=result["status"], result=result)
    return coverage
