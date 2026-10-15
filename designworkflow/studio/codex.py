"""Installed Codex CLI adapter. Authentication stays in the CLI."""

import json
from pathlib import Path
import shutil

from .processes import run_process
from ..brief import read_json
from ..runner import ROOT, write_json

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["kind", "summary", "questions", "files", "brief_json"],
    "properties": {
        "kind": {"type": "string", "enum": ["design", "clarification"]},
        "summary": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "files": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["path", "content"],
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}},
        "brief_json": {"type": "string"},
    },
}


def cli_command():
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("Codex CLI was not found. Install it and run codex login, then restart Studio.")
    path = Path(executable)
    if path.suffix.lower() in {".cmd", ".ps1", ".bat"}:
        entry = path.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        node = shutil.which("node")
        if entry.is_file() and node:
            return [node, str(entry)]
        raise RuntimeError("Cannot resolve the Codex Node entry point. Put the native codex executable on PATH.")
    return [str(path)]


def generate(prompt, *, directory: Path, cancel, emit, model=None, timeout=420):
    directory.mkdir(parents=True, exist_ok=True)
    schema_file = directory / "proposal.schema.json"
    response_file = directory / "proposal.json"
    write_json(schema_file, SCHEMA)
    (directory / "request.txt").write_text(prompt, encoding="utf-8")
    command = [*cli_command(), "exec", "--json", "--color", "never", "--ephemeral",
               "--ignore-user-config", "--sandbox", "read-only", "--skip-git-repo-check",
               "--cd", str(directory), "--output-schema", str(schema_file),
               "--output-last-message", str(response_file)]
    if model:
        command.extend(["--model", model])
    command.append("-")
    usage = None
    events_file = directory / "codex.jsonl"
    errors_file = directory / "codex.stderr.txt"
    with events_file.open("x", encoding="utf-8") as events, errors_file.open("x", encoding="utf-8") as errors:
        def on_line(name, line):
            nonlocal usage
            if name == "stderr":
                errors.write(line)
                errors.flush()
                return
            events.write(line)
            events.flush()
            try:
                event = json.loads(line)
            except ValueError:
                return
            if event.get("type") == "turn.completed":
                usage = event.get("usage")
            elif event.get("type") in {"error", "turn.failed"}:
                emit("message", {"text": event.get("message") or str(event.get("error", "Codex reported an error"))})
            elif event.get("type") == "item.completed":
                item = event.get("item", {})
                if item.get("type") == "agent_message" and not item.get("text", "").lstrip().startswith("{"):
                    emit("message", {"text": item.get("text", "")[:600]})
        result = run_process(command, cwd=ROOT, cancel=cancel, timeout=timeout,
                             stdin=prompt, on_line=on_line)
    if result.returncode or not response_file.is_file():
        detail = (result.stderr or result.stdout)[-2500:]
        raise RuntimeError("Codex generation failed. Check codex login status, model access, and usage limits. " + detail)
    proposal = read_json(response_file)
    if proposal.get("kind") not in {"design", "clarification"} or not isinstance(proposal.get("files"), list):
        raise ValueError("Codex returned an invalid artifact proposal")
    write_json(directory / "usage.json", {"requested_model": model or "CLI default", "usage": usage})
    return proposal


def design_prompt(*, instruction, design_id, brief_revision, history, source,
                  current_brief, selected, repair_failure=None):
    contracts = (ROOT / "designworkflow" / "CONTRACTS.md").read_text(encoding="utf-8")
    # Include a compact reference for correct source/API usage, not an answer
    # template selected by the user's prose.
    sample = (ROOT / "designworkflow" / "templates" / "mounting-plate" / "project.py").read_text(encoding="utf-8")
    manifest = '[project]\nid = "' + design_id + '"\nname = "My design"\nentrypoint = "project.py:create_project"\n'
    context = {"instruction": instruction, "design_id": design_id, "brief_revision": brief_revision,
               "selected_components": selected, "conversation": history,
               "current_source_files": source, "current_brief": current_brief,
               "repair_failure": repair_failure}
    return f'''You are the mechanical designer inside cadHarness Studio. Return only the structured final artifact proposal. Do not execute commands or use tools: all needed context follows. The application writes source and builds CAD in a separate worker.

Generate accurate, editable parametric build123d 0.13 Python and a cadharness.toml manifest. A factory returns CADDocument with named native shapes; use role="printable-part" for manufacturing parts and role="reference-envelope" for envelopes. Keep separate parts separate. Millimeters, Z up. The manifest and document IDs must agree (use "{design_id}"). You may omit named variants and use a zero-argument factory with a parameter dataclass/defaults. Do not import ocp_vscode, start viewers, install packages, write artifacts from the factory, or use network/filesystem side effects. Use explicit build123d imports and stable lowercase IDs.

Ask a clarification ONLY for missing information that prevents sound geometry; otherwise choose practical named defaults and disclose them. An underspecified hardware family name is not an interface specification. If clarification is required, kind="clarification", list the concrete questions, files=[], brief_json="". Missing units or conflicting dimensions require clarification.

For kind="design", files must include the complete project.py and cadharness.toml, plus any required local Python helpers. Paths are relative to the candidate project; no absolute paths, parent paths, artifact outputs, or engine edits. brief_json is a JSON-encoded designworkflow.brief v1 following the contract below, id="{design_id}", revision={brief_revision}. Domain may also be "general-mechanical". Physical evidence stays unverified. Include independently geometry-derived acceptance checks for ALL explicit dimensions/interfaces in the user request. Do not check a parameter against itself. Do not generate candidate workflow.* checks: the host binds acceptance requirements externally.

Bindings use criteria.expected/minimum/maximum/absolute_tolerance and exact binding names from the contract. For cylinder selectors, radii, axis_location_mm, axis_direction, concavity are selector fields; value_path is e.g. diameter_mm or extent_mm. Hole-pattern count is measured; check explicit hole locations separately to establish orientation. For clearance distance use mm; interference uses its own binding and mm^3. Unsupported requirements remain explicit, not falsely passing. Do not invent evidence kinds or units (counts use null). Do not reuse an old dimensional expectation after the user deliberately changes it.

For a follow-up user instruction, preserve unrelated geometry and acceptance requirements; update the brief only for the requested change, with stable requirement IDs. Repair_failure means this is an automatic repair: brief_json MUST be empty and requirements are frozen; fix the source, never relax/omit checks. Return a concise summary of the geometric change, defaults, and any important limitations.

CONTRACT:\n{contracts}

MANIFEST REFERENCE (entrypoint is a relative .py file, not a module name):\n{manifest}

SOURCE API REFERENCE (illustrative, not a template to copy blindly):\n{sample}

DESIGN CONTEXT:\n{json.dumps(context, ensure_ascii=False, allow_nan=False)}'''
