# Geometry measurement guide

CAD-Harness 0.9 requires build123d 0.13.x. Measurement helpers inspect the built
OCCT geometry independently of declared parameter values. They do not certify
physical fit, materials, manufacturing capability, or hardware compatibility.

## Supported measurements

| Type | Components | Evidence and limits |
| --- | --- | --- |
| `cylindrical-feature` | One | Analytic face radius, world axis, axial parameter envelope, and surface area. Exactly one selected face is required. |
| `hole-pattern` | One | Simple full concave cylinders on parallel axes: count, diameters, projected centers, centroid, and regular-pattern residuals. |
| `shape-clearance` | Two distinct components | Unsigned minimum distance, closest points, common volume, and separated/contact/interference state. Requires solids. |
| `directional-thickness` | One | Material chord lengths through every specified interior point along one direction. Requires solids. |

Cylinder selectors constrain component, radius bounds, axis direction, axis
location, and concavity. Axis locations identify an infinite line: displacement
along the axis does not select a different line. `axis_angular_tolerance_deg`
and `location_tolerance_mm` describe selection tolerances. Computational
tolerances describe classification and kernel operations; engineering acceptance
limits belong to checks and are independent of both.

Feature IDs hash rounded geometric signatures, including axial location. They
are repeatable diagnostic identities for unchanged geometry within a toolchain,
not permanent topology references across arbitrary redesigns. Reported quantities
retain OCCT precision. Face indices are diagnostic only.

`hole-pattern` rejects selected partial cylinders and irregularly trimmed faces
as unsupported. Multiple selected faces on one axis, including a counterbore,
remain ambiguous: narrow the radius selector to the intended bore. Mixed axes
also remain ambiguous. Counts refer to supported selected cylinders and do not
infer through-holes, thread forms, or design intent. Pattern circle metrics are
unavailable (`null`) with fewer than three centers. For larger inventories,
success reports the centroid-based estimate; check radial/angular residuals and
centroid position to establish the intended regular pattern.

Directional thickness uses OCCT solid classification and an edge/solid common
operation. Every point must lie strictly inside one solid and resolve to one
material chord. Missing, boundary, or ambiguous samples prevent success, even
when other samples resolve. Diagnostics retain the resolved and discarded
samples. This measures the requested directional chords, not global minimum
wall thickness, structural strength, or manufacturing suitability.

Clearance is unsigned: contact and overlap both have zero distance. Check the
state or common volume as well as distance when interference matters. The
volume tolerance distinguishes interference from contact; it is not penetration
depth or a manufacturing tolerance.

## Status and verification behavior

| Measurement status | CLI exit | Geometry check result |
| --- | --- | --- |
| `success` | 0 | Compare the selected value against acceptance criteria |
| `no-match` | 1 | Fail |
| `ambiguous`, `unsupported` | 1 | Skip; default verification rejects skips |
| `invalid-input`, `kernel-error` | 2 | Error; default verification rejects errors |

Usage errors also exit 2. Measurement success alone does not imply engineering
verification. Empty lists and unavailable values produce skipped checks; missing
value paths, unit mismatches, malformed evidence, and nonfinite measurements
produce errors. Underlying status, diagnostics, and evidence remain visible.

## CLI examples

Run from the checkout. Commands emit `cadharness.measurement` v1 JSON and write
no artifacts.

Or on Linux/macOS, use `./.venv/bin/python` in place of `python` in these
commands, or activate the environment first with `source .venv/bin/activate`
in Bash/Zsh. All measurement flags and project paths stay the same.

```powershell
python -m cadharness measure examples/nema17-mount --type hole-pattern --component mounting-plate --radius-min 1 --radius-max 3 --axis-direction 0 0 1
python -m cadharness measure examples/nema17-mount --type cylindrical-feature --component mounting-plate --axis-location 15.5 15.5 0
python -m cadharness measure examples/nema17-mount --type shape-clearance --component motor-envelope --component cable-keepout
python -m cadharness measure examples/nema17-mount --type directional-thickness --component mounting-plate --point 0 0 2 --direction 0 0 1
python -m cadharness verify examples/nema17-mount --variant standard
python -m cadharness verify examples/nema17-mount --variant missing-hole
```

The standard mount verifies. `missing-hole`, `shifted-hole`, `wrong-diameter`,
and `tight-clearance` deliberately fail checks against geometry while retaining
declared interface intent. The 31 mm square pattern and motor envelope are
explicit example assumptions; compare them with the selected hardware before use.

Repeat `--point X Y Z` for each thickness sample. `--direction` is required.
Optional `--linear-tolerance`, `--angular-tolerance`, and `--volume-tolerance`
configure computational tolerances; all must be finite and nonnegative.
`--axis-angular-tolerance` and `--location-tolerance` configure the cylinder
selector separately. Options for unrelated measurement types are rejected.

## Python checks and MCP

```python
from cadharness import (
    ComputationalTolerance, CylinderSelector,
    geometry_measurement_check, measure_hole_pattern,
)

selector = CylinderSelector(
    "mounting-plate", radius_min_mm=1, radius_max_mm=3,
    axis_direction=(0, 0, 1),
)
tolerance = ComputationalTolerance()
check = geometry_measurement_check(
    "mount.hole-count", "four modeled mounting holes",
    lambda document: measure_hole_pattern(
        document, "mounting-plate.holes", selector, tolerance=tolerance,
    ),
    value_path="count", expected=4, components=("mounting-plate",),
    method="analytic-concave-cylinder-inventory",
    measurement_spec={
        "selector": selector.to_dict(), "tolerance": tolerance.to_dict(),
    },
)
```

Add the check to `CADDocument.checks`. A dot-separated `value_path` selects a
dictionary value; an empty path selects the whole result value. Numeric lists
apply the same scalar bounds or expectation to every element. Exact string or
boolean expectations support facts such as clearance state. Unit conversion is
not implicit. Mixed-quantity reports such as hole patterns use no report-wide
unit; checks declare the unit of their selected quantity.

Include selection and tolerance settings in `measurement_spec` to make changes
to that intent normative requirement drift. Callback source remains trusted
Python; the framework does not infer arbitrary callback semantics.

`cadharness.operations.measure_project` builds a project and returns the same
report as the CLI. `measure_cad_project` exposes that operation through MCP with
`measurement_type`, `component_ids`, optional selector fields, sample points,
direction, and a `tolerance` object (`linear_mm`, `angular_deg`, `volume_mm3`).
It preserves configured MCP trust roots and accepts named variants, without
arbitrary parameter overrides or new file writes.
