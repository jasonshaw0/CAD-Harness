"""Explicit, evidence-preserving policies for revision comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from numbers import Real
from pathlib import Path
import json
from typing import Any, Mapping


POLICY_SCHEMA = "cadharness.comparison-policy"
SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class NumericTolerance:
    absolute: float = 0.0
    percent: float = 0.0

    def __post_init__(self) -> None:
        if self.absolute < 0 or self.percent < 0:
            raise ValueError("numeric tolerances cannot be negative")

    def accepts(self, delta: Mapping[str, float]) -> bool:
        if abs(float(delta["delta"])) <= self.absolute:
            return True
        return "percent" in delta and abs(float(delta["percent"])) <= self.percent

    def to_dict(self) -> dict[str, float]:
        return {"absolute": self.absolute, "percent": self.percent}


@dataclass(frozen=True)
class ComparisonPolicy:
    numeric_tolerances: Mapping[str, NumericTolerance] = field(default_factory=dict)
    accepted_changes: Mapping[str, str] = field(default_factory=dict)
    source: str | None = None

    @classmethod
    def exact(cls) -> "ComparisonPolicy":
        return cls()

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, source: str | None = None
    ) -> "ComparisonPolicy":
        if data.get("schema") != POLICY_SCHEMA:
            raise ValueError("comparison policy has an unsupported schema")
        if str(data.get("schema_version")) != SCHEMA_VERSION:
            raise ValueError("comparison policy has an unsupported schema version")

        raw_tolerances = data.get("numeric_tolerances", {})
        if not isinstance(raw_tolerances, Mapping):
            raise TypeError("numeric_tolerances must be an object")
        tolerances: dict[str, NumericTolerance] = {}
        for pattern, raw in raw_tolerances.items():
            if not isinstance(raw, Mapping):
                raise TypeError(f"tolerance {pattern!r} must be an object")
            absolute = raw.get("absolute", 0.0)
            percent = raw.get("percent", 0.0)
            if not isinstance(absolute, Real) or isinstance(absolute, bool):
                raise TypeError(f"tolerance {pattern!r} absolute must be numeric")
            if not isinstance(percent, Real) or isinstance(percent, bool):
                raise TypeError(f"tolerance {pattern!r} percent must be numeric")
            tolerances[str(pattern)] = NumericTolerance(float(absolute), float(percent))

        raw_acceptances = data.get("accepted_changes", [])
        if not isinstance(raw_acceptances, list):
            raise TypeError("accepted_changes must be a list")
        accepted: dict[str, str] = {}
        for index, record in enumerate(raw_acceptances):
            if not isinstance(record, Mapping):
                raise TypeError(f"accepted_changes[{index}] must be an object")
            path = record.get("path")
            reason = record.get("reason")
            if not isinstance(path, str) or not path:
                raise ValueError(f"accepted_changes[{index}] needs a path")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(f"accepted_changes[{index}] needs a reason")
            if path in accepted:
                raise ValueError(f"duplicate accepted change path: {path}")
            accepted[path] = reason.strip()
        return cls(tolerances, accepted, source)

    @classmethod
    def from_file(
        cls, path: str | Path, *, source: str | None = None
    ) -> "ComparisonPolicy":
        resolved = Path(path).resolve()
        with resolved.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, Mapping):
            raise TypeError("comparison policy root must be an object")
        return cls.from_dict(data, source=source or str(resolved))

    @staticmethod
    def _match(path: str, choices: Mapping[str, Any]) -> tuple[str, Any] | None:
        if path in choices:
            return path, choices[path]
        matches = [pattern for pattern in choices if fnmatchcase(path, pattern)]
        if not matches:
            return None
        pattern = max(matches, key=lambda item: (len(item.replace("*", "")), len(item)))
        return pattern, choices[pattern]

    def classify(
        self, path: str, delta: Mapping[str, float] | None = None
    ) -> dict[str, Any]:
        accepted = self._match(path, self.accepted_changes)
        if accepted:
            pattern, reason = accepted
            return {
                "disposition": "accepted",
                "policy_path": pattern,
                "reason": reason,
            }
        tolerance_match = self._match(path, self.numeric_tolerances)
        if delta is not None and tolerance_match:
            pattern, tolerance = tolerance_match
            if tolerance.accepts(delta):
                return {
                    "disposition": "tolerated",
                    "policy_path": pattern,
                    "tolerance": tolerance.to_dict(),
                }
        return {"disposition": "significant"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "numeric_tolerances": {
                path: tolerance.to_dict()
                for path, tolerance in sorted(self.numeric_tolerances.items())
            },
            "accepted_changes": [
                {"path": path, "reason": reason}
                for path, reason in sorted(self.accepted_changes.items())
            ],
        }


__all__ = ["ComparisonPolicy", "NumericTolerance"]
