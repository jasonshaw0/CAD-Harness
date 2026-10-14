"""Manifest discovery and trusted Python project loading."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
import tomllib
from typing import Any

from .model import CADDocument


MANIFEST_NAME = "cadharness.toml"


@dataclass(frozen=True)
class ProjectManifest:
    id: str
    name: str
    entrypoint: str
    description: str = ""

    @classmethod
    def from_file(cls, path: Path) -> "ProjectManifest":
        with path.open("rb") as stream:
            data = tomllib.load(stream)
        project = data.get("project")
        if not isinstance(project, dict):
            raise ValueError(f"{path} must contain a [project] table")
        required = ("id", "name", "entrypoint")
        missing = [key for key in required if not project.get(key)]
        if missing:
            raise ValueError(f"{path} is missing project fields: {', '.join(missing)}")
        return cls(
            id=str(project["id"]),
            name=str(project["name"]),
            entrypoint=str(project["entrypoint"]),
            description=str(project.get("description", "")),
        )


@dataclass(frozen=True)
class LoadedProject:
    root: Path
    manifest_path: Path
    manifest: ProjectManifest
    document: CADDocument


def _manifest_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    manifest = candidate / MANIFEST_NAME if candidate.is_dir() else candidate
    if manifest.name != MANIFEST_NAME or not manifest.is_file():
        raise FileNotFoundError(f"no {MANIFEST_NAME} found at {candidate}")
    return manifest


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _load_document(root: Path, entrypoint: str) -> CADDocument:
    module_name, separator, factory_name = entrypoint.partition(":")
    if not separator or not module_name or not factory_name:
        raise ValueError("entrypoint must use 'relative/path.py:factory_name' syntax")
    module_path = (root / module_name).resolve()
    try:
        module_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("project entrypoint must stay inside the project root") from exc
    if module_path.suffix != ".py" or not module_path.is_file():
        raise FileNotFoundError(f"project entrypoint does not exist: {module_path}")

    unique_name = f"_cadharness_project_{abs(hash(module_path))}"
    spec = importlib.util.spec_from_file_location(unique_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not create a module spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    modules_before = set(sys.modules)
    sys.modules[unique_name] = module
    sys.path.insert(0, str(root))
    try:
        spec.loader.exec_module(module)
        factory = getattr(module, factory_name, None)
        if not callable(factory):
            raise TypeError(f"entrypoint factory {factory_name!r} is not callable")
        document = factory()
    finally:
        sys.path.remove(str(root))
        # Avoid collisions between common project-local module names such as
        # ``parameters`` and ``assembly`` when a long-lived MCP process loads
        # unrelated projects. Built documents and check closures retain the
        # module globals they actually need.
        for name in set(sys.modules) - modules_before:
            loaded_module = sys.modules.get(name)
            source = getattr(loaded_module, "__file__", None)
            if source and _inside(Path(source), root):
                sys.modules.pop(name, None)
    return document


def load_project(path: str | Path) -> LoadedProject:
    """Execute a trusted project's factory and return its built document."""
    manifest_path = _manifest_path(path)
    root = manifest_path.parent
    manifest = ProjectManifest.from_file(manifest_path)
    document = _load_document(root, manifest.entrypoint)
    if not isinstance(document, CADDocument):
        raise TypeError("project factory must return a CADDocument")
    if document.id != manifest.id:
        raise ValueError(
            f"manifest id {manifest.id!r} does not match document id {document.id!r}"
        )
    return LoadedProject(root, manifest_path, manifest, document)


def discover_projects(root: str | Path) -> list[dict[str, Any]]:
    resolved = Path(root).expanduser().resolve()
    projects = []
    for manifest_path in sorted(resolved.rglob(MANIFEST_NAME)):
        try:
            manifest = ProjectManifest.from_file(manifest_path)
            projects.append(
                {
                    "id": manifest.id,
                    "name": manifest.name,
                    "description": manifest.description,
                    "path": str(manifest_path.parent),
                }
            )
        except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
            projects.append({"path": str(manifest_path.parent), "error": str(exc)})
    return projects

