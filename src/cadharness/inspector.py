"""Self-contained read-only HTML rendering for cadHarness evidence."""

from __future__ import annotations

from html import escape
import json
from typing import Any, Iterable, Mapping


def _text(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(", ", ": "))
    return str(value)


def _html(value: Any) -> str:
    return escape(_text(value), quote=True)


def _component_links(result: Mapping[str, Any], component_ids: set[str]) -> str:
    evidence = result.get("evidence")
    candidates: list[str] = []
    if isinstance(evidence, Mapping):
        linked = evidence.get("components")
        if isinstance(linked, list):
            candidates.extend(str(item) for item in linked)
    check_id = str(result.get("id", ""))
    if check_id.startswith("geometry."):
        candidates.append(check_id.removeprefix("geometry."))
    links = [
        f'<a href="#component-{escape(item, quote=True)}">{escape(item)}</a>'
        for item in dict.fromkeys(candidates)
        if item in component_ids
    ]
    return " · ".join(links)


def render_inspector(
    inspection: Mapping[str, Any],
    validation: Mapping[str, Any],
    *,
    previews: Iterable[Mapping[str, Any]] = (),
    verification: Mapping[str, Any] | None = None,
) -> str:
    """Render trusted report data into a portable, read-only HTML document."""
    project = inspection.get("project", {})
    components = inspection.get("components", {})
    parameters = inspection.get("parameters", {})
    results = validation.get("results", [])
    if not isinstance(project, Mapping):
        raise TypeError("inspection project must be an object")
    if not isinstance(components, Mapping):
        raise TypeError("inspection components must be an object")
    if not isinstance(parameters, Mapping):
        raise TypeError("inspection parameters must be an object")
    if not isinstance(results, list):
        raise TypeError("validation results must be a list")

    component_ids = {str(item) for item in components}
    preview_cards = []
    for preview in previews:
        view = _html(preview.get("view", "preview"))
        href = escape(str(preview.get("href", "")), quote=True)
        preview_cards.append(
            f'<figure><img src="{href}" alt="{view} CAD preview">'
            f"<figcaption>{view} view</figcaption></figure>"
        )

    component_cards = []
    for component_id, raw_component in sorted(components.items()):
        component = raw_component if isinstance(raw_component, Mapping) else {}
        geometry = component.get("geometry", {})
        geometry = geometry if isinstance(geometry, Mapping) else {}
        bbox = geometry.get("bounding_box", {})
        bbox = bbox if isinstance(bbox, Mapping) else {}
        size = bbox.get("size_mm", [])
        dimensions = " × ".join(_html(value) for value in size) if size else "—"
        safe_id = escape(str(component_id), quote=True)
        component_cards.append(
            f'<article class="card component" id="component-{safe_id}" '
            f'data-testid="component-{safe_id}">'
            f"<div class=\"eyebrow\">{_html(component.get('role', 'component'))}</div>"
            f"<h3>{_html(component_id)}</h3>"
            "<dl>"
            f"<div><dt>Valid</dt><dd>{_html(geometry.get('valid'))}</dd></div>"
            f"<div><dt>Manifold</dt><dd>{_html(geometry.get('manifold'))}</dd></div>"
            f"<div><dt>Volume</dt><dd>{_html(geometry.get('volume_mm3'))} mm³</dd></div>"
            f"<div><dt>Bounds</dt><dd>{dimensions} mm</dd></div>"
            f"<div><dt>Material</dt><dd>{_html(component.get('material'))}</dd></div>"
            "</dl></article>"
        )

    check_cards = []
    for raw_result in results:
        result = raw_result if isinstance(raw_result, Mapping) else {}
        status = str(result.get("status", "error"))
        links = _component_links(result, component_ids)
        evidence = result.get("evidence", {})
        details = _html(evidence) if evidence else "No supplemental evidence"
        evidence_kind = _html(result.get("evidence_kind", "unspecified"))
        check_cards.append(
            f'<article class="check check-{escape(status, quote=True)}" '
            f'data-status="{escape(status, quote=True)}">'
            f'<span class="status">{_html(status)}</span>'
            f"<h3>{_html(result.get('id'))}</h3>"
            f"<p>{_html(result.get('message'))}</p>"
            f'<p class="evidence-kind">Evidence: {evidence_kind}</p>'
            f"<p>Actual: {_html(result.get('actual'))}<br>Expected: {_html(result.get('expected'))}</p>"
            f'<p class="links">{links}</p>'
            f"<details><summary>Evidence</summary><pre>{details}</pre></details>"
            "</article>"
        )

    parameter_rows = []
    for name, raw_parameter in sorted(parameters.items()):
        parameter = raw_parameter if isinstance(raw_parameter, Mapping) else {}
        parameter_rows.append(
            "<tr>"
            f"<th scope=\"row\">{_html(name)}</th>"
            f"<td>{_html(parameter.get('value'))}</td>"
            f"<td>{_html(parameter.get('unit'))}</td>"
            f"<td>{_html(parameter.get('source'))}</td>"
            f"<td>{_html(parameter.get('description'))}</td>"
            "</tr>"
        )

    gate = verification if verification is not None else {
        "passed": validation.get("passed"), "reasons": []
    }
    passed = bool(gate.get("passed"))
    verdict = (
        ("Verified" if passed else "Verification failed")
        if verification is not None
        else ("Validation passed" if passed else "Validation failed")
    )
    verdict_class = "pass" if passed else "fail"
    title = _html(project.get("name", project.get("id", "cadHarness project")))
    variant = inspection.get("manifest", {})
    variant_name = variant.get("variant") if isinstance(variant, Mapping) else None
    gate_reasons = gate.get("reasons", [])
    reason_text = (
        "Verification gate was not run."
        if verification is None
        else _html(gate_reasons) if gate_reasons else "No verification gate failures."
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · cadHarness inspector</title>
<style>
:root {{ color-scheme: dark; --bg:#0b0e12; --panel:#141920; --line:#2a333e;
  --text:#e8edf2; --muted:#9ba8b5; --accent:#55d6be; --pass:#65d08a;
  --fail:#ff7b72; --warn:#e3b341; font-family:Inter,ui-sans-serif,system-ui,sans-serif; }}
* {{ box-sizing:border-box; }} html {{ scroll-behavior:smooth; }}
body {{ margin:0; background:var(--bg); color:var(--text); line-height:1.5; }}
a {{ color:var(--accent); }} .shell {{ width:min(1180px,calc(100% - 32px)); margin:auto; }}
header {{ padding:56px 0 28px; border-bottom:1px solid var(--line); }}
.eyebrow {{ color:var(--accent); font:700 .72rem/1.2 ui-monospace,monospace;
  letter-spacing:.12em; text-transform:uppercase; }}
h1 {{ margin:.25rem 0; font-size:clamp(2rem,5vw,4.5rem); letter-spacing:-.055em; }}
h2 {{ margin:0 0 18px; font-size:1.55rem; }} h3 {{ margin:.35rem 0; }}
.meta,.filters {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
.pill,.filters button {{ border:1px solid var(--line); border-radius:999px; padding:6px 11px;
  background:transparent; color:var(--muted); font:inherit; }}
.pill.pass,.status {{ color:var(--pass); }} .pill.fail,.check-fail .status,.check-error .status {{ color:var(--fail); }}
.check-warn .status,.check-skip .status {{ color:var(--warn); }}
nav {{ position:sticky; top:0; z-index:2; background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:blur(14px); border-bottom:1px solid var(--line); }}
nav .shell {{ display:flex; gap:18px; overflow:auto; padding:12px 0; }}
nav a {{ color:var(--muted); text-decoration:none; white-space:nowrap; }}
main section {{ padding:36px 0; border-bottom:1px solid var(--line); scroll-margin-top:48px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:14px; }}
.card,.check,figure {{ margin:0; padding:18px; background:var(--panel); border:1px solid var(--line); border-radius:14px; }}
figure img {{ display:block; width:100%; aspect-ratio:16/10; object-fit:contain; background:#fff; border-radius:8px; }}
figcaption {{ color:var(--muted); margin-top:8px; }} dl {{ margin:12px 0 0; }}
dl div {{ display:flex; justify-content:space-between; gap:14px; border-top:1px solid var(--line); padding:7px 0; }}
dt {{ color:var(--muted); }} dd {{ margin:0; text-align:right; }}
.check {{ border-left:3px solid var(--pass); }} .check-fail,.check-error {{ border-left-color:var(--fail); }}
.check-warn,.check-skip {{ border-left-color:var(--warn); }} .status {{ float:right; text-transform:uppercase; font-size:.75rem; }}
.links:empty {{ display:none; }} details {{ color:var(--muted); }} pre {{ white-space:pre-wrap; overflow-wrap:anywhere; }}
button[aria-pressed="true"] {{ color:var(--text); border-color:var(--accent); }}
table {{ width:100%; border-collapse:collapse; font-size:.92rem; }} th,td {{ padding:10px; border-bottom:1px solid var(--line); text-align:left; }}
thead th {{ color:var(--muted); }} .table-wrap {{ overflow:auto; }}
footer {{ padding:28px 0 48px; color:var(--muted); }}
@media (max-width:640px) {{ header {{ padding-top:32px; }} th:nth-child(4),td:nth-child(4),th:nth-child(5),td:nth-child(5) {{ display:none; }} }}
</style>
</head>
<body>
<header><div class="shell">
  <div class="eyebrow">cadHarness · read-only evidence</div>
  <h1>{title}</h1>
  <div class="meta">
    <span class="pill {verdict_class}" data-testid="verdict">{verdict}</span>
    <span class="pill">Revision {_html(project.get('revision'))}</span>
    <span class="pill">Variant {_html(variant_name)}</span>
    <span class="pill">{len(components)} components</span>
    <span class="pill">{len(results)} checks</span>
  </div>
</div></header>
<nav aria-label="Inspector sections"><div class="shell">
  <a href="#previews">Previews</a><a href="#components">Components</a>
  <a href="#checks">Checks</a><a href="#parameters">Parameters</a>
</div></nav>
<main class="shell">
  <section id="verification"><h2>Verification</h2><p>{reason_text}</p></section>
  <section id="previews"><h2>Previews</h2><div class="grid">{''.join(preview_cards) or '<p>No preview artifacts linked.</p>'}</div></section>
  <section id="components"><h2>Components</h2><div class="grid">{''.join(component_cards)}</div></section>
  <section id="checks"><h2>Checks</h2>
    <div class="filters" role="group" aria-label="Filter checks">
      <button type="button" data-filter="all" aria-pressed="true">All</button>
      <button type="button" data-filter="pass" aria-pressed="false">Passing</button>
      <button type="button" data-filter="review" aria-pressed="false">Needs review</button>
    </div><div class="grid" data-testid="check-grid">{''.join(check_cards)}</div>
  </section>
  <section id="parameters"><h2>Parameters</h2><div class="table-wrap"><table>
    <thead><tr><th>Name</th><th>Value</th><th>Unit</th><th>Source</th><th>Description</th></tr></thead>
    <tbody>{''.join(parameter_rows)}</tbody></table></div></section>
</main>
<footer><div class="shell">Generated from source-built computational evidence. Not physical or manufacturing validation.</div></footer>
<script>
for (const button of document.querySelectorAll('[data-filter]')) {{
  button.addEventListener('click', () => {{
    const filter = button.dataset.filter;
    for (const peer of document.querySelectorAll('[data-filter]')) peer.setAttribute('aria-pressed', String(peer === button));
    for (const card of document.querySelectorAll('[data-status]')) {{
      const matches = filter === 'all' || card.dataset.status === filter || (filter === 'review' && card.dataset.status !== 'pass');
      card.hidden = !matches;
    }}
  }});
}}
</script>
</body>
</html>
"""


__all__ = ["render_inspector"]
