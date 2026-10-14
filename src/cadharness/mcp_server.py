"""Bounded MCP transport for trusted, source-backed cadharness projects."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from mcp.server.fastmcp import FastMCP

from .operations import discover_projects, export_project, inspect_project, validate_project


def _configured_roots() -> tuple[Path, ...]:
    raw = os.environ.get("CADHARNESS_PROJECT_ROOTS", "")
    values = [value for value in raw.split(os.pathsep) if value]
    if not values:
        values = [str(Path.cwd())]
    return tuple(Path(value).expanduser().resolve() for value in values)


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
mcp = FastMCP(
    "cadharness",
    instructions=(
        "Inspect and validate trusted source-backed build123d projects. "
        "Project factories execute local Python and are restricted to configured roots."
    ),
)


@mcp.tool()
def list_cad_projects() -> dict[str, Any]:
    """List cadharness manifests beneath the configured project roots."""
    return {"roots": [str(root) for root in ROOTS], "projects": sum((discover_projects(root) for root in ROOTS), [])}


@mcp.tool()
def inspect_cad_project(project_path: str) -> dict[str, Any]:
    """Build a trusted project and return parameters, components, and OCCT metrics."""
    return inspect_project(_resolve_in_roots(project_path, ROOTS))


@mcp.tool()
def validate_cad_project(project_path: str) -> dict[str, Any]:
    """Run geometry checks and source-defined engineering assertions."""
    return validate_project(_resolve_in_roots(project_path, ROOTS))


@mcp.tool()
def export_cad_project(
    project_path: str,
    file_format: str = "step",
    output_dir: str = "exports/cadharness",
    component_ids: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Explicitly export a project or selected components inside its project root."""
    return export_project(
        _resolve_in_roots(project_path, ROOTS),
        file_format=file_format,
        output_dir=output_dir,
        component_ids=component_ids,
        overwrite=overwrite,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

