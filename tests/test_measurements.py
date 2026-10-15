import contextlib
import json
import unittest
from io import StringIO
from math import cos, radians, sin
from pathlib import Path
from unittest.mock import patch

from build123d import Align, Box, Cylinder, Part, Pos, Rot

from cadharness import (
    CADDocument,
    Component,
    ComputationalTolerance,
    CylinderSelector,
    MeasurementResult,
    MeasurementStatus,
    build_snapshot,
    geometry_measurement_check,
    geometry_fingerprint,
    interference_check,
    measure_cylindrical_feature,
    measure_directional_thickness,
    measure_hole_pattern,
    measure_shape_clearance,
    require_schema,
    verify_document,
)
from cadharness.cli import main as cli_main
from cadharness.operations import measure_project, verify_project

ROOT = Path(__file__).resolve().parents[1]
MOUNT = ROOT / "examples" / "nema17-mount"
Z_MIN = (Align.CENTER, Align.CENTER, Align.MIN)


def plate_document(
    count: int = 4,
    *,
    diameter: float = 4.0,
    moved_index: int | None = None,
    rotation=None,
) -> CADDocument:
    shape = Box(50, 50, 4, align=Z_MIN)
    locations = [(-15, -15), (-15, 15), (15, 15), (15, -15)]
    for index, (x, y) in enumerate(locations[:count]):
        if index == moved_index:
            x += 3
        shape -= Pos(x, y, -1) * Cylinder(diameter / 2, 6, align=Z_MIN)
    result = Part(shape).clean()
    if rotation is not None:
        result = rotation * result
    return CADDocument(
        id="measurement-fixture",
        name="Measurement Fixture",
        revision="1",
        components={"plate": Component("plate", result)},
    )


def selector(axis=(0, 0, 1)) -> CylinderSelector:
    return CylinderSelector(
        "plate", radius_min_mm=1, radius_max_mm=3, axis_direction=axis
    )


