# GitHub beta release procedure

Owner decision, 2026-10-16: Apache-2.0, Copyright 2026 Jason Shaw;
GitHub release downloads. The first candidate is `0.10.0b1`, tag `v0.10.0b1`.
The beta suffix reflects experimental interfaces and the acceptance limits in
the release notes. PyPI, standalone installers and promotional posts are outside
this release scope. This procedure prepares evidence; a commit/push does not
automatically create a tag or publish a release.

## Candidate gate

1. Keep version, the changelog and `docs/releases/<version>.md` aligned.
   Changes to dependency ranges/locks require refreshed provenance and notices.
2. Build the frontend and run the Python/frontend suites. The existing CI
   builds an sdist, builds its wheel from that sdist, compares source/resources
   and complete license/NOTICE bytes, checks SPDX/attribution metadata, and
   rejects native binaries in these package-only artifacts.
3. CI installs core and full extras in a new environment outside the checkout,
   verifies real geometry/MCP/export and saved-workspace package replacement,
   and retains wheel/sdist hashes plus `DEPENDENCIES.json`. Each platform's
   inventory records its resolved dependencies, license metadata/file hashes
   and native files; it is not a compliance certificate or dependency lock.
4. After real Linux Playwriter rendering/demo checks, CI prepares
   `github-beta-candidate`. `prepare_release.py` rechecks archive bytes, version,
   dependency inventory and hashes, then adds notes, commit/run provenance and
   checksums for **all** attached files. All CI jobs on that exact commit must
   be green, not only the Linux job. Do not rebuild assets after acceptance.

Local preparation, after a fresh distribution gate:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_distribution.py --fresh-install --output dist/validated-beta
.\.venv\Scripts\python.exe scripts/prepare_release.py --validated dist/validated-beta --output dist/release-beta --tag v0.10.0b1
```

Use `./.venv/bin/python` on Linux/macOS. Existing output directories are
preserved. Local preparation records tracked changes in `BUILD.json`; do not
publish a candidate with `tracked_source_dirty: true`. Final release artifacts
must come from the passing CI run on the committed source. The candidate helper
does not itself establish that CI or browser acceptance passed.

## Publication

Review the exact notes, commit, successful CI matrix, checksums, inventory and
artifact contents. The owner chose GitHub downloads; the current engineering
task ends with committed preparation. An instruction to publish this concrete
candidate authorizes the following separate operation:

- Download `github-beta-candidate` from that commit's successful CI run.
  Verify every file against its `SHA256SUMS` and the recorded commit/run URL.
- Create the matching tag at that exact commit, never at a moving `main`.
- Create a GitHub draft release with the prepared notes and attach the wheel,
  sdist, `DEPENDENCIES.json`, `BUILD.json`, `RELEASE_NOTES.md` and `SHA256SUMS`.
  Mark it **pre-release**, with **latest** disabled; review before publishing.
- Publish, download the public assets, recheck hashes and install the public
  wheel in a new environment. Run `pip check` and `cadharness demo --prepare-only`.
  Record the release URL and results in the roadmap.

No credential, permission, trusted-publisher or external-account change is
needed for preparation. Upstream [GitHub release guidance](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

## Beta feedback

Collect the release version, OS/architecture/Python, installation route,
redacted diagnostics, steps, expected/observed behavior, whether the demo passed,
and whether data survived an update. Use the repository's beta feedback form.
Avoid private project source, local usernames, tokens or personal host settings.
Classify failures by install, host connection, geometry/checks, Studio or exports;
fix reproducible failures before expanding distribution scope.
