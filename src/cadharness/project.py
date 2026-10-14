"""Manifest discovery and trusted, typed Python project loading."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
import importlib.util
from pathlib import Path
import re
import sys
import tomllib
import types
from typing import Any, Literal, Mapping, Union, get_args, get_origin, get_type_hints

from .model import CADDocument


MANIFEST_NAME = "cadharness.toml"
_VARIANT_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$")


@dataclass(frozen=True)
class ProjectManifest:
    id: str
    name: str
    entrypoint: str
    description: str = ""
    parameter_type: str | None = None
    default_variant: str | None = None
    comparison_policy: str | None = None
    variants: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

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

        raw_variants = data.get("variants", {})
        if not isinstance(raw_variants, dict):
            raise TypeError(f"{path} [variants] must contain named tables")
        variants: dict[str, Mapping[str, Any]] = {}
        for name, values in raw_variants.items():
            if not _VARIANT_NAME.fullmatch(name):
                raise ValueError(f"invalid variant identifier: {name!r}")
            if not isinstance(values, dict):
                raise TypeError(f"variant {name!r} must be a table")
            variants[name] = values

        parameter_type = project.get("parameter_type")
        default_variant = project.get("default_variant")
        if variants and not parameter_type:
            raise ValueError("named variants require project.parameter_type")
        if default_variant is not None and default_variant not in variants:
            raise ValueError(f"default variant {default_variant!r} is not defined")
        if variants and default_variant is None:
            raise ValueError("projects with variants must declare project.default_variant")

        return cls(
            id=str(project["id"]),
            name=str(project["name"]),
            entrypoint=str(project["entrypoint"]),
            description=str(project.get("description", "")),
            parameter_type=str(parameter_type) if parameter_type else None,
            default_variant=str(default_variant) if default_variant else None,
            comparison_policy=(
                str(project["comparison_policy"])
                if project.get("comparison_policy")
                else None
            ),
            variants=variants,
        )


@dataclass(frozen=True)
class LoadedProject:
    root: Path
    manifest_path: Path
    manifest: ProjectManifest
    document: CADDocument
    variant: str | None = None
    variant_values: Mapping[str, Any] = field(default_factory=dict)


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


def _reference(root: Path, reference: str, label: str) -> tuple[Path, str]:
    module_name, separator, object_name = reference.partition(":")
    if not separator or not module_name or not object_name:
        raise ValueError(f"{label} must use 'relative/path.py:object_name' syntax")
    module_path = (root / module_name).resolve()
    try:
        module_path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the project root") from exc
    if module_path.suffix != ".py" or not module_path.is_file():
        raise FileNotFoundError(f"{label} module does not exist: {module_path}")
    return module_path, object_name


def _execute_module(module_path: Path, suffix: str) -> Any:
    unique_name = f"_cadharness_project_{abs(hash(module_path))}_{suffix}"
    spec = importlib.util.spec_from_file_location(unique_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not create a module spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def _coerce_value(name: str, value: Any, annotation: Any) -> Any:
    if annotation is Any:
        return value
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        errors = []
        for option in get_args(annotation):
            try:
                return _coerce_value(name, value, option)
            except (TypeError, ValueError) as exc:
                errors.append(str(exc))
        raise TypeError(f"variant field {name!r} does not match {annotation!r}")
    if origin is Literal:
        if value not in get_args(annotation):
            raise ValueError(f"variant field {name!r} must be one of {get_args(annotation)!r}")
        return value
    if origin is list:
        if not isinstance(value, list):
            raise TypeError(f"variant field {name!r} must be a list")
        (item_type,) = get_args(annotation) or (Any,)
        return [_coerce_value(name, item, item_type) for item in value]
    if annotation is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"variant field {name!r} must be a number")
        return float(value)
    if annotation is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"variant field {name!r} must be an integer")
        return value
    if annotation is bool:
        if not isinstance(value, bool):
            raise TypeError(f"variant field {name!r} must be a boolean")
        return value
    if annotation is str:
        if not isinstance(value, str):
            raise TypeError(f"variant field {name!r} must be a string")
        return value
    if annotation is type(None):
        if value is not None:
            raise TypeError(f"variant field {name!r} must be null")
        return None
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        try:
            return annotation(value)
        except ValueError as exc:
            raise ValueError(f"invalid value for variant field {name!r}: {value!r}") from exc
    if isinstance(annotation, type) and isinstance(value, annotation):
        return value
    raise TypeError(f"unsupported or invalid type for variant field {name!r}: {annotation!r}")


def _typed_parameters(parameter_class: type, values: Mapping[str, Any]) -> Any:
    if not is_dataclass(parameter_class):
        raise TypeError("project.parameter_type must reference a dataclass")
    declared = {item.name for item in fields(parameter_class) if item.init}
    unknown = sorted(set(values) - declared)
    if unknown:
        raise ValueError(f"unknown variant fields: {', '.join(unknown)}")
    hints = get_type_hints(parameter_class)
    coerced = {
        name: _coerce_value(name, value, hints.get(name, Any))
        for name, value in values.items()
    }
    parameters = parameter_class(**coerced)
    validate = getattr(parameters, "validate", None)
    if callable(validate):
        validate()
    return parameters


def _load_document(
    root: Path, manifest: ProjectManifest, variant: str | None
) -> tuple[CADDocument, str | None, Mapping[str, Any]]:
    module_path, factory_name = _reference(root, manifest.entrypoint, "entrypoint")
    selected_variant = variant if variant is not None else manifest.default_variant
    if selected_variant is not None and selected_variant not in manifest.variants:
        available = ", ".join(sorted(manifest.variants)) or "none"
        raise ValueError(
            f"unknown variant {selected_variant!r}; available variants: {available}"
        )
    values = dict(manifest.variants.get(selected_variant, {}))

    modules_before = set(sys.modules)
    sys.path.insert(0, str(root))
    try:
        module = _execute_module(module_path, "entry")
        factory = getattr(module, factory_name, None)
        if not callable(factory):
            raise TypeError(f"entrypoint factory {factory_name!r} is not callable")

        if manifest.parameter_type:
            parameter_path, parameter_name = _reference(
                root, manifest.parameter_type, "parameter_type"
            )
            parameter_module = (
                module
                if parameter_path == module_path
                else _execute_module(parameter_path, "parameters")
            )
            parameter_class = getattr(parameter_module, parameter_name, None)
            if not isinstance(parameter_class, type):
                raise TypeError(f"parameter type {parameter_name!r} is not a class")
            parameters = _typed_parameters(parameter_class, values)
            document = factory(parameters)
        else:
            if variant is not None:
                raise ValueError("this project does not declare typed variants")
            document = factory()
    finally:
        sys.path.remove(str(root))
        for name in set(sys.modules) - modules_before:
            loaded_module = sys.modules.get(name)
            source = getattr(loaded_module, "__file__", None)
            if source and _inside(Path(source), root):
                sys.modules.pop(name, None)
    return document, selected_variant, values


def load_project(path: str | Path, *, variant: str | None = None) -> LoadedProject:
    """Execute a trusted project factory with a named, typed variant."""
    manifest_path = _manifest_path(path)
    root = manifest_path.parent
    manifest = ProjectManifest.from_file(manifest_path)
    document, selected_variant, values = _load_document(root, manifest, variant)
    if not isinstance(document, CADDocument):
        raise TypeError("project factory must return a CADDocument")
    if document.id != manifest.id:
        raise ValueError(
            f"manifest id {manifest.id!r} does not match document id {document.id!r}"
        )
    return LoadedProject(
        root, manifest_path, manifest, document, selected_variant, values
    )


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
                    "default_variant": manifest.default_variant,
                    "variants": sorted(manifest.variants),
                }
            )
        except (OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
            projects.append({"path": str(manifest_path.parent), "error": str(exc)})
    return projects
