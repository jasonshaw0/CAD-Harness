"""Versioned identities and compatibility checks for public JSON documents."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

SCHEMA_VERSION = "1"
INSPECTION_SCHEMA = "cadharness.inspection"
VALIDATION_SCHEMA = "cadharness.validation"
SNAPSHOT_SCHEMA = "cadharness.snapshot"
DIFF_SCHEMA = "cadharness.diff"
POLICY_SCHEMA = "cadharness.comparison-policy"
VERIFICATION_SCHEMA = "cadharness.verification"
MEASUREMENT_SCHEMA = "cadharness.measurement"


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
        MEASUREMENT_SCHEMA,
        SCHEMA_VERSION,
        (
            "schema",
            "schema_version",
            "id",
            "type",
            "status",
            "value",
            "unit",
            "provenance",
            "components",
            "features",
            "method",
            "computational_tolerance",
            "limitations",
            "diagnostics",
        ),
        ("project_id", "revision", "variant"),
    ),
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
    """Reject unsupported identities and malformed structures used by consumers."""
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
    if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
        raise TypeError(f"{path} must be {expected.__name__}")


def _record(value: Any, fields: Mapping[str, type], path: str) -> None:
    _expect(value, Mapping, path)
    for key, kind in fields.items():
        if key not in value:
            raise ValueError(f"{path} is missing required key: {key}")
        _expect(value[key], kind, f"{path}.{key}")


def _strings(value: Any, path: str) -> None:
    _expect(value, list, path)
    for index, item in enumerate(value):
        _expect(item, str, f"{path}[{index}]")


def _finite_json(value: Any, path: str) -> None:
    """Measurement values must remain portable, finite JSON data."""
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"{path} must not contain NaN or infinity")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _finite_json(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _finite_json(item, f"{path}[{index}]")


def _unique_records(value: Any, path: str) -> None:
    _expect(value, list, path)
    seen = set()
    for index, item in enumerate(value):
        _record(item, {"id": str}, f"{path}[{index}]")
        if not item["id"] or item["id"] in seen:
            raise ValueError(f"{path} has empty or duplicate id: {item['id']!r}")
        seen.add(item["id"])


def _policy_fields(document: Mapping[str, Any], label: str) -> None:
    tolerances = document.get("numeric_tolerances", {})
    _expect(tolerances, Mapping, f"{label}.numeric_tolerances")
    for pattern, values in tolerances.items():
        _expect(pattern, str, f"{label}.numeric_tolerances key")
        _expect(values, Mapping, f"{label}.numeric_tolerances.{pattern}")
        for name in ("absolute", "percent"):
            value = values.get(name, 0.0)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(
                    f"{label}.numeric_tolerances.{pattern}.{name} must be numeric"
                )
            if not isfinite(value) or value < 0:
                raise ValueError(
                    f"{label}.numeric_tolerances.{pattern}.{name} must be finite and nonnegative"
                )
    accepted = document.get("accepted_changes", [])
    _expect(accepted, list, f"{label}.accepted_changes")
    paths = set()
    for index, item in enumerate(accepted):
        _record(
            item, {"path": str, "reason": str}, f"{label}.accepted_changes[{index}]"
        )
        if not item["path"]:
            raise ValueError(f"{label}.accepted_changes[{index}] needs a path")
        if not item["reason"].strip():
            raise ValueError(f"{label}.accepted_changes[{index}] needs a reason")
        if item["path"] in paths:
            raise ValueError(
                f"{label}.accepted_changes has duplicate path: {item['path']}"
            )
        paths.add(item["path"])


def _inspection_fields(document: Mapping[str, Any], label: str) -> None:
    _record(
        document["project"],
        {"id": str, "name": str, "revision": str},
        f"{label}.project",
    )
    for key in ("parameters", "components"):
        _expect(document[key], Mapping, f"{label}.{key}")
        for name, item in document[key].items():
            _expect(item, Mapping, f"{label}.{key}.{name}")
            if key == "components":
                _record(item, {"geometry": Mapping}, f"{label}.{key}.{name}")
                geometry = item["geometry"]
                for field in ("bounding_box", "topology", "geometry_types"):
                    if field in geometry:
                        _expect(
                            geometry[field],
                            Mapping,
                            f"{label}.{key}.{name}.geometry.{field}",
                        )
                if "fingerprint" in geometry:
                    _expect(
                        geometry["fingerprint"],
                        str,
                        f"{label}.{key}.{name}.geometry.fingerprint",
                    )
    _unique_records(document["checks"], f"{label}.checks")
    builtin_ids = {f"geometry.{name}" for name in document["components"]}
    for index, check in enumerate(document["checks"]):
        path = f"{label}.checks[{index}]"
        if check["id"] in builtin_ids:
            raise ValueError(f"{path} shadows a built-in geometry check")
        # New v0.8 fields are optional in older v1 snapshots.
        if "requirement" in check:
            _record(
                check["requirement"],
                {"type": str, "criteria": Mapping},
                f"{path}.requirement",
            )
        if "evidence" in check:
            _record(check["evidence"], {"kind": str, "method": str}, f"{path}.evidence")
            if check["evidence"]["kind"] not in {
                "declared",
                "geometry-derived",
                "external",
            }:
                raise ValueError(f"{path}.evidence.kind is unsupported")
            for field in ("components", "limitations"):
                if field in check["evidence"]:
                    _strings(check["evidence"][field], f"{path}.evidence.{field}")


def _validate_nested(document: Mapping[str, Any], schema_name: str, label: str) -> None:
    """Validate the nested structures consumed by cadharness itself.

    V1 remains additive and accepts legacy fixtures which omit newer optional
    fields, while rejecting wrong container and scalar types.
    """
    if schema_name == MEASUREMENT_SCHEMA:
        for key in ("id", "type", "status", "method"):
            _expect(document[key], str, f"{label}.{key}")
        if document["status"] not in {
            "success",
            "no-match",
            "ambiguous",
            "unsupported",
            "invalid-input",
            "kernel-error",
        }:
            raise ValueError(f"{label}.status is unsupported")
        if document["unit"] is not None:
            _expect(document["unit"], str, f"{label}.unit")
        _record(document["provenance"], {"kind": str}, f"{label}.provenance")
        if document["provenance"]["kind"] != "geometry-derived":
            raise ValueError(f"{label}.provenance.kind must be geometry-derived")
        _strings(document["components"], f"{label}.components")
        _strings(document["limitations"], f"{label}.limitations")
        _expect(document["features"], list, f"{label}.features")
        for index, feature in enumerate(document["features"]):
            _record(feature, {"id": str}, f"{label}.features[{index}]")
        _expect(document["diagnostics"], Mapping, f"{label}.diagnostics")
        _expect(
            document["computational_tolerance"],
            Mapping,
            f"{label}.computational_tolerance",
        )
        for key in ("linear_mm", "angular_deg", "volume_mm3"):
            value = document["computational_tolerance"].get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value < 0
            ):
                raise ValueError(
                    f"{label}.computational_tolerance.{key} must be finite and nonnegative"
                )
        _finite_json(document["value"], f"{label}.value")
        _finite_json(document["features"], f"{label}.features")
    elif schema_name in {INSPECTION_SCHEMA, SNAPSHOT_SCHEMA}:
        _inspection_fields(document, label)
        if schema_name == SNAPSHOT_SCHEMA:
            require_schema(
                document["validation"], VALIDATION_SCHEMA, label=f"{label}.validation"
            )
            validation = document["validation"]
            if (
                validation["project_id"] != document["project"]["id"]
                or validation["revision"] != document["project"]["revision"]
            ):
                raise ValueError(f"{label}.validation identity does not match project")
            if "toolchain" in document:
                _expect(document["toolchain"], Mapping, f"{label}.toolchain")
    elif schema_name == VALIDATION_SCHEMA:
        _expect(document["project_id"], str, f"{label}.project_id")
        _expect(document["revision"], str, f"{label}.revision")
        _expect(document["passed"], bool, f"{label}.passed")
        _expect(document["summary"], Mapping, f"{label}.summary")
        _unique_records(document["results"], f"{label}.results")
        counts = dict.fromkeys(("pass", "warn", "fail", "error", "skip"), 0)
        for index, result in enumerate(document["results"]):
            _record(result, {"status": str}, f"{label}.results[{index}]")
            if result["status"] not in counts:
                raise ValueError(f"{label}.results[{index}].status is unsupported")
            counts[result["status"]] += 1
            evidence = result.get("evidence", {})
            if isinstance(evidence, Mapping) and "measurement" in evidence:
                require_schema(
                    evidence["measurement"],
                    MEASUREMENT_SCHEMA,
                    label=f"{label}.results[{index}].evidence.measurement",
                )
        for status, count in counts.items():
            value = document["summary"].get(status, 0)
            _expect(value, int, f"{label}.summary.{status}")
            if value != count:
                raise ValueError(f"{label}.summary.{status} disagrees with results")
        if document["passed"] != (not counts["fail"] and not counts["error"]):
            raise ValueError(f"{label}.passed disagrees with results")
    elif schema_name == DIFF_SCHEMA:
        for key in ("summary", "policy", "parameters", "components", "validation"):
            _expect(document[key], Mapping, f"{label}.{key}")
        _expect(document["decisions"], list, f"{label}.decisions")
        _expect(document["changed"], bool, f"{label}.changed")
        if document["severity"] not in {
            "identical",
            "accepted",
            "changed",
            "regression",
        }:
            raise ValueError(f"{label}.severity is unsupported")
        _policy_fields(document["policy"], f"{label}.policy")
        for index, decision in enumerate(document["decisions"]):
            _record(
                decision,
                {"path": str, "kind": str, "disposition": str},
                f"{label}.decisions[{index}]",
            )
            if decision["disposition"] not in {"accepted", "tolerated", "significant"}:
                raise ValueError(
                    f"{label}.decisions[{index}].disposition is unsupported"
                )
        for field in ("parameters", "components", "requirements"):
            if field not in document:
                continue
            _expect(document[field], Mapping, f"{label}.{field}")
            for key in ("added", "removed", "unchanged"):
                if key in document[field]:
                    _strings(document[field][key], f"{label}.{field}.{key}")
            for key in ("changed", "modified"):
                if key in document[field]:
                    _expect(document[field][key], Mapping, f"{label}.{field}.{key}")
        for key in ("added", "removed", "regressions", "resolutions"):
            if key in document["validation"]:
                _strings(document["validation"][key], f"{label}.validation.{key}")
    elif schema_name == POLICY_SCHEMA:
        _policy_fields(document, label)
    elif schema_name == VERIFICATION_SCHEMA:
        require_schema(
            document["validation"], VALIDATION_SCHEMA, label=f"{label}.validation"
        )
        require_schema(
            document["current_snapshot"],
            SNAPSHOT_SCHEMA,
            label=f"{label}.current_snapshot",
        )
        if document["comparison"] is not None:
            require_schema(
                document["comparison"], DIFF_SCHEMA, label=f"{label}.comparison"
            )
        gate = document["verification"]
        _record(
            gate,
            {"passed": bool, "outcome": str, "reasons": list, "policy": Mapping},
            f"{label}.verification",
        )
        if gate["outcome"] not in {"passed", "failed", "error"}:
            raise ValueError(f"{label}.verification.outcome is unsupported")
        if gate["passed"] != (gate["outcome"] == "passed") or gate["passed"] != (
            not gate["reasons"]
        ):
            raise ValueError(f"{label}.verification verdict is inconsistent")
        for index, reason in enumerate(gate["reasons"]):
            _record(reason, {"code": str}, f"{label}.verification.reasons[{index}]")
            if "detail" not in reason:
                raise ValueError(
                    f"{label}.verification.reasons[{index}] is missing detail"
                )
        for key, value in gate["policy"].items():
            _expect(value, bool, f"{label}.verification.policy.{key}")
        project = document["current_snapshot"]["project"]
        if (
            document["project_id"] != project["id"]
            or document["revision"] != project["revision"]
            or document["variant"] != project.get("variant")
        ):
            raise ValueError(f"{label} identity does not match current_snapshot")
        if document["validation"] != document["current_snapshot"]["validation"]:
            raise ValueError(f"{label}.validation does not match current_snapshot")
        comparison = document["comparison"]
        if comparison is not None and (
            comparison["project_id"] != document["project_id"]
            or comparison["current_revision"] != document["revision"]
            or comparison["current_variant"] != document["variant"]
        ):
            raise ValueError(
                f"{label}.comparison identity does not match current_snapshot"
            )


__all__ = [
    "MEASUREMENT_SCHEMA",
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
