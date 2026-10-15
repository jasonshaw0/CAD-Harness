"""Studio integration checks without a model account or a browser in CI."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient
from cadharness import CADDocument, Component
from build123d import Box, Pos

from cadharness.workflow.benchmarks.cases import get_case
from cadharness.workflow.brief import read_json
from cadharness.workflow.runner import ROOT, check_revision, init_run, revise
from cadharness.studio.assistant import IDEAssistant
from cadharness.studio.jobs import ACTIVE, Jobs
from cadharness.studio.processes import Cancelled, run_process
from cadharness.studio.scene import write_scene
from cadharness.studio.server import create_app
from cadharness.studio.store import Store, contained, save, write_candidate


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "studio")

    def wait(self, jobs, job, seconds=25):
        deadline = time.monotonic() + seconds
        while jobs.active_id and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertIsNone(jobs.active_id, "job did not finish")
        return jobs.store.job(job["id"])

    def proposal(self, instruction="", *, defect=False, revision=1):
        fixture = get_case("square-mount")
        brief = deepcopy(fixture["brief"])
        brief["revision"] = revision
        template = ROOT / fixture["template"]
        files = [{"path": p.name, "content": p.read_text(encoding="utf-8")}
                 for p in template.iterdir() if p.suffix in {".py", ".toml"}]
        if defect:
            for item in files:
                item["content"] = item["content"].replace("modeled_hole_count: int = -1", "modeled_hole_count: int = 3")
        return {"kind": "design", "summary": instruction or "A mounting plate", "questions": [],
                "files": files, "brief_json": json.dumps(brief)}

    def test_mesh_preserves_component_world_coordinates_and_geometry_identity(self):
        doc = CADDocument("mesh-test", "Mesh", "v1", components={
            "part": Component("part", Pos(10, 20, 30) * Box(4, 6, 8), role="printable-part"),
            "reference": Component("reference", Box(2, 2, 2), role="reference-envelope")})
        before = doc.inspect()
        scene = write_scene(doc, before, self.root / "scene.json", self.root / "cache")
        self.assertEqual(before, doc.inspect(), "tessellation changed the authoritative shapes")
        self.assertEqual([c["id"] for c in scene["components"]], list(doc.components))
        part = scene["components"][0]
        self.assertEqual(part["fingerprint"], before["components"]["part"]["geometry"]["fingerprint"])
        self.assertEqual((min(part["positions"][::3]), max(part["positions"][::3])), (8, 12))
        self.assertLess(max(part["indices"]), len(part["positions"]) // 3)
        cached = write_scene(doc, before, self.root / "cached.json", self.root / "cache")
        self.assertEqual(scene, cached)

    def test_authorization_origin_and_proposal_containment(self):
        with TestClient(create_app(self.root / "api")) as client:
            token = client.get("/api/session").json()["token"]
            self.assertEqual(client.post("/api/designs", json={"example": "flange"}).status_code, 403)
            headers = {"X-Studio-Token": token}
            self.assertEqual(client.post("/api/designs", headers=headers, json={"example": "flange"}).status_code, 403)
            self.assertEqual(client.post("/api/session", headers={**headers, "Origin": "https://evil.invalid"}, json={"authorize": True}).status_code, 403)
            self.assertTrue(client.post("/api/session", headers=headers, json={"authorize": True}).json()["authorized"])
            self.assertEqual(client.get("/api/designs/bad..id").status_code, 400)
        for name in ("../x.py", "C:/x.py", "/x.py", "a\\x.py", "exports/x.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                write_candidate(self.root / name.replace("/", "_").replace(":", "_").replace("\\", "_").replace("..", "dot"), [{"path": name, "content": ""}])
        with self.assertRaises(ValueError):
            contained(self.root, "../outside")

    def test_trusted_execution_does_not_claim_human_review(self):
        revision = Path(init_run("trusted", "fixture", root=self.root, case="square-mount")["revision"])
        with self.assertRaisesRegex(ValueError, "session authorization"):
            check_revision(revision, execution_mode="trusted-session")
        report = check_revision(revision, execution_mode="trusted-session", session_id="session-test")
        self.assertTrue(report["ready_for_review"])
        self.assertIsNone(report["reviewed_source"])
        self.assertEqual(report["execution_authorization"], {"mode": "trusted-session", "session_id": "session-test"})

    def test_examples_have_real_scenes_and_failed_build_retains_display(self):
        jobs = Jobs(self.store)
        for example in ("square-mount", "enclosure", "flange"):
            design = self.store.create(example)
            job = jobs.submit(design["id"], example=example, session_id="test")
            result = self.wait(jobs, job)
            self.assertEqual(result["status"], "ready", result)
            design = self.store.get(design["id"])
            self.assertEqual(design["display_revision"], "r001")
            revision = self.store.design_root(design["id"]) / "revisions/r001"
            self.assertTrue(read_json(revision / "project/evidence/scene.json")["components"])
        job = jobs.submit(design["id"], rebuild=True, session_id="test")
        self.assertEqual(self.wait(jobs, job)["status"], "ready")
        design = self.store.get(design["id"])
        root = self.store.design_root(design["id"])
        self.assertEqual(read_json(root / "revisions/r001/run.json")["brief_sha256"],
                         read_json(root / "revisions/r002/run.json")["brief_sha256"])
        # A real failing factory is evaluated; the preceding model remains selected.
        broken = self.proposal()
        broken["files"] = [{"path": "project.py", "content": "raise RuntimeError('seeded build failure')"},
                           {"path": "cadharness.toml", "content": '[project]\nid="broken"\nname="Broken"\nentrypoint="project.py:create_project"\n'}]
        brief = json.loads(broken["brief_json"])
        brief.update(id=design["id"], revision=2)
        revision = jobs.revision(design, brief, broken["files"], "job-failure")
        report = jobs.evaluate(revision, "test", threading.Event())
        jobs.evaluated(design, revision, report, "Deliberate failure")
        saved = self.store.get(design["id"])
        self.assertEqual(saved["display_revision"], "r002")
        self.assertEqual(saved["latest_revision"], "r003")
        self.assertEqual(report["outcome"], "error")

    def test_repair_freezes_requirements_but_next_turn_can_change_intent(self):
        calls = []
        def generator(prompt, **kwargs):
            calls.append(prompt)
            proposal = self.proposal(defect=len(calls) == 1)
            if len(calls) == 2:
                proposal["brief_json"] = ""
            return proposal
        jobs = Jobs(self.store, generator=generator)
        design = self.store.create("repair")
        job = jobs.submit(design["id"], "Make a plate", session_id="test")
        self.assertEqual(self.wait(jobs, job)["status"], "ready")
        root = self.store.design_root(design["id"])
        one, two = [read_json(root / f"revisions/{r}/run.json") for r in ("r001", "r002")]
        self.assertEqual(one["brief_sha256"], two["brief_sha256"])
        self.assertIn('"repair_failure": {', calls[1])
        # Existing *.lock.json files must not prevent a subsequent turn.
        job = jobs.submit(design["id"], "Keep dimensions; continue", selected=["plate"], session_id="test")
        self.assertEqual(self.wait(jobs, job)["status"], "ready")
        self.assertTrue((root / "brief-v002.json").exists())
        self.assertIn('"selected_components": ["plate"]', calls[-1])

    def test_requirement_relaxation_is_rejected_during_repair(self):
        attempts = 0
        def generator(prompt, **kwargs):
            nonlocal attempts
            attempts += 1
            result = self.proposal(defect=True)
            if attempts == 2:
                brief = json.loads(result["brief_json"])
                brief["requirements"][0]["criteria"]["expected"] = 999
                result["brief_json"] = json.dumps(brief)
            return result
        jobs = Jobs(self.store, generator=generator)
        design = self.store.create("drift")
        job = jobs.submit(design["id"], "Make a plate", session_id="test")
        result = self.wait(jobs, job)
        self.assertEqual(result["status"], "failed")
        self.assertIn("frozen acceptance", result["error"])
        self.assertEqual(len(self.store.get(design["id"])["revisions"]), 1)

    def test_unsupported_measurement_remains_unknown_without_futile_repairs(self):
        calls = []
        def generator(prompt, **kwargs):
            calls.append(prompt)
            proposal = self.proposal()
            brief = json.loads(proposal["brief_json"])
            brief["requirements"].append({"id": "unsupported", "description": "Unmeasured cavity",
                "mandatory": True, "prompt_ref": "user", "evidence_kind": "geometry-derived",
                "unit": "mm", "criteria": {"expected": 42}, "binding": {"type": "cavity-face"}})
            proposal["brief_json"] = json.dumps(brief)
            return proposal
        jobs = Jobs(self.store, generator=generator)
        design = self.store.create("unsupported")
        job = jobs.submit(design["id"], "Measure a cavity", session_id="test")
        self.assertEqual(self.wait(jobs, job)["status"], "needs-revision")
        self.assertEqual(len(calls), 1)
        design = self.store.get(design["id"])
        self.assertEqual(design["display_revision"], "r001")
        report = read_json(self.store.design_root(design["id"]) / "revisions/r001/run.json")
        self.assertFalse(report["ready_for_review"])
        self.assertEqual(report["coverage"][-1]["status"], "unknown")

    def test_budget_is_per_turn_and_can_continue_after_three_failures(self):
        jobs = Jobs(self.store)
        design = self.store.create("budget")
        root = self.store.design_root(design["id"])
        (root / "prompt.txt").write_text("plate")
        proposal = self.proposal()
        brief = json.loads(proposal["brief_json"])
        brief.update(id=design["id"])
        # The owned worker fails, allowing a cheap independent check of runner limits.
        import subprocess
        failed_worker = lambda *a, **k: subprocess.CompletedProcess([], 2, "", "seeded")
        for i in range(3):
            files = deepcopy(proposal["files"])
            files[0]["content"] += f"\n# attempt {i}\n"
            revision = jobs.revision(design, brief, files, "job-first")
            check_revision(revision, execution_mode="trusted-session", session_id="test", worker_runner=failed_worker)
        revision = jobs.revision(design, brief, proposal["files"], "job-second")
        report = check_revision(revision, execution_mode="trusted-session", session_id="test", worker_runner=failed_worker)
        self.assertNotIn("initial candidate plus two repairs exhausted", report["blocking_reasons"])
        self.assertEqual(report["outcome"], "error")

    def test_clarification_and_cancellation_preserve_state(self):
        def clarify(*args, **kwargs):
            return {"kind": "clarification", "summary": "Specify the interface.", "questions": ["What hole spacing in mm?"], "files": [], "brief_json": ""}
        jobs = Jobs(self.store, generator=clarify)
        design = self.store.create("NEMA mount")
        job = jobs.submit(design["id"], "Make a NEMA mount", session_id="test")
        self.assertEqual(self.wait(jobs, job)["status"], "needs-input")
        self.assertTrue(self.store.get(design["id"])["questions"])
        entered = threading.Event()
        def slow(*args, cancel, **kwargs):
            entered.set()
            cancel.wait(10)
            raise Cancelled()
        jobs.generator = slow
        job = jobs.submit(design["id"], "Use 31 mm spacing", session_id="test")
        self.assertTrue(entered.wait(2))
        with self.assertRaises(ValueError):
            jobs.submit(design["id"], "parallel", session_id="test")
        jobs.cancel(job["id"])
        self.assertEqual(self.wait(jobs, job)["status"], "cancelled")
        self.assertFalse(self.store.get(design["id"])["revisions"])

    def test_terminal_job_status_does_not_block_new_ide_submit(self):
        jobs = Jobs(self.store)
        ide = IDEAssistant(self.store, jobs)
        design = ide.create("stale active")
        turn = ide.start_turn(design["id"], "Create a mounting plate")["turn"]
        proposal = self.proposal()
        stale = {"id": "job-deadbeef", "design_id": design["id"], "status": "ready"}
        self.store.put_job(stale)
        jobs.active_id = stale["id"]
        self.assertFalse(jobs.is_active())

        submitted = {}
        def fake_submit(*args, **kwargs):
            submitted["called"] = True
            return {"id": "job-new", "status": "queued"}
        jobs.submit = fake_submit

        brief = json.loads(proposal["brief_json"])
        result = ide.submit(turn["id"], proposal["files"], brief, "Native MCP source", session_id="test")
        self.assertTrue(submitted["called"])
        self.assertEqual(result["id"], "job-new")

    def test_owned_process_tree_cancellation(self):
        cancel = threading.Event()
        # stdout proves the child has actually started before cancellation.
        def on_line(name, line):
            if "started" in line:
                cancel.set()
        start = time.monotonic()
        with self.assertRaises(Cancelled):
            run_process([sys.executable, "-u", "-c", "import time; print('started'); time.sleep(30)"],
                        cwd=self.root, cancel=cancel, on_line=on_line)
        self.assertLess(time.monotonic() - start, 5)

    def test_next_job_waits_for_terminal_worker_to_release_its_lock(self):
        jobs = Jobs(self.store)
        design = self.store.create("terminal cleanup")
        previous = {"id": "job-deadbeef", "design_id": design["id"], "status": "ready"}
        self.store.put_job(previous)
        jobs.active_id = previous["id"]
        jobs.lock.acquire()
        # Reproduce polling a terminal status before the old worker's finally
        # block releases its lock. The next operation must wait for that cleanup.
        cleanup = threading.Timer(.05, jobs.lock.release)
        cleanup.start()
        jobs.export = lambda *args: None
        try:
            submitted = jobs.submit(design["id"], export_format="stl", session_id="test")
            self.assertEqual(self.wait(jobs, submitted)["status"], "ready")
        finally:
            cleanup.join()

    def test_cancelled_build_has_terminal_revision_state(self):
        entered = threading.Event()
        jobs = Jobs(self.store, generator=lambda *args, **kwargs: self.proposal())
        def evaluate(revision, session, cancel, **kwargs):
            entered.set()
            cancel.wait(10)
            raise Cancelled()
        jobs.evaluate = evaluate
        design = self.store.create("cancel build")
        job = jobs.submit(design["id"], "Build it", session_id="test")
        self.assertTrue(entered.wait(2))
        jobs.cancel(job["id"])
        self.assertEqual(self.wait(jobs, job)["status"], "cancelled")
        self.assertEqual(self.store.get(design["id"])["revisions"][-1]["status"], "cancelled")

    def test_restart_marks_incomplete_jobs_and_retains_previous_scene_identity(self):
        design = self.store.create("restart")
        design.update(status="building", latest_revision="r002", display_revision="r001",
                      revisions=[{"id": "r001", "scene": True, "status": "ready"}, {"id": "r002", "scene": False, "status": "building"}])
        self.store.put(design)
        self.store.put_job({"id": "job-abcd", "design_id": design["id"], "status": "building"})
        restarted = Store(self.store.root)
        self.assertEqual(restarted.job("job-abcd")["status"], "interrupted")
        self.assertEqual(restarted.get(design["id"])["display_revision"], "r001")
        self.assertEqual(restarted.get(design["id"])["revisions"][-1]["status"], "interrupted")

    def test_windows_record_replace_retries_a_transient_reader_handle(self):
        record = self.root / "record.json"
        save(record, {"value": "old"})
        original = Path.replace
        calls = []
        def replace(source, target):
            calls.append(source)
            if len(calls) == 1:
                self.assertEqual(read_json(record)["value"], "old")
                raise PermissionError("reader owns the destination handle")
            return original(source, target)
        with patch.object(Path, "replace", replace):
            save(record, {"value": "new"})
        self.assertEqual(read_json(record)["value"], "new")
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_record_read_retries_transient_replace_access_denial(self):
        design = self.store.create("concurrent reader")
        original = Path.read_text
        calls = []
        def read(path, *args, **kwargs):
            calls.append(path)
            if len(calls) < 3:
                raise PermissionError("writer is replacing studio.json")
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", read):
            self.assertEqual(self.store.get(design["id"])["title"], "concurrent reader")
        self.assertEqual(len(calls), 3)

    def test_record_read_surfaces_permanent_denial_and_invalid_json(self):
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")) as read:
            with patch("cadharness.workflow.brief.time.sleep"):
                with self.assertRaises(PermissionError):
                    read_json(self.root / "record.json")
            self.assertEqual(read.call_count, 8)
        with patch.object(Path, "read_text", return_value="{invalid") as read:
            with self.assertRaises(json.JSONDecodeError):
                read_json(self.root / "record.json")
            self.assertEqual(read.call_count, 1)


if __name__ == "__main__":
    unittest.main()
