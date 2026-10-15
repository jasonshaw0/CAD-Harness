# Workflow records and acceptance bindings

Workflow JSON records carry `schema` and `schema_version: "1"`. These are
independent of CADHarness's seven existing v1 contracts, which are validated with
`require_schema`. The workflow is currently a checkout tool, not an installed
`cadharness` subcommand or MCP tool.

## Brief

`brief-vNNN.json` contains:

| Field | Contract |
| --- | --- |
| `id`, `revision` | Lowercase design ID matching the run directory; positive integer matching the filename. |
| `domain` | `mounting-plate` or bounded `simple-enclosure`. The flange fixture uses the mounting-plate measurement family. |
| `coordinate_frame` | Explicit description; mounting plate fixtures are centered XY, lower face Z=0. |
| `printable_components` | Explicit expected printable IDs; the worker rejects changed roles or substituted reference components. |
| `dimensions` | Named records with `value`, explicit original `unit`, `source`, and `prompt_ref`. |
| `questions`, `assumptions` | Objects with `description` and boolean `blocking`. Remove resolved questions and preserve answers in `clarifications.md`. |
| `physical_validation_gaps` | Descriptions of absent physical evidence. |
| `requirements` | Stable IDs, description, boolean `mandatory`, `prompt_ref`, `evidence_kind`, normalized `unit`, `criteria`, and `binding`. At least one mandatory requirement is required. |

Dimensions retain original units and add normalized records in saved evidence.
Supported input units are `mm`, `cm`, `m`, `in`, and `deg`. Units are never
guessed. Optional `normalized_value` must agree with conversion. The assistant
must resolve contradictory prompt statements and make check criteria match the
brief; this tool does not infer prose semantics or automatically substitute
dimension records into check criteria.

Dimension provenance is one of `user-statement`, `user-measurement`,
`referenced-specification`, `calculation`, `configurable-default`, or
`unverified-assumption`. `prompt_ref` can identify a clarification, measurement,
or external specification as well as a prompt line. No standard interface
certification is inferred from a hardware family name.

Requirement criteria use `expected` and optional `absolute_tolerance`, or
inclusive `minimum`/`maximum`. Check units are `mm`, `deg`, `mm^3`, or null for
counts. Numbers must be finite. Geometry acceptance defaults in the fixtures are
0.01 mm/degree; count checks are exact. These acceptance limits are separate from
CADHarness computational tolerances, preserved in measurement evidence.

Requirements use `geometry-derived`, `declared`, or `external` provenance.
Only supported geometry bindings are executed automatically. Declared/external
requirements need explicit additional evidence; this release leaves them
unresolved instead of treating a project-supplied number as a geometry proof.

## Bindings

Bindings construct CADHarness checks on the built `CADDocument`. Candidate
checks are retained but cannot use the reserved `workflow.` namespace.

| `type` | Fields and measurement |
| --- | --- |
| `bbox` | `component`, `axis: X/Y/Z`, optional `quantity: size/min/max/center`; OCCT bounding box. |
| `solid-count` | `component`; actual solids in the shape. |
| `printable-count` | Components with `role: printable-part`; contract metadata, not physical evidence. |
| `hole-pattern` | `component`, `selector`, `value_path`; CADHarness simple parallel-cylinder inventory and pattern metrics. |
| `cylinder` | `component`, `selector`, `value_path`; explicit feature dimensions, extent, and angular span. |
| `clearance` | Two `components`, `value_path`; CADHarness unsigned distance/state. Optional `z_slab_mm: [lower, upper]` clips the actual shapes to an explicit slab before measurement. |
| `interference` | Two `components`, maximum volume criterion, unit `mm^3`; existing CADHarness boolean-common check. |
| `thickness` | `component`, `points_mm`, `direction`, `value_path`; existing sampled material-chord measurement. |
| Other / `physical` / `external` | Explicitly unsupported or not-yet-verified. Mandatory unresolved requirements prevent readiness. |

Cylinder `selector` fields use `CylinderSelector` names: `radius_min_mm`,
`radius_max_mm`, `axis_direction`, `axis_location_mm`,
`axis_angular_tolerance_deg`, `location_tolerance_mm`, and `concavity`.
Selectors, samples, and tolerances are normative intent. Narrowing a selector to
hide an unwanted feature is not a repair.

For `angular_span_deg`, the adapter creates selected angular evidence with a
degree unit and retains the complete original cylinder report in diagnostics.
The core report has a report-wide millimeter unit despite containing angular
fields. No raw source measurement is discarded.

Hole counts alone do not prove a pattern. Fixtures check explicit locations,
diameters, full cylindrical span, and depth. Counterbores, partial faces, mixed
axes, and ambiguous selections must not silently pass. Slab clearance and
directional thickness are local evidence, never universal clearance or wall
thickness guarantees. Contact/overlap both have zero unsigned distance; use the
interference binding when contact is allowed but overlap is forbidden.

## Revisions and evidence

`revision.json` names a run-local brief and optional named variant. Each attempt
owns a `project/` and immutable `run.json`. `check --review-hashes` reads inputs
without importing candidate code. Both explicit review hashes are required to
execute. All candidate input files and revision settings contribute to source
identity; generated output/cache directories are excluded. Prompt and
clarification file hashes also contribute. Links are rejected. This is
provenance, not an execution security boundary.

The first accepted check locks that numbered brief. `revise` copies source to
the next attempt without outputs. Same-brief repairs cannot remove requirements
or modify normative criteria; snapshot comparisons show both geometry changes
and requirement drift. Intentional changes use a new numbered brief. Revision
comparison during initial design is informational and cannot waive current
checks. Approved engineering-baseline/sign-off workflows are deferred.

`run.json` records coverage, original check results, warnings/errors, blockers,
time, source/brief hashes, code/toolchain provenance, geometry fingerprints, and
artifact hashes. Frozen prompt/brief copies, CADHarness reports, and failure logs
live under `project/evidence/`. Read-only review HTML and Markdown live beside
`run.json`. A worker error or timeout leaves mandatory coverage unknown; an
unexecuted check remains not-yet-verified. A core skip/warning maps to unknown,
and the original status remains available. Warning-only optional evidence is
retained separately.

Exit codes: `check` returns 0 for ready-for-review, 1 for blocked/needs-revision,
and 2 for execution/usage errors. Hash inspection, initialization, revision
creation, and successful explicit export return 0. Inputs and evidence are
checked again before export; changed evaluator code or artifacts require a new
evaluation. Source geometry is fingerprinted before export because exporter
serialization/tessellation may change post-export BREP bytes.
