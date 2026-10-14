"""Deterministic snapshots and policy-aware revision comparison."""

from __future__ import annotations

from numbers import Real
from typing import Any, Mapping

from .model import CADDocument
from .policy import ComparisonPolicy
from .schema import (
    DIFF_SCHEMA,
    SCHEMA_VERSION,
    SNAPSHOT_SCHEMA,
    require_schema,
)


def build_snapshot(
    document: CADDocument, *, variant: str | None = None
) -> dict[str, Any]:
    """Capture geometry, parameters, metadata, and validation without timestamps."""
    inspection = document.inspect()
    project = dict(inspection["project"])
    project["variant"] = variant
    return {
        "schema": SNAPSHOT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "parameters": inspection["parameters"],
        "components": inspection["components"],
        "checks": inspection["checks"],
        "validation": document.validate().to_dict(),
    }


def _require_snapshot(snapshot: Mapping[str, Any], label: str) -> None:
    require_schema(snapshot, SNAPSHOT_SCHEMA, label=label)
    if not isinstance(snapshot.get("project"), Mapping):
        raise ValueError(f"{label} has no project record")


def _number_delta(baseline: Any, current: Any) -> dict[str, float] | None:
    if (
        not isinstance(baseline, Real)
        or isinstance(baseline, bool)
        or not isinstance(current, Real)
        or isinstance(current, bool)
    ):
        return None
    baseline_value = float(baseline)
    current_value = float(current)
    absolute = current_value - baseline_value
    result = {"baseline": baseline_value, "current": current_value, "delta": absolute}
    if baseline_value != 0:
        result["percent"] = absolute / abs(baseline_value) * 100
    return result


def _decision(
    policy: ComparisonPolicy,
    decisions: list[dict[str, Any]],
    path: str,
    kind: str,
    delta: Mapping[str, float] | None = None,
    *,
    force_significant: bool = False,
) -> dict[str, Any]:
    assessment = (
        {"disposition": "significant"}
        if force_significant
        else policy.classify(path, delta)
    )
    record = {"path": path, "kind": kind, **assessment}
    if delta is not None:
        record["delta"] = dict(delta)
    decisions.append(record)
    return assessment


