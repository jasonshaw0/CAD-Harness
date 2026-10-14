"""Command-line interface with deterministic JSON output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .operations import discover_projects, export_project, inspect_project, validate_project


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cadharness")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="find projects beneath a root")
    list_parser.add_argument("root", nargs="?", default=".")

    inspect_parser = subparsers.add_parser("inspect", help="build and inspect a project")
    inspect_parser.add_argument("project")

    validate_parser = subparsers.add_parser("validate", help="run project checks")
    validate_parser.add_argument("project")

    export_parser = subparsers.add_parser("export", help="explicitly export CAD geometry")
    export_parser.add_argument("project")
    export_parser.add_argument("--format", choices=("step", "stl"), default="step")
    export_parser.add_argument("--output-dir", default="exports/cadharness")
    export_parser.add_argument("--component", action="append", dest="components")
    export_parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            result = {"projects": discover_projects(Path(args.root))}
        elif args.command == "inspect":
            result = inspect_project(args.project)
        elif args.command == "validate":
            result = validate_project(args.project)
        else:
            result = export_project(
                args.project,
                output_dir=args.output_dir,
                file_format=args.format,
                component_ids=args.components,
                overwrite=args.overwrite,
            )
        json.dump(result, sys.stdout, indent=None if args.compact else 2, sort_keys=True)
        sys.stdout.write("\n")
        if args.command == "validate" and not result["passed"]:
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

