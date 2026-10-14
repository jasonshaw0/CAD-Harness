# cadHarness architecture — typed variants and revision policy

## Product boundary

cadHarness is a general-purpose, source-backed engineering workflow for build123d projects. It is not a geometric kernel, an assembly replacement, a sketch editor, or an embedded autonomous agent.

The authoritative artifact remains ordinary Python that creates build123d/OCCT shapes. A project factory returns a `CADDocument`, which attaches stable identity and engineering meaning to those native shapes.

```text
trusted Python project source
          |
          v
  build123d / OCCT shapes
          |
          v
 CADDocument ---- parameters + provenance
          |       components + roles
          |       checks + evidence
          |
     +----+----------------+------------------+
     |                     |                  |
 inspection/validation  snapshot/diff     preview/export
     |                     |                  |
 Python API, JSON CLI, and bounded MCP tools share operations
```

Keeping native `Shape` instances avoids a second topology model and retains direct access to OCCT booleans, joints, measurements, traversal, and exchange. The framework owns project semantics and workflow evidence instead.

## Project contract

Each project has a `cadharness.toml` manifest. Its entrypoint is trusted Python and must return a `CADDocument` with:

- a stable project ID and explicit revision label;
- named `Component` records containing native build123d shapes;
- `Parameter` values with unit, source classification, and description;
- `Check` evaluators returning structured status, actual/expected values, units, and evidence;
- metadata for assumptions and physical-validation gaps.

Projects may also declare a dataclass `parameter_type`, a default named variant,
and additional variant tables. The loader validates field names and TOML value
types before constructing the dataclass and calling the project factory. Agents
can therefore select a bounded, source-reviewed configuration by name rather
than sending an arbitrary parameter dictionary.

The loader keeps project-local imports isolated between builds. MCP paths are restricted to `CADHARNESS_PROJECT_ROOTS`. That prevents accidental path drift, but executing a project still executes its Python code and is not sandboxing.

## Capabilities

### Inspection

Inspection reports OCCT validity, manifold state, mass properties, bounding boxes, topology counts, surface and curve type histograms, and a SHA-256 fingerprint of serialized BREP geometry. These are measured facts; feature intent is not inferred from topology.

### Validation

Validation first checks every component for nonempty, valid geometry and required solids. Project source then defines domain checks such as dimensions, clearance budgets, interference pairs, counts, or sampled states. Computational success is never labeled physical validation.

Reusable constructors cover inclusive numeric ranges, clearances, modeled wall
thicknesses, hole diameters with explicit deviations, and signed one-dimensional
tolerance stacks. Each result carries its actual value, explicit bounds, unit,
and measurement kind. Tolerance stacks report nominal and worst-case arithmetic
bounds plus every signed contributor; they do not infer statistical distributions
or manufacturing capability.

### Revision evidence

`snapshot` records deterministic project, parameter, component, geometry, and validation evidence. It intentionally omits timestamps so unchanged builds produce byte-stable JSON.

`compare` rebuilds current source and explains changes against a saved snapshot:

- parameters added, removed, or changed;
- components added, removed, or changed;
- exact BREP fingerprint changes;
- volume, area, bounding-box, topology, and geometry-type deltas;
- validation regressions and resolutions.

An optional project comparison policy adds numeric tolerances and explicit
accepted-change records. Every changed leaf remains in the report with one of
three dispositions: `significant`, `tolerated`, or `accepted`. Accepted records
must include a reason. A transition into `fail` or `error` is always a
regression, even when a policy pattern attempts to accept it.

Exact fingerprints detect a change; geometric deltas and policy decisions help
explain and review it. Policy acceptance is recorded engineering intent, not a
claim of geometric identity or physical suitability.

### Visualization and exchange

`preview` generates headless hidden-line SVG views (`iso`, `top`, `front`, and `right`) for review artifacts and future interfaces. It is intentionally not a modeling UI. `export` writes STEP or STL only when explicitly requested. Both operations confine outputs to the project root and refuse overwrite by default.

## Interfaces

The CLI and MCP server call the same operation layer:

- `list`: discover manifests;
- `inspect`: build and report project evidence;
- `validate`: execute geometry and project checks;
- `snapshot`: persist deterministic revision evidence;
- `compare`: explain current-versus-baseline changes;
- `preview`: produce SVG review views;
- `export`: explicitly write STEP or STL geometry.

The Python API exposes the same model and snapshot primitives for tests and custom integrations.

### Public JSON schemas

Inspection, validation, snapshot, diff, and comparison-policy documents carry a
stable `schema` identity and `schema_version`. `cadharness schemas` and the
`list_cad_schemas` MCP tool publish the supported versions and top-level keys.
The v1 examples in `tests/fixtures/schema-v1` are compatibility fixtures: tests
validate every fixture and require runtime documents to retain the same root
contract. Additive operation metadata is listed separately as optional.

Schema versions protect document structure, not geometric-kernel behavior.
Exact BREP fingerprints can still vary if a project deliberately changes its
build123d/OCCT toolchain; revision evidence should record and review that change.

## Known limitations

- Variants are source-declared and bounded; ad-hoc typed overrides and composed variant inheritance are not yet supported.
- Policies classify measured evidence but do not prove geometric equivalence; an accepted fingerprint change still requires human engineering intent.
- Surface and curve summaries describe topology, not semantic features such as a recognized counterbore or fillet chain.
- Checks are synchronous Python callbacks. There is no dependency graph, incremental execution, or persisted history store.
- Dimensional checks consume values or project callbacks; topology-derived wall,
  section, and feature recognition remain the project's responsibility.
- Tolerance stacks are worst-case one-dimensional arithmetic over declared
  deviations, not RSS/statistical analysis or measured process capability.
- SVG previews provide deterministic review evidence but no picking, annotations, section planes, or interactive component linking.
- STEP/STL export does not yet preserve a rich assembly/product metadata model.
- No physical test, material certificate, solver result, or manufacturing measurement is implied by framework validation.

## Next priorities

1. Build a read-only inspector linking components, variants, policy decisions, previews, and failed checks.
2. Add topology-derived measurement helpers only where OCCT evidence can be made explicit and robust.
3. Add typed command-line overrides and variant inheritance only if real projects demonstrate a need beyond named configurations.
4. Add review/sign-off metadata without turning cadHarness into a full PLM system.
5. Evaluate XDE assembly export and external analysis adapters only when independent projects demonstrate the need.

Out of scope for the near term: a custom kernel, a general constraint solver, a full sketch-based editor, an in-process LLM, or remote execution of untrusted project source.
