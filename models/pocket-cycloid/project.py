"""All-printed, open-frame cycloidal reducer. mm, assembled axis Z.

The flank is the inward normal offset of the pin-centre hypotrochoid,
not a sinusoidal approximation. Polygon sampling is deliberately explicit:
the independent motion check reads the actual final disc's straight edges.
No bought hardware, lubricant, or rolling bearings are required by the design.
Physical fit, friction and cotter endurance are not established by CAD.
"""
from dataclasses import dataclass, fields
from math import cos, sin, pi, radians

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from build123d import Align, Box, Cylinder, Edge, GeomType, Part, Polygon, Pos, Rot, extrude
from cadharness import CADDocument, Component, EvidenceKind, Parameter, equals_check, range_check

Z_MIN = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass(frozen=True)
class GearboxParameters:
    ring_pins: int = 10
    pin_circle_radius: float = 33.0
    ring_pin_radius: float = 3.5
    eccentricity: float = 1.5
    running_gap: float = 0.30  # radial, not diametral
    body_radius: float = 45.0
    output_pin_radius: float = 2.8
    output_pin_circle: float = 20.0
    disc_thickness: float = 6.0
    profile_samples: int = 720
    input_angle_deg: float = 0.0

    def validate(self):
        if self.ring_pins != 10 or self.profile_samples % (self.ring_pins - 1):
            raise ValueError('This packaged frame is a ten-pin/nine-lobe design; use whole-lobe sampling')
        if not 0.15 <= self.running_gap <= .5 or not 1 <= self.eccentricity <= 1.8:
            raise ValueError('Gap/eccentricity outside the documented frame envelope')
        if self.disc_thickness != 6 or self.body_radius < 45:
            raise ValueError('Changing stack thickness or shrinking the frame needs a stack redesign')
        if self.eccentricity * self.ring_pins >= self.pin_circle_radius:
            raise ValueError('Invalid curtate coefficient')


def cyl(radius, lo, hi, x=0, y=0):
    return Pos(x, y, lo) * Cylinder(radius, hi-lo, align=Z_MIN)


def box(sx, sy, lo, hi, x=0, y=0):
    return Pos(x, y, lo) * Box(sx, sy, hi-lo, align=Z_MIN)


def polar(radius, degrees):
    a = radians(degrees)
    return radius*cos(a), radius*sin(a)


def profile(p):
    t = np.arange(p.profile_samples) * 2*pi/p.profile_samples
    n, r, e = p.ring_pins, p.pin_circle_radius, p.eccentricity
    k = e*n/r
    den = np.sqrt(1 + k*k - 2*k*np.cos((n-1)*t))
    roller = p.ring_pin_radius + p.running_gap
    return np.column_stack((r*np.cos(t)-e*np.cos(n*t)-roller*(np.cos(t)-k*np.cos(n*t))/den,
                            r*np.sin(t)-e*np.sin(n*t)-roller*(np.sin(t)-k*np.sin(n*t))/den))


def make_rear(p):
    rear = cyl(p.body_radius, 0, 4) - cyl(8+p.running_gap, -1, 5)
    # Pin roots are continuous with the rear plate; front sockets brace their tips.
    for i in range(p.ring_pins):
        x, y = polar(p.pin_circle_radius, i*360/p.ring_pins)
        rear += cyl(p.ring_pin_radius, 3.8, 21.8, x, y)
    for a in (60, 180, 300):
        x, y = polar(40, a)
        post = cyl(4.8, 3.8, 19, x, y) + cyl(4, 18.9, 28, x, y)
        slot = Pos(x, y, 0) * Rot(0, 0, a) * box(4.6, 13, 24.2, 26.8)
        rear += post - slot
    # A rear-face radial index notch makes carrier rotation easy to compare.
    rear -= box(7, 1.2, -.1, .65, 13, 0)
    return Part(rear).clean()


def make_front(p):
    front = cyl(p.body_radius, 19, 24) - cyl(36, 18, 25)
    front += cyl(11, 19, 24)
    for a in (60, 180, 300):
        # Three 7 mm wide ribs join the central journal to the continuous rim.
        front += Rot(0, 0, a) * box(32, 7, 19, 24, 23, 0)
    for i in range(p.ring_pins):
        x, y = polar(p.pin_circle_radius, i*360/p.ring_pins)
        front += cyl(5.2, 19, 24, x, y)
    for i in range(p.ring_pins):
        x, y = polar(p.pin_circle_radius, i*360/p.ring_pins)
        front -= cyl(p.ring_pin_radius+p.running_gap, 18, 22.3, x, y)
    for a in (60, 180, 300):
        x, y = polar(40, a)
        front -= cyl(4.3, 18, 25, x, y)
    return Part(front - cyl(5+p.running_gap, 18, 25)).clean()


