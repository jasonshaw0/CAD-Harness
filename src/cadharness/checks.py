"""Reusable geometric and engineering check constructors."""

from __future__ import annotations

from math import isclose
from typing import Any, Callable

from .model import CADDocument, Check, CheckResult, CheckStatus


ValueSource = Any | Callable[[CADDocument], Any]


def _value(source: ValueSource, document: CADDocument) -> Any:
    return source(document) if callable(source) else source


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

