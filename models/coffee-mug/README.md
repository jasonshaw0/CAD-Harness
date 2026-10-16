# Parametric coffee mug

Edit `MugParameters` in [project.py](project.py). The factory returns one fused
solid; body, bore, oval sweep and root blends remain separate readable features.
All dimensions are finished nominal millimeters, without ceramic shrinkage or
glaze allowances.

| Feature | Dimension |
| --- | --- |
| Cylindrical body | Ø90 × 96 high, axis at XY origin, base Z=0 |
| Bore | Ø84, Z=6 to Z=96, 90 deep |
| Straight wall / bottom | 3 / 6 |
| Exterior lip / bottom fillets | R2 / R2 |
| Handle root center heights | Z=74 / Z=24 |
| Overall width including +X handle | 128 |
| Oval grip section | 16 in the path-normal direction × 12 across Y |
| Root blends | R2 |
| Measured cavity capacity | 498.759 mL |

The user chose to preserve width, attachment centers and grip section, accepting
a smaller handle opening: **22 horizontal at Z=49 × 34 vertical at X=50**.
These are clear spans on two perpendicular measurement lines, not a guaranteed
22 × 34 rectangular clearance envelope. The handle uses a semicircular path
with tangent horizontal roots. Its oval major axis follows the bend.

The R2 lip rounds the **outer** edge and leaves a 1 mm flat top land. Two R2
fillets across a 3 mm wall would overlap. The inner bore and floor remain exact;
the flat bottom contact disk has radius 43 mm. No foot ring is added.

```powershell
.\.venv\Scripts\python.exe -m cadharness verify models/coffee-mug --summary
```

Or on Linux/macOS, from the repository root:
`./.venv/bin/python -m cadharness verify models/coffee-mug --summary`.

The 15 source checks cover validity, one solid, bounds, cavity volume, handle
opening spans and grip chords. Studio's retained brief additionally checks
actual wall and bottom chords. The bore was independently measured through MCP
as an analytic Ø84 cylindrical surface spanning Z=6 to Z=96.

Live Studio: <http://127.0.0.1:8741>, design `design-b366d14f`, finished revision
`r002`. The preceding revision shows the body construction stage. Both retain
their complete Python/TOML source and measured evidence. The task-local MCP
client keeps this viewer connection open; restarting it does not delete the
saved design in `runs/studio`.
