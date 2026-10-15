# Author a CAD-Harness project

CAD-Harness wraps ordinary build123d shapes with stable component IDs and
engineering checks. Start with a small project, then replace the example geometry
with your existing shape factory.

Studio creates projects using this same contract. This guide covers writing or
wrapping a project yourself; it requires only the framework, without Studio.
Create a virtual environment and install with `python -m pip install -e .`
as described in [CLI setup](CLI_MCP.md#install-from-a-checkout). Commands below
assume that checkout and its virtual environment.

## Create two files

Create a new `my-plate` directory with this structure:

```text
my-plate/
  cadharness.toml
  project.py
```

In `my-plate/cadharness.toml`:

```toml
[project]
id = "my-plate"
name = "My Plate"
entrypoint = "project.py:create_project"
```

In `my-plate/project.py`:

```python
from build123d import Box
from cadharness import (
    CADDocument, Component, EvidenceKind, range_check,
)


def create_project():
    plate = Box(40, 20, 4)  # Illustrative dimensions in millimeters.
    return CADDocument(
        id="my-plate",
        name="My Plate",
        revision="1",
        components={"plate": Component("plate", plate)},
        checks=(
            range_check(
                "plate.thickness",
                "Plate thickness",
                lambda document: document.components["plate"].shape.bounding_box().size.Z,
                minimum=3.0,
                unit="mm",
                evidence_kind=EvidenceKind.GEOMETRY,
                measurement_method="occt-bounding-box-z",
                components=("plate",),
            ),
        ),
    )
```

The check reads the **built geometry**, not the number supplied to `Box`.
Overall Z size measures thickness for this axis-aligned rectangular plate.
It is not a general wall-thickness method; see the
[measurement guide](MEASUREMENTS.md) for bounded feature and chord measurements.

## Verify and review

```powershell
.\.venv\Scripts\python.exe -m cadharness verify my-plate --summary
.\.venv\Scripts\python.exe -m cadharness inspector my-plate --summary
Invoke-Item .\my-plate\.cadharness\inspector\index.html
```

On macOS/Linux, use `./.venv/bin/python` and open the HTML file in your browser.
Expect verification to pass with two checks: built-in geometry validity and
`plate.thickness`. The report shows the model, its measured dimensions, and the
check's actual/expected values.

Change `Box(40, 20, 4)` to `Box(40, 20, 2)` and run `verify` again. The thickness
check fails: actual geometry is 2 mm, below the 3 mm minimum. The command exits 1.
Keep the requirement intact when testing a design regression.

To update the report after an edit:

```powershell
.\.venv\Scripts\python.exe -m cadharness inspector my-plate --summary --overwrite
```

Report generation exits 0 when the files are built successfully, even if the
report shows failed verification. Use `verify` to gate a script or CI job.
Files are written under the project's `.cadharness` directory; existing artifacts
are protected unless you explicitly choose `--overwrite`.

## Bring your existing model

Replace `Box(...)` with your shape factory, keeping the returned build123d shape
inside a `Component`. Give each part a stable lowercase ID. Add checks that
express the requirements you want future edits to preserve. A manifest points
to a factory returning `CADDocument`; an existing factory returning only a
`Shape` needs this small wrapper.

Run `cadharness list <root>` to discover manifests, or use
`python -m cadharness list <root>` with your chosen interpreter. Pass the project
directory to `verify`, `inspector`, or another operation. The manifest ID and
document ID must agree.

An MCP assistant uses these same projects after the optional MCP extra is
installed and trusted roots are configured. Follow the
[MCP setup guide](CLI_MCP.md#connect-an-mcp-client) when you need that interface.

For named variants and engineering measurements, study
[the NEMA mount source](../examples/nema17-mount/project.py). For revision
evidence and command details, continue with the [CLI guide](CLI_MCP.md).
