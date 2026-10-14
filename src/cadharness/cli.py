"""Command-line interface with deterministic JSON output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

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
from .preview import VIEW_NAMES
from .schema import schema_catalog


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cadharness")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("schemas", help="list supported public JSON schemas")

    list_parser = subparsers.add_parser("list", help="find projects beneath a root")
    list_parser.add_argument("root", nargs="?", default=".")

    inspect_parser = subparsers.add_parser("inspect", help="build and inspect a project")
    inspect_parser.add_argument("project")
    inspect_parser.add_argument("--variant")

    inspector_parser = subparsers.add_parser(
        "inspector", help="generate a linked read-only HTML evidence report"
    )
    inspector_parser.add_argument("project")
    inspector_parser.add_argument("--variant")
    inspector_parser.add_argument(
        "--output", default="artifacts/inspector/index.html"
    )
    inspector_parser.add_argument(
        "--view", action="append", choices=VIEW_NAMES, dest="views"
    )
    inspector_parser.add_argument("--component", action="append", dest="components")
    inspector_parser.add_argument("--overwrite", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="run project checks")
    validate_parser.add_argument("project")
    validate_parser.add_argument("--variant")

    snapshot_parser = subparsers.add_parser(
        "snapshot", help="save deterministic geometry and validation evidence"
    )
    snapshot_parser.add_argument("project")
    snapshot_parser.add_argument("--variant")
    snapshot_parser.add_argument("--output", default=".cadharness/baseline.json")
    snapshot_parser.add_argument("--overwrite", action="store_true")

    compare_parser = subparsers.add_parser(
        "compare", help="compare current source-built geometry with a snapshot"
    )
    compare_parser.add_argument("project")
    compare_parser.add_argument("--baseline", default=".cadharness/baseline.json")
    compare_parser.add_argument("--variant")
    compare_parser.add_argument("--policy")
    compare_parser.add_argument("--output")
    compare_parser.add_argument("--overwrite", action="store_true")

    preview_parser = subparsers.add_parser(
        "preview", help="generate headless hidden-line SVG views"
    )
    preview_parser.add_argument("project")
    preview_parser.add_argument("--variant")
    preview_parser.add_argument("--output-dir", default="artifacts/previews")
    preview_parser.add_argument(
        "--view", action="append", choices=VIEW_NAMES, dest="views"
    )
    preview_parser.add_argument("--component", action="append", dest="components")
    preview_parser.add_argument("--overwrite", action="store_true")

    export_parser = subparsers.add_parser("export", help="explicitly export CAD geometry")
    export_parser.add_argument("project")
    export_parser.add_argument("--variant")
    export_parser.add_argument("--format", choices=("step", "stl"), default="step")
    export_parser.add_argument("--output-dir", default="exports/cadharness")
    export_parser.add_argument("--component", action="append", dest="components")
    export_parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "schemas":
            result = schema_catalog()
        elif args.command == "list":
            result = {"projects": discover_projects(Path(args.root))}
        elif args.command == "inspect":
            result = inspect_project(args.project, variant=args.variant)
        elif args.command == "inspector":
            result = inspector_project(
                args.project,
                output_file=args.output,
                views=args.views or ("iso", "top"),
                component_ids=args.components,
                variant=args.variant,
                overwrite=args.overwrite,
            )
        elif args.command == "validate":
            result = validate_project(args.project, variant=args.variant)
        elif args.command == "snapshot":
            result = snapshot_project(
                args.project,
                output_file=args.output,
                variant=args.variant,
                overwrite=args.overwrite,
            )
        elif args.command == "compare":
            result = compare_project(
                args.project,
                baseline_file=args.baseline,
                variant=args.variant,
                policy_file=args.policy,
                output_file=args.output,
                overwrite=args.overwrite,
            )
        elif args.command == "preview":
            result = preview_project(
                args.project,
                output_dir=args.output_dir,
                views=args.views or ("iso",),
                component_ids=args.components,
                variant=args.variant,
                overwrite=args.overwrite,
            )
        elif args.command == "export":
            result = export_project(
                args.project,
                output_dir=args.output_dir,
                file_format=args.format,
                component_ids=args.components,
                variant=args.variant,
                overwrite=args.overwrite,
            )
        else:  # pragma: no cover - argparse guarantees a registered command
            parser.error(f"unsupported command: {args.command}")
        json.dump(result, sys.stdout, indent=None if args.compact else 2, sort_keys=True)
        sys.stdout.write("\n")
        if args.command == "validate" and not result["passed"]:
            return 1
        if args.command == "compare" and result["severity"] == "regression":
            return 1
        return 0
    except Exception as exc:
        json.dump(
            {"error": type(exc).__name__, "message": str(exc)},
            sys.stderr,
            indent=2,
        )
        sys.stderr.write("\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
