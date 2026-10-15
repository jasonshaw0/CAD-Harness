"""Repeatable scripted regression benchmark, explicitly not an AI-quality eval."""

import argparse
import json
from pathlib import Path
import statistics
import time

from .cases import get_case
from ..brief import read_json
from ..runner import init_run, review_hashes, check_revision, revise, write_json


def trusted_fixture_check(revision):
    # Only repository-owned fixtures and explicit mutations below are attested.
    hashes = review_hashes(revision)
    return check_revision(revision, reviewed_source=hashes["source_sha256"], accepted_brief=hashes["brief_sha256"])


def edit_source(revision, before, after):
    path = revision / "project" / "project.py"
    source = path.read_text(encoding="utf-8")
    if before not in source:
        raise ValueError(f"fixture mutation no longer matches source: {before}")
    path.write_text(source.replace(before, after), encoding="utf-8")


def run_suite(output: Path):
    output = output.resolve()
    if output.exists():
        raise FileExistsError("benchmark output must be a new directory")
    output.mkdir(parents=True)
    started = time.perf_counter()
    records = []

    def create(case, run_id):
        return Path(init_run(run_id, get_case(case)["prompt"], root=output, case=case)["revision"])

    def record(name, report, expected, expected_outcome=None):
        item = {"case": name, "expected_ready": expected, "ready": report["ready_for_review"],
                "outcome": report["outcome"], "seconds": report["elapsed_seconds"],
                "expected_outcome": expected_outcome or ("ready-for-review" if expected else "needs-revision"),
                "unresolved_mandatory": sum(row["mandatory"] and row["status"] in {"unknown", "not-yet-verified"} for row in report["coverage"]),
                "revision": report["revision"], "source_sha256": report["source_sha256"],
                "brief_sha256": report["brief_sha256"]}
        records.append(item)
        print(f"{name}: {report['outcome']}", flush=True)
        return item

    for case in ("square-mount", "circular-plate"):
        for trial in range(1, 4):
            record(f"{case}-{trial}", trusted_fixture_check(create(case, f"{case}-{trial}")), True)

    seeds = (
        ("square-mount", "missing-hole", "modeled_hole_count: int = -1", "modeled_hole_count: int = 3"),
        ("square-mount", "shifted-hole", "last_hole_shift: float = 0.0", "last_hole_shift: float = 3.0"),
        ("square-mount", "wrong-diameter", "diameter_offset: float = 0.0", "diameter_offset: float = 0.5"),
        ("square-mount", "tight-clearance", "cable_gap: float = 4.0", "cable_gap: float = 2.0"),
        ("square-mount", "rotated-pattern", "rotation_offset_deg: float = 0.0", "rotation_offset_deg: float = 45.0"),
        ("circular-plate", "blind-bore", "blind_bore: bool = False", "blind_bore: bool = True"),
        ("flange", "declared-count", "range(params.bolt_count)", "range(params.bolt_count - 1)"),
        ("enclosure", "thin-wall", "return Part(outer - cavity).clean()", "return Part((outer - cavity) - Pos(31.6, 0, 10) * Box(2, 8, 8)).clean()"),
        ("enclosure", "skirt-interference", "params.inside_x - 2 * params.lid_clearance_per_side", "params.inside_x + 1.0"),
    )
    repairs, detected = [], []
    for case, defect, before, after in seeds:
        revision = create(case, defect)
        edit_source(revision, before, after)
        failed = trusted_fixture_check(revision)
        record(defect, failed, False)
        repair = Path(revise(revision)["revision"])
        edit_source(repair, after, before)
        passed = trusted_fixture_check(repair)
        record(defect + "-repair", passed, True)
        measured_failure = failed["outcome"] == "needs-revision" and any(row["status"] == "fail" for row in failed["coverage"])
        detected.append(measured_failure)
        repairs.append(measured_failure and passed["ready_for_review"] and failed["brief_sha256"] == passed["brief_sha256"])

    revision = create("square-mount", "parameter-edit")
    # Change intent before its first acceptance, then satisfy it via a named parameter.
    path = revision.parent.parent / "brief-v001.json"
    brief = read_json(path)
    for req in brief["requirements"]:
        if req["id"] == "plate.z" or req["id"].endswith(".extent") or req["id"] in {"motor-envelope.bottom", "cable-keepout.bottom"}:
            req["criteria"]["expected"] = 5
    path.write_text(json.dumps(brief, indent=2), encoding="utf-8")
    failed = trusted_fixture_check(revision)
    record("parameter-edit-before", failed, False)
    repaired = Path(revise(revision)["revision"])
    edit_source(repaired, "thickness: float = 4.0", "thickness: float = 5.0")
    passed = trusted_fixture_check(repaired)
    record("parameter-edit-after", passed, True)

    for name, prompt in (("ambiguous-hardware", "Make a NEMA 17 mount"),
                         ("conflicting-units", "Make a plate 2 inches / 60 mm wide")):
        revision = Path(init_run(name, prompt, root=output)["revision"])
        record(name, trusted_fixture_check(revision), False, "blocked")

    baseline = records[:6]
    false_ready = sum(row["ready"] and not row["expected_ready"] for row in records)
    summary = {"schema": "designworkflow.benchmark", "schema_version": "1",
               "mode": "scripted-regression", "model_backend": None,
               "baseline_completed": sum(row["ready"] for row in baseline), "baseline_total": 6,
               "false_ready": false_ready, "seeded_defects": len(seeds),
               "measured_defects_detected": sum(detected),
               "successful_scripted_repairs": sum(repairs), "editability_passed": passed["ready_for_review"],
               "median_build_check_seconds": statistics.median(row["seconds"] for row in records),
               "total_seconds": time.perf_counter() - started,
               "ai_correctness": None, "ai_repair_success": None, "generation_seconds": None,
               "manual_speed_baseline": None, "speed_improvement_claim": None,
               "notes": "Tests supplied source and scripted repairs, not natural-language model performance. AI authoring/review speed and clarification quality require separately timed IDE trials.",
               "passed": false_ready == 0 and sum(row["ready"] for row in baseline) >= 5 and all(repairs) and all(row["outcome"] == row["expected_outcome"] for row in records),
               "records": records}
    write_json(output / "benchmark.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory for preserved benchmark runs")
    args = parser.parse_args()
    result = run_suite(args.output)
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
