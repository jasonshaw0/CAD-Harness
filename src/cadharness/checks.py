"""Reusable geometric and engineering check constructors."""

from __future__ import annotations

from math import isclose
from typing import Any, Callable, Mapping

from .model import CADDocument, Check, CheckResult, CheckStatus


ValueSource = Any | Callable[[CADDocument], Any]


def _value(source: ValueSource, document: CADDocument) -> Any:
    return source(document) if callable(source) else source


def _measurement_evidence(
    kind: str, evidence: Mapping[str, Any] | None
) -> dict[str, Any]:
    return {"measurement_kind": kind, **dict(evidence or {})}


def range_check(
    check_id: str,
    description: str,
    actual: ValueSource,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    unit: str | None = None,
    evidence: Mapping[str, Any] | None = None,
    category: str = "dimension",
) -> Check:
    """Check a measured value against one or both inclusive bounds."""
    if minimum is None and maximum is None:
        raise ValueError("range_check requires a minimum, maximum, or both")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("range_check minimum cannot exceed maximum")

    expected = {
        key: value
        for key, value in (("minimum", minimum), ("maximum", maximum))
        if value is not None
    }

    def evaluate(document: CADDocument) -> CheckResult:
        measured = float(_value(actual, document))
        passed = (minimum is None or measured >= minimum) and (
            maximum is None or measured <= maximum
        )
        bounds = " and ".join(f"{name} {value:g}{unit or ''}" for name, value in expected.items())
        return CheckResult(
            id=check_id,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            message=(
                f"{description}: {measured:g}{unit or ''} is within {bounds}"
                if passed
                else f"{description}: {measured:g}{unit or ''} is outside {bounds}"
            ),
            actual=measured,
            expected=expected,
            unit=unit,
            evidence=dict(evidence or {}),
        )

    return Check(check_id, description, evaluate, category=category)


def clearance_check(
    check_id: str,
    description: str,
    actual: ValueSource,
    minimum: float,
    *,
    maximum: float | None = None,
    unit: str = "mm",
    evidence: Mapping[str, Any] | None = None,
) -> Check:
    """Check a modeled clearance while preserving its measurement meaning."""
    return range_check(
        check_id,
        description,
        actual,
        minimum=minimum,
        maximum=maximum,
        unit=unit,
        evidence=_measurement_evidence("clearance", evidence),
        category="clearance",
    )


def wall_thickness_check(
    check_id: str,
    description: str,
    actual: ValueSource,
    minimum: float,
    *,
    unit: str = "mm",
    evidence: Mapping[str, Any] | None = None,
) -> Check:
    """Check a modeled wall or section thickness against a lower bound."""
    return range_check(
        check_id,
        description,
        actual,
        minimum=minimum,
        unit=unit,
        evidence=_measurement_evidence("wall-thickness", evidence),
        category="section",
    )


def hole_diameter_check(
    check_id: str,
    description: str,
    actual: ValueSource,
    nominal: float,
    *,
    lower_deviation: float = 0.0,
    upper_deviation: float = 0.0,
    unit: str = "mm",
    evidence: Mapping[str, Any] | None = None,
) -> Check:
    """Check a hole diameter against explicit nominal deviations."""
    if lower_deviation > upper_deviation:
        raise ValueError("hole lower_deviation cannot exceed upper_deviation")
    return range_check(
        check_id,
        description,
        actual,
        minimum=nominal + lower_deviation,
        maximum=nominal + upper_deviation,
        unit=unit,
        evidence=_measurement_evidence(
            "hole-diameter",
            {
                "nominal": nominal,
                "lower_deviation": lower_deviation,
                "upper_deviation": upper_deviation,
                **dict(evidence or {}),
            },
        ),
        category="hole",
    )


def minimum_check(
    check_id: str,
    description: str,
    actual: ValueSource,
    minimum: float,
    *,
    unit: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> Check:
    def evaluate(document: CADDocument) -> CheckResult:
        measured = float(_value(actual, document))
        passed = measured >= minimum
        return CheckResult(
            id=check_id,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            message=(
                f"{description}: {measured:g}{unit or ''} meets minimum {minimum:g}{unit or ''}"
                if passed
                else f"{description}: {measured:g}{unit or ''} is below {minimum:g}{unit or ''}"
            ),
            actual=measured,
            expected={"minimum": minimum},
            unit=unit,
            evidence=evidence or {},
        )

    return Check(check_id, description, evaluate)


def maximum_check(
    check_id: str,
    description: str,
    actual: ValueSource,
    maximum: float,
    *,
    unit: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> Check:
    def evaluate(document: CADDocument) -> CheckResult:
        measured = float(_value(actual, document))
        passed = measured <= maximum
        return CheckResult(
            id=check_id,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            message=(
                f"{description}: {measured:g}{unit or ''} is within {maximum:g}{unit or ''}"
                if passed
                else f"{description}: {measured:g}{unit or ''} exceeds {maximum:g}{unit or ''}"
            ),
            actual=measured,
            expected={"maximum": maximum},
            unit=unit,
            evidence=evidence or {},
        )

    return Check(check_id, description, evaluate)


def equals_check(
    check_id: str,
    description: str,
    actual: ValueSource,
    expected: Any,
    *,
    absolute_tolerance: float = 0.0,
    unit: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> Check:
    def evaluate(document: CADDocument) -> CheckResult:
        measured = _value(actual, document)
        if isinstance(measured, (int, float)) and isinstance(expected, (int, float)):
            passed = isclose(
                float(measured),
                float(expected),
                rel_tol=0.0,
                abs_tol=absolute_tolerance,
            )
        else:
            passed = measured == expected
        return CheckResult(
            id=check_id,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            message=(
                f"{description}: observed expected value"
                if passed
                else f"{description}: observed {measured!r}, expected {expected!r}"
            ),
            actual=measured,
            expected={"value": expected, "absolute_tolerance": absolute_tolerance},
            unit=unit,
            evidence=evidence or {},
        )

    return Check(check_id, description, evaluate)


def boolean_check(
    check_id: str,
    description: str,
    actual: ValueSource,
    *,
    evidence: dict[str, Any] | None = None,
) -> Check:
    return equals_check(
        check_id,
        description,
        lambda document: bool(_value(actual, document)),
        True,
        evidence=evidence,
    )


def interference_check(
    check_id: str,
    first_component: str,
    second_component: str,
    *,
    maximum_volume_mm3: float = 1e-5,
    description: str | None = None,
) -> Check:
    summary = description or f"{first_component} and {second_component} do not overlap"

    def evaluate(document: CADDocument) -> CheckResult:
        first = document.components[first_component].shape
        second = document.components[second_component].shape
        intersection = first & second
        volume = 0.0 if intersection is None else float(intersection.volume)
        passed = volume <= maximum_volume_mm3
        return CheckResult(
            id=check_id,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            message=(
                f"{summary}: overlap {volume:g}mm^3"
                if passed
                else f"{summary}: overlap {volume:g}mm^3 exceeds {maximum_volume_mm3:g}mm^3"
            ),
            actual=volume,
            expected={"maximum": maximum_volume_mm3},
            unit="mm^3",
            evidence={"components": [first_component, second_component]},
        )

    return Check(check_id, summary, evaluate, category="interference")
