# Third-party software and distribution scope

Reviewed 2026-10-16 for CAD-Harness 0.10.0b1. CAD-Harness's own code is
Copyright 2026 Jason Shaw, licensed under [Apache-2.0](LICENSE). Upstream
software retains its own terms. These notices do not relicense dependencies.

## Bundled frontend

The wheel and source archive contain compiled JavaScript with fflate,
lucide-react, react, react-dom, scheduler and three. Their versions, copyright
notices and complete license texts are generated from the npm lockfile into
`cadharness/studio/web/THIRD_PARTY_LICENSES.md` in the wheel (under `src/` in
the sdist). Studio serves the same bytes at `/THIRD_PARTY_LICENSES.md`.
Lucide includes its ISC and MIT attribution; retain the complete generated
file rather than replacing it with CAD-Harness's Apache license.

An identical, versioned copy is in [licenses/FRONTEND.txt](licenses/FRONTEND.txt),
also included in `.dist-info/licenses/`. The distribution's SPDX expression is
`Apache-2.0 AND MIT AND ISC` to account for the bundled frontend; CAD-Harness's
own license remains Apache-2.0. Separately installed dependencies are not added
to that expression. See [PyPA's bundled-license example](https://packaging.python.org/en/latest/guides/licensing-examples-and-user-scenarios/#advanced-example).

Vite and the other frontend build/test tools are development dependencies;
`node_modules` is not shipped. The sdist includes the editable frontend and
lockfile. Rebuild and check notices when changing dependencies.

## Separately installed Python dependencies

CAD-Harness release downloads contain its wheel, source archive and evidence;
they do not contain Python, an environment, dependency wheels or native
libraries. Pip obtains dependencies separately. The fresh-install gate retains
`DEPENDENCIES.json`, including exact installed versions, declared license
metadata, license-file hashes and native-file names for that runner. Metadata
is an inventory, not proof that an upstream wheel includes all required notices.
Dependency ranges are not a reproducible lock; other installation dates and
platforms can resolve different versions.

The reviewed direct dependencies are build123d 0.13.0 (Apache-2.0), mcp 2.3.0
(MIT), Starlette 1.8.0 and Uvicorn 0.54.0 (BSD-3-Clause). Their installed wheels
include license files. build123d also includes its upstream NOTICE. These
packages and their transitive dependencies are not copied into our artifacts.

## Native geometry provenance

CAD-Harness makes use of facilities provided by **Open CASCADE Technology
(OCCT)** through build123d and the OCP Python wrapper. The reviewed chain is:

1. [build123d v0.13.0](https://github.com/gumyr/build123d/tree/v0.13.0)
   declares `cadquery-ocp-novtk>=8.0,<8.1`.
2. The inspected `cadquery-ocp-novtk` and `cadquery-ocp-proxy` 8.0.1.1.0 wheels
   declare Apache-2.0 for the wrapper. Their installed file records contain no
   LICENSE/NOTICE files. That declaration does **not** describe OCCT's terms.
   [Package record](https://pypi.org/project/cadquery-ocp-novtk/8.0.1.1.0/).
3. The upstream [OCP build recipe](https://github.com/CadQuery/ocp-build-system/tree/eace4e42cfa2c162ac39bc36864534fe5f5787a6)
   identifies OCP 8.0.1.1 and OCCT 8.0.1. It downloads generated OCP release
   sources and clones OCCT tag `V8_0_1`, applying the recipe's patches.
   [OCP source release](https://github.com/CadQuery/OCP/releases/tag/8.0.1.1),
   [OCP wrapper license](https://github.com/CadQuery/OCP/blob/a6d078cfda3e5e695c68d2bfbfe38e91b0ccb566/LICENSE).
4. [OCCT V8_0_1](https://github.com/Open-Cascade-SAS/OCCT/tree/b8f597c677811d1f9f4d8a97f5ae2825c0353a42)
   states **LGPL version 2.1 with the Open CASCADE exception**, alternatively
   available commercially. Copies of its unmodified upstream terms are in
   [licenses/OCCT-LGPL-2.1.txt](licenses/OCCT-LGPL-2.1.txt) and
   [licenses/OCCT-LGPL-EXCEPTION.txt](licenses/OCCT-LGPL-EXCEPTION.txt).
   [Upstream licensing statement](https://github.com/Open-Cascade-SAS/OCCT/blob/b8f597c677811d1f9f4d8a97f5ae2825c0353a42/README.md#license).

This traces the published recipe, not a reproducible rebuild or independent
attestation of every upstream binary. The native dependencies can themselves
contain other libraries; their complete binary redistribution obligations
have not been established here. The selected release scope ships no such
binaries. A standalone installer, environment archive or dependency mirror
would require a separate review of corresponding sources, patches, license
notices, library replacement/relinking requirements and bundled native libraries.
Do not reuse this package-only review as approval for that different scope.
