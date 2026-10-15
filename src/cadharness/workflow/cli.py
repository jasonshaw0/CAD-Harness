"""Reviewed design commands, shared by the unified CLI and module entrypoint."""

import argparse
import json
from pathlib import Path
import sys

from .runner import init_run, review_hashes, check_revision, revise, export_revision, worker


def add_arguments(parser):
    commands = parser.add_subparsers(dest="workflow_command", required=True)
    init = commands.add_parser("init", help="preserve prompt and create a source/brief scaffold")
    init.add_argument("--id", required=True)
    init.add_argument("--prompt-file", type=Path, required=True)
    init.add_argument("--root", type=Path)
    init.add_argument("--case", choices=("square-mount", "circular-plate", "enclosure", "flange"))
    check = commands.add_parser("check", help="review hashes or evaluate a reviewed revision")
    check.add_argument("revision", type=Path)
    check.add_argument("--review-hashes", action="store_true", help="read inputs without executing Python")
    check.add_argument("--reviewed-source")
    check.add_argument("--accepted-brief")
    check.add_argument("--timeout", type=float, default=120)
    check.add_argument("--active-seconds", type=float, default=0, help="authoring/review seconds, excluding waits; added to measured worker time")
    repair = commands.add_parser("revise", help="copy source to the next revision, preserving evidence")
    repair.add_argument("revision", type=Path)
    repair.add_argument("--brief", help="new brief-vNNN.json for an intentional requirements change")
    export = commands.add_parser("export", help="explicit STEP/STL export of printable components")
    export.add_argument("revision", type=Path)
    export.add_argument("--format", choices=("step", "stl"), default="step")
    export.add_argument("--component", action="append", default=[])
    export.add_argument("--timeout", type=float, default=120)
    internal = commands.add_parser("_worker", help="internal project subprocess entrypoint")
    internal.add_argument("action", choices=("check", "export"))
    internal.add_argument("revision", type=Path)
    internal.add_argument("extra", nargs="*")


def run(args):
    command = args.workflow_command
    try:
        if command == "_worker":
            worker(args.action, args.revision, args.extra)
            return 0
        if command == "init":
            result = init_run(args.id, args.prompt_file.read_text(encoding="utf-8-sig"), root=args.root, case=args.case)
        elif command == "revise":
            result = revise(args.revision, brief_name=args.brief)
        elif command == "export":
            result = export_revision(args.revision, file_format=args.format, component_ids=args.component, timeout=args.timeout)
        elif args.review_hashes:
            result = review_hashes(args.revision)
        else:
            if not args.reviewed_source or not args.accepted_brief:
                raise ValueError("review source and brief, then supply --reviewed-source HASH --accepted-brief HASH; use --review-hashes to inspect identities")
            result = check_revision(args.revision, reviewed_source=args.reviewed_source, accepted_brief=args.accepted_brief,
                                    timeout=args.timeout, active_seconds=args.active_seconds)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        if result.get("outcome") == "error":
            return 2
        return 1 if result.get("ready_for_review") is False else 0
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cad-harness design", description="Reviewed source and brief workflow; trusted local Python execution")
    add_arguments(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
