# Try the measured design loop

After [installation](INSTALLATION.md), run:

```powershell
.\.venv\Scripts\python.exe -m cadharness demo
```

On Linux/macOS use `./.venv/bin/python`. After activating the environment,
`cad-harness demo` is equivalent. The viewer needs the `[studio]` extras and a
built frontend; MCP and model credentials are not required. A validated full
wheel includes the frontend and needs no Node.js at runtime. For a checkout,
`python bootstrap.py` installs and builds it.

The command copies the bundled mounting-plate template to a **new** workspace,
builds two actual OCCT revisions, and evaluates the same frozen brief against
both. It then opens Studio on an available loopback port. The workspace path
and exact URL are printed. Startup takes several seconds for native imports,
two builds and measurement; no model generates or repairs this demonstration.

| Revision | Source change | Measured evidence |
| --- | --- | --- |
| `r001` | Manifest selects `missing-hole` | Three actual mounting holes where four are required; 29 of 37 checks pass. |
| `r002` | Manifest selects `standard` | Four actual holes; all 37 checks pass against the unchanged brief. |

The editable `project.py` is identical in both revisions. `cadharness.toml`
selects a named parameter variant; it changes the built geometry, not the
acceptance criteria. Missing-hole diameter/extent and pattern checks also fail
in `r001`, so its failure is not limited to the displayed count.

## Walk through Studio

1. The walkthrough opens on the failed `r001` geometry. Choose **Open measured
   checks**, expand **holes count**, and compare measured `3` with required `4`.
   Export remains disabled for this historical failed revision.
2. Reopen **Demo walkthrough** using its header icon. Choose **Inspect the
   repaired plate** to view `r002` and its passing evidence. Both revisions
   were evaluated during command startup; this button switches the recorded view.
3. Choose **Compare the revisions**. The plate changes; the requirements do
   not. The optional amber overlay shows previous geometry identities, not an
   exact solid difference. Turn the overlay off for an unobstructed current view.
4. **Inspect editable source** opens the selected manifest. Choose `project.py`
   to inspect named parameters and geometry construction. Source bundles and
   evidence reports can be downloaded from Export. Retained revisions are
   read-only; author changes in a new revision.
5. Select **plate** in Explorer, choose **Isolate part**, and use **View → Top**
   to see all four holes. Drag the canvas to orbit. The motor and cable shapes
   are reference envelopes; they are not printable components.
6. To create a geometry file, enable the trusted local session, choose
   **Export repaired part…** in the walkthrough, then **STEP** or **STL**.
   Export rechecks current evidence and downloads only the printable plate.
   Preparing or opening the demo never exports geometry automatically.

On a narrow screen the walkthrough scrolls. Close its panel and collapse
Explorer to see the model; the header icon reopens the guide. Physical fit,
material capability, print suitability and mechanical performance remain
unverified. This is an illustrative interface, not a certified motor mount.

## Keep, reopen or prepare without a viewer

By default each invocation uses a unique `runs/demo-<id>` directory beneath
the current working directory. It does not use or modify the default MCP Studio
workspace. To choose a destination or suppress browser opening:

```powershell
.\.venv\Scripts\python.exe -m cadharness demo --workspace D:/CAD/demo-first-look --no-browser
```

Use an actual local path on your OS. The destination must not exist, even if
empty; a repeated command refuses it without rewriting saved data. Port `0`
(the default) chooses a free port. `--port 8748` explicitly selects another
loopback port and refuses an occupied one. No existing Studio owner is attached
or stopped and no MCP roots or host settings are changed.

Press **Ctrl+C** in the launching terminal to stop the viewer. Source, briefs,
measurements, scenes, history and any explicit exports stay on disk. Reopen the
saved workspace without recreating it:

```powershell
.\.venv\Scripts\python.exe -m cadharness studio --workspace D:/CAD/demo-first-look --port 8748
```

To build the two revisions and print their workspace metadata as JSON without
opening a browser or starting HTTP:

```powershell
.\.venv\Scripts\python.exe -m cadharness demo --prepare-only --workspace D:/CAD/demo-headless
```

Preparation alone works with the core package, without MCP/server extras or a
frontend. Failures preserve partial source/reports for diagnosis and do not
write a completion receipt. Use a fresh destination after correcting the cause.
To make your own designs afterwards, follow [MCP host setup](MCP_HOSTS.md).
The demo's computational pass does not replace physical validation or authorize
publication.

## Acceptance

The unit and installed-wheel suites check actual counts, one locked brief,
retained source, comparison, failed-export rejection and workspace preservation.
For real browser acceptance with a new private Playwriter headless session:

```powershell
.\.venv\Scripts\python.exe scripts/verify_demo.py --output runs/demo-acceptance
```

Read the Playwriter skill first; install its test browser if needed with
`cmd /d /s /c npx -y playwriter@latest browser install` (Linux/macOS: run `npx`
directly). This exercises the guide, count details, comparison, source,
isolation, STEP/STL downloads and desktop/mobile layouts, retaining screenshots
and browser logs. `--require-installed` refuses an editable checkout import.
The distribution runner's `--render-browser` option includes this acceptance
against the wheel outside the checkout. Headless Chrome validates desktop/mobile
viewport layouts; it does not establish native touch-device behavior.
