"""A successful build must not hide missing or stale installed resources."""

from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
import unittest
import zipfile

from scripts.smoke_distribution import REQUIRED_RESOURCES, SDIST_INPUTS, check_archives


class DistributionTests(unittest.TestCase):
    def make_artifacts(self, root, *, omit=None, altered=None, stale=False, version="0.9.0",
                       omit_source=None, extra_source=None):
        package = root / "src/cadharness"
        files = {name: b"resource" for name in REQUIRED_RESOURCES}
        files.update({"__init__.py": b"", "studio/web/assets/index-test.js": b"app",
                      "studio/web/assets/renderView-test.js": b"renderer"})
        for name, content in files.items():
            path = package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (root / "pyproject.toml").write_text(
            '[project]\nname="CAD-Harness"\nversion="0.9.0"\n'
            '[tool.setuptools.package-data]\n"cadharness.studio"=["web/*", "web/assets/*"]\n',
            encoding="utf-8")
        source_inputs = {name: b"source" for name in SDIST_INPUTS}
        source_inputs["studio/web/src/main.tsx"] = b"frontend"
        for name, content in source_inputs.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        metadata = f"Name: CAD-Harness\nVersion: {version}\n".encode()
        wheel, sdist = root / "package.whl", root / "package.tar.gz"
        with zipfile.ZipFile(wheel, "w") as whl, tarfile.open(sdist, "w:gz") as source:
            entries = {f"src/cadharness/{name}": content for name, content in files.items()}
            entries["PKG-INFO"] = metadata
            entries.update(source_inputs)
            if omit_source:
                entries.pop(omit_source)
            if extra_source:
                entries[extra_source] = b"must not ship"
            for name, content in entries.items():
                entry = tarfile.TarInfo(f"cad_harness-0.9.0/{name}")
                entry.size = len(content)
                source.addfile(entry, BytesIO(content))
            for name, content in files.items():
                if name != omit:
                    whl.writestr(f"cadharness/{name}", b"changed" if name == altered else content)
            if stale:
                whl.writestr("cadharness/studio/web/assets/old.js", b"stale")
            whl.writestr("cad_harness-0.9.0.dist-info/METADATA", metadata)
        return wheel, sdist

    def test_complete_archives_match_checkout(self):
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            root = Path(directory)
            check_archives(*self.make_artifacts(root), root=root)

    def test_missing_guidance_template_and_lazy_render_chunk_are_rejected(self):
        for name in ("workflow/AUTHORING.md", "workflow/templates/enclosure/project.py",
                     "studio/web/assets/renderView-test.js", "studio/web/THIRD_PARTY_LICENSES.md"):
            with self.subTest(name=name), TemporaryDirectory() as directory:
                root = Path(directory)
                artifacts = self.make_artifacts(root, omit=name)
                with self.assertRaisesRegex(ValueError, "Missing distribution resource"):
                    check_archives(*artifacts, root=root)

    def test_changed_resources_stale_assets_and_wrong_version_are_rejected(self):
        for options, error in (({"altered": "workflow/CONTRACTS.md"}, "differs from checkout"),
                               ({"stale": True}, "stale Studio assets"),
                               ({"version": "0.8.0"}, "name/version differs")):
            with self.subTest(options=options), TemporaryDirectory() as directory:
                root = Path(directory)
                artifacts = self.make_artifacts(root, **options)
                with self.assertRaisesRegex(ValueError, error):
                    check_archives(*artifacts, root=root)

    def test_incomplete_sdist_is_rejected_even_when_wheel_is_complete(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            wheel, sdist = self.make_artifacts(root)
            with tarfile.open(sdist, "w:gz") as source:
                entry = tarfile.TarInfo("cad_harness-0.9.0/PKG-INFO")
                source.addfile(entry, BytesIO())
            with self.assertRaisesRegex(ValueError, "Missing (?:distribution resource|source distribution input)"):
                check_archives(wheel, sdist, root=root)

    def test_source_archive_requires_editable_frontend_and_lockfile(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            wheel, sdist = self.make_artifacts(root)
            # The archive must match the current lockfile rather than silently
            # shipping bytes from an earlier build.
            (root / "studio/web/package-lock.json").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "input differs from checkout.*package-lock"):
                check_archives(wheel, sdist, root=root)

    def test_source_archive_rejects_missing_frontend_and_dependency_environments(self):
        for options, message in (({"omit_source": "studio/web/src/main.tsx"}, "Missing source distribution input"),
                                  ({"extra_source": "studio/web/node_modules/react/index.js"}, "dependency environment"),
                                  ({"extra_source": ".venv/pyvenv.cfg"}, "dependency environment")):
            with self.subTest(options=options), TemporaryDirectory() as directory:
                root = Path(directory)
                wheel, sdist = self.make_artifacts(root, **options)
                with self.assertRaisesRegex(ValueError, message):
                    check_archives(wheel, sdist, root=root)


if __name__ == "__main__":
    unittest.main()
