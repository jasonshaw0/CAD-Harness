# cadHarness Studio

Studio is the included application for the cadHarness framework. Your IDE
assistant writes parametric Python through MCP; Studio builds revisions,
displays the actual geometry, and returns measured acceptance evidence to the
same conversation. Source remains editable and every attempt retains its report.

## One-command setup

Use Python 3.11–3.14 and Node.js 22.12+. Installation includes build123d 0.13.x.
From the repository root on Windows:

```powershell
python bootstrap.py
```

On macOS or Linux:

```bash
python3 bootstrap.py
```

Setup creates or reuses `.venv`, installs the Python extras and frontend
dependencies, builds the canvas, verifies the example CAD project, and writes
`.cadharness/mcp.json`. It works from any current directory; paths are resolved
from the script's checkout. Rerun it after updates. No activation is required.

`python bootstrap.py --check` checks prerequisites without changing files.
For framework-only use without Node.js, run `python bootstrap.py --framework-only`.
Missing Python/Node.js versions need to be installed first; the script reports
what is missing and does not install system software.

Select trust roots, workspace, and port in the same setup command:

```powershell
python bootstrap.py --root D:/CAD/my-project --workspace D:/CAD/my-project/workspace --port 8742
```

Roots default to this checkout; `--root` can be repeated. A workspace cannot
expand those roots. Existing differing config files are preserved; select a new
`--config PATH` or explicitly use `--overwrite-config` to regenerate one.
The script never edits the MCP host's own settings or rewrites saved designs.

For manual installation or frontend-only work, the individual commands remain:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mcp,studio]"
npm --prefix studio/web ci
npm --prefix studio/web run build
.\.venv\Scripts\python.exe -m cadharness mcp-config . --studio
```

The canvas builds into `src/cadharness/studio/web/`, where Python serves it.
Node.js is needed to build it; the running application serves static files.

## Connect your assistant

Copy the `cadharness` entry from `.cadharness/mcp.json` into your MCP host's
`mcpServers` object. For manual setup, use the printed `mcp-config` output.
It uses this environment's absolute interpreter, explicit trusted roots, and
`--studio`. Hosts with stdio configuration can use the same command and
arguments. Reload the host after configuration changes.

The host starts the framework CAD tools and Studio design tools together, plus
the loopback viewer at **http://127.0.0.1:8741**. Call `studio_status` to confirm
the exact URL and `frontend_available`. Do not start another viewer on the same port.

Use a dedicated trusted root for real projects. Studio's default workspace is
`runs/studio/` beneath the **first explicit MCP root**. For a different location:

```powershell
.\.venv\Scripts\python.exe -m cadharness mcp-config D:/CAD/my-project --studio --studio-workspace D:/CAD/my-project/workspace --studio-port 8742
```

The workspace must stay inside a configured root; configuration never adds
roots implicitly. With multiple roots, specify the workspace if the first root
is not its intended home. The saved-run library reads only the configured root
containing that workspace and imports source by explicit action.

## First design and iteration

Ask your assistant for a Studio design with explicit dimensions, units, hole
positions, and printable components. For example:

> Create a centered 60 × 60 × 4 mm plate, bottom at Z=0, with four diameter
> 3.5 mm through-holes at (±15.5, ±15.5) mm. Keep the source parametric and
> measure the plate dimensions and hole pattern before presenting it.

The assistant uses these tools in order:

1. `studio_status`, then `studio_create_design` or `studio_open_design`.
2. `studio_start_turn` for the user's instruction, and `studio_get_context`
   with `include_contract=True` before first authoring.
3. `studio_submit_candidate` with complete Python/TOML files and a structured
   brief. Submission returns a job, not a passing design verdict.
4. `studio_get_job` until the build finishes. Read actual/expected measurements
   and requirement coverage before presenting or repairing it.
5. Repair in the same turn with its frozen brief, with at most two repairs.
   A further user instruction starts a new turn and brief revision.

The browser updates as revisions and assistant messages arrive. Click a part
to give the assistant selection context; continue the conversation in your IDE.
Studio makes no separate model calls in MCP mode and needs no browser model
login. Unknown mandatory evidence cannot produce a ready verdict.

## Controls and outputs

| Control | Behavior |
| --- | --- |
| Canvas | Drag to orbit, right-drag to pan, scroll to zoom; use Fit or a standard view. |
| Components | Select geometry or a row; eye buttons hide parts, and the selection card isolates one. Reference envelopes appear ghosted. |
| Revisions | Open earlier geometry. Overlay shows changed prior components in amber; it is not an exact solid difference. |
| Checks | Inspect actual/expected values, assumptions, and requirement changes. |
| Rebuild | Copy current source to a new revision and evaluate without a model call. |
| Source / Report | Download Python, manifest, and frozen brief as ZIP, or the recorded evidence. |
| STEP / STL | Explicitly export current, passing printable components; references are excluded. |

Failed builds and cancellation retain the labeled previous scene. Designs,
turns, sessions, source, checks, meshes, and exports stay in the workspace.
One CAD job runs at a time, builds time out after 120 seconds, and each turn
allows three candidates. Restart marks interrupted jobs and restores designs.

The MCP launch authorizes trusted local execution. Generated Python is not
sandboxed or labeled human-reviewed. Workers receive no model credentials;
root restrictions, hashes, frozen requirements, and cancellation still apply.
Readiness does not establish physical fit or manufacturing performance.

## Standalone and development modes

`python -m cadharness studio` serves the viewer/API without an MCP transport.
It defaults to `<checkout>/runs/studio/` for an editable install and
`<cwd>/runs/studio/` for a wheel. Use `--workspace PATH` to choose explicitly.
Use the MCP-host launch above for the integrated assistant experience.

The earlier separate Codex CLI designer remains opt-in:

```powershell
.\.venv\Scripts\python.exe -m cadharness studio --designer codex
```

Only that mode requires a signed-in `codex` executable and supports `--model NAME`.
For frontend development, run the backend on port 8741 and
`npm --prefix studio/web run dev`; Vite proxies `/api` to that backend.

## Troubleshooting

- **No canvas:** check `frontend_available`, rebuild the frontend, then restart
  the MCP host so its static mount is refreshed.
- **Port occupied:** close the duplicate instance or configure `--studio-port`.
  A standalone viewer is not the host's MCP session.
- **No Studio tools:** install `.[mcp,studio]`, confirm `--studio` in the host's
  actual arguments, and reload it.
- **Workspace rejected:** keep it within an explicit root; correct the path
  instead of adding an unrelated parent directory.
- **Old designs missing:** follow [migration](MIGRATION.md) to reopen the prior
  workspace without rewriting its evidence.

[Manual workflow](DESIGN_WORKFLOW.md) · [CLI/MCP](CLI_MCP.md) ·
[Historical prototype acceptance](STUDIO_ACCEPTANCE.md)
