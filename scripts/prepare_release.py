"""Prepare GitHub prerelease assets from a validated distribution; never publish.

Run from the same source revision that produced the archives. The CI job runs
this only after distribution and browser acceptance have succeeded.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tomllib

try:
    from scripts.smoke_distribution import ROOT, check_archives
except ModuleNotFoundError:
    from smoke_distribution import ROOT, check_archives


def prepare(validated, output, *, tag, ci_run_url=None, root=ROOT):
    validated, output = Path(validated), Path(output)
    if output.exists():
        raise ValueError(f"Keeping existing release evidence at {output}.")
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if tag != f"v{version}" or not re.fullmatch(r"\d+\.\d+\.\d+b\d+", version):
        raise ValueError("Tag must match the project's beta version exactly.")
    names = (f"cad_harness-{version}-py3-none-any.whl", f"cad_harness-{version}.tar.gz")
    expected_sums = "".join(f"{hashlib.sha256((validated / name).read_bytes()).hexdigest()}  {name}\n"
                            for name in names)
    if (validated / "SHA256SUMS").read_text(encoding="utf-8") != expected_sums:
        raise ValueError("Validated distribution checksums do not match the candidate.")
    check_archives(*(validated / name for name in names), root=root)
    inventory = json.loads((validated / "DEPENDENCIES.json").read_text(encoding="utf-8"))
    packages = {item["name"].lower().replace("_", "-"): item["version"] for item in inventory["packages"]}
    if inventory.get("schema") != "cadharness.dependency-inventory" or packages.get("cad-harness") != version:
        raise ValueError("Dependency inventory does not describe this candidate.")
    if not {"build123d", "cadquery-ocp-novtk", "mcp", "starlette", "uvicorn"} <= packages.keys():
        raise ValueError("Dependency inventory must come from the full extras installation.")
    notes = root / "docs/releases" / f"{version}.md"
    if not notes.read_text(encoding="utf-8").startswith(f"# CAD-Harness {version}"):
        raise ValueError("Release notes do not match this candidate.")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, text=True).strip())
    output.mkdir(parents=True)
    for name in (*names, "DEPENDENCIES.json"):
        shutil.copyfile(validated / name, output / name)
    shutil.copyfile(notes, output / "RELEASE_NOTES.md")
    (output / "BUILD.json").write_text(json.dumps({
        "version": version, "tag": tag, "commit": commit, "tracked_source_dirty": dirty,
        "ci_run_url": ci_run_url, "prerelease": True,
        "scope": "CAD-Harness wheel and sdist; dependencies installed separately",
    }, indent=2) + "\n", encoding="utf-8")
    (output / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(output.iterdir())), encoding="utf-8")
    print(f"Prepared {tag} at {output}; source commit {commit}; tracked changes: {dirty}. No publication.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--ci-run-url")
    args = parser.parse_args()
    prepare(args.validated, args.output, tag=args.tag, ci_run_url=args.ci_run_url)
