# CAD-Harness architecture

## Product boundary

CAD-Harness combines a reusable framework for build123d projects with Studio,
an included MCP design workbench. The framework owns project semantics and
engineering evidence; design orchestration owns briefs and retained attempts;
Studio provides assistant tools and a live 3D interface. build123d/OCCT builds
and measures geometry. The IDE assistant interprets instructions and authors
source; MCP mode embeds no model client.

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

## One product, three layers

```text
IDE assistant <------- MCP -------> CAD-Harness Studio <----> browser canvas
   |                                | selection, jobs, revisions
   +--- Python/TOML + brief ---------+
                                    v
                         cadharness.workflow
                         frozen requirements, attempts,
                         source hashes, bounded repairs
                                    |
                                    v
                         CAD-Harness framework operations
                         CADDocument + build123d/OCCT
                         measurements, checks, reports, exports
```

`src/cadharness/` contains the framework and common CLI/MCP entrypoints.
`workflow/` contains orchestration, acceptance bindings, templates, and contracts;
`studio/` contains the application API, MCP tools, file store, scene generation,
and job lifecycle. Editable frontend source lives in `studio/web/` at the repo
root and builds into the Python package as static assets. Framework-only users
do not need Studio's server dependencies or frontend.

All layers use the same project manifest and `CADDocument`. Workflow acceptance
binds the brief to independently measured geometry; it does not replace the
framework's validator. Studio source downloads retain ordinary Python/TOML,
so projects can also be inspected through framework commands.

Each Studio instruction starts a turn with a brief revision and a three-candidate
budget. Repairs preserve the frozen brief; later user instructions create new
turns. Revisions retain their evidence and failed builds preserve the previously
displayed scene. A ready verdict requires passing CAD evidence and coverage of
mandatory requirements; unknown and external physical evidence stay explicit.

The MCP host can enable both interfaces with `--studio`. Its workspace defaults
inside the first explicit trust root, and another workspace must be contained
by a configured root. HTTP is loopback-only; starting MCP authorizes a trusted
local execution session, without claiming human source review or sandboxing.
The optional separate Codex CLI designer remains an explicit opt-in.

See [repository layout and packaging](../CONTRIBUTING.md),
[Studio operations](STUDIO.md), and [design contracts](../src/cadharness/workflow/CONTRACTS.md).

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

The loader keeps project-local imports isolated between builds and compiles
project factories and local Python helpers from current source. Timestamp-based
bytecode caches cannot hide same-size edits made within one clock tick. MCP paths are
restricted to explicit `--root` arguments, with `CADHARNESS_PROJECT_ROOTS` as a
compatibility fallback. Generated client configurations use absolute
interpreter and root paths, so the host working directory cannot change the
selected trust boundary. Path restriction prevents accidental drift, but
executing a project still executes its Python code and is not sandboxing.

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

### Geometry measurements

The measurement engine operates directly on built OCCT shapes. It supports
bounded analytic-cylinder selections, inventories of simple parallel cylindrical
holes with pattern residuals, solid-pair minimum distance and interference volume,
and material chords through explicit interior sample points. Reports separate
success, no match, ambiguity, unsupported geometry, invalid input, and kernel
failure. They carry selected components, features, methods, computational
tolerances, limitations, and diagnostics.

No empty or unresolved sample set can pass a geometry measurement check.
Counterbores, partial cylinders, and mixed axes require an explicit supported
selection rather than an inferred hole count. Directional thickness is sampled
evidence, not a global minimum wall measurement. Computational tolerances are
independent of manufacturing acceptance limits. The
[measurement guide](MEASUREMENTS.md) defines these boundaries and the shared
Python, CLI, and MCP interfaces.

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

### Verification integrity

`verify` evaluates whether the current design satisfies engineering requirements,
optionally combining that assessment with revision comparison against a baseline snapshot.

Crucially, CAD-Harness maintains a strict separation of concerns:
- **Geometry validity**: whether the solid can be constructed and is topologically sound.
- **Engineering validation**: whether the model satisfies declared functional checks and bounds.
- **Revision comparison**: an objective diff between two states (which may report "identical" even between two failing revisions).
- **Verification gate**: whether the current revision passes all engineering gates under the active policy.

An accepted geometric difference cannot override failed engineering validation, and an identical failing baseline remains a failed current design.

Checks declare stable `Requirement` definitions (type, criteria, units, origin) and `EvidenceSpec` provenance (distinguishing `declared`, `geometry-derived`, and `external` evidence). Revision comparisons track added, removed, and modified requirements, distinguishing normative acceptance-criteria changes from harmless description edits.

