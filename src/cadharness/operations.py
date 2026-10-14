"""Agent-friendly project operations shared by CLI and MCP transports."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

from build123d import Compound, export_step, export_stl

from .model import shape_metrics
from .project import LoadedProject, discover_projects, load_project


_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_.-]+")


def inspect_project(path: str | Path) -> dict:
    loaded = load_project(path)
    report = loaded.document.inspect()
    report["manifest"] = {
        "path": str(loaded.manifest_path),
        "description": loaded.manifest.description,
    }
    return report


def validate_project(path: str | Path) -> dict:
    loaded = load_project(path)
    report = loaded.document.validate().to_dict()
    report["manifest_path"] = str(loaded.manifest_path)
    return report


def _contained_path(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"path must stay within {resolved_root}") from exc
    return resolved


def export_project(
    path: str | Path,
    *,
    output_dir: str | Path = "exports/cadharness",
    file_format: str = "step",
    component_ids: Iterable[str] | None = None,
    overwrite: bool = False,
) -> dict:
    """Explicitly export selected components or the whole built document."""
    loaded = load_project(path)
    normalized_format = file_format.lower()
    if normalized_format not in {"step", "stl"}:
        raise ValueError("file_format must be 'step' or 'stl'")

    output_candidate = Path(output_dir)
    if not output_candidate.is_absolute():
        output_candidate = loaded.root / output_candidate
    target_dir = _contained_path(loaded.root, output_candidate)
    target_dir.mkdir(parents=True, exist_ok=True)

    selected = list(component_ids or [])
    if selected:
        unknown = sorted(set(selected) - set(loaded.document.components))
        if unknown:
            raise KeyError(f"unknown component ids: {', '.join(unknown)}")
        export_items = [
            (component_id, loaded.document.components[component_id].shape)
            for component_id in selected
        ]
    else:
        shapes = [component.shape for component in loaded.document.components.values()]
        export_items = [
            (
                loaded.document.id,
                Compound(label=loaded.document.id, children=shapes),
            )
        ]

    outputs = []
    exporter = export_step if normalized_format == "step" else export_stl
    for item_id, shape in export_items:
        filename = _SAFE_NAME.sub("-", item_id).strip("-.")
        output_path = target_dir / f"{filename}.{normalized_format}"
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing export: {output_path}")
        exporter(shape, output_path)
        outputs.append(
            {
                "component_id": item_id,
                "path": str(output_path),
                "geometry": shape_metrics(shape),
            }
        )
    return {
        "project_id": loaded.document.id,
        "format": normalized_format,
        "outputs": outputs,
    }


__all__ = [
    "discover_projects",
    "export_project",
    "inspect_project",
    "validate_project",
]

