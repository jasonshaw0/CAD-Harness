"""Small mechanical-integration fixture for geometry-derived verification.

The 31 mm square mounting pattern is an explicit example interface assumption,
not a certification that every motor sold under the NEMA 17 family matches the
motor envelope, shaft, boss, connector, or clearance values used here.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

from build123d import Align, Box, Cylinder, Part, Pos

from cadharness import (
    DEFAULT_TOLERANCE,
    CADDocument,
    Component,
    CylinderSelector,
    Parameter,
    geometry_measurement_check,
    measure_hole_pattern,
    measure_shape_clearance,
)

Z_MIN = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass(frozen=True)
class MountParameters:
    plate_size: float = 60.0
    plate_thickness: float = 4.0
    mounting_square: float = 31.0
    mounting_hole_diameter: float = 3.5
    generated_hole_count: int = 4
    motor_body: float = 42.3
    motor_length: float = 40.0
    cable_keepout_gap: float = 4.0
    hole_position_shift: float = 0.0
    hole_diameter_offset: float = 0.0

    def validate(self) -> None:
        if any(
            not isfinite(value) or value <= 0
            for value in (
                self.plate_size,
                self.plate_thickness,
                self.mounting_square,
                self.mounting_hole_diameter,
                self.motor_body,
                self.motor_length,
                self.cable_keepout_gap,
            )
        ):
            raise ValueError("mount dimensions must be positive")
        if not 0 <= self.generated_hole_count <= 4:
            raise ValueError("generated_hole_count must be between zero and four")
        if not all(
            isfinite(value)
            for value in (self.hole_position_shift, self.hole_diameter_offset)
        ):
            raise ValueError("fixture offsets must be finite")
        if self.mounting_hole_diameter + self.hole_diameter_offset <= 0:
            raise ValueError("modeled hole diameter must be positive")


DEFAULTS = MountParameters()


def make_plate(params: MountParameters) -> Part:
    plate = Box(
        params.plate_size, params.plate_size, params.plate_thickness, align=Z_MIN
    )
    offset = params.mounting_square / 2
    locations = (
        (-offset, -offset),
        (-offset, offset),
        (offset, offset),
        (offset, -offset),
    )
    for index, (x, y) in enumerate(locations[: params.generated_hole_count]):
        if index == 3:
            x += params.hole_position_shift
        plate -= Pos(x, y, -1) * Cylinder(
            (params.mounting_hole_diameter + params.hole_diameter_offset) / 2,
            params.plate_thickness + 2,
            align=Z_MIN,
        )
    return Part(plate).clean()


def create_project(params: MountParameters = DEFAULTS) -> CADDocument:
    params.validate()
    motor = Pos(0, 0, params.plate_thickness) * Box(
        params.motor_body, params.motor_body, params.motor_length, align=Z_MIN
    )
    keepout_x = params.motor_body / 2 + params.cable_keepout_gap + 2
    keepout = Pos(keepout_x, 0, params.plate_thickness) * Box(4, 20, 10, align=Z_MIN)
    components = {
        "mounting-plate": Component(
            "mounting-plate", make_plate(params), role="printable-part"
        ),
        "motor-envelope": Component(
            "motor-envelope", motor, role="reference-envelope", require_solid=True
        ),
        "cable-keepout": Component(
            "cable-keepout", keepout, role="reference-envelope", require_solid=True
        ),
    }
    parameters = {
        name: Parameter(
            getattr(params, name),
            unit=None if name == "generated_hole_count" else "mm",
            source="explicit-example-assumption",
            description="Illustrative interface value; verify against the selected hardware.",
        )
        for name in params.__dataclass_fields__
    }
    selector = CylinderSelector(
        "mounting-plate",
        radius_min_mm=1.0,
        radius_max_mm=3.0,
        axis_direction=(0, 0, 1),
        concavity="concave",
    )

    def holes(document: CADDocument):
        return measure_hole_pattern(document, "mounting-plate.holes", selector)

    def cable_clearance(document: CADDocument):
        return measure_shape_clearance(
            document, "motor.cable-clearance", "motor-envelope", "cable-keepout"
        )

    hole_spec = {
        "selector": selector.to_dict(),
        "tolerance": DEFAULT_TOLERANCE.to_dict(),
    }

    checks = (
        geometry_measurement_check(
            "mount.hole-count",
            "actual mounting-hole count",
            holes,
            value_path="count",
            expected=4,
            components=("mounting-plate",),
            method="analytic-concave-cylinder-inventory",
            measurement_spec=hole_spec,
        ),
        geometry_measurement_check(
            "mount.hole-diameter",
            "actual mounting-hole diameters",
            holes,
            value_path="diameters_mm",
            expected=params.mounting_hole_diameter,
            absolute_tolerance=1e-6,
            unit="mm",
            components=("mounting-plate",),
            method="analytic-cylinder-radius",
            measurement_spec=hole_spec,
        ),
        geometry_measurement_check(
            "mount.pattern-diameter",
            "actual mounting bolt-circle diameter",
            holes,
            value_path="bolt_circle_diameter_mm",
            expected=params.mounting_square * sqrt(2),
            absolute_tolerance=1e-6,
            unit="mm",
            components=("mounting-plate",),
            method="centroid-circle-fit",
            measurement_spec=hole_spec,
        ),
        geometry_measurement_check(
            "mount.pattern-radial-residual",
            "mounting-hole radial pattern residual",
            holes,
            value_path="maximum_radial_residual_mm",
            maximum=1e-6,
            unit="mm",
            components=("mounting-plate",),
            method="centroid-circle-fit",
            measurement_spec=hole_spec,
        ),
        geometry_measurement_check(
            "mount.pattern-angular-residual",
            "mounting-hole angular pattern residual",
            holes,
            value_path="maximum_angular_residual_deg",
            maximum=1e-4,
            unit="deg",
            components=("mounting-plate",),
            method="centroid-circle-fit",
            measurement_spec=hole_spec,
        ),
        geometry_measurement_check(
            "mount.pattern-center",
            "mounting-hole pattern centered on plate origin",
            holes,
            value_path="centroid_uv_mm",
            expected=0.0,
            absolute_tolerance=1e-6,
            unit="mm",
            components=("mounting-plate",),
            method="projected-axis-centroid",
            measurement_spec=hole_spec,
        ),
        geometry_measurement_check(
            "assembly.cable-clearance",
            "motor envelope to cable keepout clearance",
            cable_clearance,
            value_path="distance_mm",
            minimum=3.0,
            unit="mm",
            components=("motor-envelope", "cable-keepout"),
            method="occt-minimum-distance-and-boolean-common-volume",
            measurement_spec={"tolerance": DEFAULT_TOLERANCE.to_dict()},
        ),
    )
    return CADDocument(
        id="nema17-mount",
        name="Illustrative NEMA 17 Mount",
        revision="example-v1",
        components=components,
        parameters=parameters,
        checks=checks,
        metadata={
            "purpose": "independent mechanical integration and adversarial geometry example",
            "physical_validation": "not performed",
            "standards_note": "Mount pattern is an explicit example assumption; motor details require a selected datasheet or measurement.",
        },
    )
