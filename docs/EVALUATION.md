# Evaluation

[`cases.py`](../src/cadharness/workflow/benchmarks/cases.py) contains fixed prompt/acceptance fixtures independent of generated
candidate parameters. Prompt files are provided for CLI use. Templates are
ordinary editable projects, adapted from existing repository examples.

Run `python -m cadharness.workflow.benchmarks --output <new-directory>`. The scripted
suite preserves every failed and repaired revision, plus `benchmark.json`:

- Three square and three circular baseline plate trials.
- Missing/shifted/wrong-diameter holes, tight clearance, and rotated patterns.
- A blind center bore and flange count mismatch despite declared count checks.
- A locally thinned enclosure wall and actual skirt interference.
- A named thickness parameter edit under unchanged accepted requirements.
- Blocked unspecified hardware and conflicting-unit prompts.

Success requires zero false-ready results, at least five of six baseline
successes, every seeded defect detected, and all scripted repairs succeeding
without brief changes. Geometry is actually built and measured; these are not
mocked geometry tests. The enclosure fixture also checks real skirt clearance
in a specified Z slab. Samples do not prove global thickness.

The suite explicitly labels model quality, generation latency, manual baseline,
and AI repair success as **unmeasured**. Scripted repairs demonstrate runner
behavior, not autonomous model performance.

For an IDE-assisted trial, start a fresh run from one of the exact prompts and
have the assistant extract the brief and generate source instead of supplying
the template as the answer. Retain questions/answers and rejected assumptions.
Use three trials per plate prompt. Record first-pass correctness, final
correctness, false-ready rate, repair count, named-parameter editability, actual
authoring/review/build times, unresolved assumptions, and provenance coverage.
Use `--active-seconds` for authoring/review time. Stop at two repairs, 120 seconds
per build, 15 minutes active work, or unchanged failed source. Do not include
user-response waits in the active budget.

Time a manual source-and-check workflow on the same prompts and toolchain before
claiming improved speed. Keep human review and physical fit evidence distinct.

## Browser checks

Read the Playwriter skill, create a task-specific session, and run:

```powershell
cmd /d /s /c npx -y playwriter@latest session new --tab-group cadharness
# Set state.reviewRevision to the absolute saved revision path in that session
# with a Playwriter -e snippet or an initialization .js file.
cmd /d /s /c npx -y playwriter@latest -s SESSION_ID --timeout 30000 -f scripts/verify_workflow_browser.js
```

Repeat the file invocation until it reports `done`; each invocation performs one
action and prints the resulting snapshot and logs. The script uses only Playwriter for
browser control. Screenshots are written beside the review, outside the hashed
evidence bundle. Inspect screenshots as well as automated assertions. Use a
new output directory for every evaluation; no previous artifacts are replaced.
