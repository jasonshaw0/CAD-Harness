"""Illustrative dimensions, not a hardware specification or print qualification.

Edit named parameters or a manifest variant. Acceptance lives outside this file.
"""

from dataclasses import dataclass
from math import cos, sin, radians, sqrt, isfinite

from build123d import Align, Box, Cylinder, Part, Pos
from cadharness import CADDocument, Component, Parameter

Z_MIN = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass(frozen=True)
class PlateParameters:
    size_x: float = 60.0
    size_y: float = 60.0
    thickness: float = 4.0
    circular: bool = False
    pattern: str = "square"
    mounting_square: float = 31.0
    bolt_circle: float = 50.0
    hole_count: int = 4
    hole_diameter: float = 3.5
    bore_diameter: float = 0.0
    reference_envelopes: bool = True
    motor_body: float = 42.3
    motor_length: float = 40.0
    cable_gap: float = 4.0
    modeled_hole_count: int = -1
    last_hole_shift: float = 0.0
    diameter_offset: float = 0.0
    rotation_offset_deg: float = 0.0
    blind_bore: bool = False

    def validate(self):
        for name in ("size_x", "size_y", "thickness", "mounting_square", "bolt_circle", "hole_diameter", "motor_body", "motor_length", "cable_gap"):
            value = getattr(self, name)
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.pattern not in {"square", "circle"} or self.hole_count < 3:
            raise ValueError("use square/circle patterns of at least three holes")
        if self.pattern == "square" and self.hole_count != 4:
            raise ValueError("square pattern requires four holes")
        if not -1 <= self.modeled_hole_count <= self.hole_count:
            raise ValueError("modeled_hole_count must be -1 or a bounded fixture count")
        for name in ("bore_diameter", "last_hole_shift", "diameter_offset", "rotation_offset_deg"):
            if not isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        if self.bore_diameter < 0 or self.hole_diameter + self.diameter_offset <= 0:
            raise ValueError("invalid bore/hole diameter")


def make_plate(params):
    params.validate()
    shape = (Cylinder(params.size_x / 2, params.thickness, align=Z_MIN) if params.circular
             else Box(params.size_x, params.size_y, params.thickness, align=Z_MIN))
    radius = params.mounting_square / sqrt(2) if params.pattern == "square" else params.bolt_circle / 2
    first = 45 if params.pattern == "square" else 0
    count = params.hole_count if params.modeled_hole_count < 0 else params.modeled_hole_count
    for index in range(count):
        angle = radians(first + index * 360 / params.hole_count + params.rotation_offset_deg)
        x, y = radius * cos(angle), radius * sin(angle)
        if index == count - 1:
            x += params.last_hole_shift
        shape -= Pos(x, y, -1) * Cylinder((params.hole_diameter + params.diameter_offset) / 2,
                                        params.thickness + 2, align=Z_MIN)
    if params.bore_diameter:
        start = params.thickness / 2 if params.blind_bore else -1
        shape -= Pos(0, 0, start) * Cylinder(params.bore_diameter / 2, params.thickness + 2, align=Z_MIN)
    return Part(shape).clean()


def create_project(params: PlateParameters = PlateParameters()):
    components = {"plate": Component("plate", make_plate(params), role="printable-part")}
    if params.reference_envelopes:
        motor = Pos(0, 0, params.thickness) * Box(params.motor_body, params.motor_body, params.motor_length, align=Z_MIN)
        keepout = Pos(params.motor_body / 2 + params.cable_gap + 2, 0, params.thickness) * Box(4, 20, 10, align=Z_MIN)
        components.update({"motor-envelope": Component("motor-envelope", motor, role="reference-envelope"),
                           "cable-keepout": Component("cable-keepout", keepout, role="reference-envelope")})
    return CADDocument(
        id="mounting-plate", name="Editable mounting plate", revision="source-v1", components=components,
        parameters={name: Parameter(getattr(params, name),
                                   unit="deg" if name == "rotation_offset_deg" else "mm" if name in {
                                       "size_x", "size_y", "thickness", "mounting_square", "bolt_circle", "hole_diameter",
                                       "bore_diameter", "motor_body", "motor_length", "cable_gap", "last_hole_shift", "diameter_offset"} else None,
                                   source="configurable-default",
                                   description="Illustrative source parameter; acceptance is defined in the brief.")
                    for name in params.__dataclass_fields__},
        metadata={"physical_validation": "not performed", "coordinate_frame": "XY plate; lower face Z=0"})
