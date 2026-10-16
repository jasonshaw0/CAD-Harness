"""Validate the installed Codex CLI using an isolated profile, without model calls.

Requires Codex on PATH. Personal Codex/Claude settings are never written.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time
import tomllib


def host_catalog(launcher, env, cwd, output, label):
    """Exercise native host discovery/reload; never start a model turn."""
    from cadharness.studio.processes import terminate_tree

    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with (output / f"{label}.stderr.log").open("w", encoding="utf-8") as errors:
        process = subprocess.Popen([*launcher, "app-server"], cwd=cwd, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                                   text=True, encoding="utf-8", errors="replace", **flags)
        messages = queue.Queue()

        def read():
            for line in process.stdout:
                messages.put(json.loads(line))
            messages.put(None)

        reader = threading.Thread(target=read, daemon=True)
        reader.start()

        def send(message):
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()

        def rpc(identifier, method, params):
            send({"id": identifier, "method": method, "params": params})
            deadline = time.monotonic() + 45
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"Timed out waiting for {method}; inspect {label}.stderr.log")
                message = messages.get(timeout=remaining)
                if message is None:
                    raise RuntimeError(f"Codex exited before {method}; inspect {label}.stderr.log")
                if message.get("id") == identifier:
                    if "error" in message:
                        raise RuntimeError(f"{method}: {message['error']}")
                    return message["result"]

        try:
            rpc(1, "initialize", {"clientInfo": {"name": "cadharness_acceptance", "version": "0.9.0"}})
            send({"method": "initialized", "params": {}})
            before = rpc(2, "mcpServerStatus/list", {"serverName": "cadharness"})
            rpc(3, "config/mcpServer/reload", None)
            after = rpc(4, "mcpServerStatus/list", {"serverName": "cadharness"})
            for catalog in (before, after):
                server, = [server for server in catalog["data"] if server["name"] == "cadharness"]
                assert {"get_cadharness_status", "studio_status", "verify_cad_project"} <= set(server["tools"]), server
            return {"before_reload": before, "after_reload": after}
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                terminate_tree(process)
                process.wait(timeout=10)
            reader.join(timeout=2)
            process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new evidence directory (retains isolated config and backup)")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Keeping existing evidence; select a new output directory")
    output.mkdir(parents=True)
    profile = output / "isolated-codex"
    profile.mkdir()
    projects = output / "CAD space & café"
    projects.mkdir()
    config = profile / "config.toml"
    config.write_text('model = "retain-sentinel"\n[mcp_servers.other]\ncommand = "preserve-other"\n', encoding="utf-8")
    before = tomllib.loads(config.read_text(encoding="utf-8"))
    env = {**os.environ, "CODEX_HOME": str(profile)}
    command = [sys.executable, "-m", "cadharness", "setup", "--host", "codex", "--root", str(projects),
               "--studio", "--studio-workspace", str(projects / "workspace"), "--studio-port", "0", "--check"]
    with TemporaryDirectory(prefix="cadharness-host-smoke-") as cwd:
        def run(argv):
            result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=90)
            if result.returncode:
                raise RuntimeError(f"Command exited {result.returncode}: {result.stderr}\n{result.stdout}")
            return result.stdout

        preview = json.loads(run(command))
        assert preview["ready"] and not preview["changed"]
        assert tomllib.loads(config.read_text(encoding="utf-8")) == before
        applied = json.loads(run([*command, "--apply"]))
        assert applied["changed"] and applied["connection"]["passed"]
        after = tomllib.loads(config.read_text(encoding="utf-8"))
        assert after == {**before, "mcp_servers": {**before["mcp_servers"], "cadharness": applied["entry"]}}
        assert Path(applied["backup"]).is_file()
        again = json.loads(run([*command, "--apply"]))
        assert again["ready"] and not again["changed"] and again["backup"] is None
        # Read back through the real host's public CLI, not just our TOML parser.
        # Locate the mcp verb instead of depending on npm vs native launcher size.
        launcher = preview["host_command_argv"][:preview["host_command_argv"].index("mcp")]
        registered = json.loads(run([*launcher, "mcp", "get", "cadharness", "--json"]))
        transport = registered["transport"]
        assert transport["command"] == applied["entry"]["command"]
        assert transport["args"] == applied["entry"]["args"]
        version = run([*launcher, "--version"]).strip()
        # Two independent host processes prove restart as well as live reload.
        catalogs = [host_catalog(launcher, env, cwd, output, label) for label in ("host-first", "host-restarted")]
        report = {"host": version, "preview": preview, "applied": applied, "idempotent": True,
                  "host_readback": registered, "personal_config_changed": False,
                  "host_catalogs": catalogs,
                  "boundary": "Native host registration, discovery, reload/restart and SDK stdio checks; no GUI or model calls."}
        (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Isolated Codex host setup passed: {output / 'report.json'}")


if __name__ == "__main__":
    main()
