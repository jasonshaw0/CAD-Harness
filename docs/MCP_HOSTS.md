# Connect an MCP host

Install CAD-Harness first: [checkout or validated wheel](INSTALLATION.md).
Use that installation's Python for these commands. `doctor` identifies the
interpreter, imported package and MCP SDK; `setup` detects available setup paths:

```powershell
.\.venv\Scripts\python.exe -m cadharness doctor .
.\.venv\Scripts\python.exe -m cadharness setup --summary
```

On Linux/macOS use `./.venv/bin/python`. With an activated environment,
`cad-harness` is equivalent to `python -m cadharness`. Detection reports the
Codex executable and documented config locations. A present directory does not
prove an application is installed or connected.

## Preview, check, then save

Choose an **existing trusted project directory**. Paths containing spaces belong
inside quotes. Repeat `--root` for additional trusted directories. Roots never
expand to accommodate a workspace. Factories execute trusted local Python
without sandboxing; select only code you trust.

For Codex CLI, its IDE extension, or the Codex host in the ChatGPT desktop app:

```powershell
.\.venv\Scripts\python.exe -m cadharness setup --host codex --root "D:/CAD/my-project" --studio --summary
```

For Claude Desktop:

```powershell
.\.venv\Scripts\python.exe -m cadharness setup --host claude-desktop --root "D:/CAD/my-project" --studio --summary
```

On Linux/macOS substitute an existing root such as `"$HOME/CAD/my-project"`.
Omit `--studio` for framework-only tools. The preview prints the exact destination,
absolute Python command, arguments, roots, blockers and reload instructions. It
does not write files or start a server. Exit 0 means the plan is ready; exit 2
means a blocker or execution error. JSON is the default; `--summary` is readable.

Add `--check` to the same command to initialize a real stdio MCP connection from
an unrelated directory, list tools and call `get_cadharness_status`. With
`--studio`, it also calls `studio_status` and requires the built frontend.
This starts or attaches Studio and creates its workspace; it does not build
project factories, launch a browser or call a model. Initialization is bounded
to 30 seconds. A successful check validates the proposed process, **not whether
your host has reloaded it**. The temporary check process closes afterwards.

After reviewing the destination and entry, repeat the command with **`--apply`**
to authorize saving it. Combining `--check --apply` saves only after the connection
check passes. Setup adds one entry, preserves unrelated settings, and retains a
backup beside an existing file. An identical entry is a no-op. A different entry
under the same name is refused, including extra environment, filter or disabled
settings: review it in the host or choose `--name cadharness-other`. No automatic
replacement or trust/approval-policy change is performed. Malformed configs,
duplicate JSON keys, symlinks and detected concurrent changes are refused.

