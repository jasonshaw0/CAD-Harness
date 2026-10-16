# Installation, updates and removal

CAD-Harness currently installs from a checkout or a locally validated wheel.
No public PyPI package or downloadable release is established by this guide.
Use an isolated virtual environment and keep designs outside its directory.

## Compatibility and prerequisites

Use ordinary CPython 3.11–3.14 with build123d 0.13.x. Free-threaded Python,
32-bit Python, Windows ARM and other CPU architectures are not covered by the
current CI. Dependencies include native OCCT binaries, so a Python version
declaration alone does not establish platform support.

| Path | Required CI coverage |
| --- | --- |
| Framework, workflow, Studio API, CLI and real stdio MCP | Python 3.11, 3.12, 3.13 and 3.14 on Windows/Linux/macOS hosted runners |
| Full bootstrap, built wheel/sdist, core-only install, extras and install lifecycle | Python 3.12 on Windows/Linux/macOS hosted runners |
| Real browser rendering through Playwriter | Linux, Python 3.12 |

Use the [latest CI run](https://github.com/jasonshaw0/CAD-Harness/actions/workflows/ci.yml)
and [milestone evidence](RELEASE_READINESS.md#session-record-and-resumption) for
results. This is a tested-runner matrix, not a promise for every OS release or
architecture. Python 3.13/3.14 package lifecycle testing is not in the full
distribution matrix.

Studio **builds** need Node.js 22.12+ and npm. A complete prebuilt wheel already
contains Studio's static frontend and needs neither Node nor npm at runtime.
The framework alone needs neither the server extras nor a frontend build.

## Install from a checkout

On Windows PowerShell:

```powershell
git clone https://github.com/jasonshaw0/CAD-Harness.git
cd CAD-Harness
python bootstrap.py
.\.venv\Scripts\python.exe -m cadharness doctor examples
.\.venv\Scripts\python.exe -m cadharness verify examples/nema17-mount --summary
```

On Linux/macOS, use `python3 bootstrap.py`, then `./.venv/bin/python` for the
two checks. Activation is optional. For framework-only setup in a fresh checkout,
run `python bootstrap.py --framework-only` (Linux/macOS: `python3`). It does not
remove extras already installed in an existing environment.

Full bootstrap writes `.cadharness/mcp.json`; it does not edit another
application's settings. Follow [MCP host setup](MCP_HOSTS.md)
to connect an MCP host. Keep roots limited to trusted projects. Python factories
execute locally without sandboxing, and checks do not establish physical fit.

## Install a locally built wheel

Use [the contributor distribution check](../CONTRIBUTING.md#build-a-distributable-package)
to produce a validated wheel and sdist first. In a separate environment:

```powershell
python -m venv .cad-venv
.\.cad-venv\Scripts\python.exe -m pip install "C:/Downloads/cad_harness-0.9.0-py3-none-any.whl[mcp,studio]"
.\.cad-venv\Scripts\python.exe -m cadharness --help
.\.cad-venv\Scripts\python.exe -m cadharness setup --host codex --root D:/CAD/projects --studio --summary
```

Replace the illustrative wheel and trusted-project paths with actual paths.
On Linux/macOS, create the environment with `python3 -m venv .cad-venv`, use
`./.cad-venv/bin/python`, and supply local Unix paths. Omit `[mcp,studio]` for
core only, or use `[mcp]` for framework MCP without the server extras. A wheel
does not install the repository's top-level `examples/`; installed templates
are available to the existing design/Studio example workflows.

## Update or repair an installation

1. Stop the MCP connection owning Studio, disconnect its attached clients, and
   stop other CAD-Harness processes using this environment. Close Studio tabs.
2. Back up your source projects and actual workspace. The default workspace is
   `<first-root>/runs/studio`; older workspaces may be under `designworkflow/runs`.
   Keep `.cadharness/mcp.json` and record the interpreter, explicit roots, port
   and workspace used by the host. Do not copy only exported meshes.
3. For a checkout, review local changes, run `git pull --ff-only`, then rerun
   `python bootstrap.py` (`python3` on Linux/macOS). It reuses `.venv` and keeps
   a differing generated config. Review any difference before using an explicit
   `--overwrite-config`; do not overwrite the host's settings.
4. For a wheel installation, use the same environment's interpreter:

```powershell
.\.cad-venv\Scripts\python.exe -m pip install --upgrade "C:/Downloads/cad_harness-NEW_VERSION-py3-none-any.whl[mcp,studio]"
.\.cad-venv\Scripts\python.exe -m pip check
```

Use the real new filename. To repair the current package without upgrading its
dependencies, use `pip install --no-deps --force-reinstall` with the exact
validated wheel, then `pip check`. This assumes dependencies are already installed.
Use `./.cad-venv/bin/python` on Linux/macOS. Keep the old environment until a
replacement using another Python minor version has been tested; do not retarget
an existing virtual environment to a different interpreter.

Restart the owning MCP connection and attached clients, then reload Studio.
Confirm its actual workspace and version with `studio_status` and
`get_cadharness_status`. Retained revisions remain inspectable. Evaluator or
kernel changes may require **Rebuild** into a new revision before another
export; never edit stored hashes to bypass freshness checks.

If the environment contains the earlier distribution named `cadharness`, follow
the [name migration](MIGRATION.md#cad-harness-name) first. It is a different
distribution from `CAD-Harness` and can otherwise compete for legacy scripts.

## Uninstall

Stop the owning MCP connection and other CAD-Harness processes first. Use the
installation's interpreter:

```powershell
.\.cad-venv\Scripts\python.exe -m pip uninstall CAD-Harness
```

For a checkout, use `.\.venv\Scripts\python.exe`; on Linux/macOS use the
corresponding `bin/python`. Remove the CAD-Harness entry from the MCP host using
its supported configuration interface, then reload that host. Other entries
must remain intact.

Uninstall removes the Python package and its commands, not separately stored
projects, workspace history, exports or generated client JSON. It leaves
dependencies installed. An editable install also leaves the Git checkout.
Removing the environment or checkout is a separate filesystem action: first
preserve any workspace/source/config kept beneath it.

## Source archives and notices

The sdist includes editable frontend source, its npm lockfile/build config,
tests and fixtures, acceptance/packaging scripts, framework examples, operational
guides and bootstrap. Compiled frontend assets also remain included, so rebuilding
the Python wheel from the sdist needs no Node. Rebuilding the frontend uses
`npm --prefix studio/web ci` then `npm --prefix studio/web run build`.
Dependencies, virtual environments and generated example workspaces are excluded.
Showcase models under the repository's `models/` remain checkout resources.

Vite generates `studio/web/THIRD_PARTY_LICENSES.md` inside the installed package's
static frontend directory, retaining the bundled dependencies' names, versions
and license text. It is included in both wheel and sdist and served at
`/THIRD_PARTY_LICENSES.md` by Studio. Regenerate it from the lockfile on frontend
updates; do not replace upstream notices with a project license declaration.
See [Vite's license option](https://vite.dev/config/build-options#build-license).

Python/native dependencies are installed separately, not copied into the
CAD-Harness wheel. Their own license/notice obligations still need review before
public distribution or standalone bundling. The inspected build123d 0.13 wheel
has LICENSE and NOTICE files; the installed cadquery-ocp-novtk/proxy 8.0.1.1.0
metadata lists Apache-2.0 but contains no license/notice files in its file records.
That inventory is not a conclusion about the native kernel's terms. Track the
native dependency provenance and [OCCT licensing](https://dev.opencascade.org/resources/licensing)
in the owner publication review. The project's license choice remains unresolved.

Lifecycle acceptance uses a `.dev0` package fixture containing the same Python
code as the candidate. It builds a real Studio design/export, upgrades the
installed package version, reinstalls, uninstalls and reinstalls again, checking
all retained source/evidence/config/export bytes and reopening the design through
the API. This tests package replacement and preservation, not migration across
historical releases, dependency/kernel upgrades or changed evaluator code.
