"""Prepare a measured failure and repair using the packaged Studio template."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import socket
import threading
import time
import webbrowser

from ..diagnostics import package_version
from ..paths import STUDIO_WEB
from ..workflow.benchmarks.cases import get_case
from ..workflow.brief import read_json
from .assistant import IDEAssistant
from .jobs import Jobs
from .store import Store, new_id, now, save


def prepare_demo(workspace: Path | None = None) -> dict:
    """Create a new workspace only; build both revisions with one frozen brief."""
    target = (workspace or Path.cwd() / "runs" / new_id("demo")).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ValueError("Demo workspace already exists; choose a new --workspace. Reopen saved data with 'cad-harness studio --workspace PATH'.")
    target.mkdir(parents=True, exist_ok=False)
    store = Store(target)
    jobs = Jobs(store)
    design = store.create("Missing hole → measured repair")
    root = store.design_root(design["id"])
    case = get_case("square-mount")
    brief = deepcopy(case["brief"])
    brief.update(id=design["id"], revision=1)
    (root / "prompt.txt").write_text(case["prompt"], encoding="utf-8")
    files = [{"path": path.name, "content": path.read_text(encoding="utf-8")}
             for path in sorted(case["template"].iterdir()) if path.suffix in {".py", ".toml"}]
    session_id = new_id("demo")
    save(store.root / "sessions" / f"{session_id}.json", {
        "id": session_id, "mode": "trusted-session", "created": now(),
        "via": "packaged-demo-command", "source_review": "not-human-reviewed",
        "workspace": str(store.root), "scope": "Build the bundled mounting-plate demonstration"})
    try:
        for variant, count, summary in (
            ("missing-hole", 3, "Three measured holes; the unchanged brief requires four."),
            ("standard", 4, "Fourth hole restored; the same frozen brief now passes."),
        ):
            candidate = deepcopy(files)
            manifest = next(item for item in candidate if item["path"] == "cadharness.toml")
            manifest["content"] = manifest["content"].replace('default_variant = "standard"', f'default_variant = "{variant}"')
            revision = jobs.revision(design, brief, candidate, session_id)
            report = jobs.evaluate(revision, session_id, threading.Event())
            jobs.evaluated(design, revision, report, summary)
            measured = next((row for row in report["coverage"] if row["id"] == "holes.count"), {})
            if (measured.get("result", {}).get("actual") != count
                    or measured.get("status") != ("pass" if count == 4 else "fail")
                    or report["ready_for_review"] != (count == 4)
                    or not (revision / "project/evidence/scene.json").is_file()):
                raise RuntimeError(f"Demo evaluation did not establish {count} actual holes; inspect {revision / 'run.json'}")
            design["messages"].append({"role": "demo", "text": summary, "time": now(), "revision": revision.name})
            store.put(design)
        info = {"schema": "cadharness.demo", "schema_version": "1", "prepared_with": package_version(),
                "workspace": str(store.root), "design_id": design["id"],
                "failed_revision": "r001", "repaired_revision": "r002",
                "physical_validation": "not performed"}
        save(store.root / "demo.json", info)
        IDEAssistant(store, jobs).open(design["id"], "r001")
        return info
    finally:
        record = store.root / "sessions" / f"{session_id}.json"
        session = read_json(record)
        save(record, {**session, "ended": now()})


def demo_info(store: Store) -> dict | None:
    path = store.root / "demo.json"
    if not path.is_file():
        return None
    info = read_json(path)
    if info.get("schema") != "cadharness.demo" or info.get("schema_version") != "1":
        raise ValueError("Unsupported demo workspace metadata")
    design = store.get(info["design_id"])
    revisions = {row["id"] for row in design["revisions"]}
    if not {info["failed_revision"], info["repaired_revision"]} <= revisions:
        raise ValueError("Demo revisions are missing; preserve this workspace and prepare a new demo")
    return info


def serve_demo(*, workspace: Path | None = None, port: int = 0, open_browser: bool = True):
    if not 0 <= port <= 65535:
        raise ValueError("Demo port must be between 0 and 65535")
    if any(importlib.util.find_spec(name) is None for name in ("starlette", "uvicorn")):
        raise RuntimeError("Install CAD-Harness[studio] in this interpreter to run the demo viewer")
    if not (STUDIO_WEB / "index.html").is_file():
        raise RuntimeError("Studio frontend is missing; run bootstrap.py or install a validated full wheel")
    import uvicorn
    from .server import create_app

    # Reserve an actual loopback port before building. Never attach to another
    # Studio workspace or change its MCP roots, authorization or port owner.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", port))
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        print("Building the bundled demonstration: missing hole, then measured repair…", flush=True)
        info = prepare_demo(workspace)
        app = create_app(Path(info["workspace"]))
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", log_level="warning", access_log=False))
        stopped = threading.Event()

        def launch():
            while not stopped.wait(.05):
                if server.started:
                    if not webbrowser.open(url):
                        print(f"Open the demo in your browser: {url}", flush=True)
                    return

        browser = threading.Thread(target=launch, daemon=True) if open_browser else None
        print(f"CAD-Harness demo: {url}\nWorkspace: {info['workspace']}\n"
              "r001: 3 measured holes (requires 4). r002: same brief, repaired geometry.\n"
              "No model account or MCP setup required. Physical fit remains unverified.\n"
              "Press Ctrl+C to stop; source and evidence stay in this workspace.", flush=True)
        if browser:
            browser.start()
        try:
            server.run(sockets=[listener])
        finally:
            stopped.set()
            if browser:
                browser.join(timeout=1)
