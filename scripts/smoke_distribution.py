"""Build/install a full wheel and exercise it outside the source checkout.

Run after the Studio frontend build, using an environment with [mcp,studio].
The temporary venv inherits dependencies but must import CAD-Harness from its wheel.
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
from tempfile import TemporaryDirectory
import venv

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd):
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def main(*, render_browser=False):
    if not (ROOT / "src/cadharness/studio/web/index.html").is_file():
        raise SystemExit("Build the canvas first: npm --prefix studio/web run build")
    with TemporaryDirectory(prefix="cadharness-wheel-") as directory:
        work = Path(directory)
        run(sys.executable, "-m", "pip", "wheel", ROOT, "--no-deps", "--wheel-dir", work, cwd=work)
        wheel, = work.glob("cad_harness-*.whl")
        env = work / "venv"
        venv.EnvBuilder(with_pip=True).create(env)
        python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        # A child venv's system-site-packages points at base Python, not this
        # command's active venv. Process dependency .pth hooks as well (pywin32
        # needs them). The import assertion below guards wheel precedence over
        # any inherited editable-install path.
        site = env / ("Lib/site-packages" if sys.platform == "win32" else
                      f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
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
    print("Distribution smoke passed outside the checkout.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-browser', action='store_true',
                        help='Also exercise real PNG capture using isolated Playwriter (Chrome required)')
    main(render_browser=parser.parse_args().render_browser)
