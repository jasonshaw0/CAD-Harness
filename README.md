# cadHarness

**Build your CAD. Check the geometry. Review the evidence.**

cadHarness turns a build123d project into a reviewable CAD report: previews,
measured geometry, engineering checks, and clear verification results. Your
Python source stays authoritative. Use the same project from the terminal or
through an AI assistant connected over MCP.

## Try the example

You need **Git and Python 3.11–3.14**. Installation includes build123d 0.13.x.
The example is an illustrative motor mount with four mounting holes and a
clearance check.

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
You should see **Verified**, **3 components**, and **10 checks**. The report
includes two CAD views, measured values, requirements, and expandable evidence.
No MCP setup is needed for this workflow.

To regenerate an existing report, add `--overwrite` to the inspector command.

## See a real failure

The `missing-hole` variant builds three holes while the requirement still calls
for four. In PowerShell:

```powershell
.\.venv\Scripts\python.exe -m cadharness verify examples/nema17-mount --variant missing-hole --summary
```

On macOS/Linux, use `./.venv/bin/python` instead. Expect **Verification failed**,
with **Actual: 3** and **Expected: 4** for `mount.hole-count`, and exit code 1.
Other pattern checks also fail. This is an intentional regression example.

## Use it for your work

| You want to… | Start here |
| --- | --- |
| Add checks to your own build123d model | [Create your first project](docs/GETTING_STARTED.md) |
| Connect an AI assistant through MCP | [MCP setup](docs/CLI_MCP.md#connect-an-mcp-client) |
| Measure holes, clearance, or sampled thickness | [Geometry measurements](docs/MEASUREMENTS.md) |
| Save evidence and compare revisions | [CLI workflow](docs/CLI_MCP.md#cli-workflow) |
| Diagnose installation or discovery problems | [Troubleshooting](docs/CLI_MCP.md#troubleshooting) |

CLI output is JSON by default. `verify` and `inspector` also offer `--summary`
for terminal use. `verify` exits 0 when its gate passes, 1 when it fails, and 2
for rejected check errors or usage/runtime errors. Generating an inspector is a
report-building operation; use `verify` when a script needs a pass/fail gate.

Project factories execute trusted local Python. Verification describes
computational evidence; physical fit and manufacturing suitability still need
their own validation. Example dimensions are assumptions, not hardware certification.

[Architecture](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md)
