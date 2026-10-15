"""Bounded, explainable measurements of actual build123d/OCCT geometry."""

from __future__ import annotations

from copy import deepcopy

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from hashlib import sha256
from math import atan2, degrees, isclose, isfinite, pi, sqrt
from typing import Any

from build123d import Edge, Face, GeomType, Shape, Vector
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_IN, TopAbs_ON

from .model import (
    CADDocument,
    Check,
    CheckResult,
    CheckStatus,
    EvidenceKind,
    EvidenceSpec,
    Requirement,
    _require_identifier,
    json_safe,
)
from .schema import MEASUREMENT_SCHEMA, SCHEMA_VERSION, require_schema


class _InvalidInput(ValueError):
    pass


class _UnsupportedGeometry(ValueError):
    pass


def _number(value: Any, label: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _InvalidInput(f"{label} must be numeric")
    if not isfinite(value) or (nonnegative and value < 0):
        raise _InvalidInput(
            f"{label} must be finite" + (" and nonnegative" if nonnegative else "")
        )
    return float(value)


def _vector(values: Iterable[float], label: str) -> Vector:
    try:
        items = tuple(values)
    except TypeError as exc:
        raise _InvalidInput(f"{label} must contain three finite numbers") from exc
    if len(items) != 3:
        raise _InvalidInput(f"{label} must contain three finite numbers")
    return Vector(*(_number(item, label) for item in items))


class MeasurementStatus(StrEnum):
    SUCCESS = "success"
    NO_MATCH = "no-match"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    INVALID_INPUT = "invalid-input"
    KERNEL_ERROR = "kernel-error"


@dataclass(frozen=True)
class ComputationalTolerance:
    linear_mm: float = 1e-6
    angular_deg: float = 1e-4
    volume_mm3: float = 1e-7

    def __post_init__(self) -> None:
        for name in ("linear_mm", "angular_deg", "volume_mm3"):
            _number(getattr(self, name), name, nonnegative=True)
        if self.angular_deg > 90:
            raise _InvalidInput("angular_deg cannot exceed 90")

    def to_dict(self) -> dict[str, float]:
        return {
            "linear_mm": self.linear_mm,
            "angular_deg": self.angular_deg,
            "volume_mm3": self.volume_mm3,
        }


DEFAULT_TOLERANCE = ComputationalTolerance()


@dataclass(frozen=True)
class MeasurementResult:
    id: str
    type: str
    status: MeasurementStatus
    value: Any = None
    unit: str | None = None
    components: tuple[str, ...] = ()
    features: tuple[Mapping[str, Any], ...] = ()
    method: str = ""
    computational_tolerance: ComputationalTolerance = DEFAULT_TOLERANCE
    limitations: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier(self.id, "measurement id")
        if not isinstance(self.status, MeasurementStatus):
            raise TypeError("measurement status must be MeasurementStatus")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": MEASUREMENT_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "value": json_safe(self.value),
            "unit": self.unit,
            "provenance": {"kind": EvidenceKind.GEOMETRY.value},
            "components": list(self.components),
            "features": json_safe(self.features),
            "method": self.method,
            "computational_tolerance": self.computational_tolerance.to_dict(),
            "limitations": list(self.limitations),
            "diagnostics": json_safe(self.diagnostics),
        }


@dataclass(frozen=True)
class CylinderSelector:
    """Geometric constraints for analytic cylindrical faces.

    Face indices are reported only as diagnostics.  Stable selection is based
    on component identity and these geometric constraints.
    """

    component_id: str
    radius_min_mm: float | None = None
    radius_max_mm: float | None = None
    axis_direction: tuple[float, float, float] | None = None
    axis_angular_tolerance_deg: float = 0.1
    axis_location_mm: tuple[float, float, float] | None = None
    location_tolerance_mm: float = 1e-4
    concavity: str = "concave"

    def __post_init__(self) -> None:
        _require_identifier(self.component_id, "selector component id")
        if self.concavity not in {"concave", "convex", "any"}:
            raise ValueError("concavity must be 'concave', 'convex', or 'any'")
        if (
            self.radius_min_mm is not None
            and self.radius_max_mm is not None
            and self.radius_min_mm > self.radius_max_mm
        ):
            raise ValueError("radius_min_mm cannot exceed radius_max_mm")
        for name in (
            "radius_min_mm",
            "radius_max_mm",
            "axis_angular_tolerance_deg",
            "location_tolerance_mm",
        ):
            value = getattr(self, name)
            if value is not None:
                _number(value, name, nonnegative=True)
        if self.axis_angular_tolerance_deg > 90:
            raise _InvalidInput("axis_angular_tolerance_deg cannot exceed 90")
        if self.axis_direction is not None:
            _unit(self.axis_direction)
        if self.axis_location_mm is not None:
            _vector(self.axis_location_mm, "axis_location_mm")

    def to_dict(self) -> dict[str, Any]:
        return json_safe(asdict(self))


