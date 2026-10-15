"""One active job, persisted turns, reusable CAD evaluation, and Codex repairs."""

from copy import deepcopy
import json
import re
from pathlib import Path
import sys
import threading
import time

from ..workflow.brief import read_json, validate_brief
from ..workflow.runner import ROOT, _child_environment, assert_current, check_revision, source_files, write_json
from .codex import design_prompt, generate
from .processes import Cancelled, run_process
from .store import contained, new_id, now

ACTIVE = {"queued", "generating", "building", "checking", "repairing", "exporting"}


class Jobs:
    def __init__(self, store, *, model=None, generator=generate):
        self.store, self.model, self.generator = store, model, generator
        self.lock = threading.Lock()
        self.cancel_event = None
        self.active_id = None

    def submit(self, design_id, instruction="", selected=(), *, example=None, import_path=None, export_format=None, rebuild=False, candidate=None, session_id):
        if not self.lock.acquire(blocking=False):
            raise ValueError("Another design job is active. Cancel it or wait for it to finish.")
        job = {"id": new_id("job"), "design_id": design_id, "status": "queued", "created": now(),
               "instruction": instruction, "error": None,
               "requested_model": "IDE assistant via MCP" if candidate else
                   None if example or import_path or export_format or rebuild else self.model or "CLI default"}
        self.store.put_job(job)
        cancel = threading.Event()
        self.cancel_event, self.active_id = cancel, job["id"]
        def work():
            design = self.store.get(design_id)
            def emit(kind, data):
                self.store.event(job, kind, data)
            def state(status, text):
                job["status"] = status
                self.store.put_job(job)
                design["status"] = status
                self.store.put(design)
                emit("status", {"status": status, "text": text})
            try:
                if candidate:
                    state("building", "Building source supplied by the IDE assistant")
                    revision = self.revision(design, candidate["brief"], candidate["files"], candidate["turn_id"])
                    job["revision"] = revision.name
                    self.store.put_job(job)
                    report = self.evaluate(revision, session_id, cancel)
                    self.evaluated(design, revision, report, candidate["summary"])
                    design["messages"].append({"role": "assistant", "text": candidate["summary"],
                                               "time": now(), "revision": revision.name})
                    self.store.put(design)
                    emit("revision", {"revision": revision.name, "outcome": report["outcome"]})
                    state(design["status"], "CAD evaluation finished; evidence returned to the IDE assistant")
                elif rebuild:
                    state("building", "Rebuilding current source and frozen requirements")
                    previous = self.store.design_root(design_id) / "revisions" / design["latest_revision"]
                    brief = read_json(self.store.design_root(design_id) / read_json(previous / "revision.json")["brief"])
                    revision = self.revision(design, brief, self.read_source(previous), job["id"])
                    job["revision"] = revision.name
                    self.store.put_job(job)
                    report = self.evaluate(revision, session_id, cancel)
                    self.evaluated(design, revision, report, "Rebuilt current source")
                    emit("revision", {"revision": revision.name, "outcome": report["outcome"]})
                    state(design["status"], "Rebuild finished")
                elif export_format:
                    state("exporting", "Exporting evaluated printable components")
                    self.export(design, export_format, cancel)
                    state("ready", f"{export_format.upper()} export is ready")
                elif example or import_path:
                    state("building", "Building a local copy of the design")
                    self.open_design(design, job, example, import_path, session_id, cancel, emit)
                    state(design["status"], "Design opened")
                else:
                    self.turn(design, job, instruction, list(selected), session_id, cancel, state, emit)
            except Cancelled:
                if design["revisions"] and design["revisions"][-1]["status"] == "building":
                    design["revisions"][-1].update(status="cancelled", summary="Build cancelled")
                state("cancelled", "Job cancelled. The last displayed revision is unchanged.")
            except Exception as exc:
                if design["revisions"] and design["revisions"][-1]["status"] == "building":
                    design["revisions"][-1].update(status="failed", summary=str(exc))
                job["error"] = str(exc)
                state("failed", str(exc))
                design["messages"].append({"role": "assistant", "text": str(exc), "time": now(), "kind": "error"})
                self.store.put(design)
            finally:
                emit("done", {"status": job["status"], "design_id": design_id})
                self.active_id, self.cancel_event = None, None
                self.lock.release()
        threading.Thread(target=work, daemon=True, name=job["id"]).start()
        return job

    def cancel(self, job_id):
        if self.active_id != job_id or self.cancel_event is None:
            raise ValueError("This job is no longer active")
        self.cancel_event.set()

    def is_active(self):
        active = self.active_id
        if not active:
            return False
        try:
            return self.store.job(active).get("status") in ACTIVE
        except FileNotFoundError:
            return True

    def revision(self, design, brief, files, job_id):
        root = self.store.design_root(design["id"])
        existing = [int(path.name[1:]) for path in (root / "revisions").glob("r[0-9]*")]
        name = f"r{max(existing, default=0) + 1:03d}"
        revision = root / "revisions" / name
        write_candidate_path = revision / "project"
        from .store import write_candidate
        write_candidate(write_candidate_path, files)
        brief_name = f"brief-v{brief['revision']:03d}.json"
        brief_path = root / brief_name
        if not brief_path.exists():
            write_json(brief_path, brief)
        elif read_json(brief_path) != brief:
            raise ValueError("Automatic repair attempted to change a frozen brief")
        write_json(revision / "revision.json", {"schema": "designworkflow.revision", "schema_version": "1",
                   "brief": brief_name, "variant": None, "turn_id": job_id,
                   "parent": design["latest_revision"]})
        design["revisions"].append({"id": name, "status": "building", "scene": False, "brief": brief_name,
                                     "created": now(), "summary": "Building…"})
        design["latest_revision"] = name
        self.store.put(design)
        return revision

    def evaluate(self, revision, session_id, cancel, *, timeout=120):
        def runner(action, path, *, timeout):
            args = [sys.executable, "-m", "cadharness", "design", "_worker", action, str(path),
                    "studio", str(self.store.root / "mesh-cache")]
            return run_process(args, cwd=ROOT, cancel=cancel, timeout=timeout, env=_child_environment())
        return check_revision(revision, execution_mode="trusted-session", session_id=session_id,
                              worker_runner=runner, timeout=timeout)

    def evaluated(self, design, revision, report, summary):
        scene = (revision / "project/evidence/scene.json").is_file()
        row = design["revisions"][-1]
        row.update(status=report["outcome"], scene=scene, summary=summary,
                   elapsed_seconds=report["elapsed_seconds"], checks=sum(item["status"] == "pass" for item in report["coverage"]),
                   requirements=len(report["coverage"]))
        if scene:
            design["display_revision"] = revision.name
        design["status"] = "ready" if report["ready_for_review"] else "needs-revision"
        design["questions"] = []
        self.store.put(design)

    def open_design(self, design, job, example, import_path, session_id, cancel, emit):
        from ..workflow.benchmarks.cases import get_case
        if example:
            fixture = get_case(example)
            brief = deepcopy(fixture["brief"])
            brief.update(id=design["id"], revision=1)
            template = ROOT / fixture["template"]
            files = [{"path": path.relative_to(template).as_posix(), "content": path.read_text(encoding="utf-8")}
                     for path in template.rglob("*") if path.suffix in {".py", ".toml"}]
            prompt = fixture["prompt"]
        else:
            original = Path(import_path)
            from ..workflow.runner import context
            _, _, _, _, brief = context(original)
            brief = deepcopy(brief)
            brief.update(id=design["id"], revision=1)
            # Materialize the selected named variant as the new manifest default.
            spec = read_json(original / "revision.json")
            files = self.read_source(original)
            variant = spec.get("variant")
            if variant:
                for item in files:
                    if item["path"] == "cadharness.toml":
                        item["content"] = re.sub(r'^default_variant\s*=.*$', f'default_variant = "{variant}"', item["content"], flags=re.M)
            prompt = "Imported saved workflow design. Preserve its intent and component identities."
        root = self.store.design_root(design["id"])
        (root / "prompt.txt").write_text(prompt, encoding="utf-8")
        revision = self.revision(design, brief, files, job["id"])
        report = self.evaluate(revision, session_id, cancel)
        self.evaluated(design, revision, report, "Opened a local copy")
        design["messages"].append({"role": "assistant", "text": "Opened a local copy. Select a component or describe a change.", "time": now()})
        self.store.put(design)
        emit("revision", {"revision": revision.name, "outcome": report["outcome"]})

    @staticmethod
    def read_source(revision):
        project = revision / "project"
        return [{"path": name, "content": (project / name).read_text(encoding="utf-8")}
                for name in source_files(project) if Path(name).suffix in {".py", ".toml"}]

    def turn(self, design, job, instruction, selected, session_id, cancel, state, emit):
        root = self.store.design_root(design["id"])
        design["messages"].append({"role": "user", "text": instruction, "time": now(), "selected": selected})
        self.store.put(design)
        if not (root / "prompt.txt").exists():
            (root / "prompt.txt").write_text(instruction, encoding="utf-8")
        else:
            with (root / "clarifications.md").open("a", encoding="utf-8") as stream:
                stream.write(f"\n## {job['id']}\n{instruction}\n")
        source, old_brief = [], None
        if design["latest_revision"]:
            previous = root / "revisions" / design["latest_revision"]
            source = self.read_source(previous)
            old_brief = read_json(root / read_json(previous / "revision.json")["brief"])
        number = max((int(p.stem.removeprefix("brief-v")) for p in root.glob("brief-v[0-9]*.json")
                      if re.fullmatch(r"brief-v[0-9]+", p.stem)), default=0) + 1
        brief, failure = None, None
        last_files = None
        started = time.monotonic()
        for attempt in range(3):
            if cancel.is_set():
                raise Cancelled()
            if time.monotonic() - started > 900:
                raise RuntimeError("The 15-minute turn budget was exhausted. Send a new instruction to continue.")
            state("generating" if attempt == 0 else "repairing",
                  "Designing source and acceptance checks" if attempt == 0 else f"Repairing from measured evidence ({attempt}/2)")
            prompt = design_prompt(instruction=instruction, design_id=design["id"], brief_revision=number,
                                   history=design["messages"][-12:], source=source, current_brief=brief or old_brief,
                                   selected=selected, repair_failure=failure)
            proposal = self.generator(prompt, directory=self.store.job_root(job["id"]) / f"attempt-{attempt + 1}",
                                      cancel=cancel, emit=emit, model=self.model,
                                      timeout=min(420, 900 - (time.monotonic() - started)))
            if cancel.is_set():
                raise Cancelled()
            if proposal["kind"] == "clarification":
                if attempt:
                    raise RuntimeError("Repair requires clarification: " + " ".join(proposal["questions"]))
                design["questions"] = proposal["questions"]
                design["messages"].append({"role": "assistant", "text": proposal["summary"], "questions": proposal["questions"], "time": now()})
                state("needs-input", "A design detail needs your answer")
                return
            if brief is None:
                brief = json.loads(proposal["brief_json"])
                brief.update(id=design["id"], revision=number)
                brief.pop("normalized_dimensions", None)
                validate_brief(brief)
            elif proposal.get("brief_json"):
                candidate = json.loads(proposal["brief_json"])
                candidate.pop("normalized_dimensions", None)
                if candidate != brief:
                    raise ValueError("Automatic repair tried to modify the frozen acceptance brief")
            files = proposal["files"]
            if last_files == files:
                raise RuntimeError("Codex repeated the failed source unchanged. Send a more specific instruction to continue.")
            state("building", "Building native geometry and measuring requirements")
            revision = self.revision(design, brief, files, job["id"])
            remaining = 900 - (time.monotonic() - started)
            if remaining <= 0:
                raise RuntimeError("The 15-minute turn budget was exhausted; the candidate is preserved.")
            report = self.evaluate(revision, session_id, cancel, timeout=min(120, remaining))
            self.evaluated(design, revision, report, proposal["summary"])
            emit("revision", {"revision": revision.name, "outcome": report["outcome"]})
            if report["ready_for_review"]:
                design["messages"].append({"role": "assistant", "text": proposal["summary"], "time": now(), "revision": revision.name})
                state("ready", "Design and measured checks are ready for review")
                return
            unresolved = [row for row in report["coverage"] if row["mandatory"] and row["status"] != "pass"]
            if (not report["errors"] and unresolved and
                    all(row["status"] == "unknown" and row.get("check_id") is None for row in unresolved)):
                design["messages"].append({"role": "assistant", "text": proposal["summary"] +
                    "\nThe model was built. Unsupported mandatory measurements remain unknown; source repairs cannot establish that evidence.",
                    "time": now(), "revision": revision.name})
                state("needs-revision", "Geometry is available; unsupported requirements need additional evidence")
                return
            failure = {"outcome": report["outcome"], "errors": report["errors"], "blocking_reasons": report["blocking_reasons"],
                       "requirements": [row for row in report["coverage"] if row["status"] != "pass"]}
            stderr = revision / "project/evidence/worker.stderr.txt"
            if stderr.exists():
                failure["worker_stderr"] = stderr.read_text(encoding="utf-8")[-6000:]
            source, last_files = files, files
        design["messages"].append({"role": "assistant", "text": "Some checks still need attention after two repairs. Inspect the evidence and give a new instruction to continue.", "time": now()})
        state("needs-revision", "Automatic repair budget exhausted; evidence is preserved")

    def export(self, design, file_format, cancel):
        revision = self.store.design_root(design["id"]) / "revisions" / design["latest_revision"]
        receipt = revision / "project/exports" / f"{file_format}.json"
        if receipt.exists():
            assert_current(revision, read_json(revision / "run.json"))
            return read_json(receipt)
        # Run the public export command in an owned cancellable process.
        result = run_process([sys.executable, "-m", "cadharness", "design", "export", str(revision), "--format", file_format],
                             cwd=ROOT, env=_child_environment(), cancel=cancel, timeout=120)
        if result.returncode:
            raise RuntimeError(result.stderr[-2500:])
        return read_json(receipt)
