"""Loopback-only Studio HTTP API and bundled frontend."""

import asyncio
from contextlib import asynccontextmanager
import json
from io import BytesIO
from pathlib import Path
import secrets
import zipfile

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from ..workflow.brief import read_json
from ..paths import RUNS_ROOT, STUDIO_WEB
from .codex import cli_command
from .jobs import ACTIVE, Jobs
from .store import Store, contained, now, save


def create_app(workspace=None, *, model=None, generator=None, designer="mcp", library_root=None):
    if designer not in {"mcp", "codex"}:
        raise ValueError("designer must be mcp or codex")
    store = Store(workspace or RUNS_ROOT / "studio")
    jobs = Jobs(store, model=model, **({"generator": generator} if generator else {}))
    from .assistant import IDEAssistant
    assistant = IDEAssistant(store, jobs)
    if designer == "mcp" and not assistant.viewer()["design_id"]:
        saved_designs = store.listing()
        if saved_designs:
            assistant.open(saved_designs[0]["id"])
    token = secrets.token_urlsafe(32)
    authorization = {"id": None}
    library = {}
    # Discovery reads saved records only. Imports are explicit, copied, and run
    # after trusted-session authorization; MCP roots are never modified.
    for path in Path(library_root or store.root).rglob("run.json"):
        if path.is_relative_to(store.root):
            continue
        try:
            report = read_json(path)
            if (path.parent / "project/cadharness.toml").is_file():
                key = secrets.token_hex(6)
                library[key] = {"path": path.parent, "title": f"{path.parent.parent.parent.name} / {path.parent.name}",
                                "outcome": report.get("outcome")}
        except (ValueError, OSError):
            continue

    def authorize(enabled, via="browser"):
        previous = authorization["id"]
        if previous:
            record = store.root / "sessions" / f"{previous}.json"
            saved = read_json(record)
            saved["ended"] = now()
            save(record, saved)
        authorization["id"] = secrets.token_hex(16) if enabled else None
        if authorization["id"]:
            save(store.root / "sessions" / f"{authorization['id']}.json", {
                "id": authorization["id"], "mode": "trusted-session", "created": now(), "via": via,
                "workspace": str(store.root), "source_review": "not-human-reviewed",
                "scope": "IDE MCP proposals and CAD Python execution" if designer == "mcp" else "Local Codex proposals and CAD Python execution"})
        elif jobs.cancel_event:
            jobs.cancel_event.set()
        return authorization["id"]

    async def session(request):
        available = False
        if designer == "codex":
            try:
                cli_command()
                available = True
            except RuntimeError:
                pass
        if request.method == "POST":
            body = await request.json()
            authorize(body.get("authorize") is True)
        return JSONResponse({"token": token, "authorized": authorization["id"] is not None,
                             "designer": designer, "codex_available": available,
                             "model": "IDE assistant · MCP" if designer == "mcp" else model or "Codex CLI default",
                             "workspace": str(store.root), "active_job": jobs.active_id})

    def require_session():
        if not authorization["id"]:
            raise PermissionError("Enable a trusted local session before generating or building Python.")
        return authorization["id"]

    async def viewer(request):
        if request.method == "POST":
            body = await request.json()
            if "selected" in body:
                return JSONResponse(assistant.select(body["design_id"], body["selected"], body.get("revision_id")))
            return JSONResponse(assistant.open(body["design_id"], body.get("revision_id")))
        return JSONResponse(assistant.viewer())

    async def designs(request):
        if request.method == "GET":
            return JSONResponse({"designs": store.listing(), "active_job": jobs.active_id})
        require_session()
        if jobs.active_id:
            raise ValueError("A design job is already running")
        body = await request.json()
        instruction = str(body.get("prompt", "")).strip()
        example, saved = body.get("example"), body.get("saved")
        examples = {"square-mount": "Mounting plate", "enclosure": "Electronics enclosure", "flange": "Pipe flange"}
        if example and example not in examples:
            raise ValueError("unknown example")
        if saved and saved not in library:
            raise ValueError("unknown saved design")
        if not instruction and not example and not saved:
            raise ValueError("Describe a design or choose an example")
        if designer == "mcp" and not example and not saved:
            raise ValueError("Describe the design to your IDE assistant and use studio_start_turn through MCP")
        design = store.create(examples.get(example) or (library[saved]["title"] if saved else instruction))
        if designer == "mcp":
            assistant.open(design["id"])
        job = jobs.submit(design["id"], instruction, example=example,
                          import_path=library[saved]["path"] if saved else None,
                          session_id=authorization["id"])
        return JSONResponse({"design": design, "job": job}, status_code=202)

    async def design(request):
        return JSONResponse(store.get(request.path_params["design_id"]))

    async def turn(request):
        require_session()
        if designer == "mcp":
            raise ValueError("Continue the conversation in your IDE; Studio makes no model calls in MCP mode")
        body = await request.json()
        instruction = str(body.get("prompt", "")).strip()
        if not instruction:
            raise ValueError("Enter an instruction")
        design_id = request.path_params["design_id"]
        store.get(design_id)
        job = jobs.submit(design_id, instruction, body.get("selected", []), session_id=authorization["id"])
        return JSONResponse({"job": job}, status_code=202)

    async def revision(request):
        root = store.design_root(request.path_params["design_id"])
        path = contained(root / "revisions", request.path_params["revision_id"])
        report = read_json(path / "run.json") if (path / "run.json").exists() else None
        scene = read_json(path / "project/evidence/scene.json") if (path / "project/evidence/scene.json").exists() else None
        files = [p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        comparison = None
        current_snapshot = path / "project/evidence/snapshot.json"
        if scene and current_snapshot.is_file():
            rows = store.get(request.path_params["design_id"])["revisions"]
            earlier = [row for row in rows if row["id"] < path.name and row.get("scene")]
            if earlier:
                previous = earlier[-1]["id"]
                baseline = contained(root / "revisions", previous) / "project/evidence/snapshot.json"
                if baseline.is_file():
                    from cadharness import compare_snapshots
                    diff = compare_snapshots(read_json(baseline), read_json(current_snapshot))
                    comparison = {"baseline": previous, "components": diff["components"], "requirements": diff["requirements"]}
        return JSONResponse({"revision": path.name, "report": report, "scene": scene, "files": files,
                             "comparison": comparison})

    async def export(request):
        require_session()
        body = await request.json()
        file_format = body.get("format", "step")
        if file_format not in {"step", "stl"}:
            raise ValueError("format must be step or stl")
        design_id = request.path_params["design_id"]
        design = store.get(design_id)
        if not design["latest_revision"]:
            raise ValueError("No evaluated revision is available")
        job = jobs.submit(design_id, export_format=file_format, session_id=authorization["id"])
        return JSONResponse({"job": job}, status_code=202)

    async def rebuild(request):
        require_session()
        design_id = request.path_params["design_id"]
        if not store.get(design_id)["latest_revision"]:
            raise ValueError("No source revision is available to rebuild")
        job = jobs.submit(design_id, rebuild=True, session_id=authorization["id"])
        return JSONResponse({"job": job}, status_code=202)

    async def file(request):
        root = store.design_root(request.path_params["design_id"]) / "revisions"
        revision = contained(root, request.path_params["revision_id"])
        path = contained(revision, request.path_params["path"])
        if not path.is_file():
            raise FileNotFoundError("artifact not found")
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")

    async def source_archive(request):
        root = store.design_root(request.path_params["design_id"])
        revision = contained(root / "revisions", request.path_params["revision_id"])
        buffer = BytesIO()
        from ..workflow.runner import source_files
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in source_files(revision / "project"):
                archive.write(contained(revision / "project", name), name)
            brief = revision / "project/evidence/brief.json"
            if brief.exists():
                archive.write(brief, "design-brief.json")
        return Response(buffer.getvalue(), media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{request.path_params["design_id"]}-{revision.name}-source.zip"'})

    async def job(request):
        return JSONResponse(store.job(request.path_params["job_id"]))

    async def cancel(request):
        require_session()
        jobs.cancel(request.path_params["job_id"])
        return JSONResponse({"cancelling": True})

    async def events(request):
        job_id = request.path_params["job_id"]
        store.job(job_id)
        start = int(request.headers.get("last-event-id", "0"))
        async def stream():
            cursor = start
            while True:
                path = store.job_root(job_id) / "events.jsonl"
                content = path.read_text(encoding="utf-8") if path.exists() else ""
                lines = content.splitlines()
                if content and not content.endswith("\n"):
                    lines = lines[:-1]
                for index, line in enumerate(lines[cursor:], cursor + 1):
                    yield f"id: {index}\ndata: {line}\n\n"
                cursor = len(lines)
                if store.job(job_id)["status"] not in ACTIVE:
                    yield 'event: complete\ndata: {}\n\n'
                    break
                if await request.is_disconnected():
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.25)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    async def listing(request):
        return JSONResponse({"saved": [{"id": key, "title": value["title"], "outcome": value["outcome"]} for key, value in library.items()]})

    async def failure(request, exc):
        status = 403 if isinstance(exc, PermissionError) else 404 if isinstance(exc, FileNotFoundError) else 400
        return JSONResponse({"error": str(exc)}, status_code=status)

    class LocalRequests(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return JSONResponse({"error": "Studio accepts same-origin requests only"}, status_code=403)
            if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-studio-token") != token:
                return JSONResponse({"error": "Invalid Studio session token"}, status_code=403)
            return await call_next(request)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if jobs.cancel_event:
            jobs.cancel_event.set()

    routes = [Route("/api/session", session, methods=["GET", "POST"]),
              Route("/api/viewer", viewer, methods=["GET", "POST"]),
              Route("/api/designs", designs, methods=["GET", "POST"]), Route("/api/library", listing),
              Route("/api/designs/{design_id}", design), Route("/api/designs/{design_id}/turns", turn, methods=["POST"]),
              Route("/api/designs/{design_id}/revisions/{revision_id}", revision),
              Route("/api/designs/{design_id}/revisions/{revision_id}/source", source_archive),
              Route("/api/designs/{design_id}/export", export, methods=["POST"]),
              Route("/api/designs/{design_id}/rebuild", rebuild, methods=["POST"]),
              Route("/api/designs/{design_id}/revisions/{revision_id}/files/{path:path}", file),
              Route("/api/jobs/{job_id}", job), Route("/api/jobs/{job_id}/events", events),
              Route("/api/jobs/{job_id}/cancel", cancel, methods=["POST"])]
    dist = STUDIO_WEB
    if dist.is_dir():
        routes.append(Mount("/", StaticFiles(directory=dist, html=True)))
    app = Starlette(routes=routes, lifespan=lifespan,
                    exception_handlers={ValueError: failure, FileNotFoundError: failure, PermissionError: failure})
    app.add_middleware(LocalRequests)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.state.store, app.state.jobs = store, jobs
    app.state.assistant, app.state.authorize, app.state.execution_session = assistant, authorize, require_session
    return app


def serve(*, workspace=None, port=8741, model=None, designer="mcp"):
    import uvicorn
    dist = STUDIO_WEB / "index.html"
    if not dist.exists():
        raise RuntimeError("Build the Studio frontend first: cd studio/web && npm ci && npm run build")
    print(f"cadHarness Studio: http://127.0.0.1:{port}", flush=True)
    uvicorn.run(create_app(workspace, model=model, designer=designer), host="127.0.0.1", port=port, log_level="warning")