def _tuple(vector: Vector) -> tuple[float, float, float]:
    return (float(vector.X), float(vector.Y), float(vector.Z))


def _unit(vector: Iterable[float]) -> Vector:
    result = _vector(vector, "direction")
    scale = max(abs(value) for value in _tuple(result))
    if scale == 0:
        raise _InvalidInput("direction vector cannot be zero")
    return (result / scale).normalized()


def _canonical_direction(direction: Vector) -> Vector:
    values = _tuple(direction.normalized())
    for value in values:
        if abs(value) > 1e-12:
            return direction.normalized() if value > 0 else -direction.normalized()
    return direction.normalized()


def _axis_anchor(position: Vector, direction: Vector) -> Vector:
    direction = direction.normalized()
    return position - direction * position.dot(direction)


def _angle_degrees(first: Vector, second: Vector) -> float:
    first, second = first.normalized(), second.normalized()
    return degrees(atan2(first.cross(second).length, abs(first.dot(second))))


def _face_feature(face: Face, index: int) -> dict[str, Any]:
    axis = face.axis_of_rotation
    if axis is None or face.radius is None:
        raise ValueError("face is not an analytic cylinder")
    direction = _canonical_direction(axis.direction)
    anchor = _axis_anchor(axis.position, direction)
    surface = BRepAdaptor_Surface(face.wrapped, True)
    u_min, u_max = surface.FirstUParameter(), surface.LastUParameter()
    v_min, v_max = surface.FirstVParameter(), surface.LastVParameter()
    axial = sorted(
        Vector(surface.Value(u_min, v)).dot(direction) for v in (v_min, v_max)
    )
    extent = axial[1] - axial[0]
    signature = {
        "radius_mm": round(float(face.radius), 9),
        "axis_anchor_mm": [round(item, 9) for item in _tuple(anchor)],
        "axis_direction": [round(item, 9) for item in _tuple(direction)],
        "extent_mm": round(float(extent), 9),
        "axial_range_mm": [round(value, 9) for value in axial],
        "angular_span_deg": round(degrees(u_max - u_min), 9),
        "concavity": "concave" if face.is_circular_concave else "convex",
    }
    feature_id = (
        "cylinder:"
        + sha256(json.dumps(signature, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    )
    return {
        "id": feature_id,
        "topology_index": index,
        **signature,
        "radius_mm": float(face.radius),
        "axis_anchor_mm": list(_tuple(anchor)),
        "axis_direction": list(_tuple(direction)),
        "extent_mm": float(extent),
        "axial_range_mm": axial,
        "angular_span_deg": degrees(u_max - u_min),
        "diameter_mm": 2 * float(face.radius),
        "surface_area_mm2": float(face.area),
    }


def select_cylindrical_features(
    document: CADDocument,
    selector: CylinderSelector,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return matched features and all analytic-cylinder candidates."""
    if selector.component_id not in document.components:
        raise KeyError(f"unknown component id: {selector.component_id}")
    shape = _solid_shape(document, selector.component_id)
    candidates = []
    matches = []
    expected_axis = (
        _unit(selector.axis_direction) if selector.axis_direction is not None else None
    )
    expected_location = (
        _vector(selector.axis_location_mm, "axis_location_mm")
        if selector.axis_location_mm is not None
        else None
    )
    for index, face in enumerate(shape.faces()):
        if face.geom_type is not GeomType.CYLINDER:
            continue
        feature = _face_feature(face, index)
        candidates.append(feature)
        radius = float(feature["diameter_mm"]) / 2
        if selector.radius_min_mm is not None and radius < selector.radius_min_mm:
            continue
        if selector.radius_max_mm is not None and radius > selector.radius_max_mm:
            continue
        if selector.concavity != "any" and feature["concavity"] != selector.concavity:
            continue
        direction = Vector(*feature["axis_direction"])
        if (
            expected_axis is not None
            and _angle_degrees(direction, expected_axis)
            > selector.axis_angular_tolerance_deg
        ):
            continue
        if expected_location is not None:
            anchor = Vector(*feature["axis_anchor_mm"])
            comparison_direction = expected_axis or direction
            expected_anchor = _axis_anchor(expected_location, comparison_direction)
            if (anchor - expected_anchor).length > selector.location_tolerance_mm:
                continue
        matches.append(feature)
    matches.sort(key=lambda feature: (feature["id"], feature["topology_index"]))
    candidates.sort(key=lambda feature: (feature["id"], feature["topology_index"]))
    return matches, candidates


def _solid_shape(document: CADDocument, component_id: str) -> Shape:
    shape = document.components[component_id].shape
    if shape.wrapped is None or shape.wrapped.IsNull() or not shape.is_valid:
        raise _InvalidInput(
            f"component {component_id!r} must have valid, nonempty geometry"
        )
    if not shape.solids():
        raise _UnsupportedGeometry("measurement requires solid material geometry")
    return shape


def _failure(
    measurement_id: str,
    kind: str,
    components: tuple[str, ...],
    method: str,
    tolerance: ComputationalTolerance,
    exc: Exception,
) -> MeasurementResult:
    status = (
        MeasurementStatus.INVALID_INPUT
        if isinstance(exc, (KeyError, _InvalidInput))
        else (
            MeasurementStatus.UNSUPPORTED
            if isinstance(exc, _UnsupportedGeometry)
            else MeasurementStatus.KERNEL_ERROR
        )
    )
    return MeasurementResult(
        measurement_id,
        kind,
        status,
        components=components,
        method=method,
        computational_tolerance=tolerance,
        diagnostics={"error": f"{type(exc).__name__}: {exc}"},
    )


def measure_cylindrical_feature(
    document: CADDocument,
    measurement_id: str,
    selector: CylinderSelector,
    *,
    tolerance: ComputationalTolerance = DEFAULT_TOLERANCE,
) -> MeasurementResult:
    try:
        matches, candidates = select_cylindrical_features(document, selector)
    except Exception as exc:
        return _failure(
            measurement_id,
            "cylindrical-feature",
            (selector.component_id,),
            "analytic-cylinder-selector",
            tolerance,
            exc,
        )
    if not matches:
        return MeasurementResult(
            measurement_id,
            "cylindrical-feature",
            MeasurementStatus.NO_MATCH,
            components=(selector.component_id,),
            features=tuple(candidates),
            method="analytic-cylinder-selector",
            computational_tolerance=tolerance,
            diagnostics={"candidate_count": len(candidates)},
        )
    if len(matches) > 1:
        return MeasurementResult(
            measurement_id,
            "cylindrical-feature",
            MeasurementStatus.AMBIGUOUS,
            components=(selector.component_id,),
            features=tuple(matches),
            method="analytic-cylinder-selector",
            computational_tolerance=tolerance,
            diagnostics={"matched_count": len(matches)},
        )
    return MeasurementResult(
        measurement_id,
        "cylindrical-feature",
        MeasurementStatus.SUCCESS,
        value=matches[0],
        unit="mm",
        components=(selector.component_id,),
        features=tuple(matches),
        method="analytic-cylinder-selector",
        computational_tolerance=tolerance,
        limitations=(
            "Supports analytic cylindrical faces; topology indices are diagnostic only.",
            "Axial range is the trimmed surface parameter envelope.",
        ),
        diagnostics={"selector": selector.to_dict()},
    )


def measure_hole_pattern(
    document: CADDocument,
    measurement_id: str,
    selector: CylinderSelector,
    *,
    tolerance: ComputationalTolerance = DEFAULT_TOLERANCE,
) -> MeasurementResult:
    """Measure simple parallel cylindrical holes; reject unresolved feature intent."""
    method = "analytic-concave-cylinder-inventory-and-centroid-circle-fit"
    try:
        if selector.concavity != "concave":
            raise _InvalidInput("hole-pattern requires a concave cylinder selector")
        matches, candidates = select_cylindrical_features(document, selector)
    except Exception as exc:
        return _failure(
            measurement_id,
            "hole-pattern",
            (selector.component_id,),
            method,
            tolerance,
            exc,
        )
    if not matches:
        return MeasurementResult(
            measurement_id,
            "hole-pattern",
            MeasurementStatus.NO_MATCH,
            value={"count": 0},
            components=(selector.component_id,),
            features=tuple(candidates),
            method="analytic-concave-cylinder-inventory",
            computational_tolerance=tolerance,
            diagnostics={"candidate_count": len(candidates)},
        )

    direction = _canonical_direction(
        _unit(selector.axis_direction or matches[0]["axis_direction"])
    )
    limitations = (
        "Supports simple full cylindrical holes on parallel axes.",
        "Coaxial stepped or split faces require a tighter selector; no universal feature recognition.",
        "Circle and angular residuals must be checked to establish a regular pattern.",
    )

    def unresolved(status: MeasurementStatus, reason: str) -> MeasurementResult:
        return MeasurementResult(
            measurement_id,
            "hole-pattern",
            status,
            components=(selector.component_id,),
            features=tuple(matches),
            method=method,
            computational_tolerance=tolerance,
            limitations=limitations,
            diagnostics={"reason": reason, "selector": selector.to_dict()},
        )

    if any(
        _angle_degrees(direction, Vector(*feature["axis_direction"]))
        > tolerance.angular_deg
        for feature in matches
    ):
        return unresolved(
            MeasurementStatus.AMBIGUOUS, "selected cylinder axes are not parallel"
        )
    for feature in matches:
        expected_area = 2 * pi * feature["radius_mm"] * feature["extent_mm"]
        if abs(
            feature["angular_span_deg"] - 360
        ) > tolerance.angular_deg or not isclose(
            feature["surface_area_mm2"],
            expected_area,
            rel_tol=1e-8,
            abs_tol=2 * pi * feature["radius_mm"] * tolerance.linear_mm,
        ):
            return unresolved(
                MeasurementStatus.UNSUPPORTED,
                "selected faces are partial or irregularly trimmed cylinders",
            )
    for index, first in enumerate(matches):
        anchor = Vector(*first["axis_anchor_mm"])
        if any(
            (anchor - Vector(*second["axis_anchor_mm"])).length <= tolerance.linear_mm
            for second in matches[index + 1 :]
        ):
            return unresolved(
                MeasurementStatus.AMBIGUOUS,
                "multiple selected faces share an axis; possible counterbore or split hole",
            )
    reference = Vector(1, 0, 0) if abs(direction.X) < 0.9 else Vector(0, 1, 0)
    basis_u = direction.cross(reference).normalized()
    basis_v = direction.cross(basis_u).normalized()
    points = [Vector(*feature["axis_anchor_mm"]) for feature in matches]
    coordinates = [(point.dot(basis_u), point.dot(basis_v)) for point in points]
    centroid = (
        sum(point[0] for point in coordinates) / len(coordinates),
        sum(point[1] for point in coordinates) / len(coordinates),
    )
    radii = [
        sqrt((x - centroid[0]) ** 2 + (y - centroid[1]) ** 2) for x, y in coordinates
    ]
    mean_radius = sum(radii) / len(radii)
    radial_residual = max((abs(radius - mean_radius) for radius in radii), default=0.0)
    angles = sorted(atan2(y - centroid[1], x - centroid[0]) for x, y in coordinates)
    if len(angles) > 1:
        gaps = [
            (angles[(index + 1) % len(angles)] - angles[index]) % (2 * pi)
            for index in range(len(angles))
        ]
        expected_gap = 2 * pi / len(angles)
        angular_residual = degrees(max(abs(gap - expected_gap) for gap in gaps))
    else:
        angular_residual = None
    value = {
        "count": len(matches),
        "diameters_mm": [feature["diameter_mm"] for feature in matches],
        "centers_uv_mm": [[float(x), float(y)] for x, y in coordinates],
        "centroid_uv_mm": [float(centroid[0]), float(centroid[1])],
        "bolt_circle_diameter_mm": 2 * mean_radius,
        "maximum_radial_residual_mm": radial_residual,
        "maximum_angular_residual_deg": angular_residual,
        "axis_direction": list(_tuple(direction)),
        "basis_u": list(_tuple(basis_u)),
        "basis_v": list(_tuple(basis_v)),
    }
    if len(matches) < 3:
        for key in (
            "bolt_circle_diameter_mm",
            "maximum_radial_residual_mm",
            "maximum_angular_residual_deg",
        ):
            value[key] = None
    return MeasurementResult(
        measurement_id,
        "hole-pattern",
        MeasurementStatus.SUCCESS,
        value=value,
        components=(selector.component_id,),
        features=tuple(matches),
        method=method,
        computational_tolerance=tolerance,
        limitations=limitations,
        diagnostics={"selector": selector.to_dict()},
    )


def measure_shape_clearance(
    document: CADDocument,
    measurement_id: str,
    first_component: str,
    second_component: str,
    *,
    tolerance: ComputationalTolerance = DEFAULT_TOLERANCE,
) -> MeasurementResult:
    components = (first_component, second_component)
    try:
        if first_component == second_component:
            raise _InvalidInput("clearance requires two different components")
        first = _solid_shape(document, first_component)
        second = _solid_shape(document, second_component)
        distance, point_first, point_second = first.distance_to_with_closest_points(
            second
        )
        common = deepcopy(first) & deepcopy(second)
        interference_volume = 0.0 if common is None else float(common.volume)
        state = (
            "interference"
            if interference_volume > tolerance.volume_mm3
            else "contact" if distance <= tolerance.linear_mm else "separated"
        )
        return MeasurementResult(
            measurement_id,
            "shape-clearance",
            MeasurementStatus.SUCCESS,
            value={
                "state": state,
                "distance_mm": float(distance),
                "interference_volume_mm3": interference_volume,
                "closest_point_first_mm": list(_tuple(point_first)),
                "closest_point_second_mm": list(_tuple(point_second)),
            },
            unit="mm",
            components=components,
            method="occt-minimum-distance-and-boolean-common-volume",
            computational_tolerance=tolerance,
            limitations=(
                "Interference volume is not penetration depth.",
                "Distance is unsigned and is zero for contact or overlap.",
            ),
        )
    except Exception as exc:
        return _failure(
            measurement_id,
            "shape-clearance",
            components,
            "occt-minimum-distance-and-boolean-common-volume",
            tolerance,
            exc,
        )


def measure_directional_thickness(
    document: CADDocument,
    measurement_id: str,
    component_id: str,
    sample_points_mm: Iterable[tuple[float, float, float]],
    direction: tuple[float, float, float],
    *,
    tolerance: ComputationalTolerance = DEFAULT_TOLERANCE,
) -> MeasurementResult:
    """Measure material chords at every specified interior point along a direction."""
    method = "occt-edge-solid-common-material-chord"
    limitations = (
        "Measures only specified directional material chords, not global minimum wall thickness.",
        "Every sample must lie strictly inside material; boundary samples are indeterminate.",
    )
    try:
        try:
            points = tuple(sample_points_mm)
        except TypeError as exc:
            raise _InvalidInput(
                "sample_points_mm must be an iterable of points"
            ) from exc
        if not points:
            raise _InvalidInput("at least one sample point is required")
        vectors = [_vector(point, "sample point") for point in points]
        shape = _solid_shape(document, component_id)
        unit_direction = _unit(direction)
        samples = []
        discarded = []
        bbox = shape.bounding_box()
        for point in vectors:
            states = [
                BRepClass3d_SolidClassifier(
                    solid.wrapped, point.to_pnt(), tolerance.linear_mm
                ).State()
                for solid in shape.solids()
            ]
            inside = states.count(TopAbs_IN)
            if inside != 1 or TopAbs_ON in states:
                discarded.append(
                    {
                        "point_mm": list(_tuple(point)),
                        "matching_segments": inside,
                        "reason": (
                            "boundary sample"
                            if TopAbs_ON in states
                            else "point must lie in exactly one solid"
                        ),
                    }
                )
                continue
            reach = (point - bbox.center()).length + bbox.size.length + 1.0
            line = Edge.make_line(
                point - unit_direction * reach, point + unit_direction * reach
            )
            common = BRepAlgoAPI_Common(shape.wrapped, line.wrapped)
            common.SetFuzzyValue(tolerance.linear_mm)
            common.Build()
            if not common.IsDone():
                raise RuntimeError("OCCT line-solid intersection failed")
            intersections = Shape.cast(common.Shape()).edges()
            segments = [
                item
                for item in intersections
                if item.distance_to(point) <= tolerance.linear_mm
            ]
            if len(segments) == 1 and segments[0].length > tolerance.linear_mm:
                samples.append(
                    {
                        "point_mm": list(_tuple(point)),
                        "thickness_mm": float(segments[0].length),
                    }
                )
            else:
                discarded.append(
                    {
                        "point_mm": list(_tuple(point)),
                        "matching_segments": len(segments),
                        "reason": "material chord could not be resolved",
                    }
                )
        if discarded:
            status = (
                MeasurementStatus.AMBIGUOUS
                if any(item["matching_segments"] > 1 for item in discarded)
                else MeasurementStatus.NO_MATCH
            )
            if samples or any(
                item["reason"] == "boundary sample" for item in discarded
            ):
                status = MeasurementStatus.AMBIGUOUS
            return MeasurementResult(
                measurement_id,
                "directional-thickness",
                status,
                components=(component_id,),
                method=method,
                computational_tolerance=tolerance,
                limitations=limitations,
                diagnostics={
                    "discarded_samples": discarded,
                    "resolved_samples": samples,
                    "requested_sample_count": len(points),
                },
            )
        minimum = min(item["thickness_mm"] for item in samples)
        return MeasurementResult(
            measurement_id,
            "directional-thickness",
            MeasurementStatus.SUCCESS,
            value={
                "minimum_mm": minimum,
                "samples": samples,
                "sample_count": len(samples),
                "direction": list(_tuple(unit_direction)),
            },
            unit="mm",
            components=(component_id,),
            method=method,
            computational_tolerance=tolerance,
            limitations=limitations,
        )
    except Exception as exc:
        return _failure(
            measurement_id,
            "directional-thickness",
            (component_id,),
            method,
            tolerance,
            exc,
        )


MeasurementSource = Callable[[CADDocument], MeasurementResult]


def _value_at(value: Any, path: str) -> Any:
    current = value
    for item in path.split(".") if path else ():
        current = current[item]
    return current


def geometry_measurement_check(
    check_id: str,
    description: str,
    measurement: MeasurementSource,
    *,
    value_path: str,
    minimum: float | None = None,
    maximum: float | None = None,
    expected: Any = None,
    absolute_tolerance: float = 0.0,
    unit: str | None = None,
    category: str = "geometry-measurement",
    components: Iterable[str] = (),
    method: str = "occt-geometry-measurement",
    measurement_spec: Mapping[str, Any] | None = None,
) -> Check:
    if minimum is None and maximum is None and expected is None:
        raise ValueError("a geometry measurement check requires acceptance criteria")
    if not isinstance(value_path, str):
        raise TypeError("value_path must be a dot-separated string")
    for name, value in (("minimum", minimum), ("maximum", maximum)):
        if value is not None:
            _number(value, name)
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("minimum cannot exceed maximum")
    _number(absolute_tolerance, "absolute_tolerance", nonnegative=True)
    if expected is not None and not isinstance(expected, (bool, str, int, float)):
        raise TypeError("expected must be a scalar number, string, or boolean")
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        _number(expected, "expected")
    if (minimum is not None or maximum is not None) and isinstance(
        expected, (str, bool)
    ):
        raise TypeError(
            "numeric bounds cannot be combined with nonnumeric expectations"
        )
    if measurement_spec is not None and not isinstance(measurement_spec, Mapping):
        raise TypeError("measurement_spec must be an object")
    json.dumps(json_safe(measurement_spec or {}), allow_nan=False)
    criteria = {
        key: value
        for key, value in (
            ("minimum", minimum),
            ("maximum", maximum),
            ("expected", expected),
        )
        if value is not None
    }
    if expected is not None:
        criteria["absolute_tolerance"] = absolute_tolerance

    def evaluate(document: CADDocument) -> CheckResult:
        result = measurement(document)
        if not isinstance(result, MeasurementResult):
            raise TypeError("measurement callback must return MeasurementResult")
        serialized = result.to_dict()
        try:
            require_schema(serialized, MEASUREMENT_SCHEMA)
        except (ValueError, TypeError) as exc:
            return CheckResult(
                check_id,
                CheckStatus.ERROR,
                f"{description}: invalid measurement evidence: {exc}",
                expected=criteria,
                unit=unit,
                evidence_kind=EvidenceKind.GEOMETRY,
                evidence={"measurement_error": str(exc)},
            )
        evidence = {"measurement": serialized, "components": list(result.components)}
        if result.status is not MeasurementStatus.SUCCESS:
            status = (
                CheckStatus.FAIL
                if result.status is MeasurementStatus.NO_MATCH
                else (
                    CheckStatus.ERROR
                    if result.status
                    in {MeasurementStatus.INVALID_INPUT, MeasurementStatus.KERNEL_ERROR}
                    else CheckStatus.SKIP
                )
            )
            return CheckResult(
                check_id,
                status,
                f"{description}: measurement {result.status.value}",
                actual=result.value,
                expected=criteria,
                unit=unit,
                evidence_kind=EvidenceKind.GEOMETRY,
                evidence=evidence,
            )
        try:
            actual = _value_at(result.value, value_path)
        except (KeyError, TypeError, IndexError) as exc:
            return CheckResult(
                check_id,
                CheckStatus.ERROR,
                f"{description}: missing measurement value at {value_path!r}",
                expected=criteria,
                unit=unit or result.unit,
                evidence_kind=EvidenceKind.GEOMETRY,
                evidence={**evidence, "value_path_error": str(exc)},
            )
        if unit is not None and result.unit is not None and unit != result.unit:
            return CheckResult(
                check_id,
                CheckStatus.ERROR,
                f"{description}: measurement unit does not match requirement",
                actual=actual,
                expected=criteria,
                unit=unit,
                evidence_kind=EvidenceKind.GEOMETRY,
                evidence=evidence,
            )
        values = actual if isinstance(actual, list) else [actual]
        if not values or any(value is None for value in values):
            return CheckResult(
                check_id,
                CheckStatus.SKIP,
                f"{description}: measurement contains no values",
                actual=actual,
                expected=criteria,
                unit=unit or result.unit,
                evidence_kind=EvidenceKind.GEOMETRY,
                evidence=evidence,
            )

        def matches(value: Any) -> bool:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                number = _number(value, "measured value")
                numeric_expected = isinstance(
                    expected, (int, float)
                ) and not isinstance(expected, bool)
                if expected is not None and not numeric_expected:
                    raise _InvalidInput(
                        "numeric measurement has a nonnumeric expectation"
                    )
                return (
                    (minimum is None or number >= minimum)
                    and (maximum is None or number <= maximum)
                    and (
                        expected is None
                        or (
                            numeric_expected
                            and isclose(
                                number,
                                float(expected),
                                rel_tol=0.0,
                                abs_tol=absolute_tolerance,
                            )
                        )
                    )
                )
            if isinstance(value, (bool, str)):
                if (
                    minimum is not None
                    or maximum is not None
                    or type(value) is not type(expected)
                ):
                    raise _InvalidInput(
                        "measurement type does not match acceptance criteria"
                    )
                return value == expected
            raise _InvalidInput(
                "measurement value must be a scalar or a list of scalars"
            )

        try:
            outcomes = [matches(value) for value in values]
            passed = all(outcomes)
        except _InvalidInput as exc:
            return CheckResult(
                check_id,
                CheckStatus.ERROR,
                f"{description}: {exc}",
                actual=actual,
                expected=criteria,
                unit=unit or result.unit,
                evidence_kind=EvidenceKind.GEOMETRY,
                evidence=evidence,
            )
        return CheckResult(
            check_id,
            CheckStatus.PASS if passed else CheckStatus.FAIL,
            f"{description}: measured geometry {'meets' if passed else 'violates'} requirement",
            actual=actual,
            expected=criteria,
            unit=unit or result.unit,
            evidence_kind=EvidenceKind.GEOMETRY,
            evidence=evidence,
        )

    return Check(
        check_id,
        description,
        evaluate,
        category=category,
        requirement=Requirement(
            "geometry-measurement",
            criteria,
            unit,
            metadata={
                "value_path": value_path,
                "measurement_spec": json_safe(measurement_spec or {}),
            },
        ),
        evidence=EvidenceSpec(EvidenceKind.GEOMETRY, method, tuple(components)),
    )


__all__ = [
    "DEFAULT_TOLERANCE",
    "ComputationalTolerance",
    "CylinderSelector",
    "MeasurementResult",
    "MeasurementStatus",
    "geometry_measurement_check",
    "measure_cylindrical_feature",
    "measure_directional_thickness",
    "measure_hole_pattern",
    "measure_shape_clearance",
    "select_cylindrical_features",
]