def _parameter_changes(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    policy: ComparisonPolicy,
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline_keys = set(baseline)
    current_keys = set(current)
    changed: dict[str, Any] = {}
    for name in sorted(baseline_keys & current_keys):
        before = baseline[name]
        after = current[name]
        if before == after:
            continue
        delta = _number_delta(before.get("value"), after.get("value"))
        path = f"parameters.{name}"
        changed[name] = {
            "baseline": before,
            "current": after,
            "delta": delta,
            "assessment": _decision(policy, decisions, path, "parameter", delta),
        }
    for name in sorted(current_keys - baseline_keys):
        _decision(policy, decisions, f"parameters.{name}", "parameter-added")
    for name in sorted(baseline_keys - current_keys):
        _decision(policy, decisions, f"parameters.{name}", "parameter-removed")
    return {
        "added": sorted(current_keys - baseline_keys),
        "removed": sorted(baseline_keys - current_keys),
        "changed": changed,
        "unchanged": sorted((baseline_keys & current_keys) - set(changed)),
    }


def _axis_deltas(
    baseline: Any,
    current: Any,
    path_prefix: str,
    policy: ComparisonPolicy,
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    changes = {}
    if not isinstance(baseline, list) or not isinstance(current, list):
        return changes
    if len(baseline) != 3 or len(current) != 3:
        return changes
    for axis, before, after in zip(("x", "y", "z"), baseline, current):
        delta = _number_delta(before, after)
        if delta and delta["delta"] != 0:
            path = f"{path_prefix}.{axis}"
            changes[axis] = {
                **delta,
                "assessment": _decision(
                    policy, decisions, path, "geometry-metric", delta
                ),
            }
    return changes


def _geometry_delta(
    component_id: str,
    baseline_component: Mapping[str, Any],
    current_component: Mapping[str, Any],
    policy: ComparisonPolicy,
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline = baseline_component["geometry"]
    current = current_component["geometry"]
    prefix = f"components.{component_id}"
    fingerprint_changed = baseline.get("fingerprint") != current.get("fingerprint")
    fingerprint = {
        "baseline": baseline.get("fingerprint"),
        "current": current.get("fingerprint"),
        "changed": fingerprint_changed,
    }
    if fingerprint_changed:
        fingerprint["assessment"] = _decision(
            policy, decisions, f"{prefix}.fingerprint", "geometry-fingerprint"
        )

    scalars = {}
    for name in ("volume_mm3", "area_mm2"):
        delta = _number_delta(baseline.get(name), current.get(name))
        if delta and delta["delta"] != 0:
            scalars[name] = {
                **delta,
                "assessment": _decision(
                    policy, decisions, f"{prefix}.{name}", "geometry-metric", delta
                ),
            }

    baseline_box = baseline.get("bounding_box", {})
    current_box = current.get("bounding_box", {})
    bounds = _axis_deltas(
        baseline_box.get("size_mm"),
        current_box.get("size_mm"),
        f"{prefix}.bounding_box_size_mm",
        policy,
        decisions,
    )
    centers = _axis_deltas(
        baseline_box.get("center_mm"),
        current_box.get("center_mm"),
        f"{prefix}.bounding_box_center_mm",
        policy,
        decisions,
    )
    mass_centers = _axis_deltas(
        baseline.get("center_of_mass_mm"),
        current.get("center_of_mass_mm"),
        f"{prefix}.center_of_mass_mm",
        policy,
        decisions,
    )

    topology = {}
    before_topology = baseline.get("topology", {})
    after_topology = current.get("topology", {})
    for name in sorted(set(before_topology) | set(after_topology)):
        before = before_topology.get(name)
        after = after_topology.get(name)
        if before != after:
            path = f"{prefix}.topology.{name}"
            topology[name] = {
                "baseline": before,
                "current": after,
                "assessment": _decision(
                    policy, decisions, path, "topology"
                ),
            }

    geometry_types = {}
    before_types = baseline.get("geometry_types", {})
    after_types = current.get("geometry_types", {})
    for category in sorted(set(before_types) | set(after_types)):
        before_category = before_types.get(category, {})
        after_category = after_types.get(category, {})
        category_changes = {}
        for geometry_name in sorted(set(before_category) | set(after_category)):
            before_geometry = before_category.get(geometry_name)
            after_geometry = after_category.get(geometry_name)
            type_path = f"{prefix}.geometry_types.{category}.{geometry_name}"
            if before_geometry is None or after_geometry is None:
                category_changes[geometry_name] = {
                    "baseline": before_geometry,
                    "current": after_geometry,
                    "assessment": _decision(
                        policy, decisions, type_path, "geometry-type"
                    ),
                }
                continue
            metric_changes = {}
            for metric in sorted(set(before_geometry) | set(after_geometry)):
                before_metric = before_geometry.get(metric)
                after_metric = after_geometry.get(metric)
                if before_metric == after_metric:
                    continue
                delta = _number_delta(before_metric, after_metric)
                metric_path = f"{type_path}.{metric}"
                metric_changes[metric] = {
                    "baseline": before_metric,
                    "current": after_metric,
                    "delta": delta,
                    "assessment": _decision(
                        policy,
                        decisions,
                        metric_path,
                        "geometry-type-metric",
                        None if metric == "count" else delta,
                    ),
                }
            if metric_changes:
                category_changes[geometry_name] = metric_changes
        if category_changes:
            geometry_types[category] = category_changes
    return {
        "fingerprint": fingerprint,
        "scalars": scalars,
        "bounding_box_size_mm": bounds,
        "bounding_box_center_mm": centers,
        "center_of_mass_mm": mass_centers,
        "topology": topology,
        "geometry_types_changed": bool(geometry_types),
        "geometry_types": geometry_types,
    }


def _component_changes(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    policy: ComparisonPolicy,
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline_keys = set(baseline)
    current_keys = set(current)
    changed = {}
    unchanged = []
    for component_id in sorted(baseline_keys & current_keys):
        before = baseline[component_id]
        after = current[component_id]
        geometry = _geometry_delta(
            component_id, before, after, policy, decisions
        )
        metadata = {}
        for field in ("role", "material", "source", "tags", "metadata"):
            if before.get(field) != after.get(field):
                metadata[field] = {
                    "baseline": before.get(field),
                    "current": after.get(field),
                    "assessment": _decision(
                        policy,
                        decisions,
                        f"components.{component_id}.{field}",
                        "component-metadata",
                    ),
                }
        if geometry["fingerprint"]["changed"] or metadata:
            changed[component_id] = {"geometry": geometry, "metadata": metadata}
        else:
            unchanged.append(component_id)
    for name in sorted(current_keys - baseline_keys):
        _decision(policy, decisions, f"components.{name}", "component-added")
    for name in sorted(baseline_keys - current_keys):
        _decision(policy, decisions, f"components.{name}", "component-removed")
    return {
        "added": sorted(current_keys - baseline_keys),
        "removed": sorted(baseline_keys - current_keys),
        "changed": changed,
        "unchanged": unchanged,
    }


def _actual_assessments(
    check_id: str,
    baseline: Any,
    current: Any,
    policy: ComparisonPolicy,
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if baseline == current:
        return []
    changes = []
    if isinstance(baseline, Mapping) and isinstance(current, Mapping):
        for name in sorted(set(baseline) | set(current)):
            before = baseline.get(name)
            after = current.get(name)
            if before == after:
                continue
            delta = _number_delta(before, after)
            assessment = _decision(
                policy,
                decisions,
                f"validation.{check_id}.actual.{name}",
                "validation-evidence",
                delta,
            )
            changes.append({"field": name, "assessment": assessment, "delta": delta})
        return changes
    delta = _number_delta(baseline, current)
    assessment = _decision(
        policy,
        decisions,
        f"validation.{check_id}.actual",
        "validation-evidence",
        delta,
    )
    return [{"assessment": assessment, "delta": delta}]


def _validation_changes(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    policy: ComparisonPolicy,
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline_results = {item["id"]: item for item in baseline.get("results", [])}
    current_results = {item["id"]: item for item in current.get("results", [])}
    baseline_keys = set(baseline_results)
    current_keys = set(current_results)
    regressions = []
    resolutions = []
    changed = {}
    failing = {"fail", "error"}
    for check_id in sorted(baseline_keys & current_keys):
        before = baseline_results[check_id]
        after = current_results[check_id]
        status_changed = before["status"] != after["status"]
        actual_assessments = _actual_assessments(
            check_id,
            before.get("actual"),
            after.get("actual"),
            policy,
            decisions,
        )
        status_assessment = None
        is_regression = before["status"] not in failing and after["status"] in failing
        if status_changed:
            status_assessment = _decision(
                policy,
                decisions,
                f"validation.{check_id}.status",
                "validation-status",
                force_significant=is_regression,
            )
        if status_changed or actual_assessments:
            changed[check_id] = {
                "baseline_status": before["status"],
                "current_status": after["status"],
                "baseline_actual": before.get("actual"),
                "current_actual": after.get("actual"),
                "status_assessment": status_assessment,
                "actual_assessments": actual_assessments,
            }
        if is_regression:
            regressions.append(check_id)
        if before["status"] in failing and after["status"] not in failing:
            resolutions.append(check_id)
    for name in sorted(current_keys - baseline_keys):
        _decision(policy, decisions, f"validation.{name}", "validation-added")
    for name in sorted(baseline_keys - current_keys):
        _decision(policy, decisions, f"validation.{name}", "validation-removed")
    return {
        "baseline_passed": bool(baseline.get("passed")),
        "current_passed": bool(current.get("passed")),
        "added": sorted(current_keys - baseline_keys),
        "removed": sorted(baseline_keys - current_keys),
        "changed": changed,
        "regressions": regressions,
        "resolutions": resolutions,
    }


def compare_snapshots(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    policy: ComparisonPolicy | None = None,
) -> dict[str, Any]:
    """Explain and classify parameter, geometry, metadata, and validation changes."""
    _require_snapshot(baseline, "baseline")
    _require_snapshot(current, "current")
    active_policy = policy or ComparisonPolicy.exact()
    baseline_project = baseline["project"]
    current_project = current["project"]
    if baseline_project.get("id") != current_project.get("id"):
        raise ValueError(
            "snapshot project mismatch: "
            f"{baseline_project.get('id')!r} != {current_project.get('id')!r}"
        )

    decisions: list[dict[str, Any]] = []
    if baseline_project.get("revision") != current_project.get("revision"):
        _decision(active_policy, decisions, "project.revision", "project-revision")
    if baseline_project.get("variant") != current_project.get("variant"):
        _decision(active_policy, decisions, "project.variant", "project-variant")

    parameters = _parameter_changes(
        baseline.get("parameters", {}),
        current.get("parameters", {}),
        active_policy,
        decisions,
    )
    components = _component_changes(
        baseline.get("components", {}),
        current.get("components", {}),
        active_policy,
        decisions,
    )
    validation = _validation_changes(
        baseline.get("validation", {}),
        current.get("validation", {}),
        active_policy,
        decisions,
    )
    changed = bool(decisions)
    counts = {
        disposition: sum(
            decision["disposition"] == disposition for decision in decisions
        )
        for disposition in ("significant", "tolerated", "accepted")
    }
    if validation["regressions"]:
        severity = "regression"
    elif counts["significant"]:
        severity = "changed"
    elif changed:
        severity = "accepted"
    else:
        severity = "identical"
    return {
        "schema": DIFF_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "project_id": current_project["id"],
        "baseline_revision": baseline_project.get("revision"),
        "current_revision": current_project.get("revision"),
        "baseline_variant": baseline_project.get("variant"),
        "current_variant": current_project.get("variant"),
        "changed": changed,
        "severity": severity,
        "summary": {
            "parameters_added": len(parameters["added"]),
            "parameters_removed": len(parameters["removed"]),
            "parameters_changed": len(parameters["changed"]),
            "components_added": len(components["added"]),
            "components_removed": len(components["removed"]),
            "components_changed": len(components["changed"]),
            "validation_regressions": len(validation["regressions"]),
            "validation_resolutions": len(validation["resolutions"]),
            **{f"{name}_changes": count for name, count in counts.items()},
        },
        "policy": active_policy.to_dict(),
        "decisions": decisions,
        "parameters": parameters,
        "components": components,
        "validation": validation,
    }


__all__ = ["build_snapshot", "compare_snapshots"]
