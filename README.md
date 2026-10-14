# cadHarness

Source-backed CAD engineering workflows for build123d: inspect, validate,
snapshot, compare, preview, and explicitly export trusted Python projects.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"
.\.venv\Scripts\python.exe -m cadharness doctor .
.\.venv\Scripts\python.exe -m cadharness list examples
.\.venv\Scripts\python.exe -m cadharness validate examples/project-box --variant standard
.\.venv\Scripts\python.exe -m cadharness mcp-config .
```

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
- [ ] Rich assembly metadata exchange and external analysis adapters — current focus

See the [CLI and MCP guide](docs/CLI_MCP.md) for setup and usage, the
[architecture](docs/ARCHITECTURE.md) for contracts and limitations, and the
[changelog](CHANGELOG.md) for completed milestones.

Project factories execute local Python and are not sandboxed. Computational
checks are evidence, not physical or manufacturing validation.
