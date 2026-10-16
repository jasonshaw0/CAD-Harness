# Developing CAD-Harness

CAD-Harness is one product with a reusable framework, design orchestration, and
Studio. Keep CAD operations in the shared framework; Studio orchestrates and
presents their results.

## Repository layout

```text
src/cadharness/
  model.py, checks.py, measurements.py, operations.py, …  # framework
  cli.py, mcp_server.py                                 # shared entrypoints
  workflow/                                            # briefs, acceptance, attempts
    templates/, prompts/, CONTRACTS.md                  # installed authoring resources
    AUTHORING.md                                       # versioned MCP workflow guidance
    benchmarks/                                        # deterministic evaluation fixtures
  studio/                                              # API, MCP tools, jobs, scene/store
    web/                                               # generated canvas (ignored)
studio/web/                                            # editable React/Three.js frontend
tests/                                                 # framework and onboarding tests
  workflow/                                            # workflow, Studio API, real stdio tests
examples/                                              # framework project examples
docs/                                                  # guides and architecture
scripts/                                               # integration and Playwriter checks
runs/                                                  # local source and evidence (ignored)
designworkflow/                                         # legacy CLI shim / old saved runs
```

## Install and check

Use a checkout-local virtual environment. In Windows PowerShell:

```powershell
python bootstrap.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/smoke_mcp.py
```

Or on Linux/macOS:

```bash
python3 bootstrap.py
./.venv/bin/python -m unittest discover -s tests -v
./.venv/bin/python scripts/smoke_mcp.py
```

CI runs the Python/CLI/MCP checks on Windows, Linux, and macOS, and checks full
Studio setup and wheel installation on Linux and macOS. One discovery command
includes all workflow and Studio tests. The real stdio integration exercises a failed
measurement, repair under a frozen brief, follow-up turn, and STL export.

Use `cadharness --help` for shared commands. Manual design commands live under
`cadharness design`; integrated Studio is launched by the MCP host with
`--studio`. See [Studio](docs/STUDIO.md) for frontend development and
[evaluation](docs/EVALUATION.md) for repeatable defect trials.

Use Playwriter exclusively for browser control and testing. Read its skill,
create a stateful task session, exercise interactions, inspect screenshots,
and check console errors. Unit tests and a build do not establish browser acceptance.

For the Studio walkthrough, use `scripts/verify_studio_browser.js` in a dedicated
test workspace. Each Playwriter invocation performs one action and prints the
resulting snapshot and browser logs; it covers builds, selection, review,
history, source, STEP export/download, themes, and mobile views. See
[Studio UI acceptance](docs/STUDIO_UI_ACCEPTANCE.md) for setup and observations.

The capture acceptance check uses Playwriter's private headless browser with an
isolated test workspace, no personal Chrome state or extension. It drives real
stdio MCP builds, captures single/multi-part, hollow and blended geometry,
isolates components, frames close-ups and selects historical revisions. It also
checks two tabs' pixels/UI state, lazy loading, WebGL failure, closed Studio and
unchanged build evidence. Inspect the resulting PNGs in the printed run folder.
The headless browser is a development-test dependency only:

```powershell
cmd /d /s /c npx -y playwriter@latest browser install
.\.venv\Scripts\python.exe scripts/verify_studio_rendering.py
```

Or on Linux/macOS, run `npx -y playwriter@latest browser install` directly, then
`./.venv/bin/python scripts/verify_studio_rendering.py`.

Broker tests separately cover timeouts, duplicate/mismatched results, invalid
selections, authentication, and image content through an attached MCP client.

## Build a distributable package

Build the frontend **before** creating a wheel so its static assets are
included. Package discovery uses `src/`; templates, contracts, prompts, and
the generated canvas are explicit package data. Runtime needs no checkout
import-path injection.

```powershell
npm --prefix studio/web run build
.\.venv\Scripts\python.exe -m pip install build
.\.venv\Scripts\python.exe scripts/smoke_distribution.py --fresh-install --output dist/validated
```

Or on Linux/macOS, keep the npm command and use
`./.venv/bin/python` for both Python commands.

The smoke script builds a source distribution, then a wheel from that archive
using isolated build dependencies. It checks source/resource bytes and package
name/version in both artifacts, including the lazy renderer chunk, templates and
authoring guidance. It also checks editable frontend source, the lockfile, guides,
tests and scripts in the sdist, and rejects dependency environments in that archive.
Vite generates bundled dependency notices; they are required in both artifacts.
`--fresh-install` first verifies a core-only install, then adds `[mcp,studio]` in
a clean temporary environment, runs `pip check`, serves installed assets, and
runs the real Studio stdio integration outside the checkout. CI runs this path
on Windows, Linux and macOS with Python 3.12 after building the frontend. It
includes failed measurement, frozen repair, follow-up, export, guidance discovery
and direct/shared MCP image transport; no personal skills or host config are used.
It then builds a same-code `.dev0` fixture, saves a real Studio design and STL,
upgrades its package version, reinstalls, uninstalls and reinstalls again. Saved
source, geometry evidence, meshes, exports and generated MCP JSON must remain
byte-identical and reopen through the Studio API. This is a package lifecycle
test, not proof of migration across historical releases or changed evaluators.

`--output` retains the validated wheel, sdist and `SHA256SUMS` only after success.
Choose a new directory each run; existing output is preserved. This does not tag,
release or upload a package. The source archive carries compiled Studio assets
and editable frontend source/build inputs. These checks establish artifact
contents and installation behavior, not byte-identical rebuilds or physical fit.

For a faster local check, omit `--fresh-install`; that mode borrows development
dependencies and cannot establish a clean installation. `build` is a development
tool only, not an added application dependency. The default build sequence is
documented by [PyPA build](https://build.pypa.io/en/stable/how-to/basic-usage.html).
With Chrome for Testing installed, add `--render-browser` to exercise the same
real rendering acceptance runner against that installed wheel outside the checkout.

A wheel built without the frontend supports the framework and design runner;
Studio reports `frontend_available=False`. For a full Studio distribution,
build from a clean tree and include the canvas. Install the wheel with
`[mcp,studio]` extras in a separate environment, test outside the checkout, and
confirm the authoring resources and viewer are present.

See the [release-readiness audit and roadmap](docs/RELEASE_READINESS.md) for
current evidence, owner decisions, and the next incremental milestone.
The [installation guide](docs/INSTALLATION.md) records compatibility boundaries,
source-archive contents, dependency notice provenance and update/removal commands.

Keep generated CAD runs and exports out of commits. Preserve user changes,
run relevant checks before committing, and use focused commits. The local
workflow requires completed commits pushed to `origin/main` and confirmed in sync.
