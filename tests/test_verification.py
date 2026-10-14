import contextlib
from io import StringIO
from pathlib import Path
import unittest

from build123d import Box

from cadharness import (
    CADDocument,
    Check,
    CheckResult,
    ComparisonPolicy,
    Component,
    Requirement,
    VerificationPolicy,
    build_snapshot,
    minimum_check,
    verify_document,
)
from cadharness.cli import main as cli_main


ROOT = Path(__file__).resolve().parents[1]
BOX = ROOT / "examples" / "project-box"


def document(
    *,
    size: float = 10.0,
    minimum: float = 5.0,
    extra: tuple[Check, ...] = (),
) -> CADDocument:
    return CADDocument(
        id="verification-fixture",
        name="Verification Fixture",
        revision="1",
        components={"block": Component("block", Box(size, 10, 10))},
        checks=(minimum_check("size.minimum", "minimum size", size, minimum), *extra),
    )


class VerificationIntegrityTests(unittest.TestCase):
    def test_existing_requirement_regression_fails(self):
        baseline = build_snapshot(document(size=10))
        report = verify_document(document(size=4), baseline=baseline)
        self.assertFalse(report["verification"]["passed"])
        self.assertEqual(report["comparison"]["validation"]["regressions"], ["size.minimum"])

    def test_new_failing_requirement_fails(self):
        added = minimum_check("size.additional", "additional minimum", 1.0, 2.0)
        report = verify_document(document(extra=(added,)), baseline=build_snapshot(document()))
        self.assertFalse(report["verification"]["passed"])
        self.assertIn("size.additional", report["comparison"]["requirements"]["added"])

    def test_unchanged_failing_design_is_not_approved(self):
        failing = document(size=1)
        report = verify_document(failing, baseline=build_snapshot(failing))
        self.assertEqual(report["comparison"]["severity"], "identical")
        self.assertFalse(report["verification"]["passed"])

    def test_relaxed_requirement_is_normative_change(self):
        report = verify_document(document(minimum=1), baseline=build_snapshot(document(minimum=5)))
        change = report["comparison"]["requirements"]["modified"]["size.minimum"]
        self.assertIn("requirement", change["normative"])
        self.assertFalse(report["verification"]["passed"])

    def test_removed_requirement_is_explicit_and_gated(self):
        baseline = build_snapshot(document())
        current = CADDocument(
            id="verification-fixture",
            name="Verification Fixture",
            revision="1",
            components={"block": Component("block", Box(10, 10, 10))},
        )
        report = verify_document(current, baseline=baseline)
        self.assertEqual(report["comparison"]["requirements"]["removed"], ["size.minimum"])
        self.assertFalse(report["verification"]["passed"])

    def test_accepted_geometry_cannot_override_failed_engineering(self):
        policy = ComparisonPolicy.from_dict(
            {
                "schema": "cadharness.comparison-policy",
                "schema_version": "1",
                "accepted_changes": [
                    {"path": "components.block.*", "reason": "Reviewed geometry change."}
                ],
            }
        )
        report = verify_document(document(size=1), baseline=build_snapshot(document()), comparison_policy=policy)
        self.assertFalse(report["verification"]["passed"])
        self.assertIn("current_design_failed_validation", {item["code"] for item in report["verification"]["reasons"]})

    def test_check_exception_is_error_not_pass(self):
        def explode(_document):
            raise RuntimeError("fixture failure")

        check = Check(
            "fixture.error",
            "raises",
            explode,
            requirement=Requirement("assertion", {"value": True}),
        )
        report = verify_document(document(extra=(check,)))
        self.assertEqual(report["verification"]["outcome"], "error")
        self.assertFalse(report["verification"]["passed"])

    def test_gate_exceptions_remain_visible(self):
        report = verify_document(
            document(size=1),
            gate_policy=VerificationPolicy(fail_on_failed_checks=False),
        )
        self.assertTrue(report["verification"]["passed"])
        self.assertFalse(report["validation"]["passed"])
        self.assertFalse(report["verification"]["policy"]["fail_on_failed_checks"])

    def test_cli_verification_exit_codes(self):
        output = StringIO()
        with contextlib.redirect_stdout(output):
            code = cli_main(["--compact", "verify", str(BOX)])
        self.assertEqual(code, 0)
        self.assertTrue(__import__("json").loads(output.getvalue())["verification"]["passed"])

    def test_cli_and_mcp_verification_consistency_and_schema(self):
        from cadharness.mcp_server import verify_cad_project
        from cadharness.schema import require_schema
        import json

        output = StringIO()
        with contextlib.redirect_stdout(output):
            code = cli_main(["--compact", "verify", str(BOX)])
        self.assertEqual(code, 0)
        cli_result = json.loads(output.getvalue())
        mcp_result = verify_cad_project(str(BOX))

        self.assertEqual(cli_result["verification"], mcp_result["verification"])
        self.assertEqual(cli_result["project_id"], mcp_result["project_id"])
        self.assertEqual(cli_result["validation"]["passed"], mcp_result["validation"]["passed"])
        require_schema(cli_result, "cadharness.verification")
        require_schema(mcp_result, "cadharness.verification")


if __name__ == "__main__":
    unittest.main()