class GeometryMeasurementTests(unittest.TestCase):
    def test_contact_measurements_preserve_source_brep_fingerprints(self):
        outer = Box(84, 58, 34, align=Z_MIN)
        cavity = Pos(0, 0, 3) * Box(78, 52, 32, align=Z_MIN)
        doc = CADDocument("contact", "Contact", "1", components={
            "base": Component("base", Part(outer - cavity).clean()),
            "lid": Component("lid", Part(Pos(0, 0, 34) * Box(84, 58, 3, align=Z_MIN)).clean())})
        before = {key: geometry_fingerprint(item.shape) for key, item in doc.components.items()}
        result = measure_shape_clearance(doc, "clearance", "base", "lid")
        self.assertEqual(result.value["state"], "contact")
        check = interference_check("no-overlap", "base", "lid")
        self.assertEqual(check.evaluator(doc).status.value, "pass")
        self.assertEqual(before, {key: geometry_fingerprint(item.shape) for key, item in doc.components.items()})

    def test_tolerances_and_selector_reject_nonfinite_or_invalid_inputs(self):
        for value in (float("nan"), float("inf"), -1.0, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ComputationalTolerance(linear_mm=value)
            with self.subTest(selector=value), self.assertRaises(ValueError):
                CylinderSelector("plate", location_tolerance_mm=value)
        for axis in ((0, 0, 0), (1, 2), (float("nan"), 0, 1)):
            with self.subTest(axis=axis), self.assertRaises(ValueError):
                CylinderSelector("plate", axis_direction=axis)

    def test_empty_measurement_values_cannot_pass_verification(self):
        check = geometry_measurement_check(
            "holes.diameter",
            "diameter required",
            lambda d: MeasurementResult(
                "holes",
                "fixture",
                MeasurementStatus.SUCCESS,
                value={"diameters": []},
                method="fixture",
            ),
            value_path="diameters",
            expected=4.0,
        )
        current = plate_document()
        current.checks = (check,)
        report = verify_document(current)
        self.assertFalse(report["verification"]["passed"])
        self.assertEqual(report["validation"]["results"][-1]["status"], "skip")
        require_schema(report)

    def test_invalid_measurement_values_and_missing_paths_preserve_errors(self):
        for value, value_path in (
            ({"diameter": float("nan")}, "diameter"),
            ({"diameter": 4.0}, "missing"),
            ({"diameter": [3.0, {}]}, "diameter"),
            ({"diameter": {}}, "diameter"),
            ({"diameter": "4.0"}, "diameter"),
        ):
            with self.subTest(value=value):
                check = geometry_measurement_check(
                    "diameter",
                    "diameter",
                    lambda d, value=value: MeasurementResult(
                        "diameter",
                        "fixture",
                        MeasurementStatus.SUCCESS,
                        value=value,
                        method="fixture",
                    ),
                    value_path=value_path,
                    expected=4.0,
                )
                current = plate_document()
                current.checks = (check,)
                report = verify_document(current)
                self.assertEqual(report["verification"]["outcome"], "error")
                require_schema(report)
                json.dumps(report, allow_nan=False)

    def test_measurement_units_must_match_requirement(self):
        check = geometry_measurement_check(
            "diameter",
            "diameter",
            lambda d: MeasurementResult(
                "diameter",
                "fixture",
                MeasurementStatus.SUCCESS,
                value=4.0,
                unit="inch",
                method="fixture",
            ),
            value_path="",
            expected=4.0,
            unit="mm",
        )
        self.assertEqual(check.evaluator(plate_document()).status.value, "error")

    def test_invalid_acceptance_criteria_are_rejected(self):
        for kwargs in (
            {"minimum": 5, "maximum": 4},
            {"expected": float("nan")},
            {"expected": 4, "absolute_tolerance": -1},
        ):
            with self.subTest(criteria=kwargs), self.assertRaises(ValueError):
                geometry_measurement_check(
                    "fixture", "fixture", lambda d: None, value_path="", **kwargs
                )

    def test_clearance_state_expectation_remains_exact(self):
        for state, expected_status in (("separated", "pass"), ("contact", "fail")):
            with self.subTest(state=state):
                check = geometry_measurement_check(
                    "clearance.state",
                    "state",
                    lambda d, state=state: MeasurementResult(
                        "clearance",
                        "fixture",
                        MeasurementStatus.SUCCESS,
                        value={"state": state},
                        method="fixture",
                    ),
                    value_path="state",
                    expected="separated",
                )
                self.assertEqual(
                    check.evaluator(plate_document()).status.value, expected_status
                )

    def test_measurement_spec_changes_are_normative(self):
        def current(limit):
            current = plate_document()
            selected = CylinderSelector(
                "plate", radius_min_mm=1, radius_max_mm=limit, axis_direction=(0, 0, 1)
            )
            current.checks = (
                geometry_measurement_check(
                    "holes.count",
                    "count",
                    lambda d: measure_hole_pattern(d, "holes", selected),
                    value_path="count",
                    expected=4,
                    measurement_spec={"selector": selected.to_dict()},
                ),
            )
            return current

        report = verify_document(current(4), baseline=build_snapshot(current(3)))
        self.assertFalse(report["verification"]["passed"])
        self.assertIn("holes.count", report["comparison"]["requirements"]["modified"])

    def test_counterbore_is_ambiguous_until_selector_is_narrowed(self):
        shape = (
            Box(20, 20, 6, align=Z_MIN)
            - Pos(0, 0, -1) * Cylinder(2, 8, align=Z_MIN)
            - Pos(0, 0, 3) * Cylinder(4, 4, align=Z_MIN)
        )
        current = CADDocument(
            "counterbore", "Counterbore", "1", {"plate": Component("plate", shape)}
        )
        broad = measure_hole_pattern(current, "holes", CylinderSelector("plate"))
        self.assertEqual(broad.status, MeasurementStatus.AMBIGUOUS)
        self.assertIsNone(broad.value)
        narrow = measure_hole_pattern(current, "holes", selector())
        self.assertEqual(narrow.status, MeasurementStatus.SUCCESS)
        self.assertEqual(narrow.value["count"], 1)
        self.assertIsNone(narrow.value["bolt_circle_diameter_mm"])

    def test_partial_cylinder_cutout_is_not_claimed_as_a_hole(self):
        shape = Box(20, 20, 4, align=Z_MIN) - Pos(10, 0, -1) * Cylinder(
            2, 6, align=Z_MIN
        )
        current = CADDocument(
            "cutout", "Cutout", "1", {"plate": Component("plate", shape)}
        )
        report = measure_hole_pattern(current, "holes", CylinderSelector("plate"))
        self.assertEqual(report.status, MeasurementStatus.UNSUPPORTED)

    def test_mixed_hole_axes_are_not_silently_projected_into_one_pattern(self):
        shape = (
            Box(20, 20, 20)
            - Pos(5, 5, 0) * Cylinder(2, 30)
            - Pos(0, -5, -5) * Rot(0, 90, 0) * Cylinder(2, 30)
        )
        current = CADDocument(
            "mixed-axes", "Mixed axes", "1", {"plate": Component("plate", shape)}
        )
        report = measure_hole_pattern(current, "holes", CylinderSelector("plate"))
        self.assertEqual(report.status, MeasurementStatus.AMBIGUOUS)

    def test_partial_thickness_samples_and_boundary_points_are_indeterminate(self):
        current = CADDocument(
            "wall-fixture",
            "Wall",
            "1",
            {"plate": Component("plate", Box(20, 20, 4, align=Z_MIN))},
        )
        for points in (((0, 0, 2), (100, 100, 2)), ((0, 0, 0),)):
            with self.subTest(points=points):
                report = measure_directional_thickness(
                    current, "wall", "plate", points, (0, 0, 1)
                )
                self.assertEqual(report.status, MeasurementStatus.AMBIGUOUS)
                self.assertIsNone(report.value)
                require_schema(report.to_dict())
        check = geometry_measurement_check(
            "wall",
            "wall",
            lambda d: measure_directional_thickness(
                d, "wall", "plate", ((0, 0, 2), (100, 100, 2)), (0, 0, 1)
            ),
            value_path="minimum_mm",
            minimum=1.0,
        )
        current.checks = (check,)
        self.assertFalse(verify_document(current)["verification"]["passed"])

    def test_thickness_input_and_kernel_failures_are_distinct(self):
        current = plate_document()
        for points, direction in (
            ((), (0, 0, 1)),
            (((0, 0),), (0, 0, 1)),
            (((0, 0, 2),), (0, 0, 0)),
        ):
            with self.subTest(points=points, direction=direction):
                result = measure_directional_thickness(
                    current, "wall", "plate", points, direction
                )
                self.assertEqual(result.status, MeasurementStatus.INVALID_INPUT)
        tolerance = ComputationalTolerance(linear_mm=1e-5)
        with patch(
            "cadharness.measurements.BRepAlgoAPI_Common",
            side_effect=RuntimeError("kernel fixture"),
        ):
            result = measure_directional_thickness(
                current, "wall", "plate", ((0, 0, 2),), (0, 0, 1), tolerance=tolerance
            )
        self.assertEqual(result.status, MeasurementStatus.KERNEL_ERROR)
        self.assertEqual(result.computational_tolerance, tolerance)

    def test_invalid_components_do_not_report_measurement_success(self):
        current = plate_document()
        result = measure_cylindrical_feature(
            current, "missing", CylinderSelector("missing")
        )
        self.assertEqual(result.status, MeasurementStatus.INVALID_INPUT)
        same = measure_shape_clearance(current, "same", "plate", "plate")
        self.assertEqual(same.status, MeasurementStatus.INVALID_INPUT)

    def test_feature_ids_include_axial_location_and_are_repeatable(self):
        first = measure_cylindrical_feature(plate_document(1), "hole", selector())
        repeated = measure_cylindrical_feature(plate_document(1), "hole", selector())
        self.assertEqual(first.value["id"], repeated.value["id"])
        moved = measure_cylindrical_feature(
            plate_document(1, rotation=Pos(0, 0, 10)), "hole", selector()
        )
        self.assertNotEqual(first.value["id"], moved.value["id"])
        self.assertAlmostEqual(moved.value["extent_mm"], 4.0)

    def test_example_variants_fail_independently_of_declared_intent(self):
        self.assertTrue(verify_project(MOUNT)["verification"]["passed"])
        for variant, check_id in (
            ("missing-hole", "mount.hole-count"),
            ("shifted-hole", "mount.pattern-radial-residual"),
            ("wrong-diameter", "mount.hole-diameter"),
            ("tight-clearance", "assembly.cable-clearance"),
        ):
            with self.subTest(variant=variant):
                report = verify_project(MOUNT, variant=variant)
                self.assertFalse(report["verification"]["passed"])
                result = next(
                    item
                    for item in report["validation"]["results"]
                    if item["id"] == check_id
                )
                self.assertEqual(result["status"], "fail")
                self.assertEqual(result["evidence_kind"], "geometry-derived")
                require_schema(report)

    def test_cli_and_mcp_share_all_measurement_operations(self):
        from cadharness.mcp_server import measure_cad_project

        for kind, components, flags, options in (
            (
                "hole-pattern",
                ["mounting-plate"],
                [
                    "--radius-min",
                    "1",
                    "--radius-max",
                    "3",
                    "--axis-direction",
                    "0",
                    "0",
                    "1",
                ],
                {"radius_min_mm": 1, "radius_max_mm": 3, "axis_direction": [0, 0, 1]},
            ),
            (
                "cylindrical-feature",
                ["mounting-plate"],
                ["--axis-location", "15.5", "15.5", "0"],
                {"axis_location_mm": [15.5, 15.5, 0]},
            ),
            ("shape-clearance", ["motor-envelope", "cable-keepout"], [], {}),
            (
                "directional-thickness",
                ["mounting-plate"],
                ["--point", "0", "0", "2", "--direction", "0", "0", "1"],
                {"sample_points_mm": [[0, 0, 2]], "direction": [0, 0, 1]},
            ),
        ):
            with self.subTest(kind=kind):
                argv = ["measure", str(MOUNT), "--type", kind]
                for component in components:
                    argv.extend(["--component", component])
                output = StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(cli_main([*argv, *flags]), 0)
                cli = json.loads(output.getvalue())
                mcp = measure_cad_project(str(MOUNT), kind, components, **options)
                self.assertEqual(cli, mcp)
                require_schema(cli)
                if kind == "directional-thickness":
                    self.assertAlmostEqual(cli["value"]["minimum_mm"], 4.0)

    def test_cli_measurement_status_exit_codes_and_usage(self):
        for flags, code, status in (
            ([], 1, "ambiguous"),
            (["--component", "extra"], 2, None),
        ):
            output, errors = StringIO(), StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                result = cli_main(
                    [
                        "measure",
                        str(MOUNT),
                        "--type",
                        "cylindrical-feature",
                        "--component",
                        "mounting-plate",
                        *flags,
                    ]
                )
            self.assertEqual(result, code)
            if status:
                self.assertEqual(json.loads(output.getvalue())["status"], status)
        output = StringIO()
        with contextlib.redirect_stdout(output):
            code = cli_main(
                [
                    "measure",
                    str(MOUNT),
                    "--type",
                    "hole-pattern",
                    "--component",
                    "missing",
                ]
            )
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "invalid-input")

    def test_measurement_mcp_keeps_trust_roots_and_rejects_unused_options(self):
        from cadharness.mcp_server import measure_cad_project

        with patch("cadharness.mcp_server.ROOTS", (MOUNT,)):
            with self.assertRaisesRegex(ValueError, "outside"):
                measure_cad_project(str(ROOT), "hole-pattern", ["plate"])
        with self.assertRaisesRegex(ValueError, "selector options"):
            measure_project(
                MOUNT,
                measurement_type="shape-clearance",
                component_ids=("motor-envelope", "cable-keepout"),
                radius_min_mm=1,
            )

    def test_declared_eight_holes_does_not_hide_six_modeled_holes(self):
        shape = Box(60, 60, 4, align=Z_MIN)
        for index in range(6):
            angle = radians(index * 60)
            shape -= Pos(20 * cos(angle), 20 * sin(angle), -1) * Cylinder(
                2, 6, align=Z_MIN
            )
        six = CADDocument(
            id="measurement-fixture",
            name="Six modeled holes",
            revision="1",
            components={"plate": Component("plate", Part(shape).clean())},
        )
        report = measure_hole_pattern(six, "holes", selector())
        self.assertEqual(report.value["count"], 6)
        # The declared intent is deliberately independent of the actual fixture.
        check = geometry_measurement_check(
            "holes.count",
            "eight holes required",
            lambda document: measure_hole_pattern(document, "holes", selector()),
            value_path="count",
            expected=8,
        )
        self.assertEqual(check.evaluator(six).status.value, "fail")

    def test_wrong_position_preserves_count_but_fails_pattern(self):
        report = measure_hole_pattern(
            plate_document(moved_index=3), "holes", selector()
        )
        self.assertEqual(report.value["count"], 4)
        self.assertGreater(report.value["maximum_radial_residual_mm"], 0.5)

    def test_wrong_hole_diameter_is_measured(self):
        report = measure_hole_pattern(plate_document(diameter=5.0), "holes", selector())
        self.assertEqual(report.value["diameters_mm"], [5.0] * 4)

    def test_clearance_distinguishes_separation_contact_and_overlap(self):
        first = Box(10, 10, 10)
        for name, offset, state in (
            ("separated", 12, "separated"),
            ("contact", 10, "contact"),
            ("interference", 9, "interference"),
        ):
            with self.subTest(state=name):
                document = CADDocument(
                    id="clearance-fixture",
                    name="Clearance",
                    revision="1",
                    components={
                        "first": Component("first", first),
                        "second": Component(
                            "second", Pos(offset, 0, 0) * Box(10, 10, 10)
                        ),
                    },
                )
                result = measure_shape_clearance(
                    document, "clearance", "first", "second"
                )
                self.assertEqual(result.value["state"], state)

    def test_directional_wall_sample_detects_actual_thickness(self):
        shell = Box(20, 20, 10, align=Z_MIN) - Pos(0, 0, 2) * Box(
            16, 16, 10, align=Z_MIN
        )
        document = CADDocument(
            id="wall-fixture",
            name="Wall",
            revision="1",
            components={"shell": Component("shell", shell)},
        )
        result = measure_directional_thickness(
            document, "wall", "shell", ((-9, 0, 5),), (1, 0, 0)
        )
        self.assertEqual(result.status, MeasurementStatus.SUCCESS)
        self.assertAlmostEqual(result.value["minimum_mm"], 2.0)

    def test_underspecified_selector_reports_ambiguity(self):
        result = measure_cylindrical_feature(plate_document(), "one-hole", selector())
        self.assertEqual(result.status, MeasurementStatus.AMBIGUOUS)
        self.assertEqual(len(result.features), 4)

    def test_transformed_holes_keep_world_axis_and_diameter(self):
        document = plate_document(rotation=Rot(0, 90, 0))
        result = measure_hole_pattern(document, "rotated", selector((1, 0, 0)))
        self.assertEqual(result.status, MeasurementStatus.SUCCESS)
        self.assertEqual(result.value["count"], 4)
        self.assertEqual(result.value["diameters_mm"], [4.0] * 4)

    def test_no_matching_geometry_is_explicit(self):
        document = CADDocument(
            id="unsupported-fixture",
            name="Unsupported",
            revision="1",
            components={"plate": Component("plate", Box(10, 10, 2))},
        )
        result = measure_cylindrical_feature(document, "none", selector())
        self.assertEqual(result.status, MeasurementStatus.NO_MATCH)
        require_schema(result.to_dict(), "cadharness.measurement")

    def test_cli_operation_and_verification_detect_intent_geometry_mismatch(self):
        measurement = measure_project(
            MOUNT,
            measurement_type="hole-pattern",
            component_ids=("mounting-plate",),
            variant="missing-hole",
            radius_min_mm=1,
            radius_max_mm=3,
            axis_direction=(0, 0, 1),
        )
        verification = verify_project(MOUNT, variant="missing-hole")
        self.assertEqual(measurement["value"]["count"], 3)
        self.assertFalse(verification["verification"]["passed"])


if __name__ == "__main__":
    unittest.main()
