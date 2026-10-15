"""Small file-backed Studio store; all paths are workspace-contained."""

from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import secrets
import time

from ..brief import read_json


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{secrets.token_hex(4)}.tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    # Windows readers briefly hold handles that prevent an atomic replacement.
    # Keep readers on a complete record and retry the owned rename, not the job.
    try:
        for attempt in range(8):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(.01 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix):
    return f"{prefix}-{secrets.token_hex(4)}"


def contained(root: Path, name: str):
    pure = PurePosixPath(name)
    if not name or "\\" in name or ":" in name or pure.is_absolute() or ".." in pure.parts:
        raise ValueError("path must stay inside the selected workspace")
    path = (root / pure).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError("path must stay inside the selected workspace")
    probe = root
    for part in pure.parts:
        probe = probe / part
        if probe.is_symlink():
            raise ValueError("symlinks are not supported")
    return path


class Store:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "jobs").mkdir(exist_ok=True)
        (self.root / "designs").mkdir(exist_ok=True)
        for path in (self.root / "jobs").glob("*/job.json"):
            job = read_json(path)
            if job["status"] in {"queued", "generating", "building", "checking", "repairing", "exporting"}:
                job.update(status="interrupted", error="Studio restarted; this job was interrupted.", updated=now())
                save(path, job)
        for path in (self.root / "designs").glob("*/studio.json"):
            design = read_json(path)
            if design["status"] in {"queued", "generating", "building", "checking", "repairing", "exporting"}:
                design["status"] = "interrupted"
                for revision in design["revisions"]:
                    if revision["status"] == "building":
                        revision["status"] = "interrupted"
                save(path, design)

    def design_root(self, design_id):
        if not re.fullmatch(r"[a-z][a-z0-9-]*", design_id):
            raise ValueError("invalid design ID")
        return contained(self.root / "designs", design_id)

    def get(self, design_id):
        return read_json(self.design_root(design_id) / "studio.json")

    def put(self, design):
        design["updated"] = now()
        save(self.design_root(design["id"]) / "studio.json", design)

    def create(self, title):
        design = {"id": new_id("design"), "title": title[:80] or "Untitled design", "created": now(),
                  "messages": [], "revisions": [], "latest_revision": None, "display_revision": None,
                  "questions": [], "status": "empty"}
        self.put(design)
        return design

    def listing(self):
        return sorted([read_json(path) for path in (self.root / "designs").glob("*/studio.json")],
                      key=lambda item: item["updated"], reverse=True)

    def job_root(self, job_id):
        if not re.fullmatch(r"job-[a-f0-9]+", job_id):
            raise ValueError("invalid job ID")
        return contained(self.root / "jobs", job_id)

    def job(self, job_id):
        return read_json(self.job_root(job_id) / "job.json")

    def put_job(self, job):
        job["updated"] = now()
        save(self.job_root(job["id"]) / "job.json", job)

    def event(self, job, kind, data):
        path = self.job_root(job["id"]) / "events.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"type": kind, "time": now(), **data}, ensure_ascii=False) + "\n")


def write_candidate(project, files):
    project.mkdir(parents=True, exist_ok=False)
    names = set()
    for item in files:
        name = item["path"]
        target = contained(project, name)
        if target.suffix not in {".py", ".toml"} or any(part in {"evidence", "exports", "previews", ".cadharness", "__pycache__"} for part in PurePosixPath(name).parts):
            raise ValueError("candidate files must be local Python or TOML inputs")
        if name in names or not isinstance(item["content"], str):
            raise ValueError("duplicate or invalid candidate file")
        names.add(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"], encoding="utf-8")
    if not {"project.py", "cadharness.toml"}.issubset(names):
        raise ValueError("proposal requires project.py and cadharness.toml")
