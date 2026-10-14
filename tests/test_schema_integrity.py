"""Reject malformed saved evidence before comparison or verification consumes it."""

from copy import deepcopy
import unittest

from build123d import Box

from cadharness import (
    CADDocument,
    Component,
    build_snapshot,
    compare_snapshots,
    minimum_check,
    require_schema,
    verify_document,
)


def document():
    return CADDocument(
        "schema-review",
        "Schema review",
        "1",
        {"block": Component("block", Box(10, 10, 10))},
        checks=(minimum_check("size.minimum", "minimum", 10, 5),),
    )


class SchemaIntegrityTests(unittest.TestCase):
    def test_snapshot_rejects_invalid_nested_validation_and_checks(self):
        original = build_snapshot(document())
        corruptions = (
            lambda s: s.update(validation={}),
            lambda s: s["validation"]["results"][0].update(status="unknown"),
            lambda s: s["validation"]["results"].append(
                deepcopy(s["validation"]["results"][0])
            ),
            lambda s: s["validation"].update(passed=False),
            lambda s: s["checks"].append(deepcopy(s["checks"][0])),
            lambda s: s["checks"][0].update(requirement=[]),
            lambda s: s["components"]["block"].update(geometry=[]),
            lambda s: s["validation"].update(project_id="different-project"),
        )
        for corrupt in corruptions:
            with self.subTest(corruption=corrupt):
                invalid = deepcopy(original)
                corrupt(invalid)
                with self.assertRaises((TypeError, ValueError)):
                    compare_snapshots(invalid, original)

    def test_legacy_snapshot_can_omit_new_requirement_and_toolchain_fields(self):
        snapshot = build_snapshot(document())
        snapshot.pop("toolchain")
        snapshot["checks"][0].pop("requirement")
        snapshot["checks"][0].pop("evidence")
        require_schema(snapshot)
        comparison = compare_snapshots(snapshot, build_snapshot(document()))
        self.assertTrue(
            comparison["requirements"]["modified"]["size.minimum"][
                "legacy_metadata_missing"
            ]
        )

    def test_inspection_rejects_malformed_check_provenance(self):
        inspection = document().inspect()
        inspection["checks"][0]["evidence"]["kind"] = "invented"
        with self.assertRaises(ValueError):
            require_schema(inspection)

    def test_validation_rejects_missing_ids_and_inconsistent_counts(self):
        for corrupt in (
            lambda r: r["results"][0].pop("id"),
            lambda r: r["summary"].update(fail=1),
            lambda r: r["summary"].update(error=True),
        ):
            with self.subTest(corruption=corrupt):
                validation = document().validate().to_dict()
                corrupt(validation)
                with self.assertRaises((TypeError, ValueError)):
                    require_schema(validation)

    def test_diff_rejects_invalid_decisions(self):
        snapshot = build_snapshot(document())
        report = compare_snapshots(snapshot, snapshot)
        report["decisions"] = [
            {"path": "x", "kind": "parameter", "disposition": "ignored"}
        ]
        with self.assertRaises(ValueError):
            require_schema(report)

    def test_policy_rejects_nonfinite_tolerances_and_bad_acceptance_records(self):
        for fields in (
            {"numeric_tolerances": {"*": {"absolute": float("inf")}}},
            {"numeric_tolerances": {"*": {"percent": float("nan")}}},
            {"accepted_changes": ["*"]},
        ):
            with (
                self.subTest(fields=fields),
                self.assertRaises((ValueError, TypeError)),
            ):
                require_schema(
                    {
                        "schema": "cadharness.comparison-policy",
                        "schema_version": "1",
                        **fields,
                    }
                )

    def test_verification_recursively_validates_evidence_and_verdict(self):
        original = verify_document(document(), baseline=build_snapshot(document()))
        require_schema(original)
        for corrupt in (
            lambda r: r.update(validation={}),
            lambda r: r["current_snapshot"].update(schema_version="999"),
            lambda r: r["verification"].update(outcome="failed"),
            lambda r: r["verification"]["policy"].update(fail_on_check_errors=0),
            lambda r: r.update(project_id="different-project"),
            lambda r: r["comparison"].update(current_revision="different-revision"),
            lambda r: r["verification"]["reasons"].append("failure"),
        ):
            with self.subTest(corruption=corrupt):
                invalid = deepcopy(original)
                corrupt(invalid)
                with self.assertRaises((TypeError, ValueError)):
                    require_schema(invalid)


if __name__ == "__main__":
    unittest.main()
