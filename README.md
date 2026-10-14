# cadHarness

Source-backed CAD engineering workflows for build123d: inspect, validate,
verify, compare, preview, and explicitly export trusted Python projects.

## Quickstart

Requires Git and Python 3.11–3.14. Clone the repository and install the MCP
extra into a project-local virtual environment.

### Windows PowerShell

```powershell
git clone https://github.com/jasonshaw0/cadHarness.git
cd cadHarness
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"
.\.venv\Scripts\python.exe -m cadharness doctor .
.\.venv\Scripts\python.exe -m cadharness list examples
.\.venv\Scripts\python.exe -m cadharness validate examples/project-box --variant standard
.\.venv\Scripts\python.exe -m cadharness verify examples/project-box --variant standard
.\.venv\Scripts\python.exe -m cadharness inspector examples/project-box --variant standard
.\.venv\Scripts\python.exe -m cadharness mcp-config .
```

### macOS and Linux

```bash
git clone https://github.com/jasonshaw0/cadHarness.git
cd cadHarness
python3 -m venv .venv
./.venv/bin/python -m pip install -e ".[mcp]"
./.venv/bin/python -m cadharness doctor .
./.venv/bin/python -m cadharness list examples
./.venv/bin/python -m cadharness validate examples/project-box --variant standard
./.venv/bin/python -m cadharness verify examples/project-box --variant standard
./.venv/bin/python -m cadharness inspector examples/project-box --variant standard
./.venv/bin/python -m cadharness mcp-config .
```

`doctor` confirms which checkout and interpreter are active. The inspector is
written to `examples/project-box/.cadharness/inspector/index.html`. To connect
an MCP host, copy the generated `cadharness` entry into its `mcpServers`
configuration and reload the host.

Projects declare a trusted Python factory, a parameter dataclass, and bounded
named variants in `cadharness.toml`. Commands return JSON; generated artifacts
stay inside the project root and refuse accidental overwrite.

## Progress

- [x] Native build123d project/component contract
- [x] Structured inspection and executable engineering checks
- [x] Deterministic snapshots and exact geometry fingerprints
- [x] Typed named variants
- [x] Tolerance-aware, reasoned revision policies
- [x] Headless hidden-line SVG previews
- [x] Diagnosable CLI and portable MCP 2.3 interfaces
- [x] Versioned schema fixtures and compatibility checks
- [x] Reusable bounded-dimension, clearance, wall, hole, and tolerance-stack checks
- [x] Browser-verified, read-only linked project inspector
- [x] Verification gates that cannot confuse an accepted diff with a valid design
- [x] Requirement-change tracking and declared/geometry/external provenance
- [ ] Independent geometric measurement engine for actual OCCT geometry
- [ ] Rich assembly metadata exchange and external analysis adapters

See the [CLI and MCP guide](docs/CLI_MCP.md) for setup and usage, the
[architecture](docs/ARCHITECTURE.md) for contracts and limitations, and the
[changelog](CHANGELOG.md) for completed milestones.

Project factories execute local Python and are not sandboxed. Computational
checks are evidence, not physical or manufacturing validation.
