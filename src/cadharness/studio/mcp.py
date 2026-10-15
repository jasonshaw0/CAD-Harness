"""Local Studio tools for the MCP host's existing assistant, with no model client."""

import inspect
import json
from pathlib import Path
import socket
import threading
import time
from functools import wraps
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.routing import Route

from ..workflow.brief import read_json
from ..paths import STUDIO_WEB
from .server import create_app
from .rendering import RENDER_PROTOCOL


STUDIO_API_REVISION = 2


class StudioPortOccupied(RuntimeError):
    """A listener already owns the requested Studio port."""


def _identity(workspace, library_root, trusted_roots):
    workspace = Path(workspace).resolve()
    library_root = Path(library_root or workspace).resolve()
    return {"protocol": "cadharness-studio-mcp/1", "workspace": str(workspace),
            "library_root": str(library_root),
            "trusted_roots": sorted(str(Path(root).resolve()) for root in (trusted_roots or [library_root]))}


def _validate_owner(handshake, expected, port):
    if {key: handshake.get(key) for key in expected} != expected:
        raise RuntimeError(f"Studio port {port} belongs to a different workspace, trust roots, or protocol; choose --studio-port.")
    if (handshake.get('api_revision') != STUDIO_API_REVISION
            or handshake.get('render_protocol') != RENDER_PROTOCOL
            or 'studio_render_view' not in handshake.get('tools', [])):
        raise RuntimeError(f"Studio port {port} is owned by an older or incompatible MCP service "
                           "without the required image-capture API. Restart its owning MCP "
                           "connection after updating cadHarness, then reconnect this client. "
                           "The existing workspace and designs are preserved.")


class StudioService:
    def __init__(self, workspace=None, *, port=8741, library_root=None, trusted_roots=None):
        import uvicorn
        self.remote = False
        self.handlers = {}
        self.ready = False
        self.tool_lock = threading.RLock()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.bind(("127.0.0.1", port))
        except OSError as exc:
            self.socket.close()
            if exc.errno not in {98, 48, 10048}:
                raise
            raise StudioPortOccupied(f"Studio port {port} is occupied") from exc
        self.url = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
        self.app = create_app(workspace, designer="mcp", library_root=library_root)
        self.identity = _identity(self.app.state.store.root, library_root, trusted_roots)
        self.app.state.authorize(True, via="mcp-stdio-launch")
        self.assistant = self.app.state.assistant
        self.app.router.routes[:0] = [Route("/api/mcp/identity", self.bridge_identity),
                                     Route("/api/mcp/call", self.bridge_call, methods=["POST"])]
        self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", log_level="warning", access_log=False))
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.socket]}, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and self.thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.02)
        if not self.server.started:
            self.close()
            raise RuntimeError("Studio HTTP server failed to start")

    async def bridge_identity(self, request):
        return JSONResponse({**self.identity, "ready": self.ready,
                             "api_revision": STUDIO_API_REVISION,
                             "render_protocol": RENDER_PROTOCOL,
                             "tools": sorted(self.handlers)})

    async def bridge_call(self, request):
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Studio tool request must be an object")
        if body.get("identity") != self.identity:
            raise PermissionError("Studio workspace or trusted roots do not match this MCP client")
        name, arguments = body.get("tool"), body.get("arguments")
        if not isinstance(name, str) or name not in self.handlers or not isinstance(arguments, dict):
            raise ValueError("Unknown Studio tool or invalid arguments")
        try:
            inspect.signature(self.handlers[name]).bind(**arguments)
        except TypeError as exc:
            raise ValueError(str(exc)) from exc
        return JSONResponse(await run_in_threadpool(self.invoke, name, arguments))

    def invoke(self, name, arguments):
        # All clients use this owner's Store, Jobs and IDEAssistant, including
        # their active-job gate. Never open a second Store over a live workspace.
        if name == 'studio_render_view':
            return self.handlers[name](**arguments)  # Broker owns its lock; do not stall other MCP tools.
        with self.tool_lock:
            return self.handlers[name](**arguments)

    def close(self):
        if self.app.state.jobs.cancel_event:
            self.app.state.jobs.cancel_event.set()
        self.server.should_exit = True
        self.thread.join(timeout=5)
        deadline = time.monotonic() + 5
        while self.app.state.jobs.active_id and time.monotonic() < deadline:
            time.sleep(.02)
        self.socket.close()


class RemoteStudioService:
    """Forward Studio tools to the same trusted workspace's existing owner."""

    remote = True

    def __init__(self, url, identity):
        self.url, self.identity = url, identity
        self.opener = build_opener(ProxyHandler({}))
        self.token = None

    def request(self, path, body=None, *, timeout=10):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Studio-Token"] = self.token
        request = Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                          headers=headers)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            try:
                message = json.load(exc).get("error", str(exc))
            except (ValueError, AttributeError):
                message = str(exc)
            raise ValueError(message) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ValueError("Studio's owning MCP connection closed. Reconnect the MCP server to restore the shared canvas.") from exc

    def invoke(self, name, arguments):
        body = {"identity": self.identity, "tool": name, "arguments": arguments}
        timeout = 12 if name == 'studio_render_view' else 10
        try:
            return self.request("/api/mcp/call", body, timeout=timeout)
        except ValueError as exc:
            if str(exc) != 'Invalid Studio session token':
                raise
            # A restarted owner rotates its HTTP token. Refresh only after an
            # identity/capability check, and retry only a request rejected by
            # session middleware before the tool could execute.
            handshake = self.request('/api/mcp/identity')
            _validate_owner(handshake, self.identity, self.url.rsplit(':',1)[1])
            self.token = self.request('/api/session')['token']
            return self.request('/api/mcp/call', body, timeout=timeout)

    def close(self):
        pass  # A secondary client must not cancel the owner's jobs or viewer.


