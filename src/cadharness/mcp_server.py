"""Bounded MCP transport for trusted, source-backed CAD-Harness projects."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any, Iterable

from mcp.server import MCPServer

from .diagnostics import package_version
from .guidance import SERVER_INSTRUCTIONS, authoring_guide
from .operations import (
    compare_project,
    discover_projects,
    export_project,
    inspect_project,
    inspector_project,
    measure_project,
    preview_project,
    snapshot_project,
    validate_project,
    verify_project,
)
from .schema import schema_catalog
from .verification import VerificationPolicy
from .measurements import ComputationalTolerance


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
        prog="cad-harness-mcp",
        description="Run the CAD-Harness MCP server over stdio.",
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
    parser.add_argument("--studio", action="store_true", help="serve the local Studio canvas and IDE authoring tools")
    parser.add_argument("--studio-port", type=int, default=8741)
    parser.add_argument("--studio-workspace", type=Path, help="Studio store within a configured trusted root")
    return parser


def _resolve_in_roots(path: str, roots: Iterable[Path]) -> Path:
    candidate = Path(path).expanduser()
    attempts = (
        [candidate] if candidate.is_absolute() else [root / candidate for root in roots]
    )
    for attempt in attempts:
        resolved = attempt.resolve()
        if any(resolved == root or root in resolved.parents for root in roots):
            return resolved
    allowed = ", ".join(str(root) for root in roots)
    raise ValueError(f"project path is outside CADHARNESS_PROJECT_ROOTS: {allowed}")


ROOTS = _configured_roots()
mcp = MCPServer(
    "CAD-Harness",
    version=package_version(),
    instructions=SERVER_INSTRUCTIONS,
)


@mcp.tool()
def get_cad_authoring_guide() -> dict[str, Any]:
    """Read packaged workflow and adaptive visual-review guidance before first authoring. No personal skills required."""
    return authoring_guide()


@mcp.tool()
def get_cadharness_status() -> dict[str, Any]:
    """Report server version, configured trust roots, and discovered projects."""
    root_status = [{"path": str(root), "exists": root.is_dir()} for root in ROOTS]
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
    """List CAD-Harness manifests beneath the configured project roots."""
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
def measure_cad_project(
    project_path: str,
    measurement_type: str,
    component_ids: list[str],
    measurement_id: str = "measurement",
    variant: str | None = None,
    radius_min_mm: float | None = None,
    radius_max_mm: float | None = None,
    axis_direction: list[float] | None = None,
    axis_location_mm: list[float] | None = None,
    axis_angular_tolerance_deg: float = 0.1,
    location_tolerance_mm: float = 1e-4,
    concavity: str = "concave",
    sample_points_mm: list[list[float]] | None = None,
    direction: list[float] | None = None,
    tolerance: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Measure cylindrical features, hole patterns, solid clearance, or directional chords."""
    project = _resolve_in_roots(project_path, ROOTS)
    return measure_project(
        project,
        measurement_type=measurement_type,
        component_ids=component_ids,
        measurement_id=measurement_id,
        variant=variant,
        radius_min_mm=radius_min_mm,
        radius_max_mm=radius_max_mm,
        axis_direction=axis_direction,
        axis_location_mm=axis_location_mm,
        axis_angular_tolerance_deg=axis_angular_tolerance_deg,
        location_tolerance_mm=location_tolerance_mm,
        concavity=concavity,
        sample_points_mm=sample_points_mm,
        direction=direction,
        tolerance=(
            ComputationalTolerance(**tolerance)
            if tolerance is not None
            else ComputationalTolerance()
        ),
    )


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
def verify_cad_project(
    project_path: str,
    baseline_file: str | None = None,
    variant: str | None = None,
    policy_file: str | None = None,
    gate_policy: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Gate current geometry and requirements; comparison remains separate evidence."""
    gates = VerificationPolicy(**gate_policy) if gate_policy else None
    return verify_project(
        _resolve_in_roots(project_path, ROOTS),
        baseline_file=baseline_file,
        variant=variant,
        policy_file=policy_file,
        gate_policy=gates,
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
    studio = None
    try:
        if args.studio:
            from .studio.mcp import connect_studio, register_tools
            workspace = args.studio_workspace or ROOTS[0] / "runs/studio"
            workspace = _resolve_in_roots(str(workspace), ROOTS)
            library_root = next(root for root in ROOTS if workspace.is_relative_to(root))
            studio = connect_studio(workspace, port=args.studio_port, library_root=library_root, trusted_roots=ROOTS)
            register_tools(mcp, studio)
        mcp.run(transport="stdio")
    finally:
        if studio:
            studio.close()


if __name__ == "__main__":
    main()
