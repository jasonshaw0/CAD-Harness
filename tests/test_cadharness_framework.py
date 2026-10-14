import contextlib
from dataclasses import dataclass
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build123d import Box

from cadharness import (
    CADDocument,
    ComparisonPolicy,
    Component,
    Parameter,
    build_snapshot,
    clearance_check,
    compare_snapshots,
    geometry_fingerprint,
    hole_diameter_check,
    load_project,
    minimum_check,
    range_check,
    require_schema,
    schema_catalog,
    wall_thickness_check,
)
from cadharness.cli import main as cli_main
from cadharness.operations import compare_project, preview_project, snapshot_project
from cadharness.project import _typed_parameters


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOX_ROOT = PROJECT_ROOT / "examples" / "project-box"
FLANGE_ROOT = PROJECT_ROOT / "examples" / "pipe-flange"
SCHEMA_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "schema-v1"


def revision_document(size: float, minimum_size: float = 5.0) -> CADDocument:
    return CADDocument(
        id="revision-fixture",
        name="Revision Fixture",
        revision=f"size-{size:g}",
        components={"block": Component("block", Box(size, 10, 10))},
        parameters={"size": Parameter(size, unit="mm")},
        checks=(
            minimum_check(
                "size.minimum", "fixture size", size, minimum_size, unit="mm"
            ),
        ),
    )


