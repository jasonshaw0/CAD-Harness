# cadHarness Studio

Your IDE assistant designs through MCP; Studio displays the actual CAD, builds
revisions, and measures requirements. Studio makes no separate model calls in
MCP mode. Python remains editable and OCCT/CADHarness remains authoritative.

## Start through your MCP host

Install the Python extras and build the canvas once (Node 22.12+):

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[mcp,studio]"
cd designworkflow/studio/web
npm ci
npm run build
cd ../../..
```

Register the server in Codex with this checkout's absolute interpreter and root:

```powershell
codex mcp add cadharness -- D:/Projects/cadharness/.venv/Scripts/python.exe -m cadharness.mcp_server --root D:/Projects/cadharness --studio
```

Adjust paths for another checkout. Other MCP hosts use the same command and
arguments in their stdio configuration. Reload/restart the host after adding
the server. The host starts both MCP and the canvas at **http://127.0.0.1:8741**;
do not start a separate Studio instance on that port. `studio_status` returns
the exact URL and whether the frontend is built. The original 12 CAD tools
remain available alongside 12 Studio tools.

Ask your IDE assistant to create a design. It can create/open a Studio design,
start a turn for your instruction, obtain source/requirements/selection context,
and submit complete Python/TOML files plus a structured brief. Studio builds
those files and returns measured results. The assistant repairs from those
results using the same turn and frozen brief, with at most two repair attempts.
A further user instruction starts a new turn and brief revision.

Selection flows back to `studio_get_context`. New revisions and assistant
messages appear automatically in the browser. Continue the conversation in the
IDE; the browser has no second model conversation or model login.

## Controls and artifacts

- Drag to orbit; right-drag to pan; scroll to zoom. Fit and standard views sit
  above the canvas. Click geometry or a component row to select it.
- Eye buttons hide/show parts; the selection card isolates a part. Reference
  envelopes appear ghosted. The revision strip opens earlier geometry.
- Overlay shows changed prior components in amber, not an exact solid difference.
  Checks expands actual/expected values, assumptions, and requirement changes.
- Rebuild copies current source into another revision without a model call.
  Failed builds and cancellation retain the labeled previous scene.
- Source downloads Python, manifest, and frozen brief as a ZIP. Report downloads
  evidence. Explicit STEP/STL exports contain printable components only and
  require current, passing CAD evidence; physical validation stays separate.

The MCP launch authorizes one trusted local execution session. Root restrictions,
source hashes, frozen requirements, worker timeouts, and cancellation still apply.
Generated Python is **not sandboxed** and is not labeled human-reviewed. CAD
workers receive no model credentials. Unknown measurements cannot produce a
ready verdict; physical fit and manufacturing performance need their own evidence.

Designs, turns, source, session records, checks, meshes, and exports stay under
ignored `designworkflow/runs/studio/`. Use `--studio-workspace PATH` (inside an
explicit trusted root) or `--studio-port PORT` on the MCP command to change them.
There is one active CAD job, a 120-second build timeout, and three candidates per
turn. Restart marks interrupted jobs and restores saved designs.

## Optional standalone mode

`python -m designworkflow studio` opens an MCP-oriented viewer without starting
an MCP transport. Prefer the MCP-host launch above for an integrated session.
The earlier separate Codex CLI designer remains opt-in:

```powershell
.\.venv\Scripts\python.exe -m designworkflow studio --designer codex
```

Only that opt-in mode requires a signed-in `codex` and supports `--model NAME`.
Frontend development uses `npm run dev` with the backend on port 8741.
The manual reviewed-hash CLI remains available. See [acceptance evidence](ACCEPTANCE.md).
