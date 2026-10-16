# Changelog

All notable CAD-Harness changes are recorded here. The project follows semantic
versioning while its public schemas remain experimental.

## Unreleased

## 0.10.0b1 — beta candidate

- Adopt Apache-2.0, Copyright 2026 Jason Shaw, with matching SPDX package
  metadata and complete license/NOTICE files in wheel and source archives.
  Document the separate OCP/OCCT terms and native source/build provenance.
- Prepare GitHub beta downloads with release notes, dependency inventories,
  source/run provenance, checksums and CI artifact checks. Publication is a
  separate owner-controlled step; no PyPI upload is configured.

- Add `cad-harness demo`: evaluate a missing-hole plate and its repair against
  one frozen brief in a new workspace, then open the included Studio walkthrough.
  Preserve editable source/history, make STEP/STL export explicit, and verify
  packaged preparation plus real Playwriter desktop/mobile interaction without
  an assistant account. Keep existing workspaces and host settings unchanged.

- Add host-specific MCP setup previews for Codex and Claude Desktop, explicit
  additive `--apply`, preserved settings/backups, collision checks and optional
  real stdio/Studio preflight. Document each host's format and reload lifecycle;
  validate native Codex registration and tool discovery across reload/restart in
  an isolated profile without model calls.

- Extend Python/CLI/MCP CI to 3.13 and 3.14 on Windows, Linux and macOS.
  Add core-only and full-wheel install lifecycle acceptance with real retained
  Studio source, evidence and STL exports across a synthetic version upgrade,
  reinstall, uninstall and reinstall. Document updates and removal.
- Include editable frontend source/build inputs and validation resources in
  source distributions. Generate and package Vite's bundled dependency license
  notices, completed by this beta's project-license/native-dependency review.

- Validate full Studio distributions by building an sdist and its wheel,
  checking bundled source/resources and version metadata, and testing fresh
  dependency installation outside the checkout. Extend bootstrap/distribution
  CI to Windows and retain validated artifacts with hashes. Add a phased
  release-readiness audit and roadmap; no package or release is published.

- Start a browser download when STEP or STL is chosen in Studio. Single parts
  download directly; multipart designs arrive in one ZIP containing the exact
  exported files. Retain individual links, report failed transfers, and preserve
  the download action when MCP polling reattaches to a fast export job.

- Keep Windows instructions primary and add short Linux/macOS equivalents to
  setup, CLI/MCP, Studio, testing, migration, and model verification guides.
  Extend Python/CLI/MCP and Studio installation CI coverage to macOS.

- Export the exact freshly verified shapes, without rebuilding the factory a
  second time. Replay boolean measurement checks before comparing BREP identity,
  preserving strict stale-evidence and geometry checks for STEP/STL delivery.

- Show asynchronous Studio job failures, including actionable stale-evidence
  export errors with a rebuild button. Reopen the download list after successful
  STEP/STL generation and keep error actions readable on narrow screens.

- Rename the product and Python distribution to CAD-Harness across Studio,
  MCP identity, CLI help, and documentation. Add `cad-harness` and
  `cad-harness-mcp` entrypoints while preserving Python imports, legacy commands,
  manifests, configuration keys, and evidence protocols. Refresh the README
  with a real Studio capture and local Python/build123d SVG badges.

- Package versioned authoring guidance through MCP initialization, tool
  descriptions and `get_cad_authoring_guide`, including adaptive visual review.
  Add `studio_render_view` for revision-specific PNGs through an open Studio tab,
  independently of the user's viewport. Authenticated single-tab claims,
  fingerprinted artifacts and bounded unavailable results preserve build
  evidence. No automatic images or visual-review gate. Changed source can refine
  passing MCP candidates within the existing frozen-brief attempt budget.

- Share one Studio canvas and job queue across MCP connections with matching
  workspaces and trust roots. Additional clients no longer lose all tools when
  the first MCP connection already owns the viewer port. Session-token and
  same-origin protection also apply to forwarded Studio calls.

- Rebuilt Studio around floating Explorer/detail panels and a compact viewport
  dock, following the v2 design reference. Added measured component properties,
  source previews, command search, persisted light/dark/system display settings,
  and responsive layouts while retaining MCP authoring, revision checks,
  comparison, cancellation, optional Codex composition, and explicit exports.

- Added `python bootstrap.py` to create/reuse the environment, install Studio,
  build its canvas, verify the example, and generate a local MCP configuration.
  Includes prerequisite checks, framework-only setup, and explicit root/workspace
  options without editing host settings or saved designs.

- Retry brief Windows access denials when reading atomically replaced Studio
  records, preventing intermittent MCP job-poll failures. Permanent denials and
  malformed JSON still surface as errors.
- Allow the next Studio operation to wait for a terminal worker's brief cleanup
  instead of rejecting a repair/export after polling has reported completion.

- Unified the framework and Studio as one installable `cadharness` package.
  Added `cadharness studio`, `cadharness design`, and Studio-aware `mcp-config`.
  Moved editable frontend source to `studio/web`, tests under `tests/`, and
  operational guides into `docs/`. Built wheels include templates/contracts
  and, after the frontend build, the canvas. Existing evidence schema IDs and
  saved workspaces are preserved; see `docs/MIGRATION.md`.

- Studio now defaults to IDE authoring through MCP: 12 new tools for source
  submission, frozen-brief repairs, context/selection, revision display, jobs,
  and exports. `cadharness-mcp --studio` serves the canvas beside the stdio
  transport. Separate Codex CLI generation is opt-in with `--designer codex`.

- Added CAD-Harness Studio: a loopback 3D workbench with installed Codex CLI
  generation, conversational revisions, bounded repairs, independent checks,
  component meshes, comparison overlays, cancellable workers, and explicit exports.
  Trusted-session authorization is separate from manual human source review.
- Preserve source BREP identities during interference and clearance checks by
  running OCCT booleans on copies, including touching enclosure/lid faces.

- Added a checkout-local, IDE-assisted `designworkflow` CLI with reviewed source
  execution, independent acceptance checks, revision evidence, explicit exports,
  mounting-plate/flange/enclosure fixtures, and scripted repair benchmarks.
- Export results retain pre-export `source_geometry` evidence alongside existing
  post-export metrics, preserving source identity when exporters update OCCT state.
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

- Established CAD-Harness as an independent, general-purpose build123d workflow.
- Added project discovery, inspection, validation, snapshot, comparison,
  hidden-line SVG preview, and explicit STEP/STL export operations.
- Added deterministic BREP fingerprints, manifold evidence, topology counts,
  bounding metrics, and surface/curve summaries.
- Added matching Python, JSON CLI, and bounded stdio MCP interfaces.
- Added independent project-box and pipe-flange example projects.
- Removed the superseded product model, FEA pipeline, exports, documentation,
  adapters, and product-specific tests from the supported repository surface.
