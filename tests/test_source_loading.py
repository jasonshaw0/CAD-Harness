"""Rebuild current trusted source despite valid-looking cached bytecode."""

import os
import importlib
import py_compile
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cadharness.project import load_project

SOURCE = """from build123d import Box
from cadharness import CADDocument, Component

def create_project():
    return CADDocument("source-fixture", "Source fixture", "1",
        {"plate": Component("plate", Box(40, 20, 4))})
"""


def fixture(root):
    (root / "cadharness.toml").write_text(
        '[project]\nid="source-fixture"\nname="Source fixture"\nentrypoint="project.py:create_project"\n',
        encoding="utf-8",
    )


class SourceLoadingTests(unittest.TestCase):
    def test_preloaded_helpers_use_current_source_and_restore_host_modules(self):
        for fail in (False, True):
            with self.subTest(fail=fail), TemporaryDirectory() as directory:
                root = Path(directory)
                fixture(root)
                package = root / "loading_package"
                package.mkdir()
                (package / "__init__.py").write_text(
                    "from .dimensions import thickness\n", encoding="utf-8"
                )
                helper = package / "dimensions.py"
                helper.write_text("thickness = 4\n", encoding="utf-8")
                sys.path.insert(0, str(root))
                original_modules = {}
                try:
                    importlib.import_module("loading_package")
                    original_modules = {
                        name: sys.modules[name]
                        for name in ("loading_package", "loading_package.dimensions")
                    }
                    timestamp = helper.stat().st_mtime_ns
                    helper.write_text("thickness = 2\n", encoding="utf-8")
                    os.utime(helper, ns=(timestamp, timestamp))
                    source = "from loading_package import thickness\n" + SOURCE.replace(
                        "Box(40, 20, 4)", "Box(40, 20, thickness)"
                    )
                    if fail:
                        source += "\nraise RuntimeError(str(thickness))\n"
                    (root / "project.py").write_text(source, encoding="utf-8")
                    before_path = list(sys.path)
                    before_meta_path = list(sys.meta_path)
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, "^2$"):
                            load_project(root)
                    else:
                        shape = load_project(root).document.components["plate"].shape
                        self.assertTrue(shape.is_valid)
                        self.assertEqual(len(shape.solids()), 1)
                        self.assertEqual(shape.bounding_box().size.Z, 2)
                        self.assertAlmostEqual(shape.volume, 1600)
                    self.assertEqual(sys.path, before_path)
                    self.assertEqual(sys.meta_path, before_meta_path)
                    for name, module in original_modules.items():
                        self.assertIs(sys.modules[name], module)
                        self.assertEqual(module.thickness, 4)
                finally:
                    sys.path.remove(str(root))
                    for name in original_modules:
                        sys.modules.pop(name, None)

    def test_entrypoint_edits_bypass_timestamp_bytecode(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            file = root / "project.py"
            file.write_text(SOURCE, encoding="utf-8")
            timestamp = file.stat().st_mtime_ns
            py_compile.compile(str(file), doraise=True)
            self.assertEqual(
                load_project(root)
                .document.components["plate"]
                .shape.bounding_box()
                .size.Z,
                4,
            )
            file.write_text(
                SOURCE.replace("Box(40, 20, 4)", "Box(40, 20, 2)"), encoding="utf-8"
            )
            os.utime(file, ns=(timestamp, timestamp))
            self.assertEqual(
                load_project(root)
                .document.components["plate"]
                .shape.bounding_box()
                .size.Z,
                2,
            )

    def test_helpers_bypass_bytecode_and_restore_import_state(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            (root / "project.py").write_text(
                "from loading_dimensions import thickness\n"
                + SOURCE.replace("Box(40, 20, 4)", "Box(40, 20, thickness)"),
                encoding="utf-8",
            )
            helper = root / "loading_dimensions.py"
            helper.write_text("thickness = 4\n", encoding="utf-8")
            timestamp = helper.stat().st_mtime_ns
            py_compile.compile(str(helper), doraise=True)
            before = list(sys.meta_path)
            load_project(root)
            helper.write_text("thickness = 2\n", encoding="utf-8")
            os.utime(helper, ns=(timestamp, timestamp))
            self.assertEqual(
                load_project(root)
                .document.components["plate"]
                .shape.bounding_box()
                .size.Z,
                2,
            )
            self.assertNotIn("loading_dimensions", sys.modules)
            self.assertEqual(sys.meta_path, before)
            (root / "project.py").write_text(
                "raise RuntimeError('fixture')", encoding="utf-8"
            )
            with self.assertRaises(RuntimeError):
                load_project(root)
            self.assertEqual(sys.meta_path, before)


if __name__ == "__main__":
    unittest.main()
