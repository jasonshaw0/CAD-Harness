"""Installed-package acceptance helper; copied outside the checkout by the smoke runner.

Uses a synthetic older package version of the same code, not a historical
release, to exercise pip replacement without claiming cross-release migration.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import threading


def tree_hashes(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts}


def core(root):
    from cadharness import (CylinderSelector, geometry_measurement_check,
                            load_project, measure_hole_pattern, verify_document)
    from cadharness.paths import PACKAGE_ROOT, WORKFLOW_ROOT
    assert PACKAGE_ROOT.is_relative_to(Path(sys.prefix).resolve())
    assert importlib.util.find_spec("mcp") is None, "Core install unexpectedly includes MCP"
    assert importlib.util.find_spec("starlette") is None, "Core install unexpectedly includes Studio server"
    project = root / "core-project"
    shutil.copytree(WORKFLOW_ROOT / "templates/mounting-plate", project,
                    ignore=shutil.ignore_patterns("__pycache__"))
    for variant, expected_pass in (("standard", True), ("missing-hole", False)):
        document = load_project(project, variant=variant).document
        # The template deliberately keeps acceptance in its external brief.
        # Supply this independent requirement instead of relying on validity alone.
        document.checks = (geometry_measurement_check("holes.count", "Four actual holes",
            lambda doc: measure_hole_pattern(doc, "install.holes",
                CylinderSelector("plate", radius_min_mm=1, radius_max_mm=3, axis_direction=(0, 0, 1))),
            value_path="count", expected=4, components=("plate",),
            method="analytic-concave-cylinder-inventory"),)
        assert verify_document(document)["verification"]["passed"] == expected_pass
    print("Core-only install: real geometry passes; missing-hole defect fails.", flush=True)
    from cadharness.studio.demo import prepare_demo
    demo = prepare_demo(root / "core-demo")
    assert demo["failed_revision"] == "r001" and demo["repaired_revision"] == "r002"
    assert importlib.util.find_spec("mcp") is None and importlib.util.find_spec("starlette") is None
    print("Core-only demo preparation passed without MCP, server extras or a browser.", flush=True)


def seed(root):
    from cadharness.diagnostics import package_version
    from cadharness.mcp_config import mcp_client_config
    from cadharness.studio.assistant import IDEAssistant
    from cadharness.studio.jobs import Jobs
    from cadharness.studio.store import Store
    state = root / "user-data"
    store = Store(state / "workspace")
    jobs = Jobs(store)
    design = store.create("Retained install-lifecycle design")
    # Synchronous use of the existing example path avoids timing assumptions.
    jobs.open_design(design, {"id": "job-lifecycle"}, "square-mount", None,
                     "lifecycle-test", threading.Event(), lambda *args: None)
    design = store.get(design["id"])
    assert design["status"] == "ready", design
    jobs.export(design, "stl", threading.Event())
    IDEAssistant(store, jobs).open(design["id"])
    config = state / ".cadharness/mcp.json"
    config.parent.mkdir()
    config.write_text(json.dumps(mcp_client_config([state], studio=True,
                      studio_workspace=store.root), indent=2), encoding="utf-8")
    (root / "lifecycle.json").write_text(json.dumps({"design_id": design["id"],
        "version": package_version(), "files": tree_hashes(state)}, indent=2), encoding="utf-8")
    print(f"Seeded real Studio source, evidence, mesh, export and config with {package_version()}.", flush=True)


def preserved(root):
    saved = json.loads((root / "lifecycle.json").read_text(encoding="utf-8"))
    actual = tree_hashes(root / "user-data")
    assert actual == saved["files"], "Installation changed saved workspace/config bytes"
    return saved


def reopen(root):
    from starlette.testclient import TestClient
    from cadharness.diagnostics import package_version
    from cadharness.studio.server import create_app
    saved = preserved(root)
    assert package_version() != saved["version"], "Upgrade must replace a different version"
    app = create_app(root / "user-data/workspace")
    design_id = saved["design_id"]
    with TestClient(app) as client:
        design = client.get(f"/api/designs/{design_id}").json()
        assert design["display_revision"] == "r001", design
        revision = client.get(f"/api/designs/{design_id}/revisions/r001").json()
        assert revision["report"]["ready_for_review"]
        assert revision["scene"]["components"]
        archive = client.get(f"/api/designs/{design_id}/revisions/r001/source")
        assert archive.status_code == 200 and archive.content.startswith(b"PK")
    # The existing export receipt must still pass the evaluator/source checks.
    app.state.jobs.export(design, "stl", threading.Event())
    preserved(root)
    print(f"Reopened retained design with {package_version()}; all saved bytes unchanged.", flush=True)


def absent(root):
    assert importlib.util.find_spec("cadharness") is None, "Package remains importable after uninstall"
    preserved(root)
    print("Uninstall removed the package and retained all workspace/config bytes.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("core", "seed", "reopen", "absent"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    {"core": core, "seed": seed, "reopen": reopen, "absent": absent}[args.action](args.root.resolve())
