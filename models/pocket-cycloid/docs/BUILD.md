# Print, assemble, and demonstrate

## Design and chosen constraints

All dimensions are millimeters. These are chosen defaults, not user measurements.
The assembled shaft is the Z axis. Hold the fixed frame and turn the upright grip;
the rear output stem turns in the opposite direction, one turn per nine input turns
under the ideal contact motion law. Running gaps introduce real backlash.

| Feature | Chosen constraint | Evidence |
| --- | --- | --- |
| Body | 90 mm diameter | Final rear-frame bounding box |
| Axial envelope | Z=-8 to +50.5; 58.5 overall | Final assembled component bounds |
| Mechanism | 10 fixed pins, 9 cycloid lobes | Actual cylindrical faces and final perimeter maxima |
| Eccentric | 1.5 mm offset; 12 mm journal | Actual shaft cylinder axis; named source geometry |
| Disc | 6 mm thick, Z=9.4..15.4 | Final solid bounds |
| Fixed pins | 7 mm diameter, 66 mm pitch circle | Final cylinder inventory used by motion sweep |
| Output coupling | Three 5.6 mm pins on 40 mm pitch circle; 9.2 mm holes | Actual pin/hole cylinders used by motion sweep |
| Front frame | 5 mm thick, three 7 mm ribs, continuous 9 mm rim | Final material chords, connected-solid check |
| Pin support | Integral rear roots and blind front sockets | Source features and closure-path collision check |
| Visibility | 15 mm clear side height; 28.54 mm front chord at Y=15 | Empty-line intersections through final frame |
| Crank | 28 mm radius; 11 mm grip, 21 mm above crank | Named source features; crank rotation sweep |
| Crank clearance | At least 0.5 mm to fixed frame at nominal Z | 72 sampled crank angles |
| Retention | Four identical printed fork cotters | Separate connected solids; see elastic-fit gap below |
| Crank tang roof | 1.8 mm above cotter slot | Final material chord through shaft top |