Studio defaults to `<first-root>/runs/studio` and loopback port 8741. Override
with `--studio-workspace PATH --studio-port 8742`; the workspace must stay within
an explicit root. Port 0 allocates a temporary port, useful for isolated checks.
Matching roots/workspace/protocol can share an existing Studio owner. A port
belonging to another workspace is an error; see [Studio ownership](STUDIO.md#connect-your-assistant).

## Codex: CLI registration and TOML

Codex uses `[mcp_servers.cadharness]` in `~/.codex/config.toml`, or
`$CODEX_HOME/config.toml` when overridden. It does **not** consume the portable
`mcpServers` JSON directly. Setup uses the installed public `codex mcp add`
command with separate argv values; Codex writes its own TOML. It preserves other
servers and top-level settings and checks them after writing. A failed write
reports the backup path for review; it does not blindly restore over newer edits.

The CLI must be on PATH. Windows npm installations use their Node entry point
without passing trusted paths through a shell. If only the IDE/app is installed,
use its **Settings → MCP servers → Add** stdio form and copy `command` and `args`
from the preview. That manual route has no automatic apply check.

Restart the affected CLI session or IDE/app after saving. In the CLI, `/mcp`
shows connection status and available tools; in the IDE/app inspect MCP settings.
`codex mcp get cadharness --json` confirms stored registration but does not prove
live tool availability. Trusted project `.codex/config.toml` can also supply MCP
settings; inspect project overrides if the live host differs from the user-level
entry. Setup writes only the user-level entry, from outside the project.

Codex documents a 10-second default startup timeout. If logs show native imports
exceed it, review `startup_timeout_sec` in the host settings. Setup does not change
host timeouts or permission policy automatically.

## Claude Desktop: desktop JSON and full restart

Open **Settings → Developer → Edit Config** first. Desktop's documented file is:

| Platform | File |
| --- | --- |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

Setup merges one `mcpServers` entry atomically into that JSON and preserves other
keys/servers. If its default directory is absent, setup asks you to open Desktop's
config first. `--config PATH` explicitly selects another Desktop JSON destination,
including an isolated test profile. No automatic Linux Desktop path is assumed.

**Fully quit and restart Claude Desktop**; closing its window may leave the old
process running. Inspect Developer settings for the `cadharness` server and its
logs. On Windows logs are under `%APPDATA%\Claude\logs`; on macOS under
`~/Library/Logs/Claude`. Check `mcp.log` and `mcp-server-cadharness.log`.

This route is for the local Desktop app. Claude Code, claude.ai and remote MCP
connectors have different configuration and connection lifecycles. This command
does not edit those hosts. Desktop also supports packaged extensions; CAD-Harness
does not currently ship an extension bundle.

## Confirm the connection and first design

In the restarted host call `get_cadharness_status`: confirm the version, roots
and projects. With Studio call `studio_status`: confirm `frontend_available` and
open its exact `viewer_url`. Ask the assistant to read `get_cad_authoring_guide`,
then follow [the first design and iteration](STUDIO.md#first-design-and-iteration).
The host assistant authors source through MCP; Studio makes no nested model calls.

If tools are absent, inspect host startup stderr and the tool catalog. Run the
same preview with `--check` and inspect `connection.error` and `connection.stderr`
in JSON output. Check the interpreter with `doctor`, install missing extras in
that interpreter, and rebuild the frontend for source installs. An occupied
Studio port requires matching the owner or choosing another port; do not broaden
roots or kill unrelated processes to make initialization succeed. Rendering
availability is reported separately by `studio_status`; MCP connectivity does
not establish a rendered-image result.

## Validation and sources

The regression suite tests preview/no-write behavior, conflicts, backups,
idempotence, unrelated settings, invalid JSON, documented platform paths and real
stdio transport. Full wheel acceptance includes the real Studio check. To verify
native Codex registration without touching a personal profile or calling a model:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_host_setup.py --output runs/isolated-host-check
```

Windows Codex CLI 0.162.1 passed registration, public CLI readback, a repeated
apply and real stdio/Studio checks in an isolated `CODEX_HOME`. The native
`app-server` discovered the tool catalog before/after live reload and again in a
second host process, without a model turn. Paths included spaces, Unicode and
`&`. Claude Desktop was not installed on that validation
machine: its merge and transport path are tested, but interactive Desktop
restart/tool discovery remains a manual acceptance step. IDE/app reload and
native Codex registration on macOS/Linux also need host-level acceptance; the
cross-platform tests cover config generation and transport, not those UIs.

Host documentation checked 2026-10-16:

- [Codex MCP configuration, CLI, IDE/app and reload](https://learn.chatgpt.com/docs/extend/mcp).
- [Codex MCP CLI commands](https://learn.chatgpt.com/docs/developer-commands#codex-mcp).
- [Codex app-server lifecycle and MCP discovery](https://learn.chatgpt.com/docs/app-server).
- [Codex shared configuration layers](https://learn.chatgpt.com/guides/best-practices#configure-codex-for-consistency).
- [MCP local servers in Claude Desktop: paths, restart and logs](https://modelcontextprotocol.io/docs/develop/connect-local-servers).
- [Claude Desktop local servers and extensions](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).
