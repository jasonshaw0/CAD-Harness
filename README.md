# cadHarness

**A Python CAD framework and a ready-to-use workbench for designing with your AI assistant.**

cadHarness keeps parametric Python source, built geometry, and engineering evidence
together. **Studio** puts that framework to work: your IDE assistant authors designs
through MCP, a local 3D canvas displays the result, and the framework measures it
against explicit requirements. Revisions retain their source, checks, and reports.

| | What you get |
| --- | --- |
| **Studio** | Live 3D viewing, component selection, assistant context, design revisions, measured feedback, and STEP/STL export. |
| **Framework** | A build123d project contract, geometry measurements, engineering checks, revision comparison, and portable HTML reports through Python, CLI, or MCP. |

Both use the same `CADDocument` and build123d/OCCT geometry. Studio uses the assistant
already in your IDE; MCP mode makes no separate model calls. Editable Python stays
the design authority.

## Start with Studio

Install Python 3.11–3.14 and Node.js 22.12+, then clone the repo and run one setup
command. In Windows PowerShell:

```powershell
git clone https://github.com/jasonshaw0/cadHarness.git
cd cadHarness
python bootstrap.py
```

Setup creates/reuses `.venv`, installs dependencies, builds Studio, checks an
example, and saves **`.cadharness/mcp.json`**. On macOS/Linux, use `python3 bootstrap.py`.
Rerun the same command after pulling updates.

Add the generated `cadharness` entry to your MCP host's configuration and reload
the host once. It starts the CAD tools and Studio together. Call `studio_status` for
the viewer URL, normally **http://127.0.0.1:8741**, then ask your assistant:

> Use cadHarness Studio to create a 60 × 60 × 4 mm plate with four 3.5 mm
> through-holes centered at X/Y = ±15.5 mm. Measure those requirements and
> show me the result before exporting.

Select a component in Studio and continue the conversation in your IDE. The
assistant receives that selection and the measured results for its next edit.

[Studio setup, other platforms, and controls](docs/STUDIO.md)

## Use the framework directly

The framework works without Studio, Node.js, or MCP. Run
`python bootstrap.py --framework-only`, then:

```powershell
.\.venv\Scripts\python.exe -m cadharness verify examples/nema17-mount --summary
.\.venv\Scripts\python.exe -m cadharness inspector examples/nema17-mount --summary
```

Open the report path printed by `inspector`. The standard example has three
components and ten checks. Add `--variant missing-hole` to `verify` to see a
measured failure. Commands return JSON by default; `verify` exits 0 for a pass,
1 for a failed gate, and 2 for usage or execution errors.

Wrap your own shapes in a `CADDocument` and point a `cadharness.toml` manifest at
the factory. [Create a project](docs/GETTING_STARTED.md), or use
[`cadharness design`](docs/DESIGN_WORKFLOW.md) for a manual source-review loop.

## Documentation and development

- [Documentation map](docs/README.md) — setup, authoring, measurements, and operations.
- [Architecture](docs/ARCHITECTURE.md) — how Studio, orchestration, and the framework fit together.
- [Contributing](CONTRIBUTING.md) — repository layout, tests, frontend builds, and packaging.
- [Migration guide](docs/MIGRATION.md) — previous `designworkflow` paths and saved workspaces.
- [Changelog](CHANGELOG.md).

cadHarness executes trusted local Python without sandboxing. Keep MCP roots
explicit. Passing CAD checks establishes computational evidence; physical fit
and manufacturing performance require their own validation.
