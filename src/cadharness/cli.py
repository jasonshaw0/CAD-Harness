"""Command-line interface with deterministic JSON output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .diagnostics import doctor_report, package_version
from .mcp_config import mcp_client_config
from .operations import (
    compare_project,
    discover_projects,
    export_project,
    inspect_project,
    inspector_project,
    preview_project,
    snapshot_project,
    validate_project,
    verify_project,
)
from .preview import VIEW_NAMES
from .schema import schema_catalog
from .verification import VerificationPolicy


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cadharness",
        description="Inspect and validate trusted source-backed build123d projects.",
        epilog=(
            "examples:\n"
            "  cadharness doctor .\n"
            "  cadharness list examples\n"
            "  cadharness validate examples/project-box --variant standard\n"
            "  cadharness verify examples/project-box --variant standard\n"
            "  cadharness inspector examples/project-box --variant standard\n"
            "\n"
            "verify exit codes: 0 gate passed, 1 gate failed, 2 usage or execution error"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {package_version()}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("schemas", help="list supported public JSON schemas")

    doctor_parser = subparsers.add_parser(
        "doctor", help="diagnose the active installation and project discovery"
    )
    doctor_parser.add_argument(
        "root", nargs="?", default=".", help="directory to scan for projects"
    )

    mcp_config_parser = subparsers.add_parser(
        "mcp-config", help="print a portable MCP client configuration"
    )
    mcp_config_parser.add_argument(
        "roots",
        nargs="*",
        default=["."],
        help="trusted project roots (default: current directory)",
    )
    mcp_config_parser.add_argument(
        "--name", default="cadharness", help="server name in the generated config"
    )

    list_parser = subparsers.add_parser("list", help="find projects beneath a root")
    list_parser.add_argument(
        "root", nargs="?", default=".", help="directory to scan (default: current)"
    )

    inspect_parser = subparsers.add_parser("inspect", help="build and inspect a project")
    inspect_parser.add_argument("project")
    inspect_parser.add_argument("--variant")

    inspector_parser = subparsers.add_parser(
        "inspector", help="generate a linked read-only HTML evidence report"
    )
    inspector_parser.add_argument("project")
    inspector_parser.add_argument("--variant")
    inspector_parser.add_argument(
        "--output", default=".cadharness/inspector/index.html"
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

    verify_parser = subparsers.add_parser(
        "verify", help="gate current engineering evidence and optional revision changes"
    )
    verify_parser.add_argument("project")
    verify_parser.add_argument("--baseline")
    verify_parser.add_argument("--variant")
    verify_parser.add_argument("--policy")
    verify_parser.add_argument("--allow-failed-checks", action="store_true")
    verify_parser.add_argument("--allow-check-errors", action="store_true")
    verify_parser.add_argument("--fail-on-warnings", action="store_true")
    verify_parser.add_argument("--allow-skipped-checks", action="store_true")
    verify_parser.add_argument("--fail-on-added-requirements", action="store_true")
    verify_parser.add_argument("--allow-removed-requirements", action="store_true")
    verify_parser.add_argument("--allow-modified-requirements", action="store_true")
    verify_parser.add_argument("--allow-unaccepted-changes", action="store_true")

    preview_parser = subparsers.add_parser(
        "preview", help="generate headless hidden-line SVG views"
    )
    preview_parser.add_argument("project")
    preview_parser.add_argument("--variant")
    preview_parser.add_argument("--output-dir", default=".cadharness/previews")
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
    raw_args = list(sys.argv[1:] if argv is None else argv)
    compact = "--compact" in raw_args
    args = parser.parse_args([item for item in raw_args if item != "--compact"])
    args.compact = compact
    try:
        if args.command == "schemas":
            result = schema_catalog()
        elif args.command == "doctor":
            result = doctor_report(args.root)
        elif args.command == "mcp-config":
            result = mcp_client_config(args.roots, name=args.name)
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
        elif args.command == "verify":
            result = verify_project(
                args.project,
                baseline_file=args.baseline,
                variant=args.variant,
                policy_file=args.policy,
                gate_policy=VerificationPolicy(
                    fail_on_failed_checks=not args.allow_failed_checks,
                    fail_on_check_errors=not args.allow_check_errors,
                    fail_on_warnings=args.fail_on_warnings,
                    fail_on_skipped_checks=not args.allow_skipped_checks,
                    fail_on_added_requirements=args.fail_on_added_requirements,
                    fail_on_removed_requirements=not args.allow_removed_requirements,
                    fail_on_modified_requirements=not args.allow_modified_requirements,
                    fail_on_unaccepted_changes=not args.allow_unaccepted_changes,
                ),
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
        if args.command == "verify":
            if result["verification"]["outcome"] == "error":
                return 2
            if not result["verification"]["passed"]:
                return 1
        return 0
    except Exception as exc:
        hint = None
        if isinstance(exc, FileExistsError):
            hint = "Use --overwrite or choose a different output path."
        elif isinstance(exc, FileNotFoundError) and "cadharness.toml" in str(exc):
            hint = "Pass a project directory containing cadharness.toml; use 'cadharness list <root>' to discover projects."
        error = {"error": type(exc).__name__, "message": str(exc)}
        if hint:
            error["hint"] = hint
        json.dump(
            error,
            sys.stderr,
            indent=2,
        )
        sys.stderr.write("\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
