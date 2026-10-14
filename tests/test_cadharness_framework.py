import contextlib
from io import StringIO
import json
from pathlib import Path
import unittest

from build123d import Box

from cadharness import CADDocument, Component, Parameter, load_project, minimum_check
from cadharness.cli import main as cli_main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = PROJECT_ROOT / "examples" / "project-box"


class CoreModelTests(unittest.TestCase):
    def test_failed_engineering_check_is_structured(self):
        document = CADDocument(
            id="test-part",
            name="Test Part",
            revision="1",
            components={"block": Component("block", Box(10, 20, 30))},
            parameters={"wall": Parameter(1.0, unit="mm")},
            checks=(
                minimum_check(
                    "wall.minimum",
                    "wall thickness",
                    1.0,
                    1.6,
                    unit="mm",
                ),
            ),
        )
        report = document.validate().to_dict()
        self.assertFalse(report["passed"])
        self.assertEqual(report["summary"]["fail"], 1)
        failed = next(result for result in report["results"] if result["status"] == "fail")
        self.assertEqual(failed["actual"], 1.0)
        self.assertEqual(failed["expected"], {"minimum": 1.6})


class ProjectLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = load_project(EXAMPLE_ROOT)

    def test_unrelated_example_uses_general_contract(self):
        self.assertEqual(self.loaded.manifest.id, "project-box")
        self.assertEqual(set(self.loaded.document.components), {"base", "lid"})
        self.assertNotIn("rotary", json.dumps(self.loaded.document.inspect()).lower())

    def test_example_validation_passes_with_evidence(self):
        report = self.loaded.document.validate().to_dict()
        self.assertTrue(report["passed"])
        self.assertEqual(report["summary"]["pass"], 7)
        check = next(
            result for result in report["results"] if result["id"] == "fit.lid-clearance"
        )
        self.assertIn("not physically verified", check["evidence"]["classification"])

    def test_cli_emits_machine_readable_json(self):
        output = StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = cli_main(["--compact", "validate", str(EXAMPLE_ROOT)])
        self.assertEqual(exit_code, 0)
        report = json.loads(output.getvalue())
        self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