Built-in geometry acceptance criteria are compared from their saved validation
results, so relaxing `require_solid` is also a normative requirement change.
Project check IDs cannot shadow these built-in checks. Malformed callback
results become check execution errors rather than passing or crashing a report.

Requirement addition/removal gates operate independently of revision acceptance.
Explicit gate exceptions remain visible in the policy and validation evidence;
the verification outcome describes the gate decision under that policy.

Snapshots record toolchain metadata (cadharness, build123d, and OCCT versions, BREP fingerprint method, and computational tolerance) without timestamps, ensuring byte-stable reproducibility while explaining environment differences.

### Visualization and exchange

`preview` generates headless hidden-line SVG views (`iso`, `top`, `front`, and `right`) for review artifacts. `inspector` combines those views with component metrics, parameters, validation results, evidence, and cross-links in a portable HTML document. It is read-only and intentionally not a modeling UI.

The inspector has no external runtime dependencies. Its passing/review filter is
local JavaScript, linked SVG files sit beside the HTML artifact, and all project
text is escaped during rendering. Browser verification covers desktop and mobile
layouts, filters, component anchors, image loading, and console errors.

`export` writes STEP or STL only when explicitly requested. Preview, inspector,
and export operations confine outputs to the project root and refuse overwrite
by default.

## Interfaces

The CLI and MCP server call the same operation layer:

- `doctor`: report the active install and project discovery environment;
- `mcp-config`: generate a portable stdio client configuration;
- `list`: discover manifests;
- `inspect`: build and report project evidence;
- `inspector`: generate linked, read-only HTML and SVG evidence;
- `validate`: execute geometry and project checks;
- `measure`: measure explicitly selected OCCT geometry without writing files;
- `verify`: gate current geometry and requirements against policies and baselines;
- `snapshot`: persist deterministic revision evidence;
- `compare`: explain current-versus-baseline changes;
- `preview`: produce SVG review views;
- `export`: explicitly write STEP or STL geometry.

The MCP server also exposes `get_cadharness_status`, which reports its package
version, configured trust roots, and discovered projects before any
project-specific operation. CLI root arguments take precedence over the legacy
environment variable and the host working directory is only a final fallback.

The Python API exposes the same model and snapshot primitives for tests and custom integrations.

### Public JSON schemas

Inspection, measurement, validation, snapshot, diff, comparison-policy, and verification documents carry a
stable `schema` identity and `schema_version`. `cadharness schemas` and the
`list_cad_schemas` MCP tool publish the supported versions and top-level keys.
The v1 examples in `tests/fixtures/schema-v1` are compatibility fixtures: tests
validate every fixture and require runtime documents to retain the same root
contract. Validation checks nested evidence identities, unique check IDs, status
values, summary counts, and verdict consistency. Snapshot and verification
contracts recursively validate their embedded reports. New requirement and
toolchain fields remain optional when reading older v1 snapshots. Additive
operation metadata is listed separately as optional.

Schema versions protect document structure, not geometric-kernel behavior.
Exact BREP fingerprints can still vary if a project deliberately changes its
build123d/OCCT toolchain; revision evidence should record and review that change.

## Known limitations

- Variants are source-declared and bounded; ad-hoc typed overrides and composed variant inheritance are not yet supported.
- Policies classify measured evidence but do not prove geometric equivalence; an accepted fingerprint change still requires human engineering intent.
- Surface and curve summaries describe topology, not semantic features such as a recognized counterbore or fillet chain.
- Framework checks are synchronous Python callbacks, without a dependency graph
  or incremental execution. Studio retains file-backed design history; standalone
  framework operations do not maintain an application history store.
- Geometry measurements cover bounded analytic features and explicit material
  chords; global wall thickness and universal feature recognition remain outside
  their scope.
- Tolerance stacks are worst-case one-dimensional arithmetic over declared
  deviations, not RSS/statistical analysis or measured process capability.
- SVG previews provide deterministic review evidence but no geometric picking,
  annotations, or section planes. Inspector links are report-level anchors, not
  topology selection.
- STEP/STL export does not yet preserve a rich assembly/product metadata model.
- No physical test, material certificate, solver result, or manufacturing measurement is implied by framework validation.

## Next priorities

1. Define richer assembly metadata exchange without duplicating build123d or XDE.
2. Add topology-derived measurement helpers only where OCCT evidence can be made explicit and robust.
3. Add typed command-line overrides and variant inheritance only if real projects demonstrate a need beyond named configurations.
4. Add review/sign-off metadata without turning CAD-Harness into a full PLM system.
5. Evaluate XDE assembly export and external analysis adapters only when independent projects demonstrate the need.

Out of scope for the near term: a custom kernel, a general constraint solver, a full sketch-based editor, an in-process LLM, or remote execution of untrusted project source.
