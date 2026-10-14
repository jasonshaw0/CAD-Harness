"""Simple flange example that exercises cylindrical geometry and hole patterns."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin

from build123d import Align, Cylinder, Part, Pos

from cadharness import CADDocument, Component, Parameter, equals_check, minimum_check


Z_MIN = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass(frozen=True)
class PipeFlangeParameters:
    flange_diameter: float = 70.0
    flange_thickness: float = 8.0
    hub_diameter: float = 36.0
    hub_height: float = 18.0
    bore_diameter: float = 20.0
    bolt_circle_diameter: float = 50.0
    bolt_hole_diameter: float = 5.5
    bolt_count: int = 6

    def validate(self) -> None:
        dimensions = (
            self.flange_diameter,
            self.flange_thickness,
            self.hub_diameter,
            self.hub_height,
            self.bore_diameter,
            self.bolt_circle_diameter,
            self.bolt_hole_diameter,
        )
        if any(value <= 0 for value in dimensions):
            raise ValueError("pipe-flange dimensions must be positive")
        if self.bolt_count < 3:
            raise ValueError("bolt_count must be at least three")
        if not self.bore_diameter < self.hub_diameter <= self.flange_diameter:
            raise ValueError("diameters must satisfy bore < hub <= flange")
        if self.hub_height < self.flange_thickness:
            raise ValueError("hub height must include the flange thickness")
        if self.bolt_edge_ligament <= 0:
            raise ValueError("bolt holes break through the flange edge")
        if self.bolt_circle_diameter / 2 - self.bolt_hole_diameter / 2 <= self.hub_diameter / 2:
            raise ValueError("bolt holes intersect the hub")

    @property
    def hub_wall(self) -> float:
        return (self.hub_diameter - self.bore_diameter) / 2

    @property
    def bolt_edge_ligament(self) -> float:
        return (
            self.flange_diameter - self.bolt_circle_diameter - self.bolt_hole_diameter
        ) / 2


DEFAULTS = PipeFlangeParameters()


def make_flange(params: PipeFlangeParameters = DEFAULTS) -> Part:
    params.validate()
    flange = Cylinder(params.flange_diameter / 2, params.flange_thickness, align=Z_MIN)
    hub = Cylinder(params.hub_diameter / 2, params.hub_height, align=Z_MIN)
    body = flange + hub
    cutter_height = params.hub_height + 2
    body -= Pos(0, 0, -1) * Cylinder(
        params.bore_diameter / 2, cutter_height, align=Z_MIN
    )
    bolt_radius = params.bolt_circle_diameter / 2
    for index in range(params.bolt_count):
        angle = radians(index * 360 / params.bolt_count)
        x = bolt_radius * cos(angle)
        y = bolt_radius * sin(angle)
        body -= Pos(x, y, -1) * Cylinder(
            params.bolt_hole_diameter / 2,
            params.flange_thickness + 2,
            align=Z_MIN,
        )
    return Part(body).clean()


def create_project(params: PipeFlangeParameters = DEFAULTS) -> CADDocument:
    params.validate()
    component = Component(
        "flange",
        make_flange(params),
        role="example-part",
        material=None,
        source="project.make_flange",
        metadata={"manufacturing_process": "unspecified"},
    )
    parameters = {
        name: Parameter(
            getattr(params, name),
            unit=None if name == "bolt_count" else "mm",
            source="configurable-default",
            description="Example value; replace with requirements for a real application.",
        )
        for name in params.__dataclass_fields__
    }
    checks = (
        equals_check(
            "dimensions.outside-diameter",
            "outside diameter",
            lambda document: document.components["flange"].shape.bounding_box().size.X,
            params.flange_diameter,
            absolute_tolerance=1e-7,
            unit="mm",
        ),
        equals_check(
            "dimensions.overall-height",
            "overall height",
            lambda document: document.components["flange"].shape.bounding_box().size.Z,
            params.hub_height,
            absolute_tolerance=1e-7,
            unit="mm",
        ),
        minimum_check(
            "geometry.hub-wall",
            "radial hub wall",
            params.hub_wall,
            5.0,
            unit="mm",
            evidence={"classification": "example design rule"},
        ),
        minimum_check(
            "geometry.bolt-edge-ligament",
            "radial material outside each bolt hole",
            params.bolt_edge_ligament,
            4.0,
            unit="mm",
            evidence={"classification": "example design rule"},
        ),
        equals_check(
            "pattern.bolt-count",
            "bolt-hole pattern count",
            params.bolt_count,
            params.bolt_count,
        ),
    )
    return CADDocument(
        id="pipe-flange",
        name="Parametric Pipe Flange",
        revision="example-v1",
        components={"flange": component},
        parameters=parameters,
        checks=checks,
        metadata={
            "purpose": "exercise cylindrical topology and repeated features",
            "physical_validation": "not performed",
            "manufacturing_note": "Dimensions and checks are illustrative, not a rated flange specification.",
        },
    )
