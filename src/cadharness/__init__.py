"""Public API for cadHarness project authors and integrations."""

from .checks import (
    boolean_check,
    clearance_check,
    equals_check,
    hole_diameter_check,
    interference_check,
    maximum_check,
    minimum_check,
    range_check,
    tolerance_stack_check,
    ToleranceContribution,
    wall_thickness_check,
)
from .model import (
    CADDocument,
    Check,
    CheckResult,
    EvidenceKind,
    EvidenceSpec,
    Component,
    Parameter,
    Requirement,
    ValidationReport,
    geometry_fingerprint,
)
from .inspector import render_inspector
from .project import LoadedProject, ProjectManifest, load_project
from .policy import ComparisonPolicy, NumericTolerance
from .revision import build_snapshot, compare_snapshots
from .schema import require_schema, schema_catalog
from .verification import VerificationPolicy, verify_document

__all__ = [
    "CADDocument",
    "Check",
    "CheckResult",
    "Component",
    "ComparisonPolicy",
    "EvidenceKind",
    "EvidenceSpec",
    "LoadedProject",
    "Parameter",
    "NumericTolerance",
    "ProjectManifest",
    "Requirement",
    "ToleranceContribution",
    "ValidationReport",
    "VerificationPolicy",
    "boolean_check",
    "build_snapshot",
    "clearance_check",
    "compare_snapshots",
    "equals_check",
    "geometry_fingerprint",
    "hole_diameter_check",
    "interference_check",
    "load_project",
    "maximum_check",
    "minimum_check",
    "range_check",
    "render_inspector",
    "require_schema",
    "schema_catalog",
    "tolerance_stack_check",
    "verify_document",
    "wall_thickness_check",
]
