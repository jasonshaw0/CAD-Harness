# cadHarness

cadHarness checks CAD models written in Python with build123d. It measures the
built geometry and tests it against requirements you define, such as hole counts
and clearances.

Use it to:

- Review a model and its check results in an HTML report.
- Run pass/fail checks from the command line or Python.
- Compare revisions, export CAD files, or connect an assistant through MCP.

## Quickstart

Requires Git and Python 3.11–3.14. Installation includes build123d.
Start by generating a report for the included motor-mount example:

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
The report shows the model, measured values, and check results. The example
should show **Verified**, with **3 components** and **10 checks**.
You do not need MCP to use the command line or view reports.

To regenerate an existing report, add `--overwrite` to the inspector command.

## Run checks

Use `verify` when you need a pass/fail result, for example in a script or CI job:

```powershell
.\.venv\Scripts\python.exe -m cadharness verify examples/nema17-mount --summary
```

On macOS/Linux, use `./.venv/bin/python` instead. By default, exit code 0 means
verification passed; 1 means it failed; 2 means a check or command encountered an
error. Generating a report does not require the model to pass verification.

To see a failed check, add `--variant missing-hole`. That example has three
mounting holes where four are required.

## Use your own model

A cadHarness project has a `cadharness.toml` file pointing to a Python function
that returns a `CADDocument`: your build123d shapes plus their checks.
Follow the [project guide](docs/GETTING_STARTED.md) to create one or wrap an
existing model.

## Documentation

| Topic | Reference |
| --- | --- |
| Create a project and add checks | [Project guide](docs/GETTING_STARTED.md) |
| MCP server configuration | [MCP setup](docs/CLI_MCP.md#connect-an-mcp-client) |
| Measure holes, clearances, and thickness | [Geometry measurements](docs/MEASUREMENTS.md) |
| Commands and revision comparison | [CLI workflow](docs/CLI_MCP.md#cli-workflow) |
| Installation and project discovery | [Troubleshooting](docs/CLI_MCP.md#troubleshooting) |

Commands return JSON by default. Use `--summary` with `verify` or `inspector`
for readable terminal output.

## Development

Install the MCP extra to run the complete integration checks. From the checkout:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/smoke_mcp.py
```

On macOS/Linux, use `./.venv/bin/python`.

Only run projects whose Python source you trust; project code is not sandboxed.
Passing checks does not replace physical fit or manufacturing validation.

[Architecture](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md)
