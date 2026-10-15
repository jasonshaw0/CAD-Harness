"""Local Studio tools for the MCP host's existing assistant, with no model client."""

import socket
import threading
import time
from functools import wraps
from typing import Any

from ..brief import read_json
from ..runner import ROOT
from .server import create_app


class StudioService:
    def __init__(self, workspace=None, *, port=8741):
        import uvicorn
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.bind(("127.0.0.1", port))
        except OSError as exc:
            self.socket.close()
            raise RuntimeError(f"Studio port {port} is occupied. Close the standalone Studio instance or choose --studio-port.") from exc
        self.url = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
        self.app = create_app(workspace, designer="mcp")
        self.app.state.authorize(True, via="mcp-stdio-launch")
        self.assistant = self.app.state.assistant
        self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", log_level="warning", access_log=False))
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.socket]}, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and self.thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.02)
        if not self.server.started:
            self.close()
            raise RuntimeError("Studio HTTP server failed to start")

    def close(self):
        if self.app.state.jobs.cancel_event:
            self.app.state.jobs.cancel_event.set()
        self.server.should_exit = True
        self.thread.join(timeout=5)
        deadline = time.monotonic() + 5
        while self.app.state.jobs.active_id and time.monotonic() < deadline:
            time.sleep(.02)
        self.socket.close()


def register_tools(server, service):
    assistant, store, jobs = service.assistant, service.app.state.store, service.app.state.jobs
    authorize = service.app.state.execution_session

    def tool(function):
        from mcp.server.mcpserver.exceptions import ToolError
        @wraps(function)
        def call(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except (ValueError, PermissionError, FileNotFoundError) as exc:
                raise ToolError(str(exc)) from exc
        return server.tool()(call)

    @tool
    def studio_status() -> dict[str, Any]:
        """Get the Studio URL and current selection. This MCP host is the designer; no nested model is called."""
        return {"viewer_url": service.url, "workspace": str(store.root), "designer": "IDE assistant via MCP",
                "model_calls": False, "frontend_available": (ROOT / "designworkflow/studio/web/dist/index.html").is_file(),
                "viewer": assistant.viewer(),
                "workflow": "Create/open a design, start one turn per user instruction, get context with include_contract=True, submit Python/TOML files and a brief, then poll studio_get_job. Repair source with the same turn_id and omit brief; at most two repairs. Unsupported evidence remains unknown. Use studio_message for explanations/clarifications. Never start a new turn merely to evade a failed check or repair budget."}

    @tool
    def studio_list_designs() -> dict[str, Any]:
        """List saved Studio designs without executing project factories."""
        return {"designs": store.listing(), "viewer_url": service.url}

    @tool
    def studio_create_design(title: str) -> dict[str, Any]:
        """Create an empty source-backed design and display it in Studio."""
        authorize()
        return {"design": assistant.create(title), "viewer_url": service.url}

    @tool
    def studio_open_design(design_id: str, revision_id: str | None = None) -> dict[str, Any]:
        """Display a saved design or earlier built revision in the live canvas."""
        return {"viewer": assistant.open(design_id, revision_id), "viewer_url": service.url}

    @tool
    def studio_get_context(design_id: str | None = None, include_contract: bool = False) -> dict[str, Any]:
        """Read source, brief, selected component IDs and measured failures. Include contract before authoring a first candidate."""
        return assistant.context(design_id, include_contract=include_contract)

    @tool
    def studio_start_turn(design_id: str, instruction: str) -> dict[str, Any]:
        """Start a new user instruction with a new brief revision. Repairs must reuse this turn, not call this tool again."""
        authorize()
        return assistant.start_turn(design_id, instruction)

    @tool
    def studio_submit_candidate(turn_id: str, files: list[dict[str, str]], brief: dict[str, Any] | None = None,
                                summary: str = "") -> dict[str, Any]:
        """Submit complete relative Python/TOML source files for a trusted local CAD build. Initial candidate needs a brief; repairs omit it. Returns a job, not a design verdict."""
        return {"job": assistant.submit(turn_id, files, brief, summary, session_id=authorize()), "viewer_url": service.url}

    @tool
    def studio_get_job(job_id: str) -> dict[str, Any]:
        """Read the actual build outcome and measured acceptance evidence. Poll until terminal; inspect failures before repairing."""
        job = store.job(job_id)
        design = store.get(job["design_id"])
        revision_id = job.get("revision") or design["latest_revision"]
        report, error, artifacts = None, None, {}
        if revision_id:
            revision = store.design_root(design["id"]) / "revisions" / revision_id
            if (revision / "run.json").exists():
                report = read_json(revision / "run.json")
            stderr = revision / "project/evidence/worker.stderr.txt"
            if stderr.exists():
                error = stderr.read_text(encoding="utf-8")[-6000:]
            base = f"{service.url}/api/designs/{design['id']}/revisions/{revision_id}"
            artifacts = {"source": base + "/source", "report": base + "/files/run.json"}
            for path in (revision / "project/exports").rglob("*"):
                if path.suffix in {".step", ".stl"}:
                    artifacts[path.name] = base + "/files/" + path.relative_to(revision).as_posix()
        return {"job": job, "report": report, "worker_stderr": error, "artifacts": artifacts,
                "displayed_revision": design["display_revision"], "viewer_url": service.url}

    @tool
    def studio_message(design_id: str, text: str, questions: list[str] | None = None) -> dict[str, Any]:
        """Show an assistant explanation or targeted clarification in Studio; the user continues the conversation in the IDE."""
        authorize()
        return {"design": assistant.message(design_id, text, questions)}

    @tool
    def studio_rebuild_design(design_id: str) -> dict[str, Any]:
        """Rebuild current source with frozen requirements in a fresh revision, without a model call."""
        if not store.get(design_id)["latest_revision"]:
            raise ValueError("No source exists to rebuild")
        assistant.open(design_id)
        return {"job": jobs.submit(design_id, rebuild=True, session_id=authorize())}

    @tool
    def studio_export_design(design_id: str, file_format: str = "step") -> dict[str, Any]:
        """Explicitly export evaluated printable parts as STEP or STL. References and stale/failed evidence are rejected."""
        if file_format not in {"step", "stl"}:
            raise ValueError("Choose step or stl")
        if not store.get(design_id)["latest_revision"]:
            raise ValueError("No evaluated revision exists")
        return {"job": jobs.submit(design_id, export_format=file_format, session_id=authorize())}

    @tool
    def studio_cancel_job(job_id: str) -> dict[str, Any]:
        """Cancel Studio's owned CAD process tree; the last built scene stays visible."""
        authorize()
        jobs.cancel(job_id)
        return {"cancelling": True}
