"""Core project, component, parameter, and validation records.

cadharness intentionally stores build123d ``Shape`` objects directly.  It adds
project identity and engineering semantics without duplicating build123d's
geometry or assembly object model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass, replace
from enum import Enum
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from collections import Counter, defaultdict
from typing import Any, Callable, Mapping

from build123d import Shape, export_brep

from .schema import INSPECTION_SCHEMA, SCHEMA_VERSION, VALIDATION_SCHEMA


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$")


def _require_identifier(value: str, label: str) -> None:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(
            f"{label} must be a stable lowercase identifier; received {value!r}"
        )


def json_safe(value: Any) -> Any:
    """Convert common project values into deterministic JSON-compatible data."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return [json_safe(item) for item in sorted(value, key=repr)]
    if isinstance(value, (tuple, list)):
        return [json_safe(item) for item in value]
    if hasattr(value, "to_tuple"):
        return json_safe(value.to_tuple())
    return repr(value)


@dataclass(frozen=True)
class Parameter:
    """A user-facing parameter value with provenance and optional units."""

    value: Any
    unit: str | None = None
    source: str = "configurable-default"
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": json_safe(self.value),
            "unit": self.unit,
            "source": self.source,
            "description": self.description,
        }

@dataclass
class Component:
    """A named build123d shape and the engineering metadata around it."""

    id: str
    shape: Shape
    role: str = "part"
    material: str | None = None
    source: str = "generated"
    tags: frozenset[str] = field(default_factory=frozenset)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    require_solid: bool = True

    def __post_init__(self) -> None:
        _require_identifier(self.id, "component id")
        if not isinstance(self.shape, Shape):
            raise TypeError(f"component {self.id!r} did not provide a build123d Shape")
        if not self.shape.label:
            self.shape.label = self.id


class CheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


class EvidenceKind(str, Enum):
    """The provenance class of evidence evaluated by an engineering check."""

    DECLARED = "declared"
    GEOMETRY = "geometry-derived"
    EXTERNAL = "external"


@dataclass(frozen=True)
class EvidenceSpec:
    """Stable description of how a check obtains its evidence."""

    kind: EvidenceKind = EvidenceKind.DECLARED
    method: str = "project-supplied-value"
    components: tuple[str, ...] = ()
    feature: str | None = None
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "method": self.method,
            "components": list(self.components),
            "feature": self.feature,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class Requirement:
    """Revision-stable engineering acceptance criteria and traceability."""

    type: str = "assertion"
    criteria: Mapping[str, Any] = field(default_factory=dict)
    unit: str | None = None
    origin: str = "project-source"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "criteria": json_safe(self.criteria),
            "unit": self.unit,
            "origin": self.origin,
            "metadata": json_safe(self.metadata),
        }


@dataclass(frozen=True)
class CheckResult:
    id: str
    status: CheckStatus
    message: str
    actual: Any = None
    expected: Any = None
    unit: str | None = None
    evidence_kind: EvidenceKind | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.value,
            "message": self.message,
            "actual": json_safe(self.actual),
            "expected": json_safe(self.expected),
            "unit": self.unit,
            "evidence_kind": (
                self.evidence_kind.value if self.evidence_kind is not None else None
            ),
            "evidence": json_safe(self.evidence),
        }


CheckEvaluator = Callable[["CADDocument"], CheckResult]


@dataclass(frozen=True)
class Check:
    """Executable, source-defined engineering assertion."""

    id: str
    description: str
    evaluator: CheckEvaluator
    category: str = "engineering"
    requirement: Requirement = field(default_factory=Requirement)
    evidence: EvidenceSpec = field(default_factory=EvidenceSpec)

    def __post_init__(self) -> None:
        _require_identifier(self.id, "check id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "description": self.description,
            "requirement": self.requirement.to_dict(),
            "evidence": self.evidence.to_dict(),
        }


def geometry_fingerprint(shape: Shape) -> str:
    """Return a deterministic SHA-256 fingerprint of the OCCT BREP geometry."""
    buffer = BytesIO()
    export_brep(shape, buffer)
    return f"sha256:{sha256(buffer.getvalue()).hexdigest()}"


def _geometry_type_summary(shape: Shape) -> dict[str, Any]:
    face_counts: Counter[str] = Counter()
    face_areas: defaultdict[str, float] = defaultdict(float)
    for face in shape.faces():
        name = face.geom_type.name.lower()
        face_counts[name] += 1
        face_areas[name] += float(face.area)

    edge_counts: Counter[str] = Counter()
    edge_lengths: defaultdict[str, float] = defaultdict(float)
    for edge in shape.edges():
        name = edge.geom_type.name.lower()
        edge_counts[name] += 1
        edge_lengths[name] += float(edge.length)

    return {
        "surfaces": {
            name: {"count": face_counts[name], "area_mm2": face_areas[name]}
            for name in sorted(face_counts)
        },
        "curves": {
            name: {"count": edge_counts[name], "length_mm": edge_lengths[name]}
            for name in sorted(edge_counts)
        },
    }


