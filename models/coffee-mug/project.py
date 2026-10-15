"""Editable ceramic mug concept. Millimeters; axis Z, bottom Z=0, handle +X.

The user elected to preserve the handle envelope and grip, accepting the smaller
opening. The 2 mm lip roundover is on the OUTER edge: two R2 edge fillets cannot
fit across a 3 mm wall. Bore diameter and depth remain exact.
"""
from dataclasses import dataclass, fields
from math import pi

from build123d import (
    Align, BuildLine, Cylinder, Edge, Ellipse, GeomType, Line, Part, Plane,
    Pos, ThreePointArc, fillet, sweep,
)
from cadharness import (
    CADDocument, Component, EvidenceKind, Parameter, equals_check,
    geometry_measurement_check, measure_directional_thickness,
)

Z_MIN = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass(frozen=True)
class MugParameters:
    outer_diameter: float = 90.0
    height: float = 96.0
    wall: float = 3.0
    bottom: float = 6.0
    rim_radius: float = 2.0
    base_radius: float = 2.0
    overall_width: float = 128.0
    handle_upper_z: float = 74.0
    handle_lower_z: float = 24.0
    grip_height: float = 16.0
    grip_thickness: float = 12.0
    root_blend: float = 2.0
    handle_embed: float = 2.0
    include_handle: bool = True  # Set False for a body-only construction preview.

    @property
    def outer_radius(self):
        return self.outer_diameter / 2

    @property
    def inner_radius(self):
        return self.outer_radius - self.wall

    @property
    def inner_depth(self):
        return self.height - self.bottom

    @property
    def handle_radius(self):
        return (self.handle_upper_z - self.handle_lower_z) / 2

    @property
    def handle_center_x(self):
        # Max X = width - body radius; the outer grip adds half its major axis.
        return self.overall_width - self.outer_radius - self.grip_height / 2 - self.handle_radius

    def validate(self):
        dimensions = [getattr(self, f.name) for f in fields(self) if f.name != 'include_handle']
        if any(value <= 0 for value in dimensions):
            raise ValueError('All dimensions must be positive')
        if not 0 < self.wall < self.outer_radius or not 0 < self.bottom < self.height:
            raise ValueError('The cavity must fit inside the body')
        if self.rim_radius >= self.wall or self.base_radius >= self.bottom:
            raise ValueError('Roundovers must fit within wall and bottom thickness')
        if self.handle_radius <= self.grip_height / 2:
            raise ValueError('Handle bend is too tight for the grip')
        if self.handle_center_x <= self.outer_radius:
            raise ValueError('Overall width is too small for this circular handle')
        if self.handle_lower_z - self.grip_height / 2 <= self.base_radius:
            raise ValueError('Lower root must clear the base roundover')
        if self.handle_upper_z + self.grip_height / 2 >= self.height - self.rim_radius:
            raise ValueError('Upper root must clear the rim')
        if self.handle_embed >= self.wall:
            raise ValueError('Keep handle sweep endpoints within the body wall')


DEFAULTS = MugParameters()


def make_outer_body(p=DEFAULTS):
    """Round only the exterior circular edges, preserving exact OD and height."""
    body = Cylinder(p.outer_radius, p.height, align=Z_MIN)
    top = [e for e in body.edges().filter_by(GeomType.CIRCLE)
           if abs(e.center().Z - p.height) < 1e-6]
    body = fillet(top, p.rim_radius)
    bottom = [e for e in body.edges().filter_by(GeomType.CIRCLE)
              if abs(e.center().Z) < 1e-6]
    return fillet(bottom, p.base_radius)


def make_cavity(p=DEFAULTS):
    return Pos(0, 0, p.bottom) * Cylinder(p.inner_radius, p.inner_depth, align=Z_MIN)


def make_handle(p=DEFAULTS):
    """G1-continuous D loop: two straight roots and one exact semicircular bend.

    The ellipse is 16 mm in the path's normal plane and 12 mm across Y. Its
    major axis starts vertical and follows the bend, giving a rounded grip.
    """
    root_x = p.outer_radius - p.handle_embed
    bend_x = p.handle_center_x
    middle_z = (p.handle_upper_z + p.handle_lower_z) / 2
    with BuildLine() as path:
        Line((root_x, 0, p.handle_upper_z), (bend_x, 0, p.handle_upper_z))
        ThreePointArc((bend_x, 0, p.handle_upper_z),
                      (bend_x + p.handle_radius, 0, middle_z),
                      (bend_x, 0, p.handle_lower_z))
        Line((bend_x, 0, p.handle_lower_z), (root_x, 0, p.handle_lower_z))
    section_plane = Plane(origin=(root_x, 0, p.handle_upper_z),
                          x_dir=(0, 0, 1), z_dir=(1, 0, 0))
    section = section_plane * Ellipse(p.grip_height / 2, p.grip_thickness / 2)
    return sweep(section, path=path.wire(), is_frenet=False)


