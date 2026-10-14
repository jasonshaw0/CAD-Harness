# cadharness architecture — milestone 1

## Decision

cadharness is a source-backed engineering project layer for build123d, not a new
geometric kernel, a second assembly system, or an embedded autonomous agent.

The authoritative artifact remains ordinary Python that creates build123d
shapes. A project factory returns a `CADDocument`, which attaches stable
component identity, parameter provenance, engineering checks, and metadata to
those native shapes. The same document is consumed by the Python API, CLI, and
MCP server.

```text
trusted Python project source
          |
          v
 build123d / OCCT shapes  <---- existing geometry, joints, topology, exchange
          |
          v
 CADDocument ------------- parameters + provenance
          |                 components + roles
          |                 executable checks + evidence
          |
     +----+---------------------+
     |              |           |
 Python API      JSON CLI      MCP tools
     |              |           |
 tests/scripts   CI + agents   coding agents
```

The core package does not know about the rotary platform. Its geometry stays
in the existing modules and `rotary_project.py` is only an adapter. The
unrelated `examples/project-box` enclosure exercises the same contract.

## What the investigation found

### build123d and OCCT already own geometry

The local build123d checkout and current documentation show that build123d
already provides:

- native OCCT topology and booleans;
- `Compound` assembly trees with labels, children, relative locations, and
  global locations;
- rigid, revolute, linear, and cylindrical joints;
- validity, volume, area, center of mass, bounding boxes, distances, and
  topology traversal;
- STEP, STL, BREP, DXF, SVG, glTF, and 3MF data exchange.

Re-wrapping those concepts would create identity and synchronization bugs.
cadharness components therefore contain native `Shape` instances directly.

References: [build123d assemblies](https://build123d.readthedocs.io/en/latest/assemblies.html),
[joints](https://build123d.readthedocs.io/en/latest/joints.html), and
[import/export](https://build123d.readthedocs.io/en/latest/import_export.html).

### Existing adjacent tools change the product boundary

- [PartCAD](https://github.com/partcad/partcad) is already pursuing a broad
  package manager/digital-thread system across multiple CAD backends. cadharness
  should not begin with remote package resolution, a registry, or PLM scope.
- [build123d-mcp](https://github.com/pzfreo/build123d-mcp) is a capable
  persistent scratch-session toolbox with rendering, measurement, feature
  recognition, snapshots, and guarded execution. cadharness should interoperate
  with it rather than fork its session tools. cadharness's MCP surface is instead
  project-aware and source-backed: list, inspect, validate, and explicit export.
- [FreeCAD FEM](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/FEM_Workbench.md)
  already coordinates geometry, meshing, external solvers, and postprocessing.
  The existing FreeCAD/CalculiX pipeline remains a downstream analysis adapter;
  FEA is not embedded in the core package.
- OCCT's [XDE/XCAF](https://dev.opencascade.org/doc/overview/html/occt_user_guides__xde.html)
  can preserve richer assembly attributes in exchange files. It is a sensible
  later export backend, but not a reason to replace Python source with a custom
  persistent document format in this milestone.

## Project contract

Each project has a `cadharness.toml` manifest:

```toml
[project]
id = "project-box"
name = "Parametric Project Box"
entrypoint = "project.py:create_project"
```

The factory returns a `CADDocument` with:

- stable project and revision identifiers;
- named `Component` records containing native build123d shapes;
- `Parameter` records with value, unit, source classification, and description;
- `Check` evaluators returning structured `CheckResult` evidence;
- metadata for risks, assumptions, source files, and physical-validation gaps.

Project files are trusted executable Python. The MCP server does not accept an
arbitrary `execute` operation and restricts project paths to
`CADHARNESS_PROJECT_ROOTS`, but this is a containment boundary, not a sandbox.

## Validation philosophy

Validation has two layers:

1. The framework checks every component for nonempty, valid OCCT geometry and
   the expected presence of solids.
2. Project source defines domain checks: dimensions, clearance budgets,
   interference pairs, counts, sampled mechanism states, or other computed
   assertions.

Every result contains status, actual value, expected condition, units, and
evidence. A computational pass is not described as physical validation. The
rotary adapter explicitly carries its axle and fit-coupon checks as unresolved
physical work.

## Agent interface

The CLI and MCP server share the same operation functions, so their output
cannot drift:

- `list`: discover manifests;
- `inspect`: build a project and return parameters, component metadata, OCCT
  metrics, and available checks;
- `validate`: run geometry and project checks and return a versioned report;
- `export`: explicitly write STEP or STL inside the project root, refusing to
  overwrite unless requested.

The MCP server uses stdio by default. It is AI-native but model-independent;
ordinary Python and CLI users receive the same capabilities.

## Why there is no visual application yet

A useful visual application needs stable concepts to display. The milestone-1
JSON schema now supplies them: component tree, roles, parameters, check status,
evidence, and geometry metrics. The first UI should be a read-only project
inspector with selection linking between the assembly and failed checks. A
sketch editor, custom modeling language, cloud account system, and general
solver UI are deliberately deferred.

## Next priorities

1. Add schema-version fixtures and compatibility tests before external clients
   depend on the report format.
2. Add configuration/variant inputs to factories without allowing arbitrary
   untyped dictionaries.
3. Add cross-section, minimum-wall, hole/feature, and tolerance-stack checks by
   composing OCCT operations; reuse mature implementations where available.
4. Define analysis adapters so the current FreeCAD pipeline can publish the
   same structured evidence model without making FreeCAD a core dependency.
5. Integrate a headless preview artifact and then build the read-only visual
   inspector.
6. Evaluate XDE assembly export and a PartCAD bridge only when real projects
   demonstrate metadata or dependency-management needs.

Not in the next milestone: a custom kernel, a general constraint solver, a
full sketch-based editor, an in-process LLM, or unsandboxed remote execution.

