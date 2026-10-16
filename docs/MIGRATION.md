# Moving from designworkflow to the unified CAD-Harness layout

Studio and design orchestration now ship inside `cadharness`. The framework
API, project manifests, CAD MCP tool names, and public framework JSON schemas
retain their contracts. Saved workflow records still use `designworkflow.*`
v1 schema IDs; path changes do not rewrite those identities.

## CAD-Harness name

The Python distribution is now `CAD-Harness`. New `cad-harness` and
`cad-harness-mcp` commands accompany the existing `cadharness` commands.
Python imports, `cadharness.toml`, `.cadharness/`, MCP configuration keys,
environment variables, and evidence schemas keep their compatible names.
Previously generated reports and CAD artifacts are not rewritten for branding.

When upgrading an environment with the old `cadharness` distribution installed,
remove that distribution before reinstalling so two distributions do not own the
same legacy command scripts. From the checkout in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip uninstall cadharness
python bootstrap.py
```

Or on Linux/macOS, run `./.venv/bin/python -m pip uninstall cadharness`, then
`python3 bootstrap.py`. Replace the Windows interpreter path with
`./.venv/bin/python` in later commands; workspace paths such as
`./designworkflow/runs/studio` are unchanged.

## Commands and source paths

| Previous | Current |
| --- | --- |
| `python -m designworkflow studio` | `python -m cadharness studio` |
| `python -m designworkflow init/check/revise/export …` | `python -m cadharness design init/check/revise/export …` |
| `python -m designworkflow.benchmarks …` | `python -m cadharness.workflow.benchmarks …` |
| `designworkflow/*.py` | `src/cadharness/workflow/` |
| `designworkflow/studio/*.py` | `src/cadharness/studio/` |
| `designworkflow/studio/web/` | `studio/web/` |
| `designworkflow/tests/` | `tests/workflow/` |
| `designworkflow/templates/` | `src/cadharness/workflow/templates/` |
| `designworkflow/CONTRACTS.md` | `src/cadharness/workflow/CONTRACTS.md` |
| Workflow and Studio READMEs | [Design workflow](DESIGN_WORKFLOW.md) and [Studio](STUDIO.md) |

The checkout retains a `python -m designworkflow` CLI shim for the old manual
and Studio commands. Internal imports moved to `cadharness.workflow` and
`cadharness.studio`; the shim does not provide old Python imports or the old
benchmark module. New scripts should use the unified commands.

## Keep existing designs and evidence

Existing ignored `designworkflow/runs/` data stays in place. No saved source,
report, hash, mesh, or export is migrated or regenerated automatically.
To continue with the previous Studio workspace:

```powershell
.\.venv\Scripts\python.exe -m cadharness mcp-config . --studio --studio-workspace ./designworkflow/runs/studio
```

Add that config to the host and restart it. `studio_status` reports the actual
workspace. For standalone use, pass the same path with
`cadharness studio --workspace ./designworkflow/runs/studio`.

Fresh MCP configs default to `<first-root>/runs/studio/`. Manual designs default
to `<checkout>/runs/` in editable installs, or `<cwd>/runs/` in a wheel install.
Both are ignored by Git. Manual commands still accept old revision paths.

CAD-Harness fingerprints evaluator source, and this refactor changes that
fingerprint. Freshness checks may reject export or revision of an old evaluated
attempt. Keep it for inspection and use Studio Rebuild to create fresh evidence.
Do not patch stored hashes to bypass freshness checks.

## Refresh the install and frontend

Reinstall with `python -m pip install -e ".[mcp,studio]"`, then run
`npm --prefix studio/web ci` and `npm --prefix studio/web run build`.
The canvas now builds into the Python package. Update IDE tabs and scripts
that reference the old frontend directory, and restart MCP processes to load
the new package and asset paths.