def make_mug(p=DEFAULTS):
    p.validate()
    exterior = make_outer_body(p)
    if p.include_handle:
        exterior += make_handle(p)
        # Select the actual curved root/body intersections, never the body's
        # periodic cylinder seam or the sweep's smooth tangent joins.
        roots = [e for e in exterior.edges()
                 if e.geom_type == GeomType.BSPLINE
                 and e.bounding_box().min.X > p.outer_radius - p.handle_embed
                 and e.bounding_box().max.X < p.outer_radius + 1e-5
                 and e.bounding_box().min.Z > p.base_radius
                 and e.bounding_box().max.Z < p.height - p.rim_radius]
        if len(roots) != 4:
            raise ValueError(f'Expected four half-ellipse root edges, found {len(roots)}')
        exterior = fillet(roots, p.root_blend)
    # Cut last: blending the roots can never put material inside the bore.
    return Part(exterior - make_cavity(p)).clean()


def clear_span(shape, start, end):
    """Longest empty segment on a specified measurement line, in millimeters."""
    empty = Edge.make_line(start, end).cut(shape)
    return max(e.length for e in empty.edges())


def capacity_mm3(shape, p=DEFAULTS):
    """OCCT volume of the specified internal cavity after all final features."""
    return make_cavity(p).cut(shape).volume


def create_project(p=DEFAULTS):
    mug = make_mug(p)
    def shape(document):
        return document.components['mug'].shape

    def check(key, description, read, expected, unit='mm', tolerance=.001):
        return equals_check(key, description, read, expected, unit=unit,
                            absolute_tolerance=tolerance, evidence_kind=EvidenceKind.GEOMETRY,
                            measurement_method='occt-final-solid', components=('mug',))

    checks = [
        check('body.height', 'Overall height', lambda d: shape(d).bounding_box().size.Z, p.height),
        check('body.diameter', 'Body diameter across Y', lambda d: shape(d).bounding_box().size.Y, p.outer_diameter),
        check('body.base-z', 'Flat bottom rests on Z=0', lambda d: shape(d).bounding_box().min.Z, 0),
        check('mug.width', 'Overall width with handle', lambda d: shape(d).bounding_box().size.X, p.overall_width),
        check('mug.solids', 'One fused watertight solid', lambda d: len(shape(d).solids()), 1, None),
        check('cavity.capacity', 'Internal cavity volume', lambda d: capacity_mm3(shape(d), p),
              pi * p.inner_radius ** 2 * p.inner_depth, 'mm^3', .01),
    ]
    if p.include_handle:
        mid_z = (p.handle_upper_z + p.handle_lower_z) / 2
        checks += [
            check('handle.opening-horizontal', 'Clear opening at handle mid-height',
                  lambda d: clear_span(shape(d), (p.outer_radius - 1, 0, mid_z),
                                       (p.overall_width - p.outer_radius + 1, 0, mid_z)),
                  p.overall_width - p.outer_diameter - p.grip_height),
            check('handle.opening-vertical', 'Clear opening through bend center',
                  lambda d: clear_span(shape(d), (p.handle_center_x, 0, p.handle_lower_z),
                                       (p.handle_center_x, 0, p.handle_upper_z)),
                  2 * p.handle_radius - p.grip_height),
        ]
        for key, point, direction, expected in [
            ('upper-height', (p.handle_center_x - 1, 0, p.handle_upper_z), (0, 0, 1), p.grip_height),
            ('upper-thickness', (p.handle_center_x - 1, 0, p.handle_upper_z), (0, 1, 0), p.grip_thickness),
            ('lower-height', (p.handle_center_x - 1, 0, p.handle_lower_z), (0, 0, 1), p.grip_height),
            ('lower-thickness', (p.handle_center_x - 1, 0, p.handle_lower_z), (0, 1, 0), p.grip_thickness),
            ('outer-grip-height', (p.handle_center_x + p.handle_radius, 0, mid_z), (1, 0, 0), p.grip_height),
            ('outer-grip-thickness', (p.handle_center_x + p.handle_radius, 0, mid_z), (0, 1, 0), p.grip_thickness),
        ]:
            checks.append(geometry_measurement_check(
                'handle.' + key, key,
                lambda d, point=point, direction=direction, key=key: measure_directional_thickness(
                    d, key, 'mug', [point], direction),
                value_path='minimum_mm', expected=expected, absolute_tolerance=.001,
                unit='mm', components=('mug',)))
    parameters = {f.name: Parameter(getattr(p, f.name), unit=None if f.name == 'include_handle' else 'mm',
                                   source='configurable-default' if f.name in {'root_blend', 'handle_embed', 'include_handle'}
                                   else 'user-statement') for f in fields(p)}
    return CADDocument(
        id='coffee-mug', name='Parametric coffee mug', revision='1',
        components={'mug': Component('mug', mug, role='printable-part', material='ceramic concept',
                                      source='project.make_mug')},
        parameters=parameters, checks=tuple(checks),
        metadata={'capacity_ml': capacity_mm3(mug, p) / 1000,
                  'handle_resolution': 'User accepted smaller opening to preserve 128 mm width, Z74/24 roots and 16x12 grip.',
                  'rim_detail': 'R2 outer lip only; 1 mm flat top land preserves the exact 84 mm bore.',
                  'manufacturing': 'Finished nominal ceramic geometry; process shrinkage and glaze allowance not applied.'})
