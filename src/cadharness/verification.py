"""Unified engineering verification gates.

Verification evaluates the current design.  Revision comparison only explains
change and is intentionally preserved as a separate fact in the report.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .model import CADDocument, CheckStatus
from .policy import ComparisonPolicy
from .revision import build_snapshot, compare_snapshots
from .schema import SCHEMA_VERSION, VERIFICATION_SCHEMA


@dataclass(frozen=True)
class VerificationPolicy:
    """Bounded gates which never rewrite the underlying engineering evidence."""

    fail_on_failed_checks: bool = True
    fail_on_check_errors: bool = True
    fail_on_warnings: bool = False
    fail_on_skipped_checks: bool = True
    fail_on_added_requirements: bool = False
    fail_on_removed_requirements: bool = True
    fail_on_modified_requirements: bool = True
    fail_on_unaccepted_changes: bool = True

    def to_dict(self) -> dict[str, bool]:
        return {
            "fail_on_failed_checks": self.fail_on_failed_checks,
            "fail_on_check_errors": self.fail_on_check_errors,
            "fail_on_warnings": self.fail_on_warnings,
            "fail_on_skipped_checks": self.fail_on_skipped_checks,
            "fail_on_added_requirements": self.fail_on_added_requirements,
            "fail_on_removed_requirements": self.fail_on_removed_requirements,
            "fail_on_modified_requirements": self.fail_on_modified_requirements,
            "fail_on_unaccepted_changes": self.fail_on_unaccepted_changes,
        }


def verify_document(
    document: CADDocument,
    *,
    baseline: Mapping[str, Any] | None = None,
    variant: str | None = None,
    comparison_policy: ComparisonPolicy | None = None,
    gate_policy: VerificationPolicy | None = None,
) -> dict[str, Any]:
    """Verify current geometry and checks, optionally against a baseline."""
    gates = gate_policy or VerificationPolicy()
    validation_report = document.validate()
    validation = validation_report.to_dict()
    current = build_snapshot(document, variant=variant, validation=validation_report)
    comparison = (
        compare_snapshots(
            baseline,
            current,
            policy=comparison_policy or ComparisonPolicy.exact(),
        )
        if baseline is not None
        else None
    )

    by_status = {
        status.value: [
            result["id"]
            for result in validation["results"]
            if result["status"] == status.value
        ]
        for status in CheckStatus
    }
    reasons: list[dict[str, Any]] = []

    def reject(code: str, detail: Any) -> None:
        reasons.append({"code": code, "detail": detail})

    if gates.fail_on_failed_checks and by_status["fail"]:
        reject("current_design_failed_validation", by_status["fail"])
    if gates.fail_on_check_errors and by_status["error"]:
        reject("check_execution_error", by_status["error"])
    if gates.fail_on_warnings and by_status["warn"]:
        reject("warnings_not_allowed", by_status["warn"])
    if gates.fail_on_skipped_checks and by_status["skip"]:
        reject("indeterminate_checks_not_allowed", by_status["skip"])

    if comparison is not None:
        requirements = comparison["requirements"]
        if gates.fail_on_added_requirements and requirements["added"]:
            reject("requirements_added", requirements["added"])
        if gates.fail_on_removed_requirements and requirements["removed"]:
            reject("requirements_removed", requirements["removed"])
        normative_modified = sorted(
            check_id
            for check_id, item in requirements["modified"].items()
            if item["normative"]
        )
        if gates.fail_on_modified_requirements and normative_modified:
            reject("requirements_modified", normative_modified)
        significant = [
            decision["path"]
            for decision in comparison["decisions"]
            if decision["disposition"] == "significant"
            and not decision["kind"].startswith("requirement-")
            and decision["kind"] != "validation-status"
        ]
        if gates.fail_on_unaccepted_changes and significant:
            reject("unaccepted_revision_changes", significant)

    has_execution_error = bool(by_status["error"])
    return {
        "schema": VERIFICATION_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "project_id": document.id,
        "revision": document.revision,
        "variant": variant,
        "validation": validation,
        "comparison": comparison,
        "verification": {
            "passed": not reasons,
            "outcome": (
                "error" if has_execution_error else "failed" if reasons else "passed"
            ),
            "reasons": reasons,
            "policy": gates.to_dict(),
        },
        "current_snapshot": current,
    }


__all__ = ["VerificationPolicy", "verify_document"]
