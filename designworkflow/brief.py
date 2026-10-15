"""Versioned design intent. Reading a brief never imports candidate Python."""

from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import re

IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$")
SOURCES = {"user-statement", "user-measurement", "referenced-specification",
           "calculation", "configurable-default", "unverified-assumption"}
UNITS = {"mm": ("mm", 1.0), "cm": ("mm", 10.0), "m": ("mm", 1000.0),
         "in": ("mm", 25.4), "deg": ("deg", 1.0)}


def read_json(path: Path) -> dict:
    def invalid(value):
        raise ValueError(f"nonfinite JSON number: {value}")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8-sig"),
                       parse_constant=invalid, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def digest(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def number(value, label: str, *, nonnegative=False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if nonnegative and value < 0:
        raise ValueError(f"{label} must be nonnegative")
    return float(value)


def identifier(value, label="id") -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a stable lowercase identifier")
    return value


def validate_brief(brief: dict) -> dict:
    """Validate intent and add normalized dimension records without changing input."""
    if brief.get("schema") != "designworkflow.brief" or brief.get("schema_version") != "1":
        raise ValueError("unsupported designworkflow brief schema/version")
    identifier(brief.get("id"))
    if type(brief.get("revision")) is not int or brief["revision"] < 1:
        raise ValueError("brief revision must be a positive integer")
    if brief.get("domain") not in {"mounting-plate", "simple-enclosure"}:
        raise ValueError("supported domains: mounting-plate, simple-enclosure")
    if not isinstance(brief.get("coordinate_frame"), str) or not brief["coordinate_frame"].strip():
        raise ValueError("coordinate_frame is required")
    printable = brief.get("printable_components")
    if not isinstance(printable, list) or not printable or len(printable) != len(set(printable)):
        raise ValueError("printable_components must list distinct expected printable component IDs")
    for name in printable:
        identifier(name, "printable component")
    normalized = {}
    for name, record in brief.get("dimensions", {}).items():
        identifier(name, "dimension")
        if not isinstance(record, dict) or record.get("unit") not in UNITS:
            raise ValueError(f"dimension {name}: explicit supported units are required")
        if record.get("source") not in SOURCES or not record.get("prompt_ref"):
            raise ValueError(f"dimension {name}: source and prompt_ref are required")
        unit, scale = UNITS[record["unit"]]
        value = number(record.get("value"), name)
        normalized[name] = {"value": value * scale, "unit": unit, "original": record}
        if "normalized_value" in record and abs(number(record["normalized_value"], name) - value * scale) > 1e-9:
            raise ValueError(f"dimension {name}: conflicting original and normalized units")
    for key in ("questions", "assumptions", "physical_validation_gaps", "requirements"):
        if not isinstance(brief.get(key), list):
            raise ValueError(f"{key} must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in brief["physical_validation_gaps"]):
        raise ValueError("physical_validation_gaps must contain nonempty descriptions")
    for item in brief["questions"] + brief["assumptions"]:
        if not isinstance(item, dict) or not item.get("description") or type(item.get("blocking")) is not bool:
            raise ValueError("questions/assumptions require description and boolean blocking")
    ids = set()
    for req in brief["requirements"]:
        if not isinstance(req, dict):
            raise ValueError("requirements must contain objects")
        req_id = identifier(req.get("id"), "requirement id")
        if req_id in ids:
            raise ValueError(f"duplicate requirement id: {req_id}")
        ids.add(req_id)
        if not req.get("description") or not req.get("prompt_ref"):
            raise ValueError(f"{req_id}: description and prompt_ref are required")
        if type(req.get("mandatory")) is not bool:
            raise ValueError(f"{req_id}: mandatory must be boolean")
        if req.get("evidence_kind") not in {"geometry-derived", "declared", "external"}:
            raise ValueError(f"{req_id}: evidence_kind is required")
        if not isinstance(req.get("binding"), dict) or not req["binding"].get("type"):
            raise ValueError(f"{req_id}: binding type is required")
        criteria = req.get("criteria", {})
        if not isinstance(criteria, dict) or set(criteria) - {"expected", "minimum", "maximum", "absolute_tolerance"}:
            raise ValueError(f"{req_id}: unsupported acceptance criteria")
        for key in ("minimum", "maximum", "absolute_tolerance"):
            if key in criteria:
                number(criteria[key], f"{req_id}.{key}", nonnegative=key == "absolute_tolerance")
        if isinstance(criteria.get("expected"), (int, float)):
            number(criteria["expected"], f"{req_id}.expected")
        if "minimum" in criteria and "maximum" in criteria and criteria["minimum"] > criteria["maximum"]:
            raise ValueError(f"{req_id}: inverted bounds")
        if req.get("unit") not in {None, "mm", "deg", "mm^3"}:
            raise ValueError(f"{req_id}: check units must be normalized")
    if not any(req["mandatory"] for req in brief["requirements"]):
        raise ValueError("at least one mandatory requirement is required")
    json.dumps(brief, allow_nan=False)
    return {**brief, "normalized_dimensions": normalized}


def load_brief(path: Path) -> dict:
    return validate_brief(read_json(path))