The disc uses a sampled inward normal offset of the pin-centre hypotrochoid,
with 720 straight segments (80 per lobe). It is a conjugate cycloidal flank,
not a decorative wave. The [closed-form construction](https://github.com/medinstech/cycloidgen/blob/main/README.md#the-geometry)
also explains the orbit-compensating output holes. This model implements that
construction directly without depending on the linked program.

## Printing

Starting process assumption: PETG, 0.4 mm nozzle, 0.2 mm layers, at least four
perimeters, and locally solid pins, shaft, grip roots, and cotters. These settings
are provisional, not a qualified print process. All assembly parts are printed;
no purchased bearings, screws, nuts, glue, springs, or lubricant are required.
The plain cylindrical journals and fixed pins slide directly against plastic.

Use contrasting filament for the disc and frame so the lobes are easy to follow.
The CAD preview uses Studio's default material. The grip is fixed to the crank;
it is not a separate free-spinning knob.

| Part | Quantity | Suggested bed orientation and support |
| --- | --- | --- |
| rear-frame | 1 | Z=0 face down; pins upright; bridge the short cotter slots |
| front-frame | 1 | Flip top face Z=24 onto bed so blind pin sockets open upward |
| output-carrier | 1 | Rear shaft end Z=-8 down; support the underside of the wide carrier flange |
| cycloid-disc | 1 | Z=9.4 face down; dimple on top; no supports |
| eccentric-input | 1 | Rear journal end Z=-7.5 down, with a brim; support cam/thrust-shoulder overhangs |
| crank | 1 | Z=24.5 face down; grip upright; no supports |
| fork cotter | 4 | Flat XY face down; all four are identical; no supports |

The source stores assembled placements. Drop each exported part to the bed in
the slicer and apply the orientations above; do not print the assembly in place.
Geometry export is available explicitly through cadHarness/Studio. No STEP/STL
exports were generated during this task.

Nominal radial running gaps are 0.30 mm (0.60 mm diametral), including disc/cam,
shaft/journals, pin sockets, and orbit-compensating output holes. The square tang
is 7 mm across flats in a 7.5 mm crank socket. Cotter slots are 4.6 by 2.6;
the flat cotter stem is 4 by 2. Remove support residue, strings, and first-layer
flare before assembly. Trial-fit each plain journal without force. Hole and
elephant-foot compensation depend on the actual printer; if fits need adjustment,
edit the named gap and rebuild/recheck, rather than scaling mating parts independently.

## Assembly

1. Put the output carrier into the rear frame from the open front. Its hollow
   output stem passes through the rear central opening. The three output pins
   point forward; the three small thrust pads face the disc.
2. Slide the disc onto the eccentric input **from the rear journal end**. Keep
   the dimple facing forward. At the source's zero pose, the eccentric offset
   points toward the dimple and one output hole. The 9 mm rear journal clears
   the disc bore even with the 1.5 mm offset; there is no trapped lower flange.
3. Lower the disc/input subassembly into the rear frame. Feed the rear input
   journal into the carrier's hollow stem and the three carrier pins through
   the disc holes. Rotate the parts gently until all nine lobes seat inside
   the ten fixed pins. Do not force an incorrect phase. The dimple/one-hole
   direction points toward a fixed pin in the source's zero pose.
4. Lower the front frame over the input tang/journal, the ten pin tips, and
   the three retention posts. Its underside rests on the post shoulders.
   Every pin tip enters its matching blind socket.
5. Insert three flat cotters tangentially through the exposed post slots.
   Push the tapered fork tips through first; both hooks must emerge on the far
   side and spring outward. The broad tab stays on the insertion side.
6. Slide the crank over the square input tang. Insert the fourth identical
   cotter through the tang slot above the crank. Check that its hooks emerge.
   The crank should retain a small axial gap above the front hub and turn freely.

All rigid insertion paths were checked at 1 mm translation increments, including
the disc-on-shaft path before the subassembly enters the cage. Cotter insertion
requires elastic deflection and is not a rigid collision-free insertion.

The cotter's hook width is 5.8 mm through a 4.6 mm slot: each arm must deflect
about 0.6 mm. A simple cantilever estimate gives about 1% bending strain using
a 1.5 mm arm and roughly 11.5 mm flex length. This is a design estimate only;
printed retention force and fatigue need physical tests. Confirm both hooks
engage. Squeeze the exposed fork tips to remove a key; do not pull against
engaged hooks.

## Verification and physical trial

From the repository root:

```powershell
.venv\Scripts\python.exe models\pocket-cycloid\verify.py
```

The saved [verification report](../evidence/verification.json) includes:

- 51 passing geometry/source checks, with valid single-solid components.
- Zero nominal overlap in all 45 assembled component pairs.
- Five rigid insertion paths, 125 poses total, with zero sampled overlap.
- 72 crank poses with at least 0.5 mm stationary clearance.
- Disc/ring motion at 1,081 poses over nine input turns, reading the actual
  final disc segments and actual cylindrical pin/hole faces.
- Minimum sampled mesh gap 0.2975 mm. A point-distance Lipschitz bound gives
  at least 0.1579 mm between samples for the same nominal ideal motion.
- Minimum output-pin/hole clearance 0.3000 mm over the motion sweep.
- A deliberately incorrect 8:1 motion intersects the pins by 0.8414 mm in the
  section-distance test, confirming the check rejects the wrong motion law.
- Separate +/-0.3 mm axial-shift checks against the fixed frame.

These checks establish nominal geometry, structural continuity, and kinematic
compatibility. They do not prove friction, tolerance accumulation, comfort,
torque capacity, impact strength, print quality, or snap durability.

For the first physical trial, turn the assembled crank through nine slow turns
in each direction without loading the output. Confirm continuous motion, one
opposite output revolution, retained keys, and no rubbing or rising effort.
Then apply only light finger resistance to the rear stem. Inspect the pin roots
and cotters afterward. Physical fit and operation remain open until this trial.

## Editable source and scope

`project.py` is authoritative; `cadharness.toml` registers its factory. The named
parameters expose the profile, eccentricity, running gap and displayed input
angle. The packaged frame and axial stack are intentionally constrained to the
ten-pin/nine-lobe, 6 mm disc configuration. Other tooth counts or stack thicknesses
require a frame/stack redesign and renewed verification.

Studio design `design-316a6790` retains the source and frozen acceptance brief.
The PNGs in `previews/` were returned through actual cadHarness MCP capture.
