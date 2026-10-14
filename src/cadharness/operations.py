"""Agent-friendly project operations shared by CLI and MCP transports."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable

from build123d import Compound, export_step, export_stl

from .inspector import render_inspector
from .model import shape_metrics
from .policy import ComparisonPolicy
from .preview import VIEW_NAMES, write_svg_previews
from .project import LoadedProject, discover_projects, load_project
from .revision import build_snapshot, compare_snapshots
from .verification import VerificationPolicy, verify_document


_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_.-]+")


def _atomic_write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def inspect_project(
    path: str | Path, *, variant: str | None = None
) -> dict[str, Any]:
    loaded = load_project(path, variant=variant)
    report = loaded.document.inspect()
    report["manifest"] = {
        "path": str(loaded.manifest_path),
        "description": loaded.manifest.description,
        "variant": loaded.variant,
        "default_variant": loaded.manifest.default_variant,
        "available_variants": sorted(loaded.manifest.variants),
    }
    return report


def inspector_project(
    path: str | Path,
    *,
    output_file: str | Path = ".cadharness/inspector/index.html",
    views: Iterable[str] = ("iso", "top"),
    component_ids: Iterable[str] | None = None,
    variant: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a linked, read-only HTML evidence artifact inside a project."""
    loaded = load_project(path, variant=variant)
    target = _project_artifact_path(loaded, output_file)
    if target.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("inspector output_file must use an .html or .htm extension")
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing inspector: {target}")

    normalized_views = [view.lower() for view in views]
    invalid = sorted(set(normalized_views) - set(VIEW_NAMES))
    if invalid:
        raise ValueError(f"unknown inspector preview views: {', '.join(invalid)}")
    target.parent.mkdir(parents=True, exist_ok=True)
    preview_dir = target.parent / "previews"
    preview_outputs = write_svg_previews(
        loaded.document,
        preview_dir,
        views=normalized_views,
        component_ids=component_ids,
        artifact_id=(
            f"{loaded.document.id}-{loaded.variant}"
            if loaded.variant
            else loaded.document.id
        ),
        overwrite=overwrite,
    )

    inspection = loaded.document.inspect()
    inspection["manifest"] = {
        "path": str(loaded.manifest_path),
        "description": loaded.manifest.description,
        "variant": loaded.variant,
        "default_variant": loaded.manifest.default_variant,
        "available_variants": sorted(loaded.manifest.variants),
    }
    verification_report = verify_document(
        loaded.document, variant=loaded.variant
    )
    validation = verification_report["validation"]
    previews = [
        {
            "view": output["view"],
            "href": Path(output["path"]).relative_to(target.parent).as_posix(),
        }
        for output in preview_outputs
    ]
    content = render_inspector(
        inspection,
        validation,
        previews=previews,
        verification=verification_report["verification"],
    )
    _atomic_write_text(target, content)
    return {
        "project_id": loaded.document.id,
        "revision": loaded.document.revision,
        "variant": loaded.variant,
        "path": str(target),
        "sha256": sha256(content.encode("utf-8")).hexdigest(),
        "validation_passed": validation["passed"],
        "verification_passed": verification_report["verification"]["passed"],
        "previews": preview_outputs,
    }


def validate_project(
    path: str | Path, *, variant: str | None = None
) -> dict[str, Any]:
    loaded = load_project(path, variant=variant)
    report = loaded.document.validate().to_dict()
    report["manifest_path"] = str(loaded.manifest_path)
    report["variant"] = loaded.variant
    return report


def _contained_path(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"path must stay within {resolved_root}") from exc
    return resolved


def _project_artifact_path(loaded: LoadedProject, candidate: str | Path) -> Path:
    path = Path(candidate)
    if not path.is_absolute():
        path = loaded.root / path
    return _contained_path(loaded.root, path)