class CoreModelTests(unittest.TestCase):
    def test_range_check_supports_inclusive_one_or_two_sided_bounds(self):
        document = revision_document(10.0)
        bounded = range_check("size.range", "bounded size", 3.0, minimum=2.0, maximum=4.0)
        lower_only = range_check("size.minimum", "minimum size", 2.0, minimum=2.0)
        self.assertEqual(bounded.evaluator(document).status.value, "pass")
        self.assertEqual(lower_only.evaluator(document).status.value, "pass")
        with self.assertRaisesRegex(ValueError, "requires"):
            range_check("size.invalid", "invalid", 1.0)
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            range_check("size.invalid", "invalid", 1.0, minimum=2.0, maximum=1.0)

    def test_specialized_dimensional_checks_preserve_measurement_meaning(self):
        document = revision_document(10.0)
        checks = (
            clearance_check("fit.clearance", "fit clearance", 0.25, 0.2),
            wall_thickness_check("section.wall", "wall thickness", 1.8, 1.6),
            hole_diameter_check(
                "hole.mount", "mounting hole", 4.1, 4.0,
                lower_deviation=0.0, upper_deviation=0.2,
            ),
        )
        self.assertEqual([check.category for check in checks], ["clearance", "section", "hole"])
        results = [check.evaluator(document) for check in checks]
        self.assertTrue(all(result.status.value == "pass" for result in results))
        self.assertEqual(
            [result.evidence["measurement_kind"] for result in results],
            ["clearance", "wall-thickness", "hole-diameter"],
        )
        self.assertEqual(results[2].expected, {"minimum": 4.0, "maximum": 4.2})

    def test_hole_diameter_check_rejects_inverted_deviations(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            hole_diameter_check(
                "hole.invalid", "invalid hole", 4.0, 4.0,
                lower_deviation=0.2, upper_deviation=0.1,
            )

    def test_published_schema_fixtures_are_supported(self):
        expected = {
            "comparison-policy.json": "cadharness.comparison-policy",
            "diff.json": "cadharness.diff",
            "inspection.json": "cadharness.inspection",
            "snapshot.json": "cadharness.snapshot",
            "validation.json": "cadharness.validation",
        }
        self.assertEqual(
            [item["name"] for item in schema_catalog()["schemas"]],
            sorted(expected.values()),
        )
        for filename, schema_name in expected.items():
            with self.subTest(fixture=filename):
                document = json.loads(
                    (SCHEMA_FIXTURES / filename).read_text(encoding="utf-8")
                )
                spec = require_schema(document, schema_name, label=filename)
                self.assertEqual(spec.version, "1")
        policy = json.loads(
            (SCHEMA_FIXTURES / "comparison-policy.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn(
            "components.*.geometry.volume_mm3",
            ComparisonPolicy.from_dict(policy).numeric_tolerances,
        )

    def test_runtime_documents_match_v1_fixture_root_contracts(self):
        document = revision_document(10.0)
        snapshot = build_snapshot(document)
        runtime_documents = {
            "inspection.json": document.inspect(),
            "validation.json": document.validate().to_dict(),
            "snapshot.json": snapshot,
            "diff.json": compare_snapshots(snapshot, build_snapshot(document)),
        }
        for filename, runtime_document in runtime_documents.items():
            with self.subTest(fixture=filename):
                fixture = json.loads(
                    (SCHEMA_FIXTURES / filename).read_text(encoding="utf-8")
                )
                require_schema(runtime_document, fixture["schema"])
                self.assertEqual(set(runtime_document), set(fixture))

    def test_schema_compatibility_rejects_unknown_versions(self):
        fixture = json.loads(
            (SCHEMA_FIXTURES / "validation.json").read_text(encoding="utf-8")
        )
        fixture["schema_version"] = "999"
        with self.assertRaisesRegex(ValueError, "unsupported.*schema version"):
            require_schema(fixture)

    def test_variant_values_are_checked_against_dataclass_types(self):
        @dataclass(frozen=True)
        class Parameters:
            width: float = 10.0
            count: int = 4

        configured = _typed_parameters(Parameters, {"width": 12})
        self.assertEqual(configured.width, 12.0)
        with self.assertRaisesRegex(TypeError, "must be an integer"):
            _typed_parameters(Parameters, {"count": 4.5})
        with self.assertRaisesRegex(ValueError, "unknown variant fields"):
            _typed_parameters(Parameters, {"depth": 5.0})

    def test_failed_engineering_check_is_structured(self):
        report = revision_document(1.0).validate().to_dict()
        self.assertFalse(report["passed"])
        self.assertEqual(report["summary"]["fail"], 1)
        failed = next(result for result in report["results"] if result["status"] == "fail")
        self.assertEqual(failed["actual"], 1.0)
        self.assertEqual(failed["expected"], {"minimum": 5.0})

    def test_geometry_fingerprint_is_stable_and_geometry_sensitive(self):
        self.assertEqual(
            geometry_fingerprint(Box(10, 20, 30)),
            geometry_fingerprint(Box(10, 20, 30)),
        )
        self.assertNotEqual(
            geometry_fingerprint(Box(10, 20, 30)),
            geometry_fingerprint(Box(11, 20, 30)),
        )

    def test_snapshot_diff_reports_geometry_and_validation_regression(self):
        baseline = build_snapshot(revision_document(10.0))
        current = build_snapshot(revision_document(4.0))
        comparison = compare_snapshots(baseline, current)
        self.assertEqual(comparison["severity"], "regression")
        self.assertEqual(comparison["summary"]["parameters_changed"], 1)
        self.assertEqual(comparison["summary"]["components_changed"], 1)
        self.assertEqual(comparison["validation"]["regressions"], ["size.minimum"])
        geometry = comparison["components"]["changed"]["block"]["geometry"]
        self.assertTrue(geometry["fingerprint"]["changed"])
        self.assertEqual(geometry["bounding_box_size_mm"]["x"]["delta"], -6.0)

    def test_identical_snapshots_compare_identically(self):
        snapshot = build_snapshot(revision_document(10.0))
        comparison = compare_snapshots(
            snapshot, build_snapshot(revision_document(10.0))
        )
        self.assertFalse(comparison["changed"])
        self.assertEqual(comparison["severity"], "identical")

    def test_validation_regression_cannot_be_accepted_by_policy(self):
        policy = ComparisonPolicy.from_dict(
            {
                "schema": "cadharness.comparison-policy",
                "schema_version": "1",
                "accepted_changes": [
                    {
                        "path": "validation.size.minimum.status",
                        "reason": "This attempted waiver must not hide a regression.",
                    }
                ],
            }
        )
        comparison = compare_snapshots(
            build_snapshot(revision_document(10.0)),
            build_snapshot(revision_document(4.0)),
            policy=policy,
        )
        self.assertEqual(comparison["severity"], "regression")
        status = next(
            decision
            for decision in comparison["decisions"]
            if decision["path"] == "validation.size.minimum.status"
        )
        self.assertEqual(status["disposition"], "significant")

    def test_policy_requires_reasoned_acceptances(self):
        with self.assertRaisesRegex(ValueError, "needs a reason"):
            ComparisonPolicy.from_dict(
                {
                    "schema": "cadharness.comparison-policy",
                    "schema_version": "1",
                    "accepted_changes": [
                        {"path": "components.block.fingerprint", "reason": ""}
                    ],
                }
            )


class ProjectWorkflowTests(unittest.TestCase):
    def test_project_discovery_examples_are_independent(self):
        box = load_project(BOX_ROOT)
        flange = load_project(FLANGE_ROOT)
        self.assertEqual(box.manifest.id, "project-box")
        self.assertEqual(flange.manifest.id, "pipe-flange")
        self.assertEqual(set(box.document.components), {"base", "lid"})
        self.assertEqual(set(flange.document.components), {"flange"})
        self.assertEqual(box.variant, "standard")
        self.assertEqual(flange.variant, "standard")

    def test_named_variants_are_typed_and_change_geometry(self):
        standard = load_project(BOX_ROOT, variant="standard")
        clearance = load_project(BOX_ROOT, variant="clearance-fit")
        self.assertEqual(clearance.variant_values, {"lid_clearance_per_side": 0.32})
        self.assertEqual(
            clearance.document.parameters["lid_clearance_per_side"].value, 0.32
        )
        self.assertNotEqual(
            geometry_fingerprint(standard.document.components["lid"].shape),
            geometry_fingerprint(clearance.document.components["lid"].shape),
        )
        with self.assertRaisesRegex(ValueError, "unknown variant"):
            load_project(BOX_ROOT, variant="missing")

    def test_examples_validate(self):
        for root in (BOX_ROOT, FLANGE_ROOT):
            with self.subTest(project=root.name):
                report = load_project(root).document.validate().to_dict()
                self.assertTrue(report["passed"])

    def test_inspection_exposes_richer_geometry_evidence(self):
        inspection = load_project(FLANGE_ROOT).document.inspect()
        geometry = inspection["components"]["flange"]["geometry"]
        self.assertTrue(geometry["valid"])
        self.assertTrue(geometry["manifold"])
        self.assertTrue(geometry["fingerprint"].startswith("sha256:"))
        self.assertIn("cylinder", geometry["geometry_types"]["surfaces"])
        self.assertIn("circle", geometry["geometry_types"]["curves"])

    def test_snapshot_compare_and_preview_artifact_workflow(self):
        with TemporaryDirectory(dir=BOX_ROOT) as temporary:
            temporary_path = Path(temporary)
            baseline = temporary_path / "baseline.json"
            diff_path = temporary_path / "clearance-fit.diff.json"
            snapshot = snapshot_project(
                BOX_ROOT, output_file=baseline, variant="standard"
            )
            comparison = compare_project(
                BOX_ROOT,
                baseline_file=baseline,
                variant="clearance-fit",
                output_file=diff_path,
            )
            preview = preview_project(
                BOX_ROOT,
                output_dir=temporary_path / "previews",
                views=("iso", "top"),
            )
            self.assertTrue(snapshot["validation_passed"])
            self.assertEqual(comparison["severity"], "accepted")
            self.assertEqual(comparison["summary"]["significant_changes"], 0)
            self.assertGreater(comparison["summary"]["tolerated_changes"], 0)
            self.assertTrue(diff_path.is_file())
            self.assertEqual(len(preview["outputs"]), 2)
            for output in preview["outputs"]:
                svg = Path(output["path"]).read_text(encoding="utf-8")
                self.assertIn("<svg", svg)
                self.assertGreater(output["visible_edges"], 0)

    def test_artifacts_cannot_escape_project_root(self):
        with self.assertRaises(ValueError):
            snapshot_project(BOX_ROOT, output_file=PROJECT_ROOT / "outside.json")

    def test_cli_emits_machine_readable_json(self):
        output = StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = cli_main(["--compact", "validate", str(BOX_ROOT)])
        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(output.getvalue())["passed"])

    def test_cli_lists_supported_schemas(self):
        output = StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = cli_main(["--compact", "schemas"])
        self.assertEqual(exit_code, 0)
        schemas = json.loads(output.getvalue())["schemas"]
        self.assertEqual(len(schemas), 5)
        self.assertEqual(schemas[0]["version"], "1")


if __name__ == "__main__":
    unittest.main()
