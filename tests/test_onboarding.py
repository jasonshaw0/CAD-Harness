"""Exercise the copyable authoring guide and first-run terminal workflow."""

import contextlib
import json
import os
import py_compile
import re
import sys
import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from cadharness.cli import main as cli_main
from cadharness.project import load_project

ROOT = Path(__file__).resolve().parents[1]
MOUNT = ROOT / "examples" / "nema17-mount"
GUIDE = ROOT / "docs" / "GETTING_STARTED.md"


def cli(args):
    output, errors = StringIO(), StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        code = cli_main(args)
    return code, output.getvalue(), errors.getvalue()


def create_guide_project(root):
    guide = GUIDE.read_text(encoding="utf-8")
    manifest = re.search(r"```toml\n(.*?)\n```", guide, re.S).group(1)
    source = re.search(r"```python\n(.*?)\n```", guide, re.S).group(1)
    (root / "cadharness.toml").write_text(manifest, encoding="utf-8")
    (root / "project.py").write_text(source, encoding="utf-8")
    return source


class OnboardingTests(unittest.TestCase):
    def test_guide_passes_then_reads_same_size_edit_despite_cached_bytecode(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = create_guide_project(root)
            file = root / "project.py"
            timestamp = file.stat().st_mtime_ns
            py_compile.compile(str(file), doraise=True)
            self.assertEqual(cli(["verify", str(root), "--summary"])[0], 0)
            file.write_text(
                source.replace("Box(40, 20, 4)", "Box(40, 20, 2)"), encoding="utf-8"
            )
            os.utime(file, ns=(timestamp, timestamp))
            code, output, errors = cli(["verify", str(root), "--summary"])
            self.assertEqual(code, 1)
            self.assertIn("Verification failed: my-plate", output)
            self.assertIn("Actual: 2.0 mm", output)
            self.assertIn("Expected: at least 3.0 mm", output)
            self.assertFalse(errors)

    def test_project_helpers_also_read_source_and_restore_import_state(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = create_guide_project(root)
            (root / "project.py").write_text(
                "from onboarding_dimensions import thickness\n"
                + source.replace("Box(40, 20, 4)", "Box(40, 20, thickness)"),
                encoding="utf-8",
            )
            helper = root / "onboarding_dimensions.py"
            helper.write_text("thickness = 4\n", encoding="utf-8")
            timestamp = helper.stat().st_mtime_ns
            py_compile.compile(str(helper), doraise=True)
            before = list(sys.meta_path)
            self.assertEqual(cli(["verify", str(root)])[0], 0)
            helper.write_text("thickness = 2\n", encoding="utf-8")
            os.utime(helper, ns=(timestamp, timestamp))
            self.assertEqual(cli(["verify", str(root)])[0], 1)
            self.assertNotIn("onboarding_dimensions", sys.modules)
            self.assertEqual(sys.meta_path, before)
            (root / "project.py").write_text(
                "raise RuntimeError('fixture')", encoding="utf-8"
            )
            with self.assertRaises(RuntimeError):
                load_project(root)
            self.assertEqual(sys.meta_path, before)

    def test_summary_and_json_preserve_gate_outcomes_and_exceptions(self):
        for flags, expected_code, verdict in (
            ([], 0, "passed"),
            (["--variant", "missing-hole"], 1, "failed"),
            (["--variant", "missing-hole", "--allow-failed-checks"], 0, "passed"),
        ):
            with self.subTest(flags=flags):
                code, output, _ = cli(["verify", str(MOUNT), *flags, "--summary"])
                self.assertEqual(code, expected_code)
                self.assertIn(f"Verification {verdict}:", output)
                json_code, serialized, _ = cli(
                    ["verify", str(MOUNT), *flags, "--compact"]
                )
                self.assertEqual(json_code, code)
                self.assertEqual(
                    json.loads(serialized)["verification"]["outcome"], verdict
                )
                if "--allow-failed-checks" in flags:
                    self.assertIn(
                        "Policy overrides: fail_on_failed_checks=false", output
                    )
                if "missing-hole" in flags:
                    self.assertIn("Actual: 3", output)
                    self.assertIn("Expected: 4", output)

    def test_inspector_summary_points_to_real_report_and_refuses_overwrite(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            create_guide_project(root)
            code, output, errors = cli(["inspector", str(root), "--summary"])
            target = root / ".cadharness" / "inspector" / "index.html"
            self.assertEqual(code, 0)
            self.assertIn(str(target), output)
            self.assertIn("Verification passed: my-plate", output)
            self.assertTrue(target.is_file())
            self.assertFalse(errors)
            before = target.read_bytes()
            code, _, errors = cli(["inspector", str(root), "--summary"])
            self.assertEqual(code, 2)
            self.assertIn("--overwrite", json.loads(errors)["hint"])
            self.assertEqual(target.read_bytes(), before)

    def test_summary_and_compact_are_mutually_exclusive(self):
        with (
            contextlib.redirect_stderr(StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            cli_main(["verify", str(MOUNT), "--summary", "--compact"])
        self.assertEqual(raised.exception.code, 2)

    def test_summary_preserves_check_error_exit_code_and_json_usage_errors(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = create_guide_project(root)
            (root / "project.py").write_text(
                source.replace(
                    'lambda document: document.components["plate"].shape.bounding_box().size.Z',
                    "lambda document: 1 / 0",
                ),
                encoding="utf-8",
            )
            code, output, _ = cli(["verify", str(root), "--summary"])
            self.assertEqual(code, 2)
            self.assertIn("Verification error: my-plate", output)
            self.assertIn("ERROR plate.thickness", output)
        code, _, errors = cli(["verify", str(root), "--summary"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(errors)["error"], "FileNotFoundError")


if __name__ == "__main__":
    unittest.main()
