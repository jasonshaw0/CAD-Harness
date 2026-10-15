"""Versioned, installed workflow guidance shared by every MCP host."""

from .paths import WORKFLOW_ROOT

GUIDE_VERSION = "1"
SERVER_INSTRUCTIONS = (
    "Author editable parametric build123d projects within configured trusted roots. "
    "Read get_cad_authoring_guide before first authoring. Resolve contradictory "
    "dimensions, preserve frozen requirements, and verify built geometry. "
    "Use studio_render_view adaptively for uncertain shapes and interfaces; "
    "screenshots are optional, never a completion gate. No personal skill or desktop "
    "control is needed. Python factories execute trusted local code, not sandboxed code."
)


def authoring_guide():
    return {"version": GUIDE_VERSION, "guide": (WORKFLOW_ROOT / "AUTHORING.md").read_text(encoding="utf-8")}
