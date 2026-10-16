"""Exercise the public demo CLI and its UI through isolated Playwriter.

Run with the installed interpreter to verify a wheel outside its checkout.
No personal browser, MCP host configuration, model account, or release upload.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from cadharness.studio.processes import terminate_tree
from cadharness.paths import PACKAGE_ROOT

SCRIPT = Path(__file__).with_name("verify_demo_browser.js")


def main():
    # Playwriter snapshots contain Unicode even on redirected Windows consoles.
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new evidence directory")
    parser.add_argument("--require-installed", action="store_true", help="require package imports from this interpreter's environment")
    args = parser.parse_args()
    if args.require_installed and not PACKAGE_ROOT.is_relative_to(Path(sys.prefix).resolve()):
        parser.error(f"Expected the installed wheel in {sys.prefix}; imported {PACKAGE_ROOT}")
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    workspace = directory / "workspace"
    command = [sys.executable, "-m", "cadharness", "demo", "--workspace", str(workspace), "--no-browser"]
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}

    def playwriter(*args):
        argv = ["npx", "-y", "playwriter@latest", *map(str, args)]
        if os.name == "nt":
            argv = ["cmd", "/d", "/s", "/c", *argv]
        result = subprocess.run(argv, cwd=directory, capture_output=True, text=True, encoding="utf-8", timeout=60)
        if result.returncode or 'Error executing code:' in result.stdout:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout

    with (directory / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=directory, stdout=log, stderr=log,
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **flags)
        session = None
        try:
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Demo exited before startup; inspect server.log")
                match = re.search(r"CAD-Harness demo: (http://127.0.0.1:\d+)", (directory / "server.log").read_text(encoding="utf-8", errors="replace"))
                if match:
                    try:
                        with urlopen(match[1] + "/api/session", timeout=2) as response:
                            metadata = json.load(response)
                        break
                    except URLError:
                        pass
                time.sleep(.1)
            else:
                raise TimeoutError("Demo did not start within five minutes")
            assert metadata["demo"] and not metadata["authorized"]
            before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in workspace.rglob("*") if path.is_file()
                      and (path.name in {"run.json", "scene.json", "project.py", "cadharness.toml"}
                           or path.name.startswith("brief-v"))}
            assert not list(workspace.rglob("*.step")) and not list(workspace.rglob("*.stl"))
            (directory / "browser-config.json").write_text(json.dumps({"url": match[1], "artifacts": str(directory)}), encoding="utf-8")
            created = playwriter("session", "new", "--browser", "headless")
            session = re.search(r"Session (\d+) created", created).group(1)
            for index in range(45):
                result = playwriter("-s", session, "--timeout", "45000", "-f", SCRIPT)
                (directory / f"step-{index:02d}.log").write_text(result, encoding="utf-8")
                print(result.strip(), flush=True)
                if "Next: done" in result:
                    break
            else:
                raise RuntimeError("Demo browser flow did not finish")
            assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in before.items())
            for suffix in ("step", "stl"):
                files = list(workspace.rglob(f"*.{suffix}"))
                assert len(files) == 1 and files[0].name == f"plate-standard.{suffix}", files
            (directory / "result.json").write_text(json.dumps({"passed": True, "demo": metadata["demo"],
                "source_and_evidence_unchanged": True, "exports": ["plate-standard.step", "plate-standard.stl"],
                "browser_steps": index + 1, "package_path": str(PACKAGE_ROOT)}, indent=2), encoding="utf-8")
        finally:
            try:
                if session:
                    playwriter("session", "delete", session)
            finally:
                terminate_tree(process)
                process.wait(timeout=10)
    print(f"Demo acceptance passed: {directory}")


if __name__ == "__main__":
    main()