def make_output(p):
    carrier = cyl(24, 4.4, 8) + cyl(8, -8, 4.5)
    carrier -= cyl(4.5+p.running_gap, -9, 9)
    # Relief keeps the cam clear even at the extremes of axial end float.
    carrier -= cyl(9.2, 7.2, 9.1)
    for i in range(3):
        x, y = polar(p.output_pin_circle, i*120)
        carrier += cyl(p.output_pin_radius, 7.8, 17.8, x, y)
        x, y = polar(11, i*120)
        carrier += cyl(1.8, 7.8, 9.0, x, y)
    # Two rear flats and a shallow index groove: visible, graspable output.
    carrier -= box(20, 4, -8.1, -2, 0, 9)
    carrier -= box(20, 4, -8.1, -2, 0, -9)
    carrier -= box(4, 1.0, -8.1, -7.4, 6.6, 0)
    return Part(carrier).clean()


def make_disc(p):
    pts = profile(p)
    disc = Pos(0, 0, 9.4) * extrude(Polygon(*[tuple(v) for v in pts], align=None), amount=p.disc_thickness)
    disc -= cyl(6+p.running_gap, 9, 16)
    for i in range(3):
        x, y = polar(p.output_pin_circle, i*120)
        disc -= cyl(p.output_pin_radius+p.eccentricity+p.running_gap, 9, 16, x, y)
    # A single blind dimple marks one lobe without weakening its flank.
    disc -= cyl(.6, 14.6, 15.5, 26, 0)
    return Part(disc).clean()


def make_input(p):
    e = p.eccentricity
    # The rear journal plus eccentricity fits through the disc bore: the disc
    # can actually slide onto this shaft from the rear before cage assembly.
    shaft = cyl(4.5, -7.5, 9.1)
    shaft += cyl(6, 8.9, 15.9, e)
    shaft += cyl(7.5, 15.8, 16.5, e)
    shaft += cyl(8.5, 16.4, 18.6)
    shaft += cyl(5, 18.5, 24.3)
    shaft += box(7, 7, 24.2, 34.4)
    shaft -= box(4.6, 12, 30.0, 32.6)
    return Part(shaft).clean()


def make_crank(p):
    # This part prints flat on Z=24.5, with the grip growing straight upwards.
    crank = cyl(10, 24.5, 29.5) + box(28, 13, 24.5, 29.5, 14)
    crank += cyl(6.5, 24.5, 29.5, 28)
    crank += cyl(5.5, 29.4, 49.5, 28)
    crank += cyl(6, 48.5, 50.5, 28)
    crank -= box(7.5, 7.5, 24, 30)
    return Part(crank).clean()


def make_cotter():
    # Forks flex in the XY print plane. 0.6 mm deflection per arm through slot.
    outline = [(-4, 7), (-4, 10), (4, 10), (4, 7), (2, 7),
               (2, -3.5), (2.9, -3.5), (2.9, -5.5), (1.4, -7),
               (-1.4, -7), (-2.9, -5.5), (-2.9, -3.5), (-2, -3.5), (-2, 7)]
    # Reverse the clockwise outline to extrude towards +Z.
    key = extrude(Polygon(*outline[::-1], align=None), amount=2)
    key -= box(1.0, 12, -.1, 2.1, 0, -2)
    return Part(key).clean()


def clear_span(shape, start, end):
    cut = Edge.make_line(start, end).cut(shape)
    return max((e.length for e in cut.edges()), default=0)


def overlap_volume(a, b):
    common = a.intersect(b)
    return 0.0 if common is None else common.volume


def material_span(shape, start, end):
    common = Edge.make_line(start,end).intersect(shape)
    return 0 if common is None else sum(e.length for e in common.edges())


