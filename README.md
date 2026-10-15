# cadHarness

cadHarness is an experimental Python tool for source-driven parametric CAD and
geometry verification using build123d and OCCT. It provides a project contract,
geometry measurements, requirement checks, revision comparison, and STEP/STL
export through Python, a CLI, and MCP.

Studio is an optional local interface for inspecting geometry, checks, source,
and revisions during assistant-driven design. The framework runs independently
of Studio or an assistant. In MCP mode, cadHarness uses the assistant in the host
IDE or CLI and makes no separate model calls.

## Project model

A `cadharness.toml` manifest points to a trusted Python factory that returns a
`CADDocument`. The document contains components with stable IDs and explicit
checks evaluated against the built geometry. Python source remains the design
authority; reports record measured values and verification results.

Studio uses the same contract, retaining candidate source, requirement briefs,
and build evidence for each attempt. Measurements and failed checks return to
the assistant for inspection and revision.

## Installation

Requires Python 3.11–3.14. Studio setup also requires Node.js 22.12+ and npm.
From Windows PowerShell:

```powershell
git clone https://github.com/jasonshaw0/cadHarness.git
cd cadHarness
python bootstrap.py
```

Setup creates or reuses `.venv`, installs dependencies, builds Studio, verifies
an example, and writes `.cadharness/mcp.json`. For framework-only installation,
use `python bootstrap.py --framework-only`; Node.js is not required.
On macOS/Linux, use `python3` for setup and `./.venv/bin/python` below.

## Command-line usage

```powershell
.\.venv\Scripts\python.exe -m cadharness verify examples/nema17-mount --summary
.\.venv\Scripts\python.exe -m cadharness inspector examples/nema17-mount --summary
```

`verify` evaluates the project's checks. Add `--variant missing-hole` to the
example command to exercise a failed check. Exit codes are 0 for a pass, 1 for
a failed gate, and 2 for usage or execution errors. Commands return JSON by
default; `--summary` selects human-readable output.

`inspector` writes an HTML report and prints its path. See
[project authoring](docs/GETTING_STARTED.md) for the manifest and factory format.

## MCP and Studio

After full setup, add the generated `cadharness` entry from
`.cadharness/mcp.json` to your MCP host's configuration and reload the host.
The host starts the CAD tools and Studio together. Call `studio_status` to
retrieve the viewer URL, normally `http://127.0.0.1:8741`.

See [Studio setup](docs/STUDIO.md) for workspace configuration and controls, or
[CLI and MCP](docs/CLI_MCP.md) for framework-only MCP configuration.

## Status and execution model

cadHarness is experimental; interfaces and workflows may change. Project
factories execute trusted local Python without sandboxing. Keep MCP roots
explicit and limited to trusted projects. Passing checks provides computational
evidence for the encoded requirements; physical fit and manufacturing
performance require separate validation.

## Documentation

- [Documentation map](docs/README.md) — setup, authoring, measurements, and operations.
- [Architecture](docs/ARCHITECTURE.md) — how Studio, orchestration, and the framework fit together.
- [Contributing](CONTRIBUTING.md) — repository layout, tests, frontend builds, and packaging.
- [Design workflow](docs/DESIGN_WORKFLOW.md) — manual source review and design iteration.
- [Migration guide](docs/MIGRATION.md) — previous `designworkflow` paths and saved workspaces.
- [Changelog](CHANGELOG.md).
