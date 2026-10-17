"""contact_check helper: validation, script safety on de-DE, report parsing (no Max)."""
import unittest

from maxmcp.helpers.contact_check import build_script, classify, parse_report, validate_args

# Captured live from 3ds Max 2025 (de-DE Windows, centimeters): two 10 cm boxes,
# the second offset by [7.75, 1.5, 1.25], tolerance 0.01, near_gap 1.0.
LIVE_REPORT = (
    "U|0.01|1|centimeters|2|1|4\n"
    "N|32007|Y2NB|12|1\n"
    "N|32030|Y2NC|12|1\n"
    "P|32007|32030|1.25|1e+30|1|1|1|1|5,5,10||2.75,5,2.25\n"
    "END\n"
)


class ClassifyTests(unittest.TestCase):
    def test_order_of_severity(self) -> None:
        self.assertEqual(classify(1.0, 3, 0.0, 0.01, 1.0), "penetrating")
        self.assertEqual(classify(0.0, 1, 0.5, 0.01, 1.0), "intersecting")
        self.assertEqual(classify(0.0, 0, 0.005, 0.01, 1.0), "touching")
        self.assertEqual(classify(0.0, 0, 0.5, 0.01, 1.0), "near_gap")
        self.assertEqual(classify(0.0, 0, 5.0, 0.01, 1.0), "separate")
        self.assertEqual(classify(0.0, 0, None, 0.01, 1.0), "separate")


class ValidateArgsTests(unittest.TestCase):
    def test_rejects_overlap_and_bad_numbers(self) -> None:
        with self.assertRaises(ValueError):
            validate_args(["a"], ["a"], 0, 0, 10, 10)
        with self.assertRaises(ValueError):
            validate_args(None, ["a"], 0, 0, 10, 10)
        with self.assertRaises(ValueError):
            validate_args(["a", "b"], None, -1, 0, 10, 10)
        with self.assertRaises(ValueError):
            validate_args(["a", "b"], None, 2.0, 1.0, 10, 10)
        with self.assertRaises(ValueError):
            validate_args(["a", "b"], None, True, 0, 10, 10)

    def test_dedupes_names(self) -> None:
        names, against, *_ = validate_args(["a", "b", "a"], None, 0, 0, 10, 10)
        self.assertEqual(names, ["a", "b"])
        self.assertEqual(against, [])


class BuildScriptTests(unittest.TestCase):
    def test_whole_number_thresholds_are_coerced_to_float(self) -> None:
        # format(1.0, ".9g") is "1": a MAXScript Integer, which formattedPrint
        # with a float format prints as 4.94e-324. The script must coerce.
        script = build_script(["a", "b"], [], 0.0, 1.0, 200, 1000)
        self.assertIn("local tol = (0) as float", script)
        self.assertIn("local near = (1) as float", script)

    def test_defaults_avoid_locale_dependent_decimal_unit_strings(self) -> None:
        # units.decodeValue "0.1mm" is 0.0 on a decimal-comma Windows.
        script = build_script(["a", "b"], [], 0.0, 0.0, 200, 1000)
        self.assertNotIn('decodeValue "0.1mm"', script)
        self.assertIn('(units.decodeValue "1mm") / 10.0', script)
        self.assertIn('units.decodeValue "10mm"', script)

    def test_names_are_escaped(self) -> None:
        script = build_script(['we"ird\\name', "b"], [], 0.0, 0.0, 200, 1000)
        self.assertIn('"we\\"ird\\\\name"', script)


class ParseReportTests(unittest.TestCase):
    def test_live_report(self) -> None:
        report = parse_report(LIVE_REPORT)
        self.assertEqual(report["units"], "centimeters")
        self.assertEqual(report["tolerance"], 0.01)
        self.assertEqual(report["near_gap"], 1.0)
        self.assertEqual(report["summary"]["penetrating"], 1)
        pair = report["pairs"][0]
        self.assertEqual((pair["a"], pair["b"]), ("ccA", "ccB"))
        self.assertEqual(pair["status"], "penetrating")
        self.assertAlmostEqual(pair["depth"], 1.25)
        self.assertIsNone(pair["gap"])
        self.assertEqual(pair["depth_point"], [5.0, 5.0, 10.0])
        self.assertIsNone(pair["gap_point"])

    def test_garbage_threshold_is_rejected(self) -> None:
        # What the unfixed script produced for near_gap=1.0 on Max 2025.
        broken = LIVE_REPORT.replace("U|0.01|1|", "U|0.01|4.940656e-324|")
        with self.assertRaisesRegex(RuntimeError, "invalid thresholds"):
            parse_report(broken)

    def test_error_and_truncation(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "boom"):
            parse_report("__ERROR__|boom")
        with self.assertRaises(RuntimeError):
            parse_report(LIVE_REPORT.replace("END\n", ""))

    def test_separate_pairs_hidden_unless_requested(self) -> None:
        far = LIVE_REPORT.replace("|1.25|1e+30|1|1|1|1|5,5,10||2.75,5,2.25", "|0|7.5|0|0|0|0||1,2,3|")
        self.assertEqual(parse_report(far)["pairs"], [])
        self.assertEqual(parse_report(far, include_separate=True)["pairs"][0]["status"], "separate")


if __name__ == "__main__":
    unittest.main()
