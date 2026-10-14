"""Bounded MCP transport for trusted, source-backed cadharness projects."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any, Iterable

from mcp.server import MCPServer

from .diagnostics import package_version
from .operations import (
    compare_project,
    discover_projects,
    export_project,
    inspect_project,
    inspector_project,
    preview_project,
    snapshot_project,
    validate_project,
)
from .schema import schema_catalog


def _configured_roots(cli_roots: Iterable[str] | None = None) -> tuple[Path, ...]:
    values = list(cli_roots or ())
    if not values:
        raw = os.environ.get("CADHARNESS_PROJECT_ROOTS", "")
        values = [value for value in raw.split(os.pathsep) if value]
    if not values:
        values = [str(Path.cwd())]
    return tuple(Path(value).expanduser().resolve() for value in values)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cadharness-mcp",
        description="Run the cadHarness MCP server over stdio.",
    )
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        help="trusted project root; repeat for multiple roots",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {package_version()}"
    )
    return parser


def _resolve_in_roots(path: str, roots: Iterable[Path]) -> Path:
    candidate = Path(path).expanduser()
    attempts = [candidate] if candidate.is_absolute() else [root / candidate for root in roots]
    for attempt in attempts:
        resolved = attempt.resolve()
        if any(resolved == root or root in resolved.parents for root in roots):
            return resolved
    allowed = ", ".join(str(root) for root in roots)
    raise ValueError(f"project path is outside CADHARNESS_PROJECT_ROOTS: {allowed}")


ROOTS = _configured_roots()
mcp = MCPServer(
    "cadHarness",
    version=package_version(),
    instructions=(
        "Inspect and validate trusted source-backed build123d projects. "
        "Project factories execute local Python and are restricted to configured roots."
    ),
)


@mcp.tool()
def get_cadharness_status() -> dict[str, Any]:
    """Report server version, configured trust roots, and discovered projects."""
    root_status = [
        {"path": str(root), "exists": root.is_dir()}
        for root in ROOTS
    ]
    projects = sum((discover_projects(root) for root in ROOTS if root.is_dir()), [])
    return {
        "version": package_version(),
        "roots": root_status,
        "project_count": len(projects),
        "projects": projects,
        "security": "Project factories execute trusted local Python within these roots.",
    }


@mcp.tool()
def list_cad_schemas() -> dict[str, Any]:
    """List supported public JSON document schemas and top-level keys."""
    return schema_catalog()


@mcp.tool()
def list_cad_projects() -> dict[str, Any]:
    """List cadharness manifests beneath the configured project roots."""
    return {
        "roots": [str(root) for root in ROOTS],
        "projects": sum((discover_projects(root) for root in ROOTS), []),
    }


@mcp.tool()
def inspect_cad_project(
    project_path: str, variant: str | None = None
) -> dict[str, Any]:
    """Build a trusted project and return parameters, components, and OCCT metrics."""
    return inspect_project(_resolve_in_roots(project_path, ROOTS), variant=variant)


@mcp.tool()
def build_cad_inspector(
    project_path: str,
    output_file: str = ".cadharness/inspector/index.html",
    views: list[str] | None = None,
    component_ids: list[str] | None = None,
    variant: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate a linked, read-only HTML evidence report inside the project."""
    return inspector_project(
        _resolve_in_roots(project_path, ROOTS),
        output_file=output_file,
        views=views or ["iso", "top"],
        component_ids=component_ids,
        variant=variant,
        overwrite=overwrite,
    )


@mcp.tool()
def validate_cad_project(
    project_path: str, variant: str | None = None
) -> dict[str, Any]:
    """Run geometry checks and source-defined engineering assertions."""
    return validate_project(_resolve_in_roots(project_path, ROOTS), variant=variant)


@mcp.tool()
def snapshot_cad_project(
    project_path: str,
    output_file: str = ".cadharness/baseline.json",
    variant: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Save deterministic geometry and validation evidence inside the project."""
    return snapshot_project(
        _resolve_in_roots(project_path, ROOTS),
        output_file=output_file,
        variant=variant,
        overwrite=overwrite,
    )


@mcp.tool()
def compare_cad_project(
    project_path: str,
    baseline_file: str = ".cadharness/baseline.json",
    variant: str | None = None,
    policy_file: str | None = None,
    output_file: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Compare current source-built geometry with a saved project snapshot."""
    return compare_project(
        _resolve_in_roots(project_path, ROOTS),
        baseline_file=baseline_file,
        variant=variant,
        policy_file=policy_file,
        output_file=output_file,
        overwrite=overwrite,
    )


@mcp.tool()
def preview_cad_project(
    project_path: str,
    output_dir: str = ".cadharness/previews",
    views: list[str] | None = None,
    component_ids: list[str] | None = None,
    variant: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate hidden-line SVG views inside the project root."""
    return preview_project(
        _resolve_in_roots(project_path, ROOTS),
        output_dir=output_dir,
        views=views or ["iso"],
        component_ids=component_ids,
        variant=variant,
        overwrite=overwrite,
    )


@mcp.tool()
def export_cad_project(
    project_path: str,
    file_format: str = "step",
    output_dir: str = "exports/cadharness",
    component_ids: list[str] | None = None,
    variant: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Explicitly export a project or selected components inside its project root."""
    return export_project(
        _resolve_in_roots(project_path, ROOTS),
        file_format=file_format,
        output_dir=output_dir,
        component_ids=component_ids,
        variant=variant,
        overwrite=overwrite,
    )


def main(argv: Iterable[str] | None = None) -> None:
    global ROOTS
    args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    ROOTS = _configured_roots(args.roots)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
