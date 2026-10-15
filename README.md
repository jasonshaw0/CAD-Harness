# cadHarness

**cadHarness** is a flexible Python framework for inspecting, validating, and comparing source-defined build123d projects.

It organizes a model into named components, parameters, and engineering checks, then builds the geometry and records the results. Each check includes acceptance criteria and evidence, distinguishing values declared in the source from measurements of the resulting shapes. Python, the command line, and an optional MCP interface expose the same underlying operations, thus making this a flexible tool for design verification and regression testing.

Use it to:

- Review a model, its measurements, and check results in an HTML report.
- Run pass/fail checks from Python or the command line.
- Compare revisions, export STEP or STL files, or connect an assistant through MCP.

## Quickstart 
[Or skip to docs](docs/)


You'll need Git and Python 3.11–3.14. Installation includes build123d 0.13.x.

Start by generating a report for an example stepper motor-mount.

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

The report shows geometry previews, measured values, and check results. The standard example should show **Verified**, with **3 components** and **10 checks**. MCP is optional; it is not needed to run commands or view reports.

To regenerate an existing report, add `--overwrite` to the inspector command.

## Run checks

Use `verify` when you need a pass/fail result, such as in a script or CI job:

```powershell
.\.venv\Scripts\python.exe -m cadharness verify examples/nema17-mount --summary
```

On macOS and Linux, replace `.\.venv\Scripts\python.exe` with `./.venv/bin/python`.

With the default verification policy:

- **0** — verification passed.
- **1** — verification failed.
- **2** — a check execution error, command execution error, or usage error occurred.

Generating a report can succeed even when verification fails. Use `verify` to gate an automated workflow.

To see a failure, add `--variant missing-hole` to the verification command. This variant builds three mounting holes while retaining the requirement for four.

## Use your own model

For a local 3D workbench driven by your IDE assistant through MCP, see [Studio setup](designworkflow/studio/README.md).
The [manual design workflow](designworkflow/README.md) also supports reviewed source and measured repairs.

A cadHarness project contains a `cadharness.toml` manifest pointing to a Python function that returns a `CADDocument`: your build123d shapes, named components, parameters, and checks.

Follow the [project guide](docs/GETTING_STARTED.md) to create a project or wrap an existing model.

## Documentation

| Topic | Reference |
| --- | --- |
| Create a project and add checks | [Project guide](docs/GETTING_STARTED.md) |
| Configure the MCP server | [MCP setup](docs/CLI_MCP.md#connect-an-mcp-client) |
| Measure holes, clearances, and sampled thickness | [Geometry measurements](docs/MEASUREMENTS.md) |
| Use commands and compare revisions | [CLI workflow](docs/CLI_MCP.md#cli-workflow) |
| Diagnose installation and project discovery | [Troubleshooting](docs/CLI_MCP.md#troubleshooting) |

Commands return JSON by default. Use `--summary` with `verify` or `inspector` for readable terminal output.

## Development

Install the MCP extra to run the full test suite and the stdio integration check. From the repository checkout:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/smoke_mcp.py
```

On macOS and Linux, use `./.venv/bin/python` instead.

Only run projects whose Python source you trust. Project loading executes that source without sandboxing. Passing checks does not establish physical fit or manufacturing suitability.

[Architecture](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md)
