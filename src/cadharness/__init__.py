"""Public API for cadHarness project authors and integrations."""

from .checks import (
    boolean_check,
    equals_check,
    interference_check,
    maximum_check,
    minimum_check,
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
    "ValidationReport",
    "boolean_check",
    "build_snapshot",
    "compare_snapshots",
    "equals_check",
    "geometry_fingerprint",
    "interference_check",
    "load_project",
    "maximum_check",
    "minimum_check",
]
