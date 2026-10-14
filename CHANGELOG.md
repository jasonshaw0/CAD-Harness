# Changelog

All notable cadHarness changes are recorded here. The project follows semantic
versioning while its public schemas remain experimental.

## Unreleased

- Simplified first-run setup around a browser report, with optional MCP setup
  and a copyable guide for wrapping an existing build123d model.
- Added readable `--summary` output for verification and inspector commands,
  preserving JSON defaults, gate policies, exit codes, and overwrite protection.
- Compile current project factories and local helpers from source so rapid edits
  cannot reuse stale timestamp-based bytecode and verify the previous geometry.

### Planned

- Richer assembly metadata exchange without duplicating build123d.

## 0.9.0 — 2026-10-14

- Added independent OCCT geometry measurements: analytic cylindrical features,
  simple hole patterns, solid clearance/interference, and sampled directional
  thickness, with explicit provenance, tolerances, diagnostics, and limitations.
- Added `geometry_measurement_check`, shared `measure_project` operations,
  `cadharness measure`, `measure_cad_project`, and the seventh public v1 schema.
- Reject nonfinite inputs, partial sample success, empty passing measurement
  lists, mixed axes, and ambiguous coaxial/split faces. Preserve measurement
  errors and enforce requirement units and measurement-spec drift.
- Added an illustrative NEMA 17 mount with missing-hole, shifted-hole,
  wrong-diameter, and tight-clearance regression variants.
- Require build123d 0.13.x and test the published minimum in CI; fresh 0.10
  dependency resolution can mix incompatible OCCT bindings.

- Fixed verification gate exceptions being overridden by validation-result
  additions/removals, and made check-error outcomes and CLI exit codes consistent.
- Included built-in geometry criteria in requirement drift and rejected check-ID
  collisions, malformed evaluator results, and nonboolean gate settings.
- Recursively validate saved evidence and corrected invalid schema fixtures.
- Avoid labeling validation-only inspector reports as verified; show warnings
  and skipped checks in review colors, and preserve artifacts on exporter failure.

## 0.8.0 — 2026-10-14

- Added first-class verification through Python, `cadharness verify`, and
  `verify_cad_project`, with deterministic 0/1/2 CLI outcomes.
- Kept revision comparison distinct from current validation and verification;
  accepted changes cannot hide failed or erroneous checks.
- Added stable requirement definitions, normative requirement-drift detection,
  evidence provenance, configurable gates, and toolchain snapshot metadata.
- Strengthened nested contract validation, atomic JSON/HTML writes, verified
  exporter output, schema fixtures, and regression coverage.

## 0.7.0 — 2026-10-14

- Added `cadharness doctor` with active-checkout, interpreter, MCP dependency,
  console-script, and project-discovery diagnostics.
- Added `cadharness mcp-config` to generate client JSON with an absolute Python
  interpreter and explicit trusted project roots.
- Added `--root`, `--help`, and `--version` handling to the stdio MCP server,
  plus a `get_cadharness_status` discovery and diagnostics tool.
- Made compact JSON positioning flexible and moved generated inspector and
  preview defaults beneath the ignored `.cadharness` workspace.
- Added a checkout-to-client CLI and MCP guide and a host-independent real
  stdio smoke test.

## 0.6.0 — 2026-10-14

- Added a self-contained, read-only HTML inspector linking preview, component,
  parameter, and validation evidence.
- Added passing/review filters and component anchors without external web
  dependencies.
- Added bounded inspector generation through Python operations, CLI, and MCP.
- Added a deterministic project-box inspector bundle with two SVG views.
- Verified the inspector in a real browser at desktop and mobile widths using
  stateful Playwriter checks; linked SVGs, filters, anchors, and logs passed.

## 0.5.0 — 2026-10-14

- Added inclusive one- and two-sided numeric range checks.
- Added semantic clearance, wall-thickness, and hole-diameter checks with
  structured measurement evidence.
- Added signed tolerance contributions and deterministic worst-case arithmetic
  stack checks with contributor-level evidence.
- Updated the enclosure and flange examples to use semantic dimensional checks
  and refreshed the deterministic enclosure baseline.

## 0.4.0 — 2026-10-14

- Added stable schema identities to inspection and validation reports.
- Centralized the v1 contracts for inspection, validation, snapshot, diff, and
  comparison-policy documents.
- Added checked-in compatibility fixtures and tests that compare runtime output
  with their stable top-level contracts.
- Added schema discovery through `cadharness schemas` and the
  `list_cad_schemas` MCP tool.
- Reused central compatibility validation when loading snapshots and policies.

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
