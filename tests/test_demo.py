"""The packaged demonstration uses real frozen-brief geometry and normal exports."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

from cadharness.cli import main
from cadharness.studio.demo import prepare_demo, serve_demo
from cadharness.studio.server import create_app
from cadharness.studio.store import Store
from cadharness.workflow.brief import read_json
from cadharness.workflow.runner import export_revision


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = TemporaryDirectory()
        cls.root = Path(cls.directory.name).resolve()
        cls.workspace = cls.root / "new demo workspace"
        with patch("cadharness.studio.jobs.Jobs.turn", side_effect=AssertionError("No model turns")):
            cls.info = prepare_demo(cls.workspace)
        cls.design_root = cls.workspace / "designs" / cls.info["design_id"]

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_failed_and_repaired_geometry_share_one_frozen_brief(self):
        store = Store(self.workspace)
        design = store.get(self.info["design_id"])
        self.assertEqual(design["latest_revision"], "r002")
        self.assertEqual(read_json(self.workspace / "viewer.json")["revision_id"], "r001")
        self.assertEqual([path.name for path in self.design_root.glob("brief-v[0-9][0-9][0-9].json")], ["brief-v001.json"])
        self.assertTrue((self.design_root / "brief-v001.lock.json").is_file())
        reports = []
        for revision, count in (("r001", 3), ("r002", 4)):
            path = self.design_root / "revisions" / revision
            report = read_json(path / "run.json")
            reports.append(report)
            row = next(row for row in report["coverage"] if row["id"] == "holes.count")
            self.assertEqual(row["result"]["actual"], count)
            self.assertEqual(row["status"], "pass" if count == 4 else "fail")
            self.assertEqual(report["ready_for_review"], count == 4)
            self.assertEqual(report["execution_authorization"]["mode"], "trusted-session")
            self.assertIsNone(report["reviewed_source"])
            scene = read_json(path / "project/evidence/scene.json")
            self.assertEqual({part["id"] for part in scene["components"]}, {"plate", "motor-envelope", "cable-keepout"})
            self.assertFalse((path / "project/exports").exists(), "Preparing a demo must not export geometry")
        self.assertEqual(reports[0]["brief_sha256"], reports[1]["brief_sha256"])
        a, b = [self.design_root / "revisions" / revision / "project/project.py" for revision in ("r001", "r002")]
        self.assertEqual(a.read_bytes(), b.read_bytes())
        sessions = [read_json(path) for path in (self.workspace / "sessions").glob("*.json")]
        self.assertTrue(all(record["via"] == "packaged-demo-command" and record.get("ended") for record in sessions))

    def test_reopen_api_has_comparison_source_and_locked_execution(self):
        with TestClient(create_app(self.workspace)) as client:
            session = client.get("/api/session").json()
            self.assertEqual(session["demo"]["design_id"], self.info["design_id"])
            self.assertFalse(session["authorized"])
            prefix = f"/api/designs/{self.info['design_id']}/revisions"
            comparison = client.get(prefix + "/r002").json()["comparison"]
            self.assertEqual(comparison["baseline"], "r001")
            self.assertIn("plate", comparison["components"]["changed"])
            self.assertEqual(comparison["requirements"]["modified"], {})
            source = client.get(prefix + "/r001/files/project/cadharness.toml")
            self.assertIn('default_variant = "missing-hole"', source.text)
            self.assertEqual(client.get(prefix + "/r002/source").status_code, 200)
            self.assertEqual(client.post(f"/api/designs/{self.info['design_id']}/export",
                headers={"X-Studio-Token": session["token"]}, json={"format": "stl"}).status_code, 403)

    def test_failed_revision_cannot_be_exported(self):
        with self.assertRaisesRegex(ValueError, "ready|verification|requirements"):
            export_revision(self.design_root / "revisions/r001", file_format="stl")

    def test_existing_workspace_is_refused_without_changing_any_saved_bytes(self):
        before = {str(path): path.read_bytes() for path in self.workspace.rglob("*") if path.is_file()}
        with self.assertRaisesRegex(ValueError, "already exists"):
            prepare_demo(self.workspace)
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.workspace.rglob("*") if path.is_file()})

    def test_failed_preparation_keeps_diagnostics_and_does_not_claim_completion(self):
        target = self.root / "failed-demo"
        with patch("cadharness.studio.jobs.Jobs.evaluate", side_effect=RuntimeError("worker failed")):
            with self.assertRaisesRegex(RuntimeError, "worker failed"):
                prepare_demo(target)
        self.assertTrue(list(target.rglob("project.py")))
        self.assertFalse((target / "demo.json").exists())
        session, = (target / "sessions").glob("*.json")
        self.assertTrue(read_json(session).get("ended"))

    def test_occupied_port_and_missing_frontend_do_not_create_a_workspace(self):
        target = self.root / "must-not-create"
        with patch("cadharness.studio.demo.STUDIO_WEB", self.root / "missing-frontend"):
            with self.assertRaisesRegex(RuntimeError, "frontend is missing"):
                serve_demo(workspace=target, open_browser=False)
        self.assertFalse(target.exists())
        with patch("cadharness.studio.demo.importlib.util.find_spec", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "CAD-Harness\\[studio\\]"):
                serve_demo(workspace=target, open_browser=False)
        # Port ownership is checked before building or opening a browser.
        frontend = self.root / "frontend"
        frontend.mkdir()
        (frontend / "index.html").write_text("test", encoding="utf-8")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with patch("cadharness.studio.demo.prepare_demo") as prepare:
                with patch("cadharness.studio.demo.STUDIO_WEB", frontend):
                    with self.assertRaises(OSError):
                        serve_demo(workspace=target, port=listener.getsockname()[1], open_browser=False)
                prepare.assert_not_called()

    def test_cli_forwards_no_browser_and_does_not_offer_overwrite(self):
        with patch("cadharness.studio.demo.serve_demo") as serve:
            self.assertEqual(main(["demo", "--workspace", str(self.root / "cli"), "--port", "8748", "--no-browser"]), 0)
        serve.assert_called_once_with(workspace=self.root / "cli", port=8748, open_browser=False)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as error:
            self.assertEqual(main(["demo", "--prepare-only", "--workspace", str(self.workspace)]), 2)
        self.assertIn("already exists", json.loads(error.getvalue())["message"])
        self.assertNotIn("overwrite", error.getvalue())


if __name__ == "__main__":
    unittest.main()