def shape_metrics(shape: Shape) -> dict[str, Any]:
    """Return reproducible OCCT facts without assuming a particular part type."""
    bbox = shape.bounding_box()
    size = bbox.size
    center = bbox.center()
    metrics: dict[str, Any] = {
        "type": type(shape).__name__,
        "valid": bool(shape.is_valid),
        "manifold": bool(shape.is_manifold),
        "fingerprint": geometry_fingerprint(shape),
        "volume_mm3": float(shape.volume),
        "area_mm2": float(shape.area),
        "bounding_box": {
            "min_mm": [float(bbox.min.X), float(bbox.min.Y), float(bbox.min.Z)],
            "max_mm": [float(bbox.max.X), float(bbox.max.Y), float(bbox.max.Z)],
            "size_mm": [float(size.X), float(size.Y), float(size.Z)],
            "center_mm": [float(center.X), float(center.Y), float(center.Z)],
        },
        "topology": {
            "solids": len(shape.solids()),
            "shells": len(shape.shells()),
            "faces": len(shape.faces()),
            "edges": len(shape.edges()),
            "vertices": len(shape.vertices()),
        },
        "geometry_types": _geometry_type_summary(shape),
    }
    try:
        mass_center = shape.center()
        metrics["center_of_mass_mm"] = [
            float(mass_center.X),
            float(mass_center.Y),
            float(mass_center.Z),
        ]
    except (ValueError, RuntimeError, NotImplementedError):
        metrics["center_of_mass_mm"] = None
    return metrics


@dataclass
class CADDocument:
    """A built CAD project snapshot ready for inspection or validation."""

    id: str
    name: str
    revision: str
    components: Mapping[str, Component]
    parameters: Mapping[str, Parameter] = field(default_factory=dict)
    checks: tuple[Check, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_identifier(self.id, "project id")
        if not self.components:
            raise ValueError("a CADDocument must contain at least one component")
        if len(set(self.components)) != len(self.components):
            raise ValueError("component ids must be unique")
        for key, component in self.components.items():
            if key != component.id:
                raise ValueError(
                    f"component mapping key {key!r} does not match id {component.id!r}"
                )
        check_ids = [check.id for check in self.checks]
        if len(set(check_ids)) != len(check_ids):
            raise ValueError("check ids must be unique")
        builtin_ids = {f"geometry.{name}" for name in self.components}
        if builtin_ids.intersection(check_ids):
            raise ValueError("check ids must not shadow built-in geometry checks")

    def inspect(self) -> dict[str, Any]:
        return {
            "schema": INSPECTION_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "project": {
                "id": self.id,
                "name": self.name,
                "revision": self.revision,
                "metadata": json_safe(self.metadata),
            },
            "parameters": {
                name: parameter.to_dict()
                for name, parameter in sorted(self.parameters.items())
            },
            "components": {
                name: {
                    "role": component.role,
                    "material": component.material,
                    "source": component.source,
                    "tags": sorted(component.tags),
                    "metadata": json_safe(component.metadata),
                    "geometry": shape_metrics(component.shape),
                }
                for name, component in sorted(self.components.items())
            },
            "checks": [check.to_dict() for check in self.checks],
        }

    def validate(self) -> "ValidationReport":
        results = [self._validate_component(component) for component in self.components.values()]
        for check in self.checks:
            try:
                result = check.evaluator(self)
                if not isinstance(result, CheckResult):
                    raise TypeError("check evaluator must return a CheckResult")
                if not isinstance(result.status, CheckStatus):
                    raise TypeError("check result status must be CheckStatus")
                if result.id != check.id:
                    raise ValueError(
                        f"check {check.id!r} returned result id {result.id!r}"
                    )
                if result.evidence_kind is None:
                    result = replace(result, evidence_kind=check.evidence.kind)
                results.append(result)
            except Exception as exc:
                results.append(
                    CheckResult(
                        id=check.id,
                        status=CheckStatus.ERROR,
                        message=f"check raised {type(exc).__name__}: {exc}",
                        evidence_kind=check.evidence.kind,
                        evidence={"category": check.category},
                    )
                )
        return ValidationReport(self.id, self.revision, tuple(results))

    @staticmethod
    def _validate_component(component: Component) -> CheckResult:
        check_id = f"geometry.{component.id}"
        try:
            # Validation is intentionally cheaper than a full inspection report.
            # Topology-wide face/edge metrics are useful on demand but expensive
            # across a large assembly.
            wrapped = component.shape.wrapped
            nonempty = wrapped is not None and not wrapped.IsNull()
            is_valid = bool(component.shape.is_valid)
            solid_count = len(component.shape.solids())
            volume_mm3 = float(component.shape.volume)
            has_required_solid = not component.require_solid or solid_count > 0
            passed = bool(nonempty and is_valid and has_required_solid)
            reasons = []
            if not nonempty:
                reasons.append("empty topology")
            if not is_valid:
                reasons.append("OCCT reports invalid geometry")
            if not has_required_solid:
                reasons.append("no solid found")
            return CheckResult(
                id=check_id,
                status=CheckStatus.PASS if passed else CheckStatus.FAIL,
                message=(
                    f"{component.id} is valid, nonempty geometry"
                    if passed
                    else f"{component.id}: {', '.join(reasons)}"
                ),
                actual={
                    "valid": is_valid,
                    "solid_count": solid_count,
                    "volume_mm3": volume_mm3,
                },
                expected={
                    "valid": True,
                    "nonempty": True,
                    "solid_required": component.require_solid,
                },
                evidence_kind=EvidenceKind.GEOMETRY,
                evidence={"role": component.role},
            )
        except Exception as exc:
            return CheckResult(
                id=check_id,
                status=CheckStatus.ERROR,
                message=f"geometry inspection raised {type(exc).__name__}: {exc}",
                evidence_kind=EvidenceKind.GEOMETRY,
            )


@dataclass(frozen=True)
class ValidationReport:
    project_id: str
    revision: str
    results: tuple[CheckResult, ...]

    @property
    def passed(self) -> bool:
        return not any(
            result.status in (CheckStatus.FAIL, CheckStatus.ERROR)
            for result in self.results
        )

    def to_dict(self) -> dict[str, Any]:
        counts = {
            status.value: sum(result.status is status for result in self.results)
            for status in CheckStatus
        }
        return {
            "schema": VALIDATION_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "project_id": self.project_id,
            "revision": self.revision,
            "passed": self.passed,
            "summary": counts,
            "results": [result.to_dict() for result in self.results],
        }
