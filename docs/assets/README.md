# README assets

`studio-hero.png` is a real 1920 × 1080 Studio screenshot, captured on
2026-10-15 through Playwriter using its private headless Chrome session.
It shows Pocket Cycloid revision r003, ten components, and its 21 recorded
workflow requirements. These results are computational evidence; physical fit
remains unverified.

The capture used a separate workspace containing a copy of the existing built
design. Original CAD source, evidence, and the active workspace were preserved.
No image generation, compositing, or replacement UI data was used.

To refresh the image, build Studio, open a dedicated workspace through
Playwriter, select a built design, choose dark mode, enable the construction
grid, and open engineering checks. Fit, orbit, zoom, and pan with the actual
viewport controls to frame the assembly between the floating panels. Hide the
Playwriter ghost cursor and capture with `page.screenshot`, an absolute output
path, and `scale: 'css'`. Inspect the saved image and browser logs before replacing
the asset. See [browser acceptance](../STUDIO_UI_ACCEPTANCE.md) for session setup.

`python.svg` and `build123d.svg` are local SVG badges reflecting the supported
versions in `pyproject.toml`; they require no third-party badge service.
