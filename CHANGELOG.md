# Changelog

All notable cadHarness changes are recorded here. The project follows semantic
versioning while its public schemas remain experimental.

## Unreleased

- Add versioned schema fixtures and compatibility checks.
- Expand reusable geometric checks and their evidence model.

## 0.3.0 — 2026-10-14

- Added manifest-declared, dataclass-backed named variants with early field and
  type validation.
- Added comparison policies with numeric tolerances, reasoned accepted changes,
  and per-change `significant`, `tolerated`, or `accepted` dispositions.
- Made validation regressions non-waivable by comparison policy.
- Added per-surface and per-curve metric comparison instead of treating geometry
  summaries as opaque values.
- Propagated variants through the Python API, CLI, MCP tools, snapshots,
  previews, and exports.
- Added variant-qualified preview and export filenames to prevent collisions.
- Migrated the server and smoke client to MCP Python SDK 2.3.
- Added standard and clearance-fit enclosure variants plus standard and
  eight-hole flange variants.
- Added deterministic baseline, comparison, and SVG example artifacts.

## 0.2.0 — 2026-10-14

- Established cadHarness as an independent, general-purpose build123d workflow.
- Added project discovery, inspection, validation, snapshot, comparison,
  hidden-line SVG preview, and explicit STEP/STL export operations.
- Added deterministic BREP fingerprints, manifold evidence, topology counts,
  bounding metrics, and surface/curve summaries.
- Added matching Python, JSON CLI, and bounded stdio MCP interfaces.
- Added independent project-box and pipe-flange example projects.
- Removed the superseded product model, FEA pipeline, exports, documentation,
  adapters, and product-specific tests from the supported repository surface.
