"""One-command checkout setup. Uses only the Python standard library."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def run(args, *, cwd=ROOT, capture=False):
    return subprocess.run(list(map(str, args)), cwd=cwd, check=True,
                          text=True, encoding="utf-8", errors="replace",
                          capture_output=capture)


def prepare(args, *, checkout=ROOT, runner=run, which=shutil.which):
    if not (3, 11) <= sys.version_info[:2] < (3, 15):
        raise ValueError("Use Python 3.11–3.14 to run bootstrap.py.")
    checkout = checkout.resolve()
    environment = checkout / ".venv"
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    roots = [Path(path).expanduser().resolve() for path in args.root] if args.root else [checkout]
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else None
    if workspace and not any(workspace.is_relative_to(root) for root in roots):
        raise ValueError("--workspace must be inside an explicit --root; no roots are added automatically.")
    if not 0 <= args.port <= 65535:
        raise ValueError("--port must be between 0 and 65535.")
    npm = None
    if not args.framework_only:
        node, npm = which("node"), which("npm")
        if not node or not npm:
            raise ValueError("Install Node.js 22.12+ (including npm), reopen your terminal, and rerun this command.")
        version = runner([node, "--version"], cwd=checkout, capture=True).stdout.strip()
        try:
            supported = tuple(map(int, version.lstrip("v").split(".")[:2])) >= (22, 12)
        except ValueError:
            supported = False
        if not supported:
            raise ValueError(f"Node.js {version} is unsupported; install Node.js 22.12+ and rerun.")
    if environment.exists():
        if not (environment / "pyvenv.cfg").is_file() or not python.is_file():
            raise ValueError(f"{environment} is not a usable virtual environment; preserve or move it before retrying.")
        version = runner([python, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                         cwd=checkout, capture=True).stdout.strip()
        if not (3, 11) <= tuple(map(int, version.split("."))) < (3, 15):
            raise ValueError(f"Existing .venv uses Python {version}; recreate it with Python 3.11–3.14.")
    print("Prerequisites ready.", flush=True)
    if args.check:
        print("Check only: no files or packages changed.")
        return
    if not python.exists():
        print("[1/4] Creating .venv", flush=True)
        runner([sys.executable, "-m", "venv", environment], cwd=checkout)
    else:
        print("[1/4] Reusing .venv", flush=True)
    print("[2/4] Installing CAD-Harness" + (" framework" if args.framework_only else " with MCP and Studio"), flush=True)
    target = str(checkout) + ("" if args.framework_only else "[mcp,studio]")
    runner([python, "-m", "pip", "install", "-e", target], cwd=checkout)
    if npm:
        print("[3/4] Installing and building the Studio canvas", flush=True)
        # Resolve npm.cmd on Windows and let cmd launch that batch entrypoint.
        command = ["cmd.exe", "/d", "/c", npm] if sys.platform == "win32" else [npm]
        runner([*command, "ci"], cwd=checkout / "studio/web")
        runner([*command, "run", "build"], cwd=checkout / "studio/web")
    else:
        print("[3/4] Framework mode: no frontend needed", flush=True)
    print("[4/4] Checking the example CAD project", flush=True)
    runner([python, "-m", "cadharness", "verify", checkout / "examples/nema17-mount", "--summary"], cwd=checkout)
    if args.framework_only:
        print("\nFramework ready. Use the interpreter in .venv; activation is optional.")
        return
    command = [python, "-m", "cadharness", "mcp-config", *map(str, roots), "--studio", "--studio-port", str(args.port)]
    if workspace:
        command.extend(("--studio-workspace", str(workspace)))
    config = json.loads(runner(command, cwd=checkout, capture=True).stdout)
    destination = Path(args.config).expanduser().resolve() if args.config else checkout / ".cadharness/mcp.json"
    if destination.exists() and not args.overwrite_config:
        if json.loads(destination.read_text(encoding="utf-8")) != config:
            raise ValueError(f"Keeping existing config at {destination}. Choose --config PATH or explicitly use --overwrite-config.")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"\nSetup complete. MCP configuration: {destination}")
    print("Add its cadharness entry to your MCP host and restart the host once.")
    print("The host starts Studio; call studio_status for the viewer URL.")
    print("No host settings or saved designs were changed.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Set up CAD-Harness from a checkout with one command.")
    parser.add_argument("--framework-only", action="store_true", help="install/check the framework without Node.js, MCP, or Studio")
    parser.add_argument("--check", action="store_true", help="check prerequisites without changing files or installing packages")
    parser.add_argument("--root", action="append", help="explicit trusted MCP root; repeat for several (default: this checkout)")
    parser.add_argument("--workspace", help="Studio workspace inside an explicit root")
    parser.add_argument("--port", type=int, default=8741)
    parser.add_argument("--config", help="generated MCP JSON path (default: .cadharness/mcp.json)")
    parser.add_argument("--overwrite-config", action="store_true", help="replace a differing generated config at the selected path")
    args = parser.parse_args(argv)
    try:
        prepare(args)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"\nSetup stopped: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr, file=sys.stderr)
        print("Fix the reported issue and rerun the same command. Existing designs are preserved.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
