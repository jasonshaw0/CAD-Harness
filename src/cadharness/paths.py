"""Installed resources and checkout defaults; never a source of MCP trust roots."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
WORKFLOW_ROOT = PACKAGE_ROOT / "workflow"
STUDIO_WEB = PACKAGE_ROOT / "studio" / "web"
_checkout = PACKAGE_ROOT.parent.parent
# Editable installs default to the checkout; wheel installs use the caller's cwd.
ROOT = _checkout if (_checkout / "pyproject.toml").is_file() else Path.cwd()
RUNS_ROOT = ROOT / "runs"
