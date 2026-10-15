# Developing cadHarness

cadHarness is one product with a reusable framework, design orchestration, and
Studio. Keep CAD operations in the shared framework; Studio orchestrates and
presents their results.

## Repository layout

```text
src/cadharness/
  model.py, checks.py, measurements.py, operations.py, …  # framework
  cli.py, mcp_server.py                                 # shared entrypoints
  workflow/                                            # briefs, acceptance, attempts
    templates/, prompts/, CONTRACTS.md                  # installed authoring resources
    benchmarks/                                        # deterministic evaluation fixtures
  studio/                                              # API, MCP tools, jobs, scene/store
    web/                                               # generated canvas (ignored)
studio/web/                                            # editable React/Three.js frontend
tests/                                                 # framework and onboarding tests
  workflow/                                            # workflow, Studio API, real stdio tests
examples/                                              # framework project examples
docs/                                                  # guides and architecture
scripts/                                               # integration and Playwriter checks
runs/                                                  # local source and evidence (ignored)
designworkflow/                                         # legacy CLI shim / old saved runs
```

## Install and check

Use a checkout-local virtual environment. In Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mcp,studio]"
npm --prefix studio/web ci
npm --prefix studio/web run build
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/smoke_mcp.py
```

On macOS/Linux, substitute `python3` for environment creation and
`./.venv/bin/python` for the interpreter. One discovery command includes all
workflow and Studio tests. The real stdio integration exercises a failed
measurement, repair under a frozen brief, follow-up turn, and STL export.

Use `cadharness --help` for shared commands. Manual design commands live under
`cadharness design`; integrated Studio is launched by the MCP host with
`--studio`. See [Studio](docs/STUDIO.md) for frontend development and
[evaluation](docs/EVALUATION.md) for repeatable defect trials.

Use Playwriter exclusively for browser control and testing. Read its skill,
create a stateful task session, exercise interactions, inspect screenshots,
and check console errors. Unit tests and a build do not establish browser acceptance.

## Build a distributable package

Build the frontend **before** creating a wheel so its static assets are
included. Package discovery uses `src/`; templates, contracts, prompts, and
the generated canvas are explicit package data. Runtime needs no checkout
import-path injection.

```powershell
npm --prefix studio/web run build
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --wheel-dir dist
```

`python scripts/smoke_distribution.py` builds a wheel, installs it in a
temporary environment, verifies its canvas/assets, and runs the real Studio
stdio integration outside the checkout. CI runs this after building the frontend.

A wheel built without the frontend supports the framework and design runner;
Studio reports `frontend_available=False`. For a full Studio distribution,
build from a clean tree and include the canvas. Install the wheel with
`[mcp,studio]` extras in a separate environment, test outside the checkout, and
confirm the authoring resources and viewer are present.

Keep generated CAD runs and exports out of commits. Preserve user changes,
run relevant checks before committing, and use focused commits. The local
workflow requires completed commits pushed to `origin/main` and confirmed in sync.