def final_disc_polygon(disc):
    """Read all 720 actual straight lower perimeter segments after hole cuts."""
    segments = []
    for edge in disc.edges():
        vertices = edge.vertices()
        if len(vertices) != 2:
            continue
        a, b = vertices
        if abs(a.Z-9.4)<1e-5 and abs(b.Z-9.4)<1e-5 and min(a.X*a.X+a.Y*a.Y, b.X*b.X+b.Y*b.Y)>26**2:
            segments.append(((a.X, a.Y), (b.X, b.Y)))
    return np.asarray(segments)


def min_segment_gaps(segments, points, radius):
    a = segments[:, 0]
    v = segments[:, 1]-a
    w = points[:, None, :]-a[None, :, :]
    t = np.clip(np.sum(w*v, axis=2)/np.sum(v*v, axis=1), 0, 1)
    dist = np.linalg.norm(w-t[:, :, None]*v, axis=2)
    return np.min(dist, axis=1)-radius


def cylinder_xy(shape, concave, radial_min, radial_max):
    found = []
    for face in shape.faces():
        if face.geom_type != GeomType.CYLINDER or face.is_circular_concave != concave:
            continue
        point = face.axis_of_rotation.position
        radial = (point.X**2+point.Y**2)**.5
        if radial_min < radial < radial_max:
            radius = BRepAdaptor_Surface(face.wrapped, True).Cylinder().Radius()
            found.append((point.X, point.Y, radius))
    return np.array(sorted(found, key=lambda v: np.arctan2(v[1],v[0])), dtype=float)


def motion_evidence(disc, rear, output, shaft, p, steps=1081):
    """Full nine input turns, 3-degree increments, using final BREP segments.

    Includes exact analytic output-hole containment, and a wrong-ratio control.
    This is a discrete unloaded kinematic test, not friction or life simulation.
    """
    seg = final_disc_polygon(disc)
    if len(seg) != p.profile_samples:
        raise ValueError(f'Expected {p.profile_samples} perimeter segments, found {len(seg)}')
    ring_features = cylinder_xy(rear, False, 30, 35)
    hole_features = cylinder_xy(disc, True, 18, 22)
    pin_features = cylinder_xy(output, False, 18, 22)
    cam_features = cylinder_xy(shaft,False, .9, 2)
    eccentricity = float(np.linalg.norm(cam_features[0,:2]))
    if abs(eccentricity-p.eccentricity)>1e-6:
        raise ValueError('Actual eccentric journal does not match the motion law')
    if len(ring_features)!=10 or len(hole_features)!=3 or len(pin_features)!=3:
        raise ValueError('Actual ring-pin/output-hole/output-pin inventories do not match')
    ring, holes, pins = ring_features[:, :2], hole_features[:, :2], pin_features[:, :2]
    if not all(np.isfinite(x).all() for x in (seg, ring_features, hole_features, pin_features)):
        raise ValueError('Nonfinite geometry in motion evidence')
    radii = np.linalg.norm(np.unique(seg.reshape(-1,2),axis=0),axis=1)
    vertices = np.unique(seg.reshape(-1,2),axis=0)
    order = np.argsort(np.arctan2(vertices[:,1],vertices[:,0]))
    radii = radii[order]
    lobes = int(np.sum((radii > np.roll(radii,1)) & (radii > np.roll(radii,-1))))
    if lobes != len(ring)-1:
        raise ValueError(f'Actual disc has {lobes} radial peaks against {len(ring)} pins')
    min_mesh, max_nearest, min_hole, wrong = 1e6, -1e6, 1e6, 1e6
    for phi in np.linspace(0, 2*pi*(p.ring_pins-1), steps):
        a = -phi/(p.ring_pins-1)
        rotation = np.array([[cos(a), -sin(a)], [sin(a), cos(a)]])
        offset = p.eccentricity*np.array([cos(phi), sin(phi)])
        # inverse rotate the fixed ring-pin centres into the disc frame
        centres = (ring-offset) @ rotation
        gaps = min_segment_gaps(seg, centres, ring_features[:,2])
        min_mesh = min(min_mesh, float(gaps.min()))
        max_nearest = max(max_nearest, float(gaps.min()))
        hole_world = holes @ rotation.T + offset
        pin_world = pins @ rotation.T
        min_hole = min(min_hole, float((hole_features[:,2]-pin_features[:,2]
                                      -np.linalg.norm(hole_world-pin_world, axis=1)).min()))
        if phi <= 2*pi+.001:
            bad = -phi/(p.ring_pins-2)
            rb = np.array([[cos(bad), -sin(bad)], [sin(bad), cos(bad)]])
            wrong = min(wrong, float(min_segment_gaps(seg, (ring-offset)@rb, ring_features[:,2]).min()))
    # Point-to-segment distance is 1-Lipschitz. Bound travel between a sampled
    # pose and its nearest sample, covering the continuous interval as well.
    speed_bound = (float(np.linalg.norm(ring,axis=1).max()) + p.eccentricity*p.ring_pins)/(p.ring_pins-1)
    half_step = pi*(p.ring_pins-1)/(steps-1)
    continuous_lower = min_mesh-speed_bound*half_step
    return {'perimeter_segments': len(seg), 'poses': steps, 'input_turns': p.ring_pins-1,
            'output_turns': -1, 'actual_lobes':lobes, 'actual_ring_pins':len(ring),
            'actual_output_hole_diameter_mm':float(2*hole_features[0,2]),
            'measured_eccentricity_mm':eccentricity,
            'mesh_min_mm': min_mesh, 'mesh_nearest_max_mm': max_nearest,
            'continuous_mesh_lower_bound_mm': continuous_lower,
            'output_pin_min_mm': min_hole, 'wrong_ratio_min_mm': wrong}


