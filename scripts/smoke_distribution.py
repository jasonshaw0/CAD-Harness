"""Build an sdist and its wheel; exercise the install outside the checkout.

Requires the development tool `build` and a built Studio frontend.
Use --fresh-install to resolve dependencies in a clean venv (the CI gate).
Without it, reuse development dependencies for a faster local smoke check.
"""

import argparse
from email.parser import BytesParser
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tarfile
from tempfile import TemporaryDirectory
import tomllib
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_RESOURCES = (
    "workflow/CONTRACTS.md", "workflow/AUTHORING.md", "workflow/prompts/workflow.md",
    "workflow/benchmarks/prompts/square-mount.txt",
    *(f"workflow/templates/{template}/{name}" for template in
      ("mounting-plate", "flange", "enclosure") for name in ("project.py", "cadharness.toml")),
    "studio/web/index.html",
)


def check_archives(wheel, sdist, *, root=ROOT):
    """Compare installed source/resources with the checkout in both artifacts."""
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package = root / "src/cadharness"
    expected = {f"cadharness/{name}": package / name for name in REQUIRED_RESOURCES}
    for path in package.rglob("*.py"):
        expected[path.relative_to(root / "src").as_posix()] = path
    for name, patterns in config["tool"]["setuptools"]["package-data"].items():
        for pattern in patterns:
            for path in (root / "src" / name.replace(".", "/")).glob(pattern):
                if path.is_file():
                    expected[path.relative_to(root / "src").as_posix()] = path
    web = package / "studio/web"
    if not list((web / "assets").glob("renderView-*.js")):
        raise ValueError("Missing Studio render chunk; rebuild the frontend before packaging.")
    # Include every generated asset, including future nested Vite output.
    for path in web.rglob("*"):
        if path.is_file():
            expected[path.relative_to(root / "src").as_posix()] = path
    with zipfile.ZipFile(wheel) as whl, tarfile.open(sdist) as source:
        roots = {name.split("/")[0] for name in source.getnames()}
        if len(roots) != 1:
            raise ValueError("Source distribution must have one top-level directory.")
        prefix, = roots
        for name, path in expected.items():
            if not path.is_file():
                raise ValueError(f"Required packaging input missing: {name}")
            try:
                source_file = source.extractfile(f"{prefix}/src/{name}")
                source_bytes = source_file.read() if source_file else None
                wheel_bytes = whl.read(name)
            except KeyError as exc:
                raise ValueError(f"Missing distribution resource: {name}") from exc
            if wheel_bytes != path.read_bytes() or source_bytes != wheel_bytes:
                raise ValueError(f"Distribution resource differs from checkout: {name}")
        expected_web = {name for name in expected if name.startswith("cadharness/studio/web/")}
        actual_web = {name for name in whl.namelist() if name.startswith("cadharness/studio/web/") and not name.endswith("/")}
        if actual_web != expected_web:
            raise ValueError("Wheel contains stale Studio assets; rebuild from clean inputs.")
        metadata, = [name for name in whl.namelist() if name.endswith(".dist-info/METADATA")]
        for raw in (whl.read(metadata), source.extractfile(f"{prefix}/PKG-INFO").read()):
            headers = BytesParser().parsebytes(raw)
            if (headers["Name"], headers["Version"]) != (config["project"]["name"], config["project"]["version"]):
                raise ValueError("Distribution name/version differs from pyproject.toml.")
    print(f"Wheel and sdist match {len(expected)} source/resource files.", flush=True)


def run(*args, cwd):
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True, env=environment)


