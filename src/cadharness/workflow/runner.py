"""Revision-local execution and provenance. These controls are not a sandbox."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from .brief import digest, identifier, load_brief, read_json, validate_brief
from ..paths import PACKAGE_ROOT, ROOT, RUNS_ROOT, WORKFLOW_ROOT

OUTPUTS = {"evidence", "previews", "inspector", "exports", ".cadharness", "__pycache__"}
ENVIRONMENT = {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT", "LANG", "LC_ALL",
               "USERPROFILE", "HOMEDRIVE", "HOMEPATH"}


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def context(revision: Path):
    revision = revision.resolve()
    if revision.parent.name != "revisions" or not revision.name.startswith("r") or not revision.name[1:].isdigit():
        raise ValueError("revision must be runs/<id>/revisions/rNNN")
    run = revision.parent.parent
    spec = read_json(revision / "revision.json")
    if spec.get("schema") != "designworkflow.revision" or spec.get("schema_version") != "1":
        raise ValueError("unsupported workflow revision schema/version")
    if spec.get("variant") is not None:
        identifier(spec["variant"], "variant")
    name = spec.get("brief", "")
    if Path(name).name != name or not name.startswith("brief-v") or not name.endswith(".json"):
        raise ValueError("revision brief must name a run-local brief-vNNN.json")
    brief_path = run / name
    if brief_path.is_symlink():
        raise ValueError("brief must not be a symlink")
    brief = load_brief(brief_path)
    if brief["id"] != run.name:
        raise ValueError("brief id must match run directory")
    expected = f"brief-v{brief['revision']:03d}.json"
    if name != expected:
        raise ValueError(f"brief filename must be {expected}")
    return revision, run, spec, brief_path, brief


def source_files(project: Path):
    """All candidate inputs, not just .py; reject links instead of hashing targets."""
    if project.is_symlink():
        raise ValueError("project symlinks are not supported")
    found = {}
    for base, directories, files in os.walk(project, followlinks=False):
        base = Path(base)
        for name in directories + files:
            if (base / name).is_symlink():
                raise ValueError("candidate input/output symlinks are not supported")
        directories[:] = [name for name in directories if name not in OUTPUTS]
        for name in sorted(files):
            if not name.endswith((".pyc", ".pyo")):
                path = base / name
                found[path.relative_to(project).as_posix()] = file_hash(path)
    if "cadharness.toml" not in found:
        raise ValueError("candidate has no cadharness.toml")
    return dict(sorted(found.items()))


def review_hashes(revision: Path):
    revision, run, spec, brief_path, brief = context(revision)
    files = source_files(revision / "project")
    inputs = {p.name: file_hash(p) for p in (run / "prompt.txt", run / "clarifications.md") if p.exists()}
    return {"source_sha256": digest({"files": files, "revision": spec, "prompt_inputs": inputs}),
            "brief_sha256": digest(read_json(brief_path)), "files": files,
            "revision_spec": spec, "prompt_inputs": inputs}


def init_run(run_id: str, prompt: str, *, root: Path | None = None, case: str | None = None):
    identifier(run_id)
    root = (root or RUNS_ROOT).resolve()
    run = root / run_id
    if run.exists():
        raise FileExistsError(f"refusing to overwrite run: {run}")
    template = WORKFLOW_ROOT / "templates" / "mounting-plate"
    if case:
        identifier(case, "benchmark case")
        from .benchmarks.cases import get_case
        fixture = get_case(case)
        brief = {**fixture["brief"], "id": run_id}
        template = ROOT / fixture["template"]
    else:
        brief = {
            "schema": "designworkflow.brief", "schema_version": "1", "revision": 1,
            "id": run_id, "domain": "mounting-plate", "coordinate_frame": "XY plate; bottom face Z=0",
            "printable_components": ["plate"],
            "dimensions": {}, "assumptions": [],
            "questions": [{"description": "Extract and confirm dimensions, units, hole locations, interfaces, and acceptance criteria from prompt.txt.", "blocking": True}],
            "physical_validation_gaps": ["Physical fit, manufacturing suitability, and performance have not been tested."],
            "requirements": [{"id": "brief.complete", "description": "Replace this placeholder with measurable prompt requirements",
                              "mandatory": True, "prompt_ref": "prompt.txt", "evidence_kind": "external",
                              "binding": {"type": "external"}, "criteria": {}}],
        }
    validate_brief(brief)
    revision = run / "revisions" / "r001"
    shutil.copytree(template, revision / "project", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if case and fixture.get("variant_values"):
        manifest = revision / "project" / "cadharness.toml"
        values = "\n".join(f"{key} = {json.dumps(value)}" for key, value in fixture["variant_values"].items())
        manifest.write_text(manifest.read_text(encoding="utf-8").replace("[variants.standard]", "[variants.standard]\n" + values), encoding="utf-8")
    (run / "prompt.txt").write_text(prompt, encoding="utf-8")
    write_json(run / "brief-v001.json", brief)
    write_json(revision / "revision.json", {"schema": "designworkflow.revision", "schema_version": "1", "brief": "brief-v001.json", "variant": "standard"})
    return {"revision": str(revision), **review_hashes(revision),
            "note": "Template dimensions are illustrative. Read prompt.txt, edit the brief and source, then review before execution."}


def revise(revision: Path, *, brief_name: str | None = None):
    revision, run, spec, _, _ = context(revision)
    if not (revision / "run.json").is_file():
        raise ValueError("evaluate this revision before creating its repair")
    # Freeze evidence and candidate inputs once evaluated. Repairs start in a
    # fresh directory, rather than silently copying an edited prior attempt.
    assert_current(revision, load_report(revision / "run.json"), allow_prompt_change=brief_name is not None)
    if brief_name is not None:
        if Path(brief_name).name != brief_name or not brief_name.startswith("brief-v"):
            raise ValueError("new brief must name a run-local brief-vNNN.json")
        new_brief = load_brief(run / brief_name)
        old_brief = load_brief(run / spec["brief"])
        if new_brief["id"] != run.name or new_brief["revision"] <= old_brief["revision"] or brief_name != f"brief-v{new_brief['revision']:03d}.json":
            raise ValueError("intent changes require a higher-numbered brief with the same design ID")
    number = int(revision.name[1:]) + 1
    target = revision.parent / f"r{number:03d}"
    if target.exists():
        raise FileExistsError(f"revision exists: {target}")
    shutil.copytree(revision / "project", target / "project",
                    ignore=shutil.ignore_patterns(*OUTPUTS, "*.pyc", "*.pyo"))
    write_json(target / "revision.json", {**spec, "brief": brief_name or spec["brief"], "parent": revision.name})
    return {"revision": str(target), **review_hashes(target)}


def _repo_state():
    def git(*args):
        try:
            result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return "unavailable"
        return result.stdout.strip() if result.returncode == 0 else "unavailable"
    return {"commit": git("rev-parse", "HEAD"), "working_tree": git("status", "--porcelain"),
            "workflow_files_sha256": digest({p.relative_to(PACKAGE_ROOT).as_posix(): file_hash(p)
                                             for p in PACKAGE_ROOT.rglob("*.py")})}


def _child_environment():
    # Allowlist rather than forwarding arbitrary provider secrets to candidate code.
    return {key: value for key, value in os.environ.items() if key.upper() in ENVIRONMENT}


def _run_worker(action: str, revision: Path, *, timeout: float, extra=()):
    args = [sys.executable, "-m", "cadharness", "design", "_worker", action, str(revision), *extra]
    return subprocess.run(args, cwd=ROOT, env=_child_environment(), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def check_revision(revision: Path, *, reviewed_source: str | None = None, accepted_brief: str | None = None,
                   timeout: float = 120, active_seconds: float = 0,
                   execution_mode: str = "manual-review", session_id: str | None = None,
                   worker_runner=None):
    revision, run, spec, brief_path, brief = context(revision)
    if not 0 < timeout <= 120 or not 0 <= active_seconds <= 900:
        raise ValueError("timeout must be 0..120 seconds; active_seconds must be 0..900")
    if (revision / "run.json").exists() or any((revision / "project" / name).exists() for name in OUTPUTS - {"__pycache__"}):
        raise FileExistsError("revision already has artifacts; use revise to preserve this attempt")
    hashes = review_hashes(revision)
    if execution_mode == "manual-review":
        if reviewed_source != hashes["source_sha256"] or accepted_brief != hashes["brief_sha256"]:
            raise ValueError("source/brief review hash mismatch; review current inputs before execution")
    elif execution_mode == "trusted-session":
        if not session_id:
            raise ValueError("trusted-session execution requires session authorization")
        # A session authorizes execution; it does not claim a human source review.
        reviewed_source, accepted_brief = None, hashes["brief_sha256"]
    else:
        raise ValueError("unknown execution mode")
    lock = run / f"{brief_path.stem}.lock.json"
    if lock.exists():
        if read_json(lock)["brief_sha256"] != hashes["brief_sha256"]:
            raise ValueError("accepted brief changed; create a new brief revision for an intent change")
    else:
        write_json(lock, {"brief_sha256": hashes["brief_sha256"]})
    prior = []
    for path in sorted((run / "revisions").glob("r*/run.json")):
        if path.parent.name >= revision.name:
            raise ValueError("revisions must be evaluated in order")
        item = load_report(path)
        if (item["brief_sha256"] == hashes["brief_sha256"]
                and item.get("revision_spec", {}).get("turn_id") == spec.get("turn_id")):
            prior.append(item)
    reasons = []
    if len(prior) >= 3:
        reasons.append("initial candidate plus two repairs exhausted")
    previous_time = sum(item.get("active_seconds", 0) for item in prior)
    if previous_time + active_seconds >= 900:
        reasons.append("15-minute active iteration budget exhausted")
    if any(item.get("source_sha256") == hashes["source_sha256"] and item.get("outcome") != "ready-for-review" for item in prior):
        reasons.append("unchanged failed candidate; diagnose before retrying")
    # Source identity excludes revision metadata when detecting blind retries.
    if prior and prior[-1].get("files") == hashes["files"] and prior[-1]["outcome"] != "ready-for-review":
        reasons.append("unchanged failed source; no blind retry")
    if prior and prior[-1].get("prompt_inputs") != hashes["prompt_inputs"]:
        raise ValueError("prompt/clarifications changed; use a new brief revision for changed intent")
    for item in brief["questions"] + brief["assumptions"]:
        if item["blocking"]:
            reasons.append(item["description"])
    evidence = revision / "project" / "evidence"
    evidence.mkdir(parents=True)
    write_json(evidence / "brief.json", brief)
    for name in ("prompt.txt", "clarifications.md"):
        if (run / name).exists():
            shutil.copyfile(run / name, evidence / name)
    started = time.perf_counter()
    errors = []
    evaluation = None
    if not reasons:
        try:
            result = (worker_runner or _run_worker)("check", revision, timeout=timeout)
            (evidence / "worker.stdout.txt").write_text(result.stdout, encoding="utf-8")
            (evidence / "worker.stderr.txt").write_text(result.stderr, encoding="utf-8")
            if result.returncode:
                errors.append(f"worker exited {result.returncode}; see worker.stderr.txt")
            elif (evidence / "evaluation.json").is_file():
                evaluation = read_json(evidence / "evaluation.json")
            else:
                errors.append("worker produced no evaluation")
        except subprocess.TimeoutExpired as exc:
            errors.append(f"worker timed out after {timeout:g} seconds")
            (evidence / "worker.stderr.txt").write_text(str(exc), encoding="utf-8")
    elapsed = time.perf_counter() - started
    try:
        if review_hashes(revision) != hashes:
            errors.append("source or brief changed during execution; evidence is stale")
    except Exception as exc:
        errors.append(f"source or brief became unreadable during execution; evidence is stale: {exc}")
    if previous_time + active_seconds + elapsed >= 900:
        reasons.append("15-minute active iteration budget exhausted")
    coverage = evaluation["coverage"] if evaluation else [
        {"id": req["id"], "mandatory": req["mandatory"], "description": req["description"],
         "status": "unknown" if errors else "not-yet-verified", "reason": "; ".join(errors + reasons)}
        for req in brief["requirements"]]
    if evaluation:
        errors.extend(evaluation.get("check_errors", []))
    comparison = None
    if evaluation and prior:
        from cadharness import compare_snapshots
        previous = run / "revisions" / prior[-1]["revision"] / "project" / "evidence" / "snapshot.json"
        if previous.exists():
            comparison = compare_snapshots(read_json(previous), read_json(evidence / "snapshot.json"))
            write_json(evidence / "comparison.json", comparison)
            requirements = comparison["requirements"]
            if requirements["removed"] or any(v["normative"] for v in requirements["modified"].values()):
                reasons.append("requirement drift: removed or modified acceptance criteria")
    passed = bool(evaluation and evaluation["verification_passed"])
    ready = passed and not reasons and not errors and all(row["status"] == "pass" for row in coverage if row["mandatory"])
    outcome = "ready-for-review" if ready else "error" if errors else "blocked" if reasons else "needs-revision"
    report = {"schema": "designworkflow.run", "schema_version": "1", "revision": revision.name,
              "brief": spec["brief"], **hashes, "repository": _repo_state(),
              "reviewed_source": reviewed_source, "accepted_brief": accepted_brief,
              "execution_authorization": {"mode": execution_mode, "session_id": session_id},
              "created_utc": datetime.now(timezone.utc).isoformat(), "variant": spec.get("variant"),
              "outcome": outcome, "ready_for_review": ready, "verification_passed": passed,
              "coverage": coverage, "errors": errors, "blocking_reasons": reasons,
              "warnings": evaluation.get("warnings", []) if evaluation else [],
              "elapsed_seconds": elapsed, "active_seconds": active_seconds + elapsed,
              "unmetered_time": "IDE/model authoring and human review time must be supplied with --active-seconds; user-response waits excluded.",
              "assumptions": brief["assumptions"], "questions": brief["questions"],
              "physical_validation": {"status": "not-yet-verified", "gaps": brief["physical_validation_gaps"]},
              "toolchain": evaluation.get("toolchain") if evaluation else None,
              "fingerprints": evaluation.get("fingerprints", {}) if evaluation else {},
              "artifacts": artifact_hashes(revision / "project")}
    write_json(revision / "run.json", report)
    write_review(revision, report)
    return report


def artifact_hashes(project):
    return {p.relative_to(project).as_posix(): file_hash(p)
            for name in ("evidence", "previews", "inspector")
            for p in sorted((project / name).rglob("*")) if p.is_file()}


def write_review(revision, report):
    lines = [f"# {revision.parent.parent.name}: {report['outcome']}", "",
             "Editable source: [project.py](project/project.py). [Frozen brief](project/evidence/brief.json).",
             "", "CAD checks and physical validation are separate. Physical fit, manufacturing suitability, and real-world performance remain unverified.", "",
             "| Requirement | Status |", "| --- | --- |"]
    lines += [f"| {row['id']} | {row['status']} |" for row in report["coverage"]]
    lines += ["", "## Assumptions and questions", ""]
    lines += ["- " + item["description"] for item in report["assumptions"] + report["questions"]]
    lines += ["", "## Physical evidence still needed", ""] + ["- " + item for item in report["physical_validation"]["gaps"]]
    lines += ["", "## Failures and blockers", ""] + ["- " + item for item in report["errors"] + report["blocking_reasons"]]
    for row in report["coverage"]:
        if row["status"] != "pass":
            lines.append(f"- {row['id']}: {row['reason']}")
    if "inspector/index.html" in report["artifacts"]:
        lines += ["", "[CAD inspector](project/inspector/index.html) · [Snapshot](project/evidence/snapshot.json) · [Verification](project/evidence/verification.json)"]
    lines += ["", "Exports are explicit: use `python -m cadharness design export <revision> --format step|stl`.",
              "", f"Source SHA-256: `{report['source_sha256']}`", f"Brief SHA-256: `{report['brief_sha256']}`", ""]
    (revision / "review.md").write_text("\n".join(lines), encoding="utf-8")
    def text(value):
        return escape(str(value), quote=True)
    rows = "".join(f"<tr><td>{text(row['id'])}</td><td>{text(row['status'])}</td><td>{text(row['reason'])}</td></tr>" for row in report["coverage"])
    assumptions = "".join(f"<li>{text(item['description'])}</li>" for item in report["assumptions"] + report["questions"])
    issues = "".join(f"<li>{text(item)}</li>" for item in report["errors"] + report["blocking_reasons"])
    gaps = "".join(f"<li>{text(item)}</li>" for item in report["physical_validation"]["gaps"])
    previews = "".join(f'<figure><img src="project/{text(name)}" alt="{text(Path(name).stem)}"><figcaption>{text(Path(name).stem)}</figcaption></figure>'
                       for name in report["artifacts"] if name.startswith("previews/") and name.endswith(".svg"))
    inspector_link = '<a href="project/inspector/index.html">CAD inspector</a>' if "inspector/index.html" in report["artifacts"] else "Inspector unavailable"
    content = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{text(revision.parent.parent.name)} — {text(report['outcome'])}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;color:#17212b;background:#f7f9fb}}a{{color:#145b8c}}h1{{font-size:30px}}.verdict{{padding:16px;border:1px solid #aab9c6;background:white}}.previews{{display:flex;flex-wrap:wrap;gap:16px}}figure{{margin:0;flex:1 1 240px;background:white;padding:12px}}img{{width:100%;height:220px}}figcaption{{font-size:13px}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #d7e0e7;overflow-wrap:anywhere}}.table{{overflow-x:auto}}code{{overflow-wrap:anywhere}}@media(max-width:600px){{body{{margin:16px auto}}td,th{{padding:8px;font-size:13px}}}}</style>
<main><p>CAD-Harness · design workflow</p><h1>{text(revision.parent.parent.name)}</h1>
<p class="verdict"><strong>{text(report['outcome'])}</strong> · Physical validation: not-yet-verified</p>
<p>Ready for review means the recorded mandatory CAD requirements pass. Physical fit, manufacturing suitability, and performance remain unverified.</p>
<nav><a href="project/project.py">Editable source</a> · <a href="project/evidence/brief.json">Design brief</a> · {inspector_link} · <a href="run.json">Evidence manifest</a></nav>
<div class="previews">{previews}</div><h2>Requirement coverage</h2>
<p>The CAD inspector's verification verdict covers executable checks. This workflow verdict also accounts for unknown requirements and blocking questions.</p>
<div class="table"><table><thead><tr><th>Requirement</th><th>Status</th><th>Evidence or limitation</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Assumptions and questions</h2><ul>{assumptions}</ul><h2>Failures and blockers</h2><ul>{issues}</ul>
<h2>Physical evidence still needed</h2><ul>{gaps}</ul><details><summary>Provenance</summary><p>Source SHA-256: <code>{text(report['source_sha256'])}</code></p><p>Brief SHA-256: <code>{text(report['brief_sha256'])}</code></p></details></main></html>'''
    (revision / "review.html").write_text(content, encoding="utf-8")


def load_report(path):
    report = read_json(path)
    if report.get("schema") != "designworkflow.run" or report.get("schema_version") != "1":
        raise ValueError("unsupported workflow run schema/version")
    if type(report.get("ready_for_review")) is not bool or report.get("outcome") not in {"ready-for-review", "needs-revision", "blocked", "error"}:
        raise ValueError("invalid workflow run outcome")
    if report["ready_for_review"] != (report["outcome"] == "ready-for-review"):
        raise ValueError("inconsistent workflow run verdict")
    for key in ("files", "artifacts", "repository", "fingerprints"):
        if not isinstance(report.get(key), dict):
            raise ValueError(f"workflow run requires {key}")
    return report


def assert_current(revision, report, *, allow_prompt_change=False):
    hashes = review_hashes(revision)
    if hashes["brief_sha256"] != report["brief_sha256"] or (hashes["source_sha256"] != report["source_sha256"] and not allow_prompt_change):
        raise ValueError("source or brief changed; saved evidence is stale")
    if hashes["files"] != report["files"]:
        raise ValueError("candidate source changed; saved evidence is stale")
    if hashes["revision_spec"] != report["revision_spec"]:
        raise ValueError("revision settings changed; saved evidence is stale")
    if artifact_hashes(revision / "project") != report["artifacts"]:
        raise ValueError("evidence artifacts changed; saved evidence is stale")
    current = _repo_state()
    if current["workflow_files_sha256"] != report["repository"]["workflow_files_sha256"]:
        raise ValueError("workflow evaluator changed; evaluate a new revision")


def export_revision(revision: Path, *, file_format="step", component_ids=(), timeout=120):
    revision, _, _, _, _ = context(revision)
    if file_format not in {"step", "stl"} or not 0 < timeout <= 120:
        raise ValueError("export requires step/stl and timeout in 0..120 seconds")
    report = load_report(revision / "run.json")
    assert_current(revision, report)
    if not report["ready_for_review"]:
        raise ValueError("export requires a ready-for-review revision")
    inspection = read_json(revision / "project" / "evidence" / "inspection.json")
    printable = {key for key, value in inspection["components"].items() if value["role"] == "printable-part"}
    selected = list(component_ids) or sorted(printable)
    if not selected or set(selected) - printable:
        raise ValueError("export selects printable-part components only; reference geometry is excluded")
    receipt = revision / "project" / "exports" / f"{file_format}.json"
    if receipt.exists():
        raise FileExistsError("export already exists; artifacts are never overwritten")
    result = _run_worker("export", revision, timeout=timeout, extra=(file_format, *selected))
    if result.returncode:
        raise RuntimeError(f"export worker failed: {result.stderr[-2000:]}")
    assert_current(revision, report)
    return read_json(receipt)


def worker(action, revision: Path, extra):
    """Only this subprocess imports candidate Python. It receives no provider secrets."""
    from cadharness import load_project, verify_document, render_inspector, require_schema
    from cadharness.preview import write_svg_previews
    from .acceptance import bind_requirements, update_coverage
    revision, _, spec, _, brief = context(revision)
    project = revision / "project"
    expected = review_hashes(revision)
    if action == "export":
        from cadharness.operations import _export_loaded_project
        report = load_report(revision / "run.json")
        assert_current(revision, report)
        # Replay evaluation before comparing BREP identities: boolean measurement
        # checks can populate OCCT serialization state on their operand shapes.
        # Export these exact verified shapes, without another factory execution.
        loaded = load_project(project, variant=spec.get("variant"))
        document, coverage = bind_requirements(loaded.document, brief)
        verification = verify_document(document, variant=loaded.variant)
        rows = update_coverage(coverage, verification["validation"])
        if not verification["verification"]["passed"] or any(row["mandatory"] and row["status"] != "pass" for row in rows):
            raise ValueError("rebuilt geometry no longer passes evaluated requirements")
        fresh = document.inspect()
        fingerprints = {key: item["geometry"]["fingerprint"] for key, item in fresh["components"].items()}
        if fingerprints != report["fingerprints"]:
            raise ValueError("rebuilt geometry differs from evaluated geometry")
        output = _export_loaded_project(replace(loaded, document=document), file_format=extra[0],
                                       component_ids=extra[1:], output_dir=f"exports/{extra[0]}")
        if any(item["source_geometry"]["fingerprint"] != report["fingerprints"][item["component_id"]] for item in output["outputs"]):
            raise ValueError("exported geometry differs from evaluated geometry; files withheld from delivery")
        if review_hashes(revision) != expected:
            raise ValueError("source changed during export")
        write_json(project / "exports" / f"{extra[0]}.json", {
            "schema": "designworkflow.export", "schema_version": "1", "source_sha256": report["source_sha256"],
            "brief_sha256": report["brief_sha256"], "outputs": [{**item, "sha256": file_hash(Path(item["path"]))} for item in output["outputs"]]})
        return
    loaded = load_project(project, variant=spec.get("variant"))
    document, coverage = bind_requirements(loaded.document, brief)
    printable = sorted(key for key, value in document.components.items() if value.role == "printable-part")
    if printable != sorted(brief["printable_components"]):
        raise ValueError("candidate printable component roles do not match the accepted brief")
    verification = verify_document(document, variant=loaded.variant)
    require_schema(verification)
    inspection = document.inspect()
    inspection["manifest"] = {"variant": loaded.variant, "default_variant": loaded.manifest.default_variant,
                              "available_variants": sorted(loaded.manifest.variants),
                              "description": loaded.manifest.description}
    require_schema(inspection)
    evidence = project / "evidence"
    for name, data in (("verification", verification), ("snapshot", verification["current_snapshot"]),
                       ("validation", verification["validation"]), ("inspection", inspection)):
        write_json(evidence / f"{name}.json", data)
    if "studio" in extra:
        from ..studio.scene import write_scene
        cache = Path(extra[extra.index("studio") + 1])
        write_scene(document, inspection, evidence / "scene.json", cache)
    else:
        previews = write_svg_previews(document, project / "previews", views=("iso", "top", "front"))
        inspector = project / "inspector" / "index.html"
        inspector.parent.mkdir()
        inspector.write_text(render_inspector(inspection, verification["validation"],
            verification=verification["verification"], previews=[{"view": item["view"], "href": "../previews/" + Path(item["path"]).name} for item in previews]), encoding="utf-8")
    write_json(evidence / "evaluation.json", {
        "coverage": update_coverage(coverage, verification["validation"]),
        "verification_passed": verification["verification"]["passed"],
        "check_errors": [item["id"] + ": " + item["message"] for item in verification["validation"]["results"] if item["status"] == "error"],
        "warnings": [item for item in verification["validation"]["results"] if item["status"] == "warn"],
        "fingerprints": {key: item["geometry"]["fingerprint"] for key, item in inspection["components"].items()},
        "toolchain": verification["current_snapshot"]["toolchain"]})