def create_project(p=GearboxParameters()):
    p.validate()
    disc_local = make_disc(p)
    rear, output, shaft = make_rear(p), make_output(p), make_input(p)
    motion = motion_evidence(disc_local, rear, output, shaft, p)
    phi = radians(p.input_angle_deg)
    out_angle = -p.input_angle_deg/(p.ring_pins-1)
    offset = (p.eccentricity*cos(phi), p.eccentricity*sin(phi))
    shapes = {'rear-frame': rear, 'front-frame': make_front(p),
              'output-carrier': Rot(0, 0, out_angle)*output,
              'cycloid-disc': Pos(*offset, 0)*Rot(0, 0, out_angle)*disc_local,
              'eccentric-input': Rot(0, 0, p.input_angle_deg)*shaft,
              'crank': Rot(0, 0, p.input_angle_deg)*make_crank(p)}
    key = make_cotter()
    for index, a in enumerate((60, 180, 300), 1):
        x, y = polar(40, a)
        shapes[f'frame-key-{index}'] = Pos(x, y, 24.5)*Rot(0, 0, a)*key
    shapes['crank-key'] = Rot(0, 0, p.input_angle_deg)*Pos(0, 0, 30.3)*key
    colors = {'rear-frame': '#365B6D', 'front-frame': '#365B6D', 'cycloid-disc': '#F4B942',
              'output-carrier': '#48B8A5', 'eccentric-input': '#E97157', 'crank': '#E97157'}
    components = {k: Component(k, s, role='printable-part', material='PETG (design assumption)',
                              metadata={'color': colors.get(k, '#C6D1DA')}) for k, s in shapes.items()}
    def s(d, k): return d.components[k].shape
    def equal(k, desc, fn, target, unit='mm', tol=.001, ids=()):
        return equals_check(k, desc, fn, target, unit=unit, absolute_tolerance=tol,
                            evidence_kind=EvidenceKind.GEOMETRY, measurement_method='occt-final-solid', components=ids)
    def lower(k, desc, fn, minimum, unit='mm', ids=()):
        return range_check(k, desc, fn, minimum=minimum, unit=unit, evidence_kind=EvidenceKind.GEOMETRY,
                           measurement_method='occt-final-solid-or-brep-section-kinematics', components=ids)
    checks = [equal('body.diameter', '90 mm handheld body', lambda d: s(d, 'rear-frame').bounding_box().size.X, 90),
              equal('mesh.segment-count', 'Read complete final cycloid perimeter', lambda d: motion['perimeter_segments'], p.profile_samples, None),
              equal('mesh.lobes', 'Nine measured radial lobe maxima', lambda d: motion['actual_lobes'],9,None),
              equal('mesh.fixed-pins', 'Ten measured fixed cylindrical pins', lambda d: motion['actual_ring_pins'],10,None),
              equal('mesh.eccentricity','Measured eccentric journal offset',lambda d:motion['measured_eccentricity_mm'],1.5),
              equal('output.hole-diameter','Measured orbit-compensation hole diameter',lambda d:motion['actual_output_hole_diameter_mm'],9.2),
              lower('mesh.full-motion', 'No ring interference in 1081 poses over nine input turns', lambda d: motion['mesh_min_mm'], .27),
              lower('mesh.continuous-bound', 'Conservative between-sample bound remains positive', lambda d: motion['continuous_mesh_lower_bound_mm'], .15),
              range_check('mesh.wrong-ratio-control', 'Incorrect 8:1 motion must jam', lambda d: motion['wrong_ratio_min_mm'],
                          maximum=-.1, unit='mm', evidence_kind=EvidenceKind.GEOMETRY,
                          measurement_method='final-brep-section-negative-control'),
              lower('output.hole-motion', 'Output pins remain inside orbit-compensating holes', lambda d: motion['output_pin_min_mm'], .299),
              lower('window.side-height', 'Uninterrupted central side viewing height',
                    lambda d: clear_span(s(d, 'rear-frame')+s(d, 'front-frame'), (0, 40, 4), (0, 40, 19)), 15),
              lower('window.front-width', 'Front view opening across mechanism at Y=15',
                    lambda d: clear_span(s(d, 'front-frame'), (-24, 15, 21), (24, 15, 21)), 18),
              lower('crank.frame-clearance', 'Assembled crank clears stationary frame',
                    lambda d: s(d, 'crank').distance_to(s(d, 'front-frame')), .49),
              lower('shaft.front-clearance', 'Input shaft clears front journal',
                    lambda d: s(d, 'eccentric-input').distance_to(s(d, 'front-frame')), .29)]
    for i,a in enumerate((60,180,300),1):
        x,y=polar(23,a)
        nx,ny=polar(5,a+90)
        checks.append(equal('structure.rib-'+str(i),'Measured 7 mm front rib chord',
            lambda d,x=x,y=y,nx=nx,ny=ny:material_span(s(d,'front-frame'),(x-nx,y-ny,21),(x+nx,y+ny,21)),7))
    checks.append(equal('structure.rim','Continuous rim is 9 mm radially at a free span',
        lambda d:material_span(s(d,'front-frame'),(0,35,21),(0,46,21)),9))
    checks.append(equal('structure.tang-roof','Crank cotter slot retains a 1.8 mm top wall',
        lambda d:material_span(s(d,'eccentric-input'),(0,0,32.5),(0,0,34.5)),1.8))
    for k in components:
        checks.append(equal('solid.'+k, 'One connected printable solid: '+k, lambda d,k=k: len(s(d,k).solids()), 1, None))
    # Actual OCCT common at the assembled pose. Contact is permitted, overlap is not.
    for a,b in [('rear-frame','front-frame'), ('rear-frame','output-carrier'),
                ('rear-frame','cycloid-disc'), ('front-frame','cycloid-disc'),
                ('output-carrier','eccentric-input'), ('output-carrier','cycloid-disc'),
                ('eccentric-input','cycloid-disc'), ('crank','eccentric-input'),
                ('rear-frame','frame-key-1'), ('rear-frame','frame-key-2'), ('rear-frame','frame-key-3'),
                ('eccentric-input','crank-key')]:
        checks.append(equal('overlap.'+a+'.'+b, 'Zero assembled interference: '+a+'/'+b,
                            lambda d,a=a,b=b: overlap_volume(s(d,a),s(d,b)), 0, 'mm^3', .001, (a,b)))
    return CADDocument(id='pocket-cycloid', name='Pocket Cycloid — all-printed 9:1 gearbox', revision='1',
        components=components, checks=tuple(checks),
        parameters={f.name: Parameter(getattr(p,f.name), unit=None if f.name in {'ring_pins','profile_samples'} else
                    'deg' if f.name=='input_angle_deg' else 'mm', source='configurable-default') for f in fields(p)},
        metadata={'coordinate_frame':'Axis Z; rear plate Z0..4; disc Z9.4..15.4; front Z19..24; handle to Z50.5',
                  'motion_evidence':motion, 'ratio':'9:1 opposite direction; one fewer disc lobe than fixed pins',
                  'physical_validation':'Not printed; dry friction, fit, snap retention and endurance need physical trial',
                  'assembly':'See README.md; four identical flat-printed split cotters; no outside hardware',
                  'profile_reference':'https://github.com/medinstech/cycloidgen/blob/main/README.md#the-geometry'})
