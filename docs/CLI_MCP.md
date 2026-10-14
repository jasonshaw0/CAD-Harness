# CLI and MCP guide

cadHarness operates on trusted source projects containing `cadharness.toml`.
Run commands from the repository checkout unless you pass absolute paths.

## Install from a checkout

Use a project-local virtual environment so another editable checkout cannot
silently replace the version you intend to run.

```powershell
git clone https://github.com/jasonshaw0/cadharness.git
cd cadharness
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"
.\.venv\Scripts\python.exe -m cadharness doctor .
```

`doctor` reports the active package version and path, Python interpreter, MCP
SDK, console scripts, scan root, and discovered projects. Its `checkout` value
should be the repository you just cloned.

The examples below use `python -m cadharness`, which does not depend on the
console-script directory being on `PATH`. After activating the environment,
the shorter `cadharness ...` commands are equivalent.

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

Every command emits JSON. Add `--compact` anywhere in the command for one-line
JSON. `validate` exits with status 1 when checks fail; `compare` exits with
status 1 for a regression; `verify` exits with status 0 on gate pass, 1 on gate
failure; usage and runtime errors exit with status 2.

| Command | Purpose | Writes files |
| --- | --- | --- |
| `doctor [root]` | Diagnose the active install and discover projects | No |
| `list [root]` | Find `cadharness.toml` manifests | No |
| `schemas` | List public JSON document contracts | No |
| `inspect <project>` | Build and return measured geometry evidence | No |
| `validate <project>` | Run geometry and project engineering checks | No |
| `verify <project>` | Gate current evidence and optional revision changes | No |
| `inspector <project>` | Create a linked HTML/SVG review report | `.cadharness/inspector/` |
| `snapshot <project>` | Save deterministic revision evidence | `.cadharness/baseline.json` |
| `compare <project>` | Compare source-built geometry with a snapshot | Only with `--output` |
| `preview <project>` | Create hidden-line SVG views | `.cadharness/previews/` |
| `export <project>` | Explicitly write STEP or STL geometry | `exports/cadharness/` |
| `mcp-config [roots...]` | Generate portable MCP client JSON | No |

Generated paths are relative to the project directory, remain inside that
directory, and refuse to overwrite existing files unless `--overwrite` is
explicitly supplied. Run `python -m cadharness <command> --help` for all
options, including variants, selected components, and preview views.

## Connect an MCP client

Generate the client entry instead of hand-writing interpreter and root paths:

```powershell
.\.venv\Scripts\python.exe -m cadharness mcp-config .
```

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

Copy the `cadharness` entry into the MCP client's `mcpServers` object, then
restart or reload that client. The absolute interpreter ensures the client uses
this checkout's environment. The explicit `--root` makes discovery independent
of whatever working directory the host chooses.

Pass multiple trusted roots when required:

```powershell
.\.venv\Scripts\python.exe -m cadharness mcp-config C:\CAD\project-a D:\CAD\project-b
```

The server exposes discovery, schema, inspection, validation, verification,
inspector, snapshot, comparison, preview, and export tools. Call
`get_cadharness_status` first to confirm the version, trusted roots, and
discovered projects visible to the host.

`cadharness-mcp` is a stdio server, not an interactive shell. Starting it
directly appears to wait silently because it is expecting an MCP client. Use
the following only to inspect its command-line interface:

```powershell
.\.venv\Scripts\cadharness-mcp.exe --help
.\.venv\Scripts\cadharness-mcp.exe --version
```

For compatibility with an existing configuration, roots can instead be set in
`CADHARNESS_PROJECT_ROOTS`; separate multiple Windows paths with `;`. Explicit
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
.\.venv\Scripts\python.exe -m pip show cadharness
.\.venv\Scripts\python.exe -c "import cadharness; print(cadharness.__file__)"
```

Re-run the editable install from the intended checkout if any path points
elsewhere. If MCP startup is still unclear, first run `cadharness-mcp --help`,
regenerate the client entry with `mcp-config`, reload the client, and call
`get_cadharness_status` before invoking project tools.
