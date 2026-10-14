"""Versioned identities and compatibility checks for public JSON documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SCHEMA_VERSION = "1"
INSPECTION_SCHEMA = "cadharness.inspection"
VALIDATION_SCHEMA = "cadharness.validation"
SNAPSHOT_SCHEMA = "cadharness.snapshot"
DIFF_SCHEMA = "cadharness.diff"
POLICY_SCHEMA = "cadharness.comparison-policy"
VERIFICATION_SCHEMA = "cadharness.verification"


@dataclass(frozen=True)
class SchemaSpec:
    """A supported public document and its stable top-level contract."""

    name: str
    version: str
    required_keys: tuple[str, ...]
    optional_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "required_keys": list(self.required_keys),
            "optional_keys": list(self.optional_keys),
        }


_SPECS = (
    SchemaSpec(
        INSPECTION_SCHEMA,
        SCHEMA_VERSION,
        (
            "schema",
            "schema_version",
            "project",
            "parameters",
            "components",
            "checks",
        ),
        ("manifest",),
    ),
    SchemaSpec(
        VALIDATION_SCHEMA,
        SCHEMA_VERSION,
        (
            "schema",
            "schema_version",
            "project_id",
            "revision",
            "passed",
            "summary",
            "results",
        ),
        ("manifest_path", "variant"),
    ),
    SchemaSpec(
        SNAPSHOT_SCHEMA,
        SCHEMA_VERSION,
        (
            "schema",
            "schema_version",
            "project",
            "parameters",
            "components",
            "checks",
            "validation",
        ),
        ("toolchain",),
    ),
    SchemaSpec(
        DIFF_SCHEMA,
        SCHEMA_VERSION,
        (
            "schema",
            "schema_version",
            "project_id",
            "baseline_revision",
            "current_revision",
            "baseline_variant",
            "current_variant",
            "changed",
            "severity",
            "summary",
            "policy",
            "decisions",
            "parameters",
            "components",
            "validation",
        ),
        ("baseline_path", "output_path", "output_sha256", "requirements"),
    ),
    SchemaSpec(
        POLICY_SCHEMA,
        SCHEMA_VERSION,
        ("schema", "schema_version"),
        ("numeric_tolerances", "accepted_changes"),
    ),
    SchemaSpec(
        VERIFICATION_SCHEMA,
        SCHEMA_VERSION,
        (
            "schema",
            "schema_version",
            "project_id",
            "revision",
            "variant",
            "validation",
            "comparison",
            "verification",
            "current_snapshot",
        ),
        ("baseline_path",),
    ),
)

SCHEMAS = {spec.name: spec for spec in _SPECS}


def schema_catalog() -> dict[str, Any]:
    """Return the supported schemas in deterministic order."""
    return {
        "catalog_version": "1",
        "schemas": [
            spec.to_dict() for spec in sorted(_SPECS, key=lambda item: item.name)
        ],
    }


def require_schema(
    document: Mapping[str, Any],
    expected_schema: str | None = None,
    *,
    label: str = "document",
) -> SchemaSpec:
    """Reject unknown identities, versions, or incomplete top-level contracts."""
    if not isinstance(document, Mapping):
        raise TypeError(f"{label} must be an object")
    schema_name = expected_schema or document.get("schema")
    if not isinstance(schema_name, str) or schema_name not in SCHEMAS:
        raise ValueError(f"{label} has an unsupported schema: {schema_name!r}")
    spec = SCHEMAS[schema_name]
    if document.get("schema") != spec.name:
        raise ValueError(f"{label} is not a {spec.name} document")
    if document.get("schema_version") != spec.version:
        raise ValueError(
            f"{label} uses unsupported {spec.name} schema version "
            f"{document.get('schema_version')!r}"
        )
    missing = [key for key in spec.required_keys if key not in document]
    if missing:
        raise ValueError(f"{label} is missing required keys: {', '.join(missing)}")
    _validate_nested(document, spec.name, label)
    return spec


def _expect(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"{path} must be {expected.__name__}")


def _validate_nested(document: Mapping[str, Any], schema_name: str, label: str) -> None:
    """Validate the nested structures consumed by cadharness itself.

    V1 remains additive and accepts legacy fixtures which omit newer optional
    fields, while rejecting wrong container and scalar types.
    """
    if schema_name == INSPECTION_SCHEMA:
        for key, kind in (("project", Mapping), ("parameters", Mapping), ("components", Mapping), ("checks", list)):
            _expect(document[key], kind, f"{label}.{key}")
    elif schema_name == VALIDATION_SCHEMA:
        _expect(document["passed"], bool, f"{label}.passed")
        _expect(document["summary"], Mapping, f"{label}.summary")
        _expect(document["results"], list, f"{label}.results")
        for index, result in enumerate(document["results"]):
            _expect(result, Mapping, f"{label}.results[{index}]")
            if not isinstance(result.get("status"), str):
                raise TypeError(f"{label}.results[{index}].status must be str")
    elif schema_name == SNAPSHOT_SCHEMA:
        for key in ("project", "parameters", "components", "validation"):
            _expect(document[key], Mapping, f"{label}.{key}")
        _expect(document["checks"], list, f"{label}.checks")
    elif schema_name == DIFF_SCHEMA:
        for key in ("summary", "policy", "parameters", "components", "validation"):
            _expect(document[key], Mapping, f"{label}.{key}")
        _expect(document["decisions"], list, f"{label}.decisions")
        _expect(document["changed"], bool, f"{label}.changed")
    elif schema_name == POLICY_SCHEMA:
        if "numeric_tolerances" in document:
            _expect(document["numeric_tolerances"], Mapping, f"{label}.numeric_tolerances")
        if "accepted_changes" in document:
            _expect(document["accepted_changes"], list, f"{label}.accepted_changes")
    elif schema_name == VERIFICATION_SCHEMA:
        _expect(document["validation"], Mapping, f"{label}.validation")
        _expect(document["verification"], Mapping, f"{label}.verification")
        _expect(document["current_snapshot"], Mapping, f"{label}.current_snapshot")
        if document["comparison"] is not None:
            _expect(document["comparison"], Mapping, f"{label}.comparison")


__all__ = [
    "DIFF_SCHEMA",
    "INSPECTION_SCHEMA",
    "POLICY_SCHEMA",
    "SCHEMAS",
    "SCHEMA_VERSION",
    "SNAPSHOT_SCHEMA",
    "SchemaSpec",
    "VALIDATION_SCHEMA",
    "VERIFICATION_SCHEMA",
    "require_schema",
    "schema_catalog",
]
