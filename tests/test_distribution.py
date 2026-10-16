"""A successful build must not hide missing or stale installed resources."""

from contextlib import redirect_stdout
from io import BytesIO, StringIO
import hashlib
import json
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from scripts.smoke_distribution import REQUIRED_RESOURCES, SDIST_INPUTS, check_archives
from scripts.prepare_release import prepare


class DistributionTests(unittest.TestCase):
    def make_artifacts(self, root, *, omit=None, altered=None, stale=False, version="0.9.0",
                       omit_source=None, extra_source=None, omit_license=None,
                       altered_license=None, license_expression="Apache-2.0", declared_files=None,
                       project_version="0.9.0"):
        package = root / "src/cadharness"
        files = {name: b"resource" for name in REQUIRED_RESOURCES}
        files.update({"__init__.py": b"", "studio/web/assets/index-test.js": b"app",
                      "studio/web/assets/renderView-test.js": b"renderer"})
        for name, content in files.items():
            path = package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (root / "pyproject.toml").write_text(
            f'[project]\nname="CAD-Harness"\nversion="{project_version}"\n'
            'license="Apache-2.0"\nauthors=[{name="Jason Shaw"}]\n'
            'license-files=["LICENSE", "NOTICE", "licenses/*.txt"]\n'
            '[tool.setuptools.package-data]\n"cadharness.studio"=["web/*", "web/assets/*"]\n',
            encoding="utf-8")
        source_inputs = {name: b"source" for name in SDIST_INPUTS}
        source_inputs["pyproject.toml"] = (root / "pyproject.toml").read_bytes()
        license_files = {"LICENSE": b"Apache text", "NOTICE": b"Copyright Jason Shaw",
                         "licenses/OCCT.txt": b"Upstream terms", "licenses/FRONTEND.txt": b"resource"}
        source_inputs.update(license_files)
        source_inputs["studio/web/src/main.tsx"] = b"frontend"
        for name, content in source_inputs.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        declared_files = license_files if declared_files is None else declared_files
        metadata = (f"Name: CAD-Harness\nVersion: {version}\nAuthor: Jason Shaw\n"
                    f"License-Expression: {license_expression}\n" +
                    "".join(f"License-File: {name}\n" for name in declared_files)).encode()
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
            for name, content in license_files.items():
                if name != omit_license:
                    whl.writestr(f"cad_harness-0.9.0.dist-info/licenses/{name}",
                                 b"changed" if name == altered_license else content)
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

    def test_license_text_and_metadata_are_required_in_both_archives(self):
        for options, error in (({"omit_license": "NOTICE"}, "Missing distribution license"),
                               ({"altered_license": "licenses/OCCT.txt"}, "license differs"),
                               ({"omit_source": "LICENSE"}, "Missing source distribution input"),
                               ({"license_expression": "MIT"}, "license expression differs"),
                               ({"declared_files": ["LICENSE"]}, "License-File metadata differs")):
            with self.subTest(options=options), TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaisesRegex(ValueError, error):
                    check_archives(*self.make_artifacts(root, **options), root=root)

    def test_native_libraries_are_outside_the_reviewed_release_scope(self):
        for name in ("libOCCT.dll", "libkernel.so.8", "libkernel.dylib"):
            with self.subTest(name=name), TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaisesRegex(ValueError, "contains a native library"):
                    check_archives(*self.make_artifacts(root, extra_source=name), root=root)

    def release_fixture(self, root):
        wheel, sdist = self.make_artifacts(root, version="0.10.0b1", project_version="0.10.0b1")
        validated = root / "validated"
        validated.mkdir()
        wheel = wheel.rename(validated / "cad_harness-0.10.0b1-py3-none-any.whl")
        sdist = sdist.rename(validated / "cad_harness-0.10.0b1.tar.gz")
        (validated / "SHA256SUMS").write_text("".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in (wheel, sdist)), encoding="utf-8")
        (validated / "DEPENDENCIES.json").write_text(json.dumps({
            "schema": "cadharness.dependency-inventory", "packages": [
                {"name": name, "version": version} for name, version in (
                    ("CAD-Harness", "0.10.0b1"), ("build123d", "0.13.0"),
                    ("cadquery-ocp-novtk", "8.0.1.1.0"), ("mcp", "2.3.0"),
                    ("starlette", "1.8.0"), ("uvicorn", "0.54.0"))]}), encoding="utf-8")
        notes = root / "docs/releases/0.10.0b1.md"
        notes.parent.mkdir(parents=True)
        notes.write_text("# CAD-Harness 0.10.0b1\nBeta notes\n", encoding="utf-8")
        # Source archive validation includes docs. Recreate the archives with
        # these final inputs, matching the real build-then-prepare order.
        with tarfile.open(sdist, "r:gz") as source:
            members = [(entry, source.extractfile(entry).read()) for entry in source.getmembers()]
        with tarfile.open(sdist, "w:gz") as source:
            for entry, content in members:
                source.addfile(entry, BytesIO(content))
            content = notes.read_bytes()
            entry = tarfile.TarInfo("cad_harness-0.9.0/docs/releases/0.10.0b1.md")
            entry.size = len(content)
            source.addfile(entry, BytesIO(content))
        (validated / "SHA256SUMS").write_text("".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in (wheel, sdist)), encoding="utf-8")
        return validated

    def test_release_bundle_preserves_archives_and_hashes_every_attachment(self):
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            root = Path(directory)
            validated = self.release_fixture(root)
            output = root / "release"
            with patch("scripts.prepare_release.subprocess.check_output", side_effect=["a" * 40, ""]):
                prepare(validated, output, tag="v0.10.0b1", root=root)
            for line in (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
                digest, name = line.split("  ")
                self.assertEqual(digest, hashlib.sha256((output / name).read_bytes()).hexdigest())
            self.assertEqual(len(list(output.iterdir())), 6)
            self.assertEqual((output / "cad_harness-0.10.0b1.tar.gz").read_bytes(),
                             (validated / "cad_harness-0.10.0b1.tar.gz").read_bytes())
            build = json.loads((output / "BUILD.json").read_text(encoding="utf-8"))
            self.assertEqual(build["commit"], "a" * 40)
            self.assertFalse(build["tracked_source_dirty"])
            with self.assertRaisesRegex(ValueError, "Keeping existing"):
                prepare(validated, output, tag="v0.10.0b1", root=root)

    def test_release_refuses_wrong_tag_changed_archives_and_stale_inventory(self):
        for failure, message in (("tag", "Tag must match"), ("hash", "checksums"),
                                 ("inventory", "does not describe")):
            with self.subTest(failure=failure), TemporaryDirectory() as directory:
                root = Path(directory)
                validated = self.release_fixture(root)
                tag = "v0.10.0b1"
                if failure == "tag":
                    tag = "v0.9.0"
                elif failure == "hash":
                    with (validated / "cad_harness-0.10.0b1.tar.gz").open("ab") as stream:
                        stream.write(b"changed")
                else:
                    path = validated / "DEPENDENCIES.json"
                    path.write_text(path.read_text(encoding="utf-8").replace("0.10.0b1", "0.8.0"), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message), redirect_stdout(StringIO()):
                    prepare(validated, root / "release", tag=tag, root=root)
                self.assertFalse((root / "release").exists())


if __name__ == "__main__":
    unittest.main()
