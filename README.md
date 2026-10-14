# cadHarness

Source-backed CAD engineering workflows for build123d: inspect, validate,
snapshot, compare, preview, and explicitly export trusted Python projects.

```powershell
python -m pip install -e ".[mcp]"
cadharness list examples
cadharness validate examples/project-box --variant standard
cadharness inspector examples/project-box --variant standard
cadharness snapshot examples/project-box --variant standard --output artifacts/baseline.json
cadharness compare examples/project-box --variant clearance-fit --baseline artifacts/baseline.json
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
- [x] CLI and MCP 2.3 interfaces
- [x] Versioned schema fixtures and compatibility checks
- [x] Reusable bounded-dimension, clearance, wall, hole, and tolerance-stack checks
- [x] Browser-verified, read-only linked project inspector
- [ ] Rich assembly metadata exchange and external analysis adapters — current focus

See [architecture](docs/ARCHITECTURE.md) for contracts and limitations, and
[changelog](CHANGELOG.md) for completed milestones.

Project factories execute local Python and are not sandboxed. Computational
checks are evidence, not physical or manufacturing validation.
