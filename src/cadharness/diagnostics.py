"""Installation and workspace diagnostics for CLI and MCP setup."""

from __future__ import annotations

from importlib import metadata, util
from pathlib import Path
import platform
import shutil
import sys
from typing import Any

from .project import discover_projects


def package_version(distribution: str = "CAD-Harness") -> str:
    """Return installed distribution version without failing from a source tree."""
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return "uninstalled"


def doctor_report(root: str | Path = ".") -> dict[str, Any]:
    """Describe the active installation and project discovery environment."""
    scan_root = Path(root).expanduser().resolve()
    module_path = Path(__file__).resolve()
    checkout = module_path.parents[2]
    projects = discover_projects(scan_root) if scan_root.is_dir() else []
    mcp_available = util.find_spec("mcp") is not None
    warnings = []
    if not scan_root.is_dir():
        warnings.append(f"scan root does not exist or is not a directory: {scan_root}")
    elif not projects:
        warnings.append(f"no cadharness.toml projects found beneath {scan_root}")
    if not mcp_available:
        warnings.append('MCP extra is not installed; run: python -m pip install -e ".[mcp]"')
    if shutil.which("cadharness") is None:
        warnings.append("cadharness console script is not on PATH")
    if shutil.which("cadharness-mcp") is None:
        warnings.append("cadharness-mcp console script is not on PATH")
    return {
        "status": "warning" if warnings else "ok",
        "cadharness": {
            "version": package_version(),
            "module": str(module_path.parent),
            "checkout": str(checkout),
        },
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "mcp": {
            "available": mcp_available,
            "version": package_version("mcp") if mcp_available else None,
        },
        "commands": {
            "cadharness": shutil.which("cadharness"),
            "cadharness_mcp": shutil.which("cadharness-mcp"),
        },
        "workspace": {
            "cwd": str(Path.cwd()),
            "scan_root": str(scan_root),
            "projects": projects,
        },
        "warnings": warnings,
    }


__all__ = ["doctor_report", "package_version"]
