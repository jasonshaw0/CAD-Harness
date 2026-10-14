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
    Component,
    Parameter,
    ValidationReport,
    geometry_fingerprint,
)
from .project import LoadedProject, ProjectManifest, load_project
from .policy import ComparisonPolicy, NumericTolerance
from .revision import build_snapshot, compare_snapshots
from .schema import require_schema, schema_catalog

__all__ = [
    "CADDocument",
    "Check",
    "CheckResult",
    "Component",
    "ComparisonPolicy",
    "LoadedProject",
    "Parameter",
    "NumericTolerance",
    "ProjectManifest",
    "ToleranceContribution",
    "ValidationReport",
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
    "require_schema",
    "schema_catalog",
    "tolerance_stack_check",
    "wall_thickness_check",
]
