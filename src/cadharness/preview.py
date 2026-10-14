"""Headless hidden-line SVG previews built from build123d projections."""

from __future__ import annotations

from hashlib import sha256
from math import sqrt
from pathlib import Path
from typing import Iterable

from build123d import Compound, ExportSVG, LineType, Shape, Vector

from .model import CADDocument


VIEW_NAMES = ("iso", "top", "front", "right")


def _camera(shape: Shape, view: str) -> tuple[Vector, Vector, Vector]:
    if view not in VIEW_NAMES:
        raise ValueError(f"view must be one of {', '.join(VIEW_NAMES)}")
    bbox = shape.bounding_box()
    center = bbox.center()
    size = bbox.size
    diagonal = max(sqrt(size.X**2 + size.Y**2 + size.Z**2), 1.0)
    if view == "top":
        return center + Vector(0, 0, diagonal * 2), Vector(0, 1, 0), center
    if view == "front":
        return center + Vector(0, -diagonal * 2, 0), Vector(0, 0, 1), center
    if view == "right":
        return center + Vector(diagonal * 2, 0, 0), Vector(0, 0, 1), center
    return (
        center + Vector(diagonal * 1.5, -diagonal * 1.5, diagonal * 1.2),
        Vector(0, 0, 1),
        center,
    )


def _preview_shape(document: CADDocument, component_ids: Iterable[str] | None) -> Shape:
    selected = list(component_ids or [])
    if selected:
        unknown = sorted(set(selected) - set(document.components))
        if unknown:
            raise KeyError(f"unknown component ids: {', '.join(unknown)}")
        shapes = [document.components[name].shape for name in selected]
    else:
        shapes = [component.shape for component in document.components.values()]
    if len(shapes) == 1:
        return shapes[0]
    return Compound(label=document.id, children=shapes)


def write_svg_previews(
    document: CADDocument,
    output_dir: Path,
    *,
    views: Iterable[str] = ("iso",),
    component_ids: Iterable[str] | None = None,
    artifact_id: str | None = None,
    overwrite: bool = False,
) -> list[dict]:
    """Write orthographic hidden-line previews and return measured evidence."""
    shape = _preview_shape(document, component_ids)
    normalized_views = list(dict.fromkeys(view.lower() for view in views))
    if not normalized_views:
        raise ValueError("at least one preview view is required")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for view in normalized_views:
        camera, up, look_at = _camera(shape, view)
        visible, hidden = shape.project_to_viewport(camera, up, look_at)
        projected = list(visible) + list(hidden)
        if not projected:
            raise RuntimeError(f"{view} projection produced no edges")
        projected_bounds = Compound(children=projected).bounding_box()
        projected_size = projected_bounds.size
        max_dimension = max(projected_size.X, projected_size.Y, 1.0)
        target = output_dir / f"{artifact_id or document.id}-{view}.svg"
        if target.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing preview: {target}")

        exporter = ExportSVG(scale=160.0 / max_dimension, margin=5.0, line_weight=0.18)
        exporter.add_layer(
            "visible",
            fill_color=None,
            line_color=0x111827,
            line_weight=0.22,
            line_type=LineType.CONTINUOUS,
        )
        exporter.add_layer(
            "hidden",
            fill_color=None,
            line_color=0x9CA3AF,
            line_weight=0.13,
            line_type=LineType.ISO_DASH,
        )
        exporter.add_shape(visible, layer="visible")
        if hidden:
            exporter.add_shape(hidden, layer="hidden")
        exporter.write(target)
        content = target.read_bytes()
        outputs.append(
            {
                "view": view,
                "path": str(target),
                "visible_edges": len(visible),
                "hidden_edges": len(hidden),
                "sha256": sha256(content).hexdigest(),
                "bytes": len(content),
            }
        )
    return outputs


__all__ = ["VIEW_NAMES", "write_svg_previews"]
