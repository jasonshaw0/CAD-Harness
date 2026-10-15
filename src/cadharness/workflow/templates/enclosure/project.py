"""Small two-part electronics enclosure used as a framework example."""

from __future__ import annotations

from dataclasses import dataclass

from build123d import Align, Box, Part, Pos

from cadharness import (
    CADDocument,
    Component,
    EvidenceKind,
    Parameter,
    clearance_check,
    equals_check,
    interference_check,
    wall_thickness_check,
)


Z_MIN = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass(frozen=True)
class ProjectBoxParameters:
    inside_x: float = 60.0
    inside_y: float = 40.0
    inside_z: float = 20.0
    wall: float = 2.4
    floor: float = 2.4
    lid_thickness: float = 2.4
    locating_skirt_depth: float = 3.0
    locating_skirt_wall: float = 2.0
    lid_clearance_per_side: float = 0.30

    def validate(self) -> None:
        positive = (
            self.inside_x,
            self.inside_y,
            self.inside_z,
            self.wall,
            self.floor,
            self.lid_thickness,
            self.locating_skirt_depth,
            self.locating_skirt_wall,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("project-box dimensions must be positive")
        if self.lid_clearance_per_side < 0:
            raise ValueError("lid clearance cannot be negative")
        skirt_x = self.inside_x - 2 * self.lid_clearance_per_side
        skirt_y = self.inside_y - 2 * self.lid_clearance_per_side
        if min(skirt_x, skirt_y) <= 2 * self.locating_skirt_wall:
            raise ValueError("locating skirt wall consumes the skirt interior")

    @property
    def outside_x(self) -> float:
        return self.inside_x + 2 * self.wall

    @property
    def outside_y(self) -> float:
        return self.inside_y + 2 * self.wall

    @property
    def base_height(self) -> float:
        return self.inside_z + self.floor


DEFAULTS = ProjectBoxParameters()


def make_base(params: ProjectBoxParameters = DEFAULTS) -> Part:
    params.validate()
    outer = Box(params.outside_x, params.outside_y, params.base_height, align=Z_MIN)
    cavity = Pos(0, 0, params.floor) * Box(
        params.inside_x,
        params.inside_y,
        params.inside_z + 1.0,
        align=Z_MIN,
    )
    return Part(outer - cavity).clean()


def make_lid(params: ProjectBoxParameters = DEFAULTS) -> Part:
    params.validate()
    top = Pos(0, 0, params.base_height) * Box(
        params.outside_x,
        params.outside_y,
        params.lid_thickness,
        align=Z_MIN,
    )
    skirt_x = params.inside_x - 2 * params.lid_clearance_per_side
    skirt_y = params.inside_y - 2 * params.lid_clearance_per_side
    skirt_outer = Box(
        skirt_x,
        skirt_y,
        params.locating_skirt_depth,
        align=Z_MIN,
    )
    skirt_inner = Pos(0, 0, -0.5) * Box(
        skirt_x - 2 * params.locating_skirt_wall,
        skirt_y - 2 * params.locating_skirt_wall,
        params.locating_skirt_depth + 1.0,
        align=Z_MIN,
    )
    skirt = Pos(0, 0, params.base_height - params.locating_skirt_depth) * (
        skirt_outer - skirt_inner
    )
    return Part(top + skirt).clean()


def create_project(params: ProjectBoxParameters = DEFAULTS) -> CADDocument:
    params.validate()
    components = {
        "base": Component(
            "base",
            make_base(params),
            role="printable-part",
            material="printed-polymer",
            source="project.make_base",
        ),
        "lid": Component(
            "lid",
            make_lid(params),
            role="printable-part",
            material="printed-polymer",
            source="project.make_lid",
        ),
    }
    parameters = {
        name: Parameter(
            getattr(params, name),
            unit="mm",
            source="configurable-default",
            description="Example value; tune for the intended contents, process, and material.",
        )
        for name in params.__dataclass_fields__
    }

    checks = (
        interference_check(
            "assembly.base-lid-interference",
            "base",
            "lid",
            maximum_volume_mm3=1e-5,
            description="assembled base and lid have no solid interference",
        ),
        clearance_check(
            "fit.lid-clearance",
            "nominal lid skirt clearance per side",
            params.lid_clearance_per_side,
            0.20,
            unit="mm",
            evidence={"classification": "configurable-default, not physically verified"},
        ),
        wall_thickness_check(
            "manufacturing.minimum-wall",
            "minimum modeled wall thickness",
            min(params.wall, params.floor, params.lid_thickness, params.locating_skirt_wall),
            1.6,
            unit="mm",
            evidence={"classification": "example design rule"},
        ),
        equals_check(
            "dimensions.outside-x",
            "base outside X dimension",
            lambda document: document.components["base"].shape.bounding_box().size.X,
            params.outside_x,
            absolute_tolerance=1e-7,
            unit="mm",
            evidence_kind=EvidenceKind.GEOMETRY,
            measurement_method="occt-bounding-box",
            components=("base",),
        ),
        equals_check(
            "dimensions.outside-y",
            "base outside Y dimension",
            lambda document: document.components["base"].shape.bounding_box().size.Y,
            params.outside_y,
            absolute_tolerance=1e-7,
            unit="mm",
            evidence_kind=EvidenceKind.GEOMETRY,
            measurement_method="occt-bounding-box",
            components=("base",),
        ),
    )
    return CADDocument(
        id="project-box",
        name="Parametric Project Box",
        revision="example-v1",
        components=components,
        parameters=parameters,
        checks=checks,
        metadata={
            "purpose": "general-purpose regression example",
            "physical_validation": "not performed",
            "manufacturing_note": "Clearance and wall rules are configurable examples, not universal print-process values.",
        },
    )
