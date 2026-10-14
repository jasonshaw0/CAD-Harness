# cadHarness

cadHarness is a Python framework and CLI for inspecting, validating, and
comparing build123d CAD projects defined in Python source. A project factory
returns a `CADDocument` containing native build123d shapes, stable component IDs,
parameters, and executable engineering checks. Shared operations expose
geometry measurements, verification gates, revision snapshots and diffs,
SVG previews, HTML inspection reports, and explicit CAD exports through the
Python API, JSON CLI, and optional MCP server.

Verification evaluates the current geometry and project checks independently
of revision comparison. An unchanged model can still fail verification.
Check results record status, actual and expected values, units, and evidence
provenance. Geometry measurements operate on OCCT shapes; the framework does
not infer design intent or replace build123d's geometry model.

## Quickstart

Requires Git and Python 3.11–3.14. Installation includes build123d 0.13.x.
The example below generates an inspection report for a motor mount with
four mounting holes and a clearance check.

### Windows PowerShell

```powershell
git clone https://github.com/jasonshaw0/cadHarness.git
cd cadHarness
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m cadharness inspector examples/nema17-mount --summary
Invoke-Item .\examples\nema17-mount\.cadharness\inspector\index.html
```

### macOS and Linux

```bash
git clone https://github.com/jasonshaw0/cadHarness.git
cd cadHarness
python3 -m venv .venv
./.venv/bin/python -m pip install -e .
./.venv/bin/python -m cadharness inspector examples/nema17-mount --summary
```

Open `examples/nema17-mount/.cadharness/inspector/index.html` in your browser.
The default variant reports **Verified**, **3 components**, and **10 checks**.
The report includes two CAD views, measured values, requirements, and
expandable evidence.
No MCP setup is needed for this workflow.

To regenerate an existing report, add `--overwrite` to the inspector command.

## Verification failure example

The `missing-hole` variant builds three holes while the requirement still calls
for four. In PowerShell:

```powershell
.\.venv\Scripts\python.exe -m cadharness verify examples/nema17-mount --variant missing-hole --summary
```

On macOS/Linux, use `./.venv/bin/python` instead. Expect **Verification failed**,
with **Actual: 3** and **Expected: 4** for `mount.hole-count`, and exit code 1.
Other pattern checks also fail. This is an intentional regression example.

## Project contract

Each project directory contains a `cadharness.toml` manifest identifying a
trusted Python factory that returns `CADDocument`. Components retain native
build123d `Shape` objects. Checks define acceptance criteria and classify
evidence as declared, geometry-derived, or external. Manifests can also declare
typed parameters and named variants. The
[project guide](docs/GETTING_STARTED.md) contains a minimal executable example.

## Interfaces and documentation

| Topic | Reference |
| --- | --- |
| Project factories and checks | [Project guide](docs/GETTING_STARTED.md) |
| MCP server configuration | [MCP setup](docs/CLI_MCP.md#connect-an-mcp-client) |
| Hole, clearance, and sampled thickness measurements | [Geometry measurements](docs/MEASUREMENTS.md) |
| Snapshots and revision comparison | [CLI workflow](docs/CLI_MCP.md#cli-workflow) |
| Installation and project discovery | [Troubleshooting](docs/CLI_MCP.md#troubleshooting) |

CLI output is JSON by default. `verify` and `inspector` also offer `--summary`
for terminal use. `verify` exits 0 when its gate passes, 1 when it fails, and 2
for rejected check errors or usage/runtime errors. Generating an inspector is a
report-building operation; use `verify` when a script needs a pass/fail gate.

## Development

Install the MCP extra to run the complete integration checks. From the checkout:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/smoke_mcp.py
```

On macOS/Linux, use `./.venv/bin/python`. CI runs unit tests, CLI checks, and
the MCP smoke test on Windows and Linux with Python 3.11 and 3.12, plus a job
using the minimum supported build123d version.

Project factories execute trusted local Python and are not sandboxed.
Verification describes computational evidence; physical fit and manufacturing
suitability still need their own validation. Example dimensions are assumptions,
not hardware certification.

[Architecture](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md)
