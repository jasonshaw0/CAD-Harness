"""The IDE assistant owns authoring; Studio only builds and records its proposals."""

from copy import deepcopy
import re
import threading

from ..workflow.brief import digest, read_json, validate_brief
from ..paths import WORKFLOW_ROOT
from ..guidance import authoring_guide
from .store import contained, new_id, now, save


class IDEAssistant:
    def __init__(self, store, jobs):
        self.store, self.jobs = store, jobs
        self.lock = threading.Lock()

    def viewer(self):
        path = self.store.root / "viewer.json"
        view = read_json(path) if path.exists() else {"design_id": None, "revision_id": None, "selected": [], "sequence": None}
        design = self.store.get(view["design_id"]) if view["design_id"] else None
        return {**view, "design_updated": design.get("updated") if design else None, "active_job": self.jobs.active_id}

    def open(self, design_id, revision_id=None):
        design = self.store.get(design_id)
        previous = self.viewer()
        if revision_id and not any(r["id"] == revision_id and r["scene"] for r in design["revisions"]):
            raise ValueError("Choose a revision with built geometry")
        save(self.store.root / "viewer.json", {"design_id": design_id, "revision_id": revision_id,
                                              "selected": previous["selected"] if previous["design_id"] == design_id else [],
                                              "sequence": new_id("view")})
        return self.viewer()

    def select(self, design_id, selected, revision_id=None):
        view = self.viewer()
        if view["design_id"] != design_id:
            return view  # Ignore an in-flight selection from the previously open scene.
        if not isinstance(selected, list) or any(not isinstance(value, str) for value in selected):
            raise ValueError("selected must contain component IDs")
        view = {key: view[key] for key in ("design_id", "revision_id", "selected", "sequence")}
        view["selected"] = selected
        if revision_id:
            if not any(row["id"] == revision_id and row["scene"] for row in self.store.get(design_id)["revisions"]):
                raise ValueError("Unknown displayed revision")
            view["revision_id"] = revision_id
        save(self.store.root / "viewer.json", view)
        return self.viewer()

    def create(self, title):
        design = self.store.create(title)
        self.open(design["id"])
        return design

    def context(self, design_id=None, *, include_contract=False):
        view = self.viewer()
        design_id = design_id or view["design_id"]
        if not design_id:
            raise ValueError("Create or open a Studio design first")
        design = self.store.get(design_id)
        root = self.store.design_root(design_id)
        result = {"design": design, "selected_components": view["selected"] if view["design_id"] == design_id else [],
                  "displayed_revision": view["revision_id"] or design["display_revision"],
                  "source_files": [], "brief": None, "report": None}
        if design["latest_revision"]:
            revision = root / "revisions" / design["latest_revision"]
            result["source_files"] = self.jobs.read_source(revision)
            result["brief"] = read_json(root / read_json(revision / "revision.json")["brief"])
            if (revision / "run.json").exists():
                result["report"] = read_json(revision / "run.json")
            stderr = revision / "project/evidence/worker.stderr.txt"
            if stderr.exists():
                result["worker_stderr"] = stderr.read_text(encoding="utf-8")[-6000:]
        if include_contract:
            result["authoring_guide"] = authoring_guide()
            result["contract"] = (WORKFLOW_ROOT / "CONTRACTS.md").read_text(encoding="utf-8")
            result["source_api_reference"] = (WORKFLOW_ROOT / "templates/mounting-plate/project.py").read_text(encoding="utf-8")
            result["manifest_reference"] = '[project]\nid="my-design"\nname="My design"\nentrypoint="project.py:create_project"\n'
        return result

    def start_turn(self, design_id, instruction):
        if not instruction.strip():
            raise ValueError("A user instruction is required")
        with self.lock:
            if self.jobs.is_active():
                raise ValueError("Wait for or cancel the active CAD job before starting a turn")
            design = self.store.get(design_id)
            root = self.store.design_root(design_id)
            number = max((int(p.stem[7:]) for p in root.glob("brief-v*.json")
                          if re.fullmatch(r"brief-v[0-9]+", p.stem)), default=0) + 1
            turn = {"id": new_id("turn"), "design_id": design_id, "instruction": instruction,
                    "brief_revision": number, "brief": None, "attempts": [], "created": now()}
            selected = self.viewer()["selected"] if self.viewer()["design_id"] == design_id else []
            design["messages"].append({"role": "user", "text": instruction, "time": now(), "selected": selected})
            design["status"] = "awaiting-ide"
            design["active_turn_id"] = turn["id"]
            self.store.put(design)
            if not (root / "prompt.txt").exists():
                (root / "prompt.txt").write_text(instruction, encoding="utf-8")
            else:
                with (root / "clarifications.md").open("a", encoding="utf-8") as stream:
                    stream.write(f"\n## {turn['id']}\n{instruction}\n")
            save(self.turn_path(turn["id"]), turn)
            self.open(design_id)
            return {"turn": turn, "context": self.context(design_id)}

    def turn_path(self, turn_id):
        if not re.fullmatch(r"turn-[a-f0-9]+", turn_id):
            raise ValueError("invalid turn ID")
        return contained(self.store.root / "turns", turn_id + ".json")

    def submit(self, turn_id, files, brief, summary, *, session_id):
        with self.lock:
            if self.jobs.is_active():
                raise ValueError("A CAD job is already active")
            path = self.turn_path(turn_id)
            turn = read_json(path)
            if self.store.get(turn["design_id"]).get("active_turn_id") != turn_id:
                raise ValueError("A newer user turn superseded this one")
            if len(turn["attempts"]) >= 3:
                raise ValueError("Initial candidate plus two repairs exhausted; wait for a new user instruction")
            if turn["attempts"]:
                previous = self.store.job(turn["attempts"][-1]["job_id"])
                if previous["status"] in {"cancelled", "interrupted"}:
                    raise ValueError("This turn is finished; start a new turn for a new user instruction")
            if turn["brief"] is None:
                if not isinstance(brief, dict):
                    raise ValueError("The initial candidate requires a structured brief")
                accepted = deepcopy(brief)
                accepted.update(id=turn["design_id"], revision=turn["brief_revision"])
                accepted.pop("normalized_dimensions", None)
                validate_brief(accepted)
            else:
                accepted = turn["brief"]
                if brief is not None and brief != accepted:
                    raise ValueError("Repair cannot change the frozen brief; omit brief when repairing source")
            source_hash = digest(files)
            if turn["attempts"] and turn["attempts"][-1]["source_hash"] == source_hash:
                raise ValueError("Unchanged source; diagnose before retrying")
            candidate = {"brief": accepted, "files": files, "summary": summary or "Source supplied by the IDE assistant",
                         "turn_id": turn_id}
            job = self.jobs.submit(turn["design_id"], candidate=candidate, session_id=session_id)
            turn["brief"] = accepted
            turn["attempts"].append({"job_id": job["id"], "source_hash": source_hash})
            save(path, turn)
            return job

    def message(self, design_id, text, questions=None):
        if self.jobs.is_active():
            raise ValueError("Wait for the active CAD job before updating the conversation")
        design = self.store.get(design_id)
        design["messages"].append({"role": "assistant", "text": text, "questions": questions or [], "time": now()})
        design["questions"] = questions or []
        if questions:
            design["status"] = "needs-input"
        elif design["status"] == "needs-input":
            design["status"] = "awaiting-ide"
        self.store.put(design)
        return design
