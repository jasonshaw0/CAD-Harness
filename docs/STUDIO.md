# CAD-Harness Studio

Studio is the included application for the CAD-Harness framework. Your IDE
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

Multiple MCP connections using the same port, workspace, and trusted roots share
the first connection's Studio canvas and job queue. Each connection still has
its own stdio transport and framework tools. Closing a secondary connection
leaves Studio running; closing the owning connection stops its viewer and jobs.
Reconnect MCP clients after restarting that owner. Different workspaces or trust
roots must use different ports; they are never attached implicitly.

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
5. Repair or refine in the same turn with its frozen brief, with at most two
   further candidates, including after a passing candidate or visual finding.
   A further user instruction starts a new turn and brief revision.

The browser updates as revisions and assistant messages arrive. Click a part
to give the assistant selection context; continue the conversation in your IDE.
Studio makes no separate model calls in MCP mode and needs no browser model
login. Unknown mandatory evidence cannot produce a ready verdict.

## Packaged guidance and visual inspection

MCP initialization includes essential workflow instructions. Call
`get_cad_authoring_guide` for the versioned guide, also included in
`studio_get_context(include_contract=True)`. It covers editable source, units,
dimensional contradictions, exact checks, frozen intent and adaptive visual
inspection. It ships with the package; no personal skill or external viewer is
needed. MCP session authorization is separate from the manual source-review
hash workflow.

Use `studio_render_view` when an image resolves uncertainty about shape or
placement. Exact checks may suffice for simple primitives or minor dimensional
edits. Rounded transitions, sweeps, hollow parts, complex cutouts, assemblies and
obscured interfaces often benefit from inspection. Start with one informative
view; add angles, isolated components or close-ups for specific questions, and
reinspect affected features after meaningful changes. Images supplement
measurements and do not establish accuracy or manufacturing suitability.

Example MCP arguments:

```json
{
  "design_id": "design-…",
  "revision_id": "r002",
  "view": "front",
  "component_ids": ["handle"],
  "focus_bounds_mm": [[40, -10, 14], [85, 10, 84]],
  "width": 1024,
  "height": 768
}
```

Only `design_id` is required. Defaults select the latest revision with built
geometry, all components, an isometric view, and a 1024 × 768 PNG. Supported
views are `iso`, `front` (looking along +Y), `right`, `left`, `top` and `bottom`;
image dimensions range from 256 to 2048 pixels. Component IDs must exist in that
revision. Focus bounds are model-space millimeter coordinates with positive
extents intersecting the selected bounds; they frame a close-up without cutting
the solid. Failed builds without geometry cannot be captured; request an older
revision explicitly if that is the scene you intend to inspect.

The result includes PNG image content directly, design/revision IDs, the retained
scene's SHA-256 fingerprint, selection, orthographic camera settings and artifact
metadata. PNGs and metadata live in `<design>/renders/`, separately from immutable
revision evidence. Capturing does not mark a design reviewed, change readiness,
consume build attempts or authorize exports. Use ordinary assistant messages for
useful observations. Text-only models may obtain images for others but must not
claim visual inspection.

An open Studio tab handles authenticated requests using a lazy private renderer
with its own scene, camera, lighting and neutral background. It loads the saved
revision independently, preserving the user's displayed model, camera, selection,
visibility and theme. No browser extension, desktop control, screen sharing or
specific user camera placement is required. Multiple tabs can register; one tab
claims each request. Normal builds generate no images.

`studio_status` and `studio_get_context` expose renderer availability. A recent
tab heartbeat indicates a connected renderer; WebGL is tested when capture is
requested. Closed Studio, WebGL failure or a 10-second capture deadline returns
`status: unavailable` with a reason and preserves the build. Background-tab
throttling can also cause a timeout. CAD-Harness does not retry or launch a browser.
Report a needed visual check honestly when unavailable; there is no screenshot
quota, review form or extra completion gate. A headless production renderer is
outside the current implementation.

## Controls and outputs

| Control | Behavior |
| --- | --- |
| Canvas | Drag to orbit, right-drag to pan, scroll to zoom; use Fit or a standard view. |
| Explorer | Search and collapse designs, components, source files, and revisions. The panel itself can collapse to leave more canvas space. |
| Properties | Select geometry or a component row to inspect measured size, bounds, volume, and fingerprint. Hide or isolate a part here. |
| Design review | Open the check summary or Inspect → Engineering checks. Expand requirements for measured/required values; filter those needing attention. |
| Revision history | Open the revision badge or Inspect → Revision history. View earlier geometry, return to current, or rebuild without a model call. |
| Compare | Compare actual geometry and requirement changes with the previous built revision. Overlay shows changed prior components in amber; it is not an exact solid difference. |
| Source files | Inspect the retained Python and manifest without modifying evidence. Download an individual file or the source/manifest/brief ZIP. |
| Agent activity | Read assistant messages and questions. In MCP mode, continue in your IDE; the optional Codex mode retains an in-app composer. |
| Export | Create STEP/STL from current passing printable components, or download source and reports. Completed exports appear in the same menu; references are excluded. |
| Settings | Switch light/dark/system theme, grid, axes, edge display, and ghost references. Preferences stay in this browser. |
| Session status | Inspect the local workspace and execution mode, and enable or lock trusted Python execution. |

The bottom dock holds Fit, standard views, inspection tools, Compare, and
distraction-free mode. `Ctrl/⌘ K` opens the command palette. Single-key shortcuts
include `E` for Explorer, `I` for properties, `R` for review, `H` for history,
`C` for comparison, `A` for activity, `F` for Fit, `G` for grid, and `D` for
distraction-free mode. Shortcuts leave text fields alone. On narrow screens,
Explorer and the detail panel share space while the dock stays available.

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
- **Port occupied / tools disappear:** an older MCP host or standalone viewer may
  own port 8741 without supporting shared MCP connections. Restart that owner
  after updating CAD-Harness, then reconnect the other MCP clients. For a separate
  workspace use `--studio-port`. A standalone viewer is not an MCP session.
- **Image capture rejected / repeated render HTTP 405:** the browser bundle and
  running Python owner are from different revisions. Restart the MCP connection
  that owns Studio, reconnect attached clients, then reload Studio. Saved designs
  and evidence stay in the workspace. MCP clients now check the owner's API and
  render capabilities before attaching; the browser only polls an advertised
  render protocol and stops on incompatible or expired-session responses.
  Updated attached MCP clients refresh a rotated session token after confirming
  the replacement owner's workspace, trust roots, and capture compatibility.
- **No Studio tools:** install `.[mcp,studio]`, confirm `--studio` in the host's
  actual arguments, and reload it.
- **Workspace rejected:** keep it within an explicit root; correct the path
  instead of adding an unrelated parent directory.
- **Old designs missing:** follow [migration](MIGRATION.md) to reopen the prior
  workspace without rewriting its evidence.

[Manual workflow](DESIGN_WORKFLOW.md) · [CLI/MCP](CLI_MCP.md) ·
[Historical prototype acceptance](STUDIO_ACCEPTANCE.md)