def main(*, render_browser=False, fresh_install=False, output=None):
    if not (ROOT / "src/cadharness/studio/web/index.html").is_file():
        raise SystemExit("Build the canvas first: npm --prefix studio/web run build")
    if importlib.util.find_spec("build") is None:
        raise SystemExit("Install the packaging test tool: python -m pip install build")
    if output is not None:
        output = Path(output).resolve()
        if output.exists():
            raise SystemExit(f"Keeping existing output at {output}; choose a new --output directory.")
    with TemporaryDirectory(prefix="cadharness-wheel-") as directory:
        work = Path(directory)
        # Default build creates an sdist, then builds its wheel in an isolated
        # extracted tree. Do not use --sdist --wheel (both build from checkout).
        run(sys.executable, "-m", "build", ROOT, "--outdir", work, cwd=work)
        wheel, = work.glob("cad_harness-*.whl")
        sdist, = work.glob("cad_harness-*.tar.gz")
        check_archives(wheel, sdist)
        env = work / "venv"
        venv.EnvBuilder(with_pip=True).create(env)
        python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        # A child venv's system-site-packages points at base Python, not this
        # command's active venv. Process dependency .pth hooks as well (pywin32
        # needs them). The import assertion below guards wheel precedence over
        # any inherited editable-install path.
        site = env / ("Lib/site-packages" if sys.platform == "win32" else
                      f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
        if fresh_install:
            print("Installing wheel extras with fresh dependencies (no borrowed packages).", flush=True)
            run(python, "-m", "pip", "install", f"{wheel}[mcp,studio]", cwd=work)
            run(python, "-m", "pip", "check", cwd=work)
        else:
            print("Fast smoke mode: borrowing development dependencies.", flush=True)
            (site / "smoke-dependencies.pth").write_text(
                f"import site; site.addsitedir({sysconfig.get_paths()['purelib']!r})\n", encoding="utf-8")
            run(python, "-m", "pip", "install", "--no-deps", "--force-reinstall", wheel, cwd=work)
        # The real stdio test runs from an unrelated cwd, using installed templates,
        # contracts, workers, API, failed measurement, frozen repair, and STL export.
        shutil.copyfile(ROOT / "tests/workflow/test_studio_mcp.py", work / "test_studio_mcp.py")
        shutil.copyfile(ROOT / "tests/workflow/test_studio_rendering.py", work / "test_studio_rendering.py")
        smoke = work / "check_install.py"
        smoke.write_text('''from pathlib import Path
import re
import sys
from starlette.testclient import TestClient
import cadharness
from cadharness.paths import PACKAGE_ROOT, WORKFLOW_ROOT
from cadharness.studio.server import create_app
assert PACKAGE_ROOT.is_relative_to(Path(sys.prefix)), cadharness.__file__
assert (WORKFLOW_ROOT / "CONTRACTS.md").is_file()
assert (WORKFLOW_ROOT / "AUTHORING.md").is_file()
assert list((PACKAGE_ROOT / 'studio/web/assets').glob('renderView-*.js'))
from cadharness.guidance import authoring_guide
from cadharness.diagnostics import package_version
assert package_version() != 'uninstalled'
assert authoring_guide()['version'] == '1'
assert (WORKFLOW_ROOT / "prompts/workflow.md").is_file()
assert (WORKFLOW_ROOT / "benchmarks/prompts/square-mount.txt").is_file()
with TestClient(create_app(Path.cwd() / "workspace")) as client:
    page = client.get("/")
    assert page.status_code == 200 and "CAD-Harness" in page.text
    assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.text)
    assert assets
    for asset in assets:
        assert client.get(asset).status_code == 200, asset
print("Installed wheel resources and canvas passed:", PACKAGE_ROOT)
''', encoding="utf-8")
        run(python, smoke, cwd=work)
        run(python, "-m", "cadharness", "--help", cwd=work)
        scripts = env / ("Scripts" if sys.platform == "win32" else "bin")
        extension = ".exe" if sys.platform == "win32" else ""
        for command in ("cad-harness", "cad-harness-mcp", "cadharness", "cadharness-mcp"):
            run(scripts / (command + extension), "--help", cwd=work)
        run(python, "-m", "unittest", "test_studio_mcp", "test_studio_rendering", "-v", cwd=work)
        if render_browser:
            # Use the permanent repository acceptance runner with the installed
            # interpreter; its server and CAD workspace are outside the checkout.
            run(python, ROOT / 'scripts/verify_studio_rendering.py',
                '--output', work / 'rendering-acceptance', cwd=work)
        if output is not None:
            output.mkdir(parents=True)
            for artifact in (wheel, sdist):
                shutil.copyfile(artifact, output / artifact.name)
            (output / "SHA256SUMS").write_text("".join(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
                for path in (wheel, sdist)), encoding="utf-8")
            print(f"Validated artifacts: {output}")
    print("Distribution smoke passed outside the checkout.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-browser', action='store_true',
                        help='Also exercise real PNG capture using isolated Playwriter (Chrome required)')
    parser.add_argument('--fresh-install', action='store_true',
                        help='Install wheel extras and all dependencies in a clean venv without borrowing packages')
    parser.add_argument('--output', type=Path,
                        help='Retain artifacts and SHA256SUMS after success; directory must not exist')
    args = parser.parse_args()
    main(render_browser=args.render_browser, fresh_install=args.fresh_install, output=args.output)