def snapshot_project(
    path: str | Path,
    *,
    output_file: str | Path = ".cadharness/baseline.json",
    variant: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build and persist a deterministic engineering snapshot."""
    loaded = load_project(path, variant=variant)
    target = _project_artifact_path(loaded, output_file)
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing snapshot: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot(loaded.document, variant=loaded.variant)
    content = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    _atomic_write_text(target, content)
    return {
        "project_id": loaded.document.id,
        "revision": loaded.document.revision,
        "variant": loaded.variant,
        "path": str(target),
        "sha256": sha256(content.encode("utf-8")).hexdigest(),
        "components": len(snapshot["components"]),
        "checks": len(snapshot["validation"]["results"]),
        "validation_passed": snapshot["validation"]["passed"],
    }


def compare_project(
    path: str | Path,
    *,
    baseline_file: str | Path = ".cadharness/baseline.json",
    variant: str | None = None,
    policy_file: str | Path | None = None,
    output_file: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Compare current source-built geometry with a saved snapshot."""
    loaded = load_project(path, variant=variant)
    baseline_path = _project_artifact_path(loaded, baseline_file)
    with baseline_path.open("r", encoding="utf-8") as stream:
        baseline = json.load(stream)
    configured_policy = policy_file or loaded.manifest.comparison_policy
    if configured_policy:
        policy_path = _project_artifact_path(loaded, configured_policy)
        policy = ComparisonPolicy.from_file(
            policy_path,
            source=policy_path.relative_to(loaded.root).as_posix(),
        )
    else:
        policy = ComparisonPolicy.exact()
    current = build_snapshot(loaded.document, variant=loaded.variant)
    report = compare_snapshots(baseline, current, policy=policy)
    report["baseline_path"] = baseline_path.relative_to(loaded.root).as_posix()
    if output_file is not None:
        target = _project_artifact_path(loaded, output_file)
        if target.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite comparison report: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(report, indent=2, sort_keys=True) + "\n"
        _atomic_write_text(target, content)
        report["output_path"] = str(target)
        report["output_sha256"] = sha256(content.encode("utf-8")).hexdigest()
    return report


def verify_project(
    path: str | Path,
    *,
    baseline_file: str | Path | None = None,
    variant: str | None = None,
    policy_file: str | Path | None = None,
    gate_policy: VerificationPolicy | None = None,
) -> dict[str, Any]:
    """Run the unified current-design verification gate."""
    loaded = load_project(path, variant=variant)
    baseline = None
    baseline_path = None
    if baseline_file is not None:
        baseline_path = _project_artifact_path(loaded, baseline_file)
        with baseline_path.open("r", encoding="utf-8") as stream:
            baseline = json.load(stream)
    configured_policy = policy_file or loaded.manifest.comparison_policy
    if configured_policy:
        policy_path = _project_artifact_path(loaded, configured_policy)
        comparison_policy = ComparisonPolicy.from_file(
            policy_path,
            source=policy_path.relative_to(loaded.root).as_posix(),
        )
    else:
        comparison_policy = ComparisonPolicy.exact()
    report = verify_document(
        loaded.document,
        baseline=baseline,
        variant=loaded.variant,
        comparison_policy=comparison_policy,
        gate_policy=gate_policy,
    )
    if baseline_path is not None:
        report["baseline_path"] = baseline_path.relative_to(loaded.root).as_posix()
    return report


def preview_project(
    path: str | Path,
    *,
    output_dir: str | Path = ".cadharness/previews",
    views: Iterable[str] = ("iso",),
    component_ids: Iterable[str] | None = None,
    variant: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate headless hidden-line SVG views as inspectable artifacts."""
    loaded = load_project(path, variant=variant)
    target_dir = _project_artifact_path(loaded, output_dir)
    normalized_views = [view.lower() for view in views]
    invalid = sorted(set(normalized_views) - set(VIEW_NAMES))
    if invalid:
        raise ValueError(f"unknown preview views: {', '.join(invalid)}")
    outputs = write_svg_previews(
        loaded.document,
        target_dir,
        views=normalized_views,
        component_ids=component_ids,
        artifact_id=(
            f"{loaded.document.id}-{loaded.variant}"
            if loaded.variant
            else loaded.document.id
        ),
        overwrite=overwrite,
    )
    return {
        "project_id": loaded.document.id,
        "revision": loaded.document.revision,
        "variant": loaded.variant,
        "outputs": outputs,
    }


def export_project(
    path: str | Path,
    *,
    output_dir: str | Path = "exports/cadharness",
    file_format: str = "step",
    component_ids: Iterable[str] | None = None,
    variant: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Explicitly export selected components or the whole built document."""
    loaded = load_project(path, variant=variant)
    normalized_format = file_format.lower()
    if normalized_format not in {"step", "stl"}:
        raise ValueError("file_format must be 'step' or 'stl'")

    target_dir = _project_artifact_path(loaded, output_dir)
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
        artifact_id = f"{item_id}-{loaded.variant}" if loaded.variant else item_id
        filename = _SAFE_NAME.sub("-", artifact_id).strip("-.")
        output_path = target_dir / f"{filename}.{normalized_format}"
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing export: {output_path}")
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target_dir,
            prefix=f".{filename}.",
            suffix=f".{normalized_format}",
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            exporter(shape, temporary_path)
            if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
                raise RuntimeError(
                    f"exporter did not produce a valid file: {output_path}"
                )
            os.replace(temporary_path, output_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
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
        "variant": loaded.variant,
        "outputs": outputs,
    }


__all__ = [
    "compare_project",
    "discover_projects",
    "export_project",
    "inspect_project",
    "inspector_project",
    "preview_project",
    "snapshot_project",
    "validate_project",
    "verify_project",
]
