# cadHarness Studio

A local 3D workbench with an installed Codex CLI as its designer. Source stays
editable Python; OCCT geometry and CADHarness checks remain authoritative.

From this checkout, install Python's Studio extra and build the frontend. Node
22.12+ and a signed-in `codex` on PATH are required for the designer. Example
projects work without a model account.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[studio]"
cd designworkflow/studio/web
npm ci
npm run build
cd ../../..
.\.venv\Scripts\python.exe -m designworkflow studio
```

Open **http://127.0.0.1:8741**. Enable the trusted local session once, choose an
example or describe a part with dimensions, and send a follow-up to change it.
Use `--model NAME` to override the Codex CLI default; Studio never switches
providers. Authentication/usage failures appear in the conversation. Sign in
with `codex login` outside Studio if necessary.

- Drag to orbit; right-drag to pan; scroll to zoom. Fit and standard views are
  above the canvas. Click geometry or its component row to select it.
- Eye buttons hide/show parts; the selection card isolates a part. Reference
  envelopes appear ghosted. Selection accompanies the next design request.
- Rebuild copies the current source into another revision and repeats checks
  without a model call. Use it after an evaluator upgrade before exporting.
- The revision strip opens earlier geometry. Overlay shows changed prior
  components in amber; it does not calculate an exact solid difference.
- Checks expands measured actual/expected values, assumptions, and requirement
  changes. Unknown mandatory evidence prevents a ready verdict.
- Source downloads a ZIP of Python, manifest, and frozen brief. Report is the
  evidence record. STEP/STL buttons explicitly export printable components from
  the current evaluated source; download links appear when complete.
- Cancel stops the owned Codex/CAD process tree. A failed build retains the last
  good scene and labels its revision. Restart recovers saved designs, marks
  interrupted jobs, and requires fresh session authorization.

Runs, raw Codex JSONL transcripts, requests, proposals, usage when reported,
session authorization, source hashes, checks, meshes, and exports are local under
ignored `designworkflow/runs/studio/`. `--workspace PATH` selects another store;
`--port PORT` changes the loopback port. There is one active job. Each instruction
gets one candidate plus two repairs with frozen requirements; a new user turn
gets a fresh budget and brief revision. CAD workers have a 120-second timeout;
Codex calls have a 420-second timeout and turns a 15-minute iteration budget.

Trusted-session mode authorizes generated local Python **without isolation**;
it does not claim a human source review. Codex receives a read-only workspace,
while a separate local CAD worker executes proposed source without model
credentials. This is a local prototype, not a hostile-code execution service.
The manual reviewed-hash CLI remains available. Keep physical fit, strength,
manufacturing suitability, and unsupported measurements unverified until their
evidence exists. Sampled wall and clearance checks cover only recorded samples.

For frontend development, `npm run dev` proxies `/api` to Studio on port 8741.
CI uses stub proposals for deterministic tests; live model acceptance outcomes
are recorded separately in [ACCEPTANCE.md](ACCEPTANCE.md).
