import contextlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

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
from cadharness.model import CheckStatus
from cadharness.operations import export_project

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
    def test_passing_added_requirement_uses_its_own_gate(self):
        current = document(extra=(minimum_check("size.additional", "extra", 10, 5),))
        baseline = build_snapshot(document())
        report = verify_document(current, baseline=baseline)
        self.assertTrue(report["verification"]["passed"])
        strict = verify_document(
            current,
            baseline=baseline,
            gate_policy=VerificationPolicy(fail_on_added_requirements=True),
        )
        self.assertEqual(
            [reason["code"] for reason in strict["verification"]["reasons"]],
            ["requirements_added"],
        )

    def test_allowed_removal_is_not_rejected_as_validation_removal(self):
        baseline = build_snapshot(
            document(extra=(minimum_check("size.additional", "extra", 10, 5),))
        )
        report = verify_document(
            document(),
            baseline=baseline,
            gate_policy=VerificationPolicy(fail_on_removed_requirements=False),
        )
        self.assertTrue(report["verification"]["passed"])

    def test_warning_and_skip_policies_gate_current_evidence(self):
        for status, policy, rejected in (
            (CheckStatus.WARN, VerificationPolicy(), False),
            (CheckStatus.WARN, VerificationPolicy(fail_on_warnings=True), True),
            (CheckStatus.SKIP, VerificationPolicy(), True),
            (CheckStatus.SKIP, VerificationPolicy(fail_on_skipped_checks=False), False),
        ):
            with self.subTest(status=status, policy=policy):
                check = Check(
                    "fixture.status",
                    "status",
                    lambda d: CheckResult("fixture.status", status, "fixture"),
                )
                report = verify_document(document(extra=(check,)), gate_policy=policy)
                self.assertEqual(report["verification"]["passed"], not rejected)

    def test_geometry_criteria_change_is_normative_even_with_same_shape(self):
        baseline = build_snapshot(document())
        current = document()
        current.components["block"].require_solid = False
        report = verify_document(current, baseline=baseline)
        self.assertFalse(report["verification"]["passed"])
        self.assertIn(
            "geometry.block", report["comparison"]["requirements"]["modified"]
        )
        allowed = verify_document(
            current,
            baseline=baseline,
            gate_policy=VerificationPolicy(fail_on_modified_requirements=False),
        )
        self.assertTrue(allowed["verification"]["passed"])

    def test_geometry_check_ids_cannot_be_shadowed(self):
        with self.assertRaisesRegex(ValueError, "shadow"):
            document(extra=(minimum_check("geometry.block", "shadow", 10, 5),))

    def test_invalid_evaluator_result_is_structured_error(self):
        for invalid in (
            None,
            CheckResult("fixture.invalid", "pass", "wrong status type"),
        ):
            with self.subTest(result=invalid):
                check = Check("fixture.invalid", "invalid", lambda d: invalid)
                report = verify_document(document(extra=(check,)))
                self.assertEqual(report["verification"]["outcome"], "error")
                self.assertFalse(report["verification"]["passed"])

    def test_allowed_check_error_has_consistent_gate_outcome(self):
        check = Check(
            "fixture.error",
            "error",
            lambda d: CheckResult("fixture.error", CheckStatus.ERROR, "fixture"),
        )
        report = verify_document(
            document(extra=(check,)),
            gate_policy=VerificationPolicy(fail_on_check_errors=False),
        )
        self.assertEqual(report["verification"]["outcome"], "passed")
        self.assertFalse(report["validation"]["passed"])

    def test_gate_policy_rejects_nonboolean_values(self):
        for value in (0, None, "false"):
            with self.subTest(value=value), self.assertRaises(TypeError):
                VerificationPolicy(fail_on_check_errors=value)

    def test_description_only_edit_is_informational(self):
        from dataclasses import replace

        current = document()
        current.checks = (replace(current.checks[0], description="new wording"),)
        report = verify_document(current, baseline=build_snapshot(document()))
        change = report["comparison"]["requirements"]["modified"]["size.minimum"]
        self.assertFalse(change["normative"])
        self.assertTrue(change["informational"])
        self.assertTrue(report["verification"]["passed"])

    def test_cli_gate_failure_error_and_override_exit_codes(self):
        error_check = Check(
            "fixture.error",
            "error",
            lambda d: CheckResult("fixture.error", CheckStatus.ERROR, "fixture"),
        )
        for current, flags, code, outcome in (
            (document(size=1), [], 1, "failed"),
            (document(extra=(error_check,)), [], 2, "error"),
            (document(extra=(error_check,)), ["--allow-check-errors"], 0, "passed"),
        ):
            with self.subTest(code=code):
                report = verify_document(
                    current,
                    gate_policy=VerificationPolicy(fail_on_check_errors=not flags),
                )
                output = StringIO()
                with (
                    patch("cadharness.cli.verify_project", return_value=report),
                    contextlib.redirect_stdout(output),
                ):
                    self.assertEqual(cli_main(["verify", str(BOX), *flags]), code)
                self.assertEqual(
                    json.loads(output.getvalue())["verification"]["outcome"], outcome
                )
        with contextlib.redirect_stderr(StringIO()):
            self.assertEqual(cli_main(["verify", str(BOX / "nonexistent")]), 2)

    def test_failed_export_preserves_existing_artifact_and_cleans_temporary(self):
        from types import SimpleNamespace

        def failed_export(shape, target):
            target.write_bytes(b"partial export")
            return False

        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "exports" / "verification-fixture.step"
            target.parent.mkdir()
            target.write_bytes(b"existing artifact")
            loaded = SimpleNamespace(root=root, document=document(), variant=None)
            with (
                patch("cadharness.operations.load_project", return_value=loaded),
                patch("cadharness.operations.export_step", side_effect=failed_export),
            ):
                with self.assertRaisesRegex(RuntimeError, "reported failure"):
                    export_project(root, output_dir="exports", overwrite=True)
            self.assertEqual(target.read_bytes(), b"existing artifact")
            self.assertEqual(list(target.parent.iterdir()), [target])

    def test_existing_requirement_regression_fails(self):
        baseline = build_snapshot(document(size=10))
        report = verify_document(document(size=4), baseline=baseline)
        self.assertFalse(report["verification"]["passed"])
        self.assertEqual(
            report["comparison"]["validation"]["regressions"], ["size.minimum"]
        )

    def test_new_failing_requirement_fails(self):
        added = minimum_check("size.additional", "additional minimum", 1.0, 2.0)
        report = verify_document(
            document(extra=(added,)), baseline=build_snapshot(document())
        )
        self.assertFalse(report["verification"]["passed"])
        self.assertIn("size.additional", report["comparison"]["requirements"]["added"])

    def test_unchanged_failing_design_is_not_approved(self):
        failing = document(size=1)
        report = verify_document(failing, baseline=build_snapshot(failing))
        self.assertEqual(report["comparison"]["severity"], "identical")
        self.assertFalse(report["verification"]["passed"])

    def test_relaxed_requirement_is_normative_change(self):
        report = verify_document(
            document(minimum=1), baseline=build_snapshot(document(minimum=5))
        )
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
        self.assertEqual(
            report["comparison"]["requirements"]["removed"], ["size.minimum"]
        )
        self.assertFalse(report["verification"]["passed"])

    def test_accepted_geometry_cannot_override_failed_engineering(self):
        policy = ComparisonPolicy.from_dict(
            {
                "schema": "cadharness.comparison-policy",
                "schema_version": "1",
                "accepted_changes": [
                    {
                        "path": "components.block.*",
                        "reason": "Reviewed geometry change.",
                    }
                ],
            }
        )
        report = verify_document(
            document(size=1),
            baseline=build_snapshot(document()),
            comparison_policy=policy,
        )
        self.assertFalse(report["verification"]["passed"])
        self.assertIn(
            "current_design_failed_validation",
            {item["code"] for item in report["verification"]["reasons"]},
        )

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
        self.assertTrue(
            __import__("json").loads(output.getvalue())["verification"]["passed"]
        )

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
        self.assertEqual(
            cli_result["validation"]["passed"], mcp_result["validation"]["passed"]
        )
        require_schema(cli_result, "cadharness.verification")
        require_schema(mcp_result, "cadharness.verification")


if __name__ == "__main__":
    unittest.main()
