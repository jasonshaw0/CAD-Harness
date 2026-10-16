"""Preview explicit stdio settings; opt in to a host-owned configuration change."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Iterable

from .mcp_config import mcp_client_config


def _codex_command() -> list[str]:
    # Reuse the Windows-safe npm/native launcher, never a shell command string.
    from .studio.codex import cli_command
    if shutil.which("codex") is None:
        raise RuntimeError("Codex CLI was not found on PATH; install it or use the host's stdio settings form")
    return cli_command()


def _config_path(host: str, config: Path | None) -> Path:
    if config is not None:
        if host != "claude-desktop":
            raise ValueError("--config is for Claude Desktop; Codex uses CODEX_HOME/config.toml")
        return Path(os.path.abspath(config.expanduser()))
    if host == "codex":
        if "CODEX_HOME" in os.environ and not os.environ["CODEX_HOME"].strip():
            raise ValueError("CODEX_HOME is empty; unset it or select a Codex configuration directory")
        home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
        return Path(os.path.abspath(home / "config.toml"))
    if sys.platform == "win32":
        if not os.environ.get("APPDATA"):
            raise ValueError("APPDATA is unavailable; select the Desktop file with --config")
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    raise ValueError("No documented automatic Claude Desktop path on this OS; use --config")


def detect_hosts() -> dict[str, Any]:
    """Report observable setup routes without claiming a client is connected."""
    hosts = []
    for host in ("codex", "claude-desktop"):
        try:
            path = str(_config_path(host, None))
            directory_present = Path(path).parent.is_dir()
        except ValueError:
            path, directory_present = None, False
        hosts.append({"host": host, "config_path": path,
                      "config_directory_present": directory_present,
                      "cli_on_path": shutil.which("codex") is not None if host == "codex" else None,
                      "connected": "unknown"})
    return {"mode": "detect", "hosts": hosts,
            "next_step": "Select --host codex or --host claude-desktop and supply an explicit --root PATH; preview before --apply."}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate configuration key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"invalid JSON constant: {value}")


def _read(path: Path, host: str) -> tuple[bytes | None, dict]:
    if path.is_symlink():
        raise ValueError("Configuration is a symlink; manage it through the host instead")
    if not path.exists():
        return None, {}
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    data = (tomllib.loads(text) if host == "codex" else json.loads(
        text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant))
    key = "mcp_servers" if host == "codex" else "mcpServers"
    if not isinstance(data, dict) or not isinstance(data.get(key, {}), dict):
        raise ValueError(f"Configuration and {key} must be objects")
    return raw, data


def _entry_state(data: dict, host: str, name: str, entry: dict) -> str:
    entries = data.get("mcp_servers" if host == "codex" else "mcpServers", {})
    if name not in entries:
        return "new"
    # Extra settings (env, cwd, filters, disabled state) can alter the process or
    # visible tools. Require manual review rather than claiming equivalence.
    return "already-configured" if entries[name] == entry else "conflict"


def _backup(path: Path, raw: bytes | None) -> str | None:
    if raw is None:
        return None
    fd, name = tempfile.mkstemp(prefix=path.name + ".cadharness-", suffix=".bak", dir=path.parent)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
    return name


def _unchanged(path: Path, host: str, raw: bytes | None) -> None:
    if _read(path, host)[0] != raw:
        raise ValueError("Configuration changed during setup; preview again before applying")


def _apply(path: Path, host: str, name: str, entry: dict, raw: bytes | None,
           data: dict, command: list[str] | None) -> str | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _unchanged(path, host, raw)
    backup = _backup(path, raw)
    if host == "codex":
        try:
            # Run outside any project's .codex directory. Codex owns TOML writing.
            with tempfile.TemporaryDirectory(prefix="cadharness-host-") as cwd:
                result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                        env={**os.environ, "CODEX_HOME": str(path.parent)},
                                        encoding="utf-8", errors="replace", timeout=30, check=False)
            if result.returncode:
                raise RuntimeError(f"Codex exited {result.returncode}: {result.stderr.strip()}")
            _, updated = _read(path, host)
            expected = {**data, "mcp_servers": {**data.get("mcp_servers", {}), name: entry}}
            if updated != expected:
                raise RuntimeError("Codex saved unexpected settings; review the host file and backup")
        except Exception as exc:
            raise RuntimeError(f"Codex setup failed; backup: {backup or 'no previous file'}. {exc}") from exc
    else:
        updated = {**data, "mcpServers": {**data.get("mcpServers", {}), name: entry}}
        fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(updated, stream, indent=2, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
            if raw is not None:
                os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            _unchanged(path, host, raw)
            os.replace(temporary, path)
        except Exception as exc:
            raise RuntimeError(f"Desktop setup failed; backup: {backup or 'no previous file'}. {exc}") from exc
        finally:
            Path(temporary).unlink(missing_ok=True)
    return backup


def check_connection(entry: dict, *, studio: bool = False) -> dict[str, Any]:
    """Start the proposed command from an unrelated cwd; never build a factory."""
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def connect():
        with tempfile.TemporaryDirectory(prefix="cadharness-check-") as cwd, tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as errors:
            try:
                with anyio.fail_after(30):
                    params = StdioServerParameters(**entry, cwd=cwd)
                    async with stdio_client(params, errlog=errors) as streams:
                        async with ClientSession(*streams) as session:
                            info = await session.initialize()
                            tools = {tool.name for tool in (await session.list_tools()).tools}
                            required = {"get_cadharness_status", "get_cad_authoring_guide", "verify_cad_project"}
                            if studio:
                                required.add("studio_status")
                            if info.server_info.name != "CAD-Harness" or not required <= tools:
                                raise RuntimeError("Unexpected server identity or missing tools")
                            status = await session.call_tool("get_cadharness_status", {})
                            if status.is_error or not status.structured_content:
                                raise RuntimeError("get_cadharness_status failed")
                            expected_roots = [entry["args"][i + 1] for i, arg in enumerate(entry["args"]) if arg == "--root"]
                            if status.structured_content.get("roots") != [{"path": root, "exists": True} for root in expected_roots]:
                                raise RuntimeError("Server reported unexpected trusted roots")
                            result = {"passed": True, "server": info.server_info.name,
                                      "version": info.server_info.version, "tools": sorted(tools),
                                      "status": status.structured_content, "host_reloaded": False}
                            if studio:
                                viewer = await session.call_tool("studio_status", {})
                                if viewer.is_error or not viewer.structured_content:
                                    raise RuntimeError("studio_status failed")
                                result["studio"] = viewer.structured_content
                                if not result["studio"].get("frontend_available"):
                                    raise RuntimeError("Studio frontend is missing; build or reinstall the full distribution")
                            return result
            except Exception as exc:
                errors.seek(0)
                # Unwrap task groups so startup/port/import errors remain actionable.
                while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
                    exc = exc.exceptions[0]
                return {"passed": False, "error": f"{type(exc).__name__}: {exc}",
                        "stderr": errors.read()[-6000:], "host_reloaded": False}

    return anyio.run(connect)


def setup_host(roots: Iterable[str | Path], *, host: str, name: str = "cadharness",
               studio: bool = False, studio_workspace: Path | None = None,
               studio_port: int = 8741, config: Path | None = None,
               check: bool = False, apply: bool = False) -> dict[str, Any]:
    """Return a reviewable plan; only --apply edits a host configuration."""
    if host not in {"codex", "claude-desktop"}:
        raise ValueError("Host must be codex or claude-desktop")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise ValueError("Server name must contain only letters, digits, underscores or hyphens")
    roots = list(roots)
    if not roots:
        raise ValueError("Supply at least one explicit --root; setup never expands trusted roots")
    entry = mcp_client_config(roots, name=name, studio=studio, studio_workspace=studio_workspace,
                              studio_port=studio_port)["mcpServers"][name]
    resolved = [str(Path(root).expanduser().resolve()) for root in roots]
    path = _config_path(host, config)
    raw, data = _read(path, host)
    state = _entry_state(data, host, name, entry)
    blockers = [f"Trusted root is not a directory: {root}" for root in resolved if not Path(root).is_dir()]
    if not Path(entry["command"]).is_file():
        blockers.append("The active Python interpreter is not an existing file")
    for dependency in (["mcp", "starlette", "uvicorn"] if studio else ["mcp"]):
        if importlib.util.find_spec(dependency) is None:
            blockers.append(f"Missing {dependency}; install CAD-Harness[mcp,studio] in this interpreter")
    command = None
    if host == "codex":
        try:
            command = [*_codex_command(), "mcp", "add", name, "--", entry["command"], *entry["args"]]
        except RuntimeError as exc:
            blockers.append(str(exc))
    elif config is None and not path.parent.is_dir():
        blockers.append("Claude Desktop configuration directory is absent; open Settings > Developer > Edit Config first")
    if state == "conflict":
        blockers.append(f"Entry {name!r} already has different settings; review it in the host or choose --name")
    result = {"host": host, "config_path": str(path), "name": name, "entry": entry,
              "trusted_roots": resolved, "existing_entry": state, "blockers": blockers,
              "mode": "apply" if apply else "preview", "changed": False,
              "connection": None, "backup": None,
              "next_steps": (["Restart the Codex host, then inspect /mcp (CLI) or MCP settings (IDE/app)."]
                             if host == "codex" else ["Fully quit and restart Claude Desktop; inspect Settings > Developer."]),
              "trust": "Project factories execute trusted local Python; roots do not sandbox that code."}
    if command:
        result["host_command_argv"] = command
    if check and not blockers:
        result["connection"] = check_connection(entry, studio=studio)
        if not result["connection"]["passed"]:
            blockers.append("Stdio connection check failed; inspect connection.error and connection.stderr")
    if apply and not blockers and state == "new":
        result["backup"] = _apply(path, host, name, entry, raw, data, command)
        result["changed"] = True
    result["ready"] = not blockers
    return result


def print_setup_summary(result: dict) -> None:
    if result.get("mode") == "detect":
        for host in result["hosts"]:
            print(f"{host['host']}: {json.dumps(host, ensure_ascii=False)}")
        print(result["next_step"])
        return
    print(f"{result['host']}: {result['mode']} ({result['existing_entry']})")
    print(f"Configuration: {result['config_path']}")
    print("Proposed entry: " + json.dumps({result["name"]: result["entry"]}, ensure_ascii=False))
    print(result["trust"])
    for blocker in result["blockers"]:
        print(f"Blocked: {blocker}")
    if result["connection"] is not None:
        print("Stdio check: " + ("passed" if result["connection"]["passed"] else "failed"))
        if not result["connection"]["passed"]:
            print(json.dumps(result["connection"], ensure_ascii=False))
    print("Host settings changed: " + str(result["changed"]).lower())
    if result["backup"]:
        print("Backup: " + result["backup"])
    if result["ready"] and result["mode"] == "preview":
        print("Review this entry and destination; rerun with --apply to save it.")
    for step in result["next_steps"]:
        print(step)
    print("After reload, call get_cadharness_status" + (" and studio_status." if "--studio" in result["entry"]["args"] else "."))