def connect_studio(workspace, *, port=8741, library_root=None, trusted_roots=None):
    """Own the viewer, or attach only to an identical Studio MCP service."""
    try:
        return StudioService(workspace, port=port, library_root=library_root, trusted_roots=trusted_roots)
    except StudioPortOccupied as exc:
        remote = RemoteStudioService(f"http://127.0.0.1:{port}", _identity(workspace, library_root, trusted_roots))
        # Another MCP process can have bound the socket but not finished startup.
        deadline = time.monotonic() + 8
        while True:
            try:
                handshake = remote.request("/api/mcp/identity")
                identity = {key: handshake.get(key) for key in remote.identity}
                ready = handshake.get("ready", False)
                if identity != remote.identity:
                    raise RuntimeError(f"Studio port {port} belongs to a different workspace, trust roots, or protocol; choose --studio-port.") from exc
                if ready:
                    _validate_owner(handshake, remote.identity, port)
                    remote.token = remote.request("/api/session")["token"]
                    return remote
            except (ValueError, KeyError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Studio port {port} is occupied by an incompatible or older service. Restart its owning MCP connection or choose --studio-port.") from exc
            time.sleep(.1)


def register_tools(server, service):
    if not service.remote:
        assistant, store, jobs = service.assistant, service.app.state.store, service.app.state.jobs
        authorize = service.app.state.execution_session

    def tool(function):
        from mcp.server.mcpserver.exceptions import ToolError
        if not service.remote:
            service.handlers[function.__name__] = function
        @wraps(function)
        def call(*args, **kwargs):
            try:
                arguments = inspect.signature(function).bind(*args, **kwargs).arguments
                result = service.invoke(function.__name__, arguments)
                if function.__name__ == 'studio_render_view' and result.get('status') == 'captured':
                    from mcp.types import CallToolResult, ImageContent, TextContent
                    metadata = {k: v for k, v in result.items() if k != '_png_base64'}
                    return CallToolResult(content=[TextContent(type='text', text=json.dumps(metadata)),
                                                  ImageContent(type='image', data=result['_png_base64'], mime_type='image/png')],
                                          structured_content=metadata)
                return result
            except (ValueError, PermissionError, FileNotFoundError) as exc:
                raise ToolError(str(exc)) from exc
        return server.tool()(call)

    @tool
    def studio_status() -> dict[str, Any]:
        """Get the Studio URL and current selection. This MCP host is the designer; no nested model is called."""
        return {"viewer_url": service.url, "workspace": str(store.root), "designer": "IDE assistant via MCP",
                "model_calls": False, "frontend_available": (STUDIO_WEB / "index.html").is_file(),
                "viewer": assistant.viewer(),
                "rendering": service.app.state.renders.availability(),
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
        """Read source, brief and measured failures; include contract before authoring. Check rendering availability and use images adaptively."""
        return {**assistant.context(design_id, include_contract=include_contract),
                "rendering": service.app.state.renders.availability()}

    @tool
    def studio_render_view(design_id: str, revision_id: str | None = None, view: str = 'iso',
                           component_ids: list[str] | None = None,
                           focus_bounds_mm: list[list[float]] | None = None,
                           width: int = 1024, height: int = 768) -> dict[str, Any]:
        """Return a PNG of a retained build using Studio's separate camera; no desktop control. Default: latest built revision, one isometric view. Inspect uncertain shapes/interfaces adaptively; use component IDs or [min_xyz,max_xyz] focus bounds for detail. Preserves the user's viewport. Closed Studio/WebGL failure returns unavailable within 10 seconds. Capturing is not reviewing; text-only models must not claim visual inspection."""
        result = service.app.state.renders.capture(design_id, revision_id, view, component_ids,
                                                   focus_bounds_mm, width, height)
        if result['status'] == 'captured':
            result['artifact']['url'] = f"{service.url}/api/designs/{design_id}/renders/{result['artifact']['id']}.png"
        return result

    @tool
    def studio_start_turn(design_id: str, instruction: str) -> dict[str, Any]:
        """Start a new user instruction with a new brief revision. Repairs must reuse this turn, not call this tool again."""
        authorize()
        return assistant.start_turn(design_id, instruction)

    @tool
    def studio_submit_candidate(turn_id: str, files: list[dict[str, str]], brief: dict[str, Any] | None = None,
                                summary: str = "") -> dict[str, Any]:
        """Submit complete Python/TOML source for a trusted build. Initial candidate needs a brief; repairs omit it. Inspect measurements, then render uncertain features as useful. Changed source may refine a passing candidate within the same turn's existing budget. Returns a job, not a verdict."""
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

    if not service.remote:
        service.ready = True
