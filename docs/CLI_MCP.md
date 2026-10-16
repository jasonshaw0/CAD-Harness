# CLI and MCP guide

The framework and Studio share the `cadharness` CLI and MCP server. Framework
commands operate on trusted source projects containing `cadharness.toml`.
Run commands from the repository checkout unless you pass absolute paths.

## Install from a checkout

Use a project-local virtual environment so another editable checkout cannot
silently replace the version you intend to run.

For the included workbench, `python bootstrap.py` handles the environment,
dependencies, canvas build, example verification, and local MCP configuration.
Use `python bootstrap.py --framework-only` for the core without Node.js or MCP.
See [Studio onboarding](STUDIO.md#one-command-setup). The manual steps below
remain available for framework-only MCP and custom development environments.

The [README](../README.md#try-the-evidence-loop) covers a first report.
Install `[mcp]` for framework-only MCP, or `[mcp,studio]` for the integrated
design workbench. See [Studio setup](STUDIO.md) for its canvas build.

```powershell
git clone https://github.com/jasonshaw0/CAD-Harness.git
cd CAD-Harness
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"
.\.venv\Scripts\python.exe -m cadharness doctor .
```

Or on Linux/macOS, use the same clone and `cd` commands, then:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -e ".[mcp]"
./.venv/bin/python -m cadharness doctor .
```

For full Studio setup, the shorter equivalent is `python3 bootstrap.py`.
Use `./.venv/bin/python` instead of the Windows interpreter path throughout
this guide. After `source .venv/bin/activate` in Bash/Zsh, `python` and the
short CLI entrypoints work directly; activation is optional.

`doctor` reports the active package version and path, Python interpreter, MCP
SDK, console scripts, scan root, and discovered projects. Its `checkout` value
should be the repository you just cloned.

The examples below use `python -m cadharness`, which does not depend on the
console-script directory being on `PATH`. After activating the environment,
the shorter `cad-harness ...` commands are equivalent. The `cadharness` and
`cadharness-mcp` entrypoints remain available for compatibility. The distribution
is named `CAD-Harness`; Python imports and `python -m cadharness` retain their
existing names, as do manifests, MCP keys, environment variables, and v1 schemas.

## CLI workflow

```powershell
$cad = ".\.venv\Scripts\python.exe"

& $cad -m cadharness list examples
& $cad -m cadharness inspect examples/project-box --variant standard
& $cad -m cadharness validate examples/project-box --variant standard
& $cad -m cadharness verify examples/project-box --variant standard
& $cad -m cadharness inspector examples/project-box --variant standard
& $cad -m cadharness snapshot examples/project-box --variant standard
& $cad -m cadharness compare examples/project-box --variant standard
```

Or in Bash/Zsh, set `cad=./.venv/bin/python` and replace `& $cad` with
`"$cad"`, for example `"$cad" -m cadharness verify examples/project-box --summary`.

Commands emit JSON by default. Add `--compact` anywhere in the command for
one-line JSON. `verify` and `inspector` accept `--summary` for readable terminal
output, including the verdict, checks needing attention, or report path.
`--summary` and `--compact` cannot be combined. Neither changes the verification
policy or exit codes. Runtime errors remain structured JSON on stderr.

`validate` exits with status 1 when checks fail; `compare` exits with
status 1 for a regression. `verify` exits with status 0 on gate pass, 1 on a
gate failure without check execution errors, and 2 when the gate rejects check
execution errors. Usage and runtime errors also exit with status 2.

Verification defaults reject failed, erroneous, or skipped checks, removed
requirements, normative requirement edits, and unaccepted revision changes.
Warnings and new passing requirements are allowed by default. Requirement gates
also cover built-in geometry criteria, including whether a solid is required.
Description-only edits remain informational.

Use `--baseline <file>` to include revision comparison and `--policy <file>`
to classify revision changes. The `--allow-*` and `--fail-on-*` flags configure
individual verification gates; for example, `--allow-removed-requirements`
allows removal without a second rejection for the associated validation result.
`--allow-check-errors` can pass the gate while the validation evidence still
records the errors. A gate exception never rewrites the underlying evidence.

| Command | Purpose | Writes files |
| --- | --- | --- |
| `doctor [root]` | Diagnose the active install and discover projects | No |
| `list [root]` | Find `cadharness.toml` manifests | No |
| `schemas` | List public JSON document contracts | No |
| `inspect <project>` | Build and return measured geometry evidence | No |
| `validate <project>` | Run geometry and project engineering checks | No |
| `measure <project>` | Measure explicitly selected geometry | No |
| `verify <project>` | Gate current evidence and optional revision changes | No |
| `inspector <project>` | Create a linked HTML/SVG review report | `.cadharness/inspector/` |
| `snapshot <project>` | Save deterministic revision evidence | `.cadharness/baseline.json` |
| `compare <project>` | Compare source-built geometry with a snapshot | Only with `--output` |
| `preview <project>` | Create hidden-line SVG views | `.cadharness/previews/` |
| `export <project>` | Explicitly write STEP or STL geometry | `exports/cadharness/` |
| `mcp-config [roots...]` | Generate portable MCP client JSON | No |
| `studio` | Serve the standalone viewer/API | Selected workspace |
| `design init/check/revise/export` | Run the manual source/brief workflow | Selected design run |

Generated paths are relative to the project directory, remain inside that
directory, and refuse to overwrite existing files unless `--overwrite` is
explicitly supplied. Run `python -m cadharness <command> --help` for all
options, including variants, selected components, and preview views.

## Connect an MCP client

Generate the client entry instead of hand-writing interpreter and root paths:

```powershell
.\.venv\Scripts\python.exe -m cadharness mcp-config .
```

Add `--studio` for the integrated workbench. `--studio-workspace PATH` must
remain within an explicit root; it defaults to `<first-root>/runs/studio/`.
Use `--studio-port PORT` to change the loopback port. These options generate
server arguments and do not launch the server themselves.

The result has this shape, with absolute paths filled in for the current
machine:

```json
{
  "mcpServers": {
    "cadharness": {
      "command": "C:\\path\\to\\cadharness\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "cadharness.mcp_server",
        "--root",
        "C:\\path\\to\\cadharness"
      ]
    }
  }
}
```

On Linux/macOS the generated `command` points to `/absolute/path/.venv/bin/python`
and roots use ordinary `/absolute/path` directories. Generate the config locally
instead of copying the Windows paths in this illustrative JSON.

Copy the `cadharness` entry into the MCP client's `mcpServers` object, then
restart or reload that client. The absolute interpreter ensures the client uses
this checkout's environment. The explicit `--root` makes discovery independent
of whatever working directory the host chooses.

Pass multiple trusted roots when required:

```powershell
.\.venv\Scripts\python.exe -m cadharness mcp-config C:\CAD\project-a D:\CAD\project-b
```

Or on Linux/macOS: `./.venv/bin/python -m cadharness mcp-config ~/CAD/project-a ~/CAD/project-b`.

The server exposes discovery, schema, inspection, measurement, validation, verification,
inspector, snapshot, comparison, preview, and export tools. Call
`get_cadharness_status` first to confirm the version, trusted roots, and
discovered projects visible to the host.

Initialization includes essential authoring instructions. Use
`get_cad_authoring_guide` for the packaged, versioned workflow, including adaptive
visual inspection and the distinction between MCP authorization and manual
source review. No personal skill is required.

To let the IDE assistant author source and update the live 3D canvas, append
`--studio` to the server arguments and install `.[mcp,studio]`. The MCP process
serves Studio on loopback and adds 13 `studio_*` tools; it calls no model itself.
`studio_render_view` returns PNG content from an open Studio tab using a separate
camera, with exact revision identity and capture metadata. It preserves the
interactive viewport and returns unavailable within 10 seconds if capture fails.
See [Studio setup and controls](STUDIO.md).

`measure_cad_project` shares its operation with `cadharness measure`. Measurement
CLI exits are 0 for success, 1 for no match, ambiguity, or unsupported geometry,
and 2 for invalid input or a kernel error. A successful measurement reports facts;
use `verify` to evaluate engineering acceptance criteria. See the
[measurement guide](MEASUREMENTS.md) for selectors, examples, and status meanings.

`cadharness-mcp` is a stdio server, not an interactive shell. Starting it
directly appears to wait silently because it is expecting an MCP client. Use
the following only to inspect its command-line interface:

```powershell
.\.venv\Scripts\cadharness-mcp.exe --help
.\.venv\Scripts\cadharness-mcp.exe --version
```

Or on Linux/macOS, use `./.venv/bin/cad-harness-mcp --help` or `--version`.

For compatibility with an existing configuration, roots can instead be set in
`CADHARNESS_PROJECT_ROOTS`; separate multiple Windows paths with `;`, or
Linux/macOS paths with `:`. Explicit
`--root` arguments take precedence, so generated configs are preferred.

## Trust boundary

Loading or operating on a project imports and executes the Python factory named
by its manifest. Roots constrain which project paths the MCP tools can select;
they do not sandbox that Python. Only configure repositories whose source you
trust. Preview, inspector, snapshot, comparison-output, and export tools also
write within the selected project when invoked.

## Troubleshooting

If commands appear stale or projects are missing, verify the active checkout:

```powershell
.\.venv\Scripts\python.exe -m cadharness doctor .
.\.venv\Scripts\python.exe -m pip show CAD-Harness
.\.venv\Scripts\python.exe -c "import cadharness; print(cadharness.__file__)"
```

Re-run the editable install from the intended checkout if any path points
elsewhere. If MCP startup is still unclear, first run `cadharness-mcp --help`,
regenerate the client entry with `mcp-config`, reload the client, and call
`get_cadharness_status` before invoking project tools.
