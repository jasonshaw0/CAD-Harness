from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cadharness import load_project, verify_document
from cadharness.workflow.cli import main
from cadharness.workflow.acceptance import bind_requirements, update_coverage
from cadharness.workflow.benchmarks.cases import get_case
from cadharness.workflow.brief import read_json, validate_brief
from cadharness.workflow.runner import (
    ROOT, _child_environment, init_run, review_hashes, check_revision,
    revise, export_revision, assert_current,
)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def create(self, case="square-mount", run_id=None):
        return Path(init_run(run_id or case, get_case(case)["prompt"], root=self.root, case=case)["revision"])

    def edit(self, path, transform):
        path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")

    def check(self, revision, **kwargs):
        # Tests attest only repository-owned fixtures that this test edits explicitly.
        hashes = review_hashes(revision)
        return check_revision(revision, reviewed_source=hashes["source_sha256"], accepted_brief=hashes["brief_sha256"], **kwargs)

    def evaluate(self, revision, variant="standard", brief=None):
        document = load_project(revision / "project", variant=variant).document
        doc, coverage = bind_requirements(document, brief or get_case(revision.parent.parent.name)["brief"])
        result = verify_document(doc)
        return result, update_coverage(coverage, result["validation"])

    def test_square_fail_repair_review_and_export_excludes_reference_geometry(self):
        revision = self.create()
        source = revision / "project" / "project.py"
        self.edit(source, lambda s: s.replace("modeled_hole_count: int = -1", "modeled_hole_count: int = 3"))
        failed = self.check(revision)
        self.assertEqual(failed["outcome"], "needs-revision")
        self.assertEqual(next(row for row in failed["coverage"] if row["id"] == "holes.count")["status"], "fail")
        old_artifacts = dict(failed["artifacts"])
        repair = Path(revise(revision)["revision"])
        self.edit(repair / "project" / "project.py", lambda s: s.replace("modeled_hole_count: int = 3", "modeled_hole_count: int = -1"))
        passed = self.check(repair)
        self.assertTrue(passed["ready_for_review"], passed["errors"] + passed["blocking_reasons"])
        self.assertEqual(old_artifacts, read_json(revision / "run.json")["artifacts"])
        self.assertEqual(passed["brief_sha256"], failed["brief_sha256"])
        self.assertTrue((repair / "project" / "evidence" / "comparison.json").is_file())
        self.assertIn("Physical fit", (repair / "review.md").read_text())
        output = export_revision(repair)
        self.assertEqual([item["component_id"] for item in output["outputs"]], ["plate"])
        self.assertGreater(Path(output["outputs"][0]["path"]).stat().st_size, 100)
        with self.assertRaises(FileExistsError):
            export_revision(repair)
        with self.assertRaisesRegex(ValueError, "reference geometry"):
            export_revision(repair, file_format="stl", component_ids=["motor-envelope"])

    def test_existing_mount_adversaries_and_rotation_are_measured(self):
        revision = self.create()
        for variant, failing_id in (("missing-hole", "holes.count"), ("shifted-hole", "holes.h2.diameter"),
                                    ("wrong-diameter", "holes.h0.diameter"), ("tight-clearance", "cable.clearance"),
                                    ("rotated-pattern", "holes.h0.diameter")):
            with self.subTest(variant=variant):
                report, rows = self.evaluate(revision, variant)
                self.assertFalse(report["verification"]["passed"])
                self.assertEqual(next(row for row in rows if row["id"] == failing_id)["status"], "fail")

    def test_circle_blind_bore_and_declared_count_do_not_hide_geometry(self):
        revision = self.create("circular-plate")
        report, _ = self.evaluate(revision)
        self.assertTrue(report["verification"]["passed"])
        # Defect variants have their own manifest defaults, so explicitly retain
        # the circular geometry while changing only bore depth.
        self.edit(revision / "project" / "project.py", lambda s: s.replace("blind_bore: bool = False", "blind_bore: bool = True"))
        report, rows = self.evaluate(revision)
        self.assertEqual(next(row for row in rows if row["id"] == "bore.extent")["status"], "fail")
        fixture = get_case("circular-plate")["brief"]
        fixture["requirements"][6]["criteria"]["expected"] = 8
        report, rows = self.evaluate(revision, brief=fixture)
        self.assertEqual(next(row for row in rows if row["id"] == "holes.count")["result"]["actual"], 6)
        self.assertFalse(report["verification"]["passed"])

    def test_enclosure_actual_wall_and_skirt_interference(self):
        revision = self.create("enclosure")
        report, rows = self.evaluate(revision)
        self.assertTrue(report["verification"]["passed"])
        self.assertEqual(next(row for row in rows if row["id"] == "fit.physical")["status"], "not-yet-verified")
        source = revision / "project" / "project.py"
        self.edit(source, lambda s: s.replace("return Part(outer - cavity).clean()", "return Part((outer - cavity) - Pos(31.6, 0, 10) * Box(2, 8, 8)).clean()"))
        report, rows = self.evaluate(revision)
        self.assertEqual(next(row for row in rows if row["id"] == "sample.x-wall")["status"], "fail")
        self.edit(source, lambda s: s.replace("params.inside_x - 2 * params.lid_clearance_per_side", "params.inside_x + 1.0"))
        report, rows = self.evaluate(revision)
        self.assertEqual(next(row for row in rows if row["id"] == "assembly.interference")["status"], "fail")

    def test_hash_inspection_never_executes_source_and_mismatch_blocks(self):
        revision = self.create()
        marker = self.root / "executed.txt"
        self.edit(revision / "project" / "project.py", lambda s: f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n" + s)
        hashes = review_hashes(revision)
        self.assertFalse(marker.exists())
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            check_revision(revision, reviewed_source="wrong", accepted_brief=hashes["brief_sha256"])
        self.assertFalse(marker.exists())

    def test_brief_relaxation_and_removal_cannot_be_a_repair(self):
        revision = self.create()
        self.check(revision)
        repair = Path(revise(revision)["revision"])
        brief_path = revision.parent.parent / "brief-v001.json"
        brief = read_json(brief_path)
        for mutate in (lambda b: b["requirements"][0]["criteria"].update(absolute_tolerance=100),
                       lambda b: b["requirements"].pop()):
            modified = deepcopy(brief)
            mutate(modified)
            brief_path.write_text(json.dumps(modified))
            with self.assertRaisesRegex(ValueError, "accepted brief changed"):
                self.check(repair)
        brief_path.write_text(json.dumps(brief))

    def test_candidate_cannot_shadow_or_omit_external_acceptance(self):
        revision = self.create()
        document = load_project(revision / "project").document
        self.assertEqual(document.checks, ())
        doc, _ = bind_requirements(document, get_case("square-mount")["brief"])
        self.assertGreater(len(doc.checks), 20)
        with self.assertRaisesRegex(ValueError, "reserved"):
            bind_requirements(doc, get_case("square-mount")["brief"])

    def test_unknown_mandatory_and_external_requirements_prevent_ready(self):
        revision = self.create()
        path = revision.parent.parent / "brief-v001.json"
        brief = read_json(path)
        brief["requirements"].append({"id": "strength", "description": "Strength", "mandatory": True,
            "evidence_kind": "external", "prompt_ref": "prompt.txt", "binding": {"type": "fea"}, "criteria": {}})
        path.write_text(json.dumps(brief))
        result = self.check(revision)
        self.assertTrue(result["verification_passed"])
        self.assertFalse(result["ready_for_review"])
        self.assertEqual(result["coverage"][-1]["status"], "unknown")

    def test_blocking_prompt_ambiguity_does_not_execute(self):
        for prompt in ("Make a NEMA 17 mount", "Make a plate 2 inches / 60 mm wide"):
            revision = Path(init_run("ambiguous-" + str(len(list(self.root.iterdir()))), prompt, root=self.root)["revision"])
            with patch("cadharness.workflow.runner._run_worker", side_effect=AssertionError("must not execute")):
                report = self.check(revision)
            self.assertEqual(report["outcome"], "blocked")
            self.assertIn(prompt, (revision.parent.parent / "prompt.txt").read_text())

    def test_units_nonfinite_and_duplicate_ids_are_rejected(self):
        brief = get_case("square-mount")["brief"]
        brief["dimensions"]["inch-input"] = {"value": 2.5, "unit": "in", "source": "user-measurement", "prompt_ref": "clarifications.md"}
        self.assertEqual(validate_brief(brief)["normalized_dimensions"]["inch-input"]["value"], 63.5)
        brief["dimensions"]["inch-input"]["normalized_value"] = 60
        with self.assertRaisesRegex(ValueError, "conflicting"):
            validate_brief(brief)
        brief["dimensions"]["inch-input"]["unit"] = None
        with self.assertRaisesRegex(ValueError, "units"):
            validate_brief(brief)
        brief = get_case("square-mount")["brief"]
        brief["requirements"].append(brief["requirements"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_brief(brief)
        brief = get_case("square-mount")["brief"]
        brief["requirements"][0]["criteria"]["expected"] = float("nan")
        with self.assertRaises(ValueError):
            validate_brief(brief)

    def test_stale_source_artifacts_and_overwrite_are_refused(self):
        revision = self.create()
        report = self.check(revision)
        with self.assertRaises(FileExistsError):
            self.check(revision)
        original_source = (revision / "project" / "project.py").read_bytes()
        self.edit(revision / "project" / "project.py", lambda s: s + "\n# changed\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            export_revision(revision)
        (revision / "project" / "project.py").write_bytes(original_source)
        self.edit(revision / "project" / "evidence" / "snapshot.json", lambda s: s + " ")
        with self.assertRaisesRegex(ValueError, "artifacts changed"):
            assert_current(revision, report)
        with self.assertRaises(FileExistsError):
            self.create()

    def test_worker_timeout_and_execution_error_preserve_failures(self):
        revision = self.create()
        with patch("cadharness.workflow.runner._run_worker", side_effect=subprocess.TimeoutExpired("worker", 0.1)):
            report = self.check(revision)
        self.assertEqual(report["outcome"], "error")
        self.assertTrue((revision / "review.md").is_file())
        revision = self.create(run_id="broken")
        self.edit(revision / "project" / "project.py", lambda s: "raise RuntimeError('deliberate failure')\n")
        report = self.check(revision)
        self.assertEqual(report["outcome"], "error")
        self.assertIn("deliberate failure", (revision / "project/evidence/worker.stderr.txt").read_text())

    def test_no_blind_retry_and_explicit_iteration_budget(self):
        revision = self.create()
        self.edit(revision / "project" / "project.py", lambda s: s.replace("modeled_hole_count: int = -1", "modeled_hole_count: int = 3"))
        self.check(revision)
        repair = Path(revise(revision)["revision"])
        with patch("cadharness.workflow.runner._run_worker", side_effect=AssertionError("must not execute")):
            report = self.check(repair)
        self.assertEqual(report["outcome"], "blocked")
        self.assertTrue(any("unchanged" in reason for reason in report["blocking_reasons"]))
        budget = self.create(run_id="budget")
        report = self.check(budget, active_seconds=900)
        self.assertEqual(report["outcome"], "blocked")

    def test_environment_drops_credentials_and_cli_requires_attestation(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret", "PROVIDER_TOKEN": "test-secret", "PYTHONPATH": "untrusted"}):
            child = _child_environment()
            self.assertNotIn("OPENAI_API_KEY", child)
            self.assertNotIn("PROVIDER_TOKEN", child)
            self.assertNotIn("PYTHONPATH", child)
        revision = self.create()
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(main(["check", str(revision)]), 2)
        self.assertIn("review", errors.getvalue())
        with redirect_stdout(output):
            self.assertEqual(main(["check", str(revision), "--review-hashes"]), 0)

    def test_intent_change_uses_new_brief_and_preserves_frozen_prompt(self):
        revision = self.create()
        first = self.check(revision)
        run = revision.parent.parent
        original_prompt = (run / "prompt.txt").read_text()
        (run / "clarifications.md").write_text("User changed plate thickness to 5 mm.")
        brief = read_json(run / "brief-v001.json")
        brief["revision"] = 2
        for req in brief["requirements"]:
            if req["id"] == "plate.z" or req["id"].endswith(".extent") or req["id"] in {"motor-envelope.bottom", "cable-keepout.bottom"}:
                req["criteria"]["expected"] = 5
        (run / "brief-v002.json").write_text(json.dumps(brief))
        repair = Path(revise(revision, brief_name="brief-v002.json")["revision"])
        self.edit(repair / "project/project.py", lambda s: s.replace("thickness: float = 4.0", "thickness: float = 5.0"))
        result = self.check(repair)
        self.assertTrue(result["ready_for_review"], result["blocking_reasons"])
        self.assertNotEqual(result["brief_sha256"], first["brief_sha256"])
        self.assertEqual((revision / "project/evidence/prompt.txt").read_text(), original_prompt)
        self.assertIn("5 mm", (repair / "project/evidence/clarifications.md").read_text())

    def test_iteration_limit_stops_fourth_candidate_before_import(self):
        revision = self.create()
        self.edit(revision / "project/project.py", lambda s: s.replace("modeled_hole_count: int = -1", "modeled_hole_count: int = 3"))
        for attempt in range(3):
            if attempt:
                revision = Path(revise(revision)["revision"])
                self.edit(revision / "project/project.py", lambda s: s + f"\n# attempted repair {attempt}\n")
            self.assertEqual(self.check(revision)["outcome"], "needs-revision")
        revision = Path(revise(revision)["revision"])
        self.edit(revision / "project/project.py", lambda s: s + "\n# fourth attempt\n")
        with patch("cadharness.workflow.runner._run_worker", side_effect=AssertionError("must not execute")):
            report = self.check(revision)
        self.assertEqual(report["outcome"], "blocked")
        self.assertIn("initial candidate plus two repairs exhausted", report["blocking_reasons"])

    def test_reference_cannot_be_relabelled_as_the_printable_part(self):
        revision = self.create()
        self.edit(revision / "project/project.py", lambda s: s.replace('role="printable-part"', 'role="reference-envelope"').replace(
            'Component("motor-envelope", motor, role="reference-envelope")', 'Component("motor-envelope", motor, role="printable-part")'))
        report = self.check(revision)
        self.assertEqual(report["outcome"], "error")
        self.assertIn("roles do not match", (revision / "project/evidence/worker.stderr.txt").read_text())

    def test_review_html_escapes_prompt_derived_text(self):
        revision = self.create()
        path = revision.parent.parent / "brief-v001.json"
        brief = read_json(path)
        brief["assumptions"].append({"description": '<script>alert("unsafe")</script>', "blocking": False})
        path.write_text(json.dumps(brief))
        report = self.check(revision)
        html = (revision / "review.html").read_text()
        self.assertTrue(report["ready_for_review"])
        self.assertNotIn('<script>alert', html)
        self.assertIn('&lt;script&gt;', html)

    def test_real_worker_receives_no_provider_secret_and_preserves_variant(self):
        revision = self.create()
        source = revision / "project/project.py"
        self.edit(source, lambda s: "import os\nassert 'OPENAI_API_KEY' not in os.environ\nassert 'PROVIDER_TOKEN' not in os.environ\n" + s)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret", "PROVIDER_TOKEN": "test-secret"}):
            report = self.check(revision)
        self.assertTrue(report["ready_for_review"], report["errors"])
        inspection = read_json(revision / "project/evidence/inspection.json")
        self.assertEqual(inspection["manifest"]["variant"], "standard")
        self.assertIn("Variant standard", (revision / "project/inspector/index.html").read_text())

    def test_real_worker_timeout_leaves_unknown_evidence(self):
        revision = self.create()
        report = self.check(revision, timeout=0.05)
        self.assertEqual(report["outcome"], "error")
        self.assertTrue(any("timed out" in item for item in report["errors"]))
        self.assertTrue(all(row["status"] == "unknown" for row in report["coverage"]))
        self.assertTrue((revision / "review.html").exists())

    def test_factory_writing_an_input_invalidates_evidence(self):
        revision = self.create()
        self.edit(revision / "project/project.py", lambda s: "from pathlib import Path\nPath(__file__).with_name('new-input.txt').write_text('changed')\n" + s)
        report = self.check(revision)
        self.assertFalse(report["ready_for_review"])
        self.assertTrue(any("stale" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
