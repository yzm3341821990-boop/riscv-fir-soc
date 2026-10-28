"""Check that deliberate numerical faults are caught without editing sources."""

import hashlib
from pathlib import Path
import unittest

from tools import check_mutations


class MutationTests(unittest.TestCase):
    def test_rounding_saturation_and_order_faults_are_detected(self):
        path = Path(__file__).resolve().parents[1] / "model/fixed_fir.py"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        report = check_mutations.check_mutations()
        self.assertEqual(report["killed_count"], 3)
        for mutation in report["mutations"]:
            with self.subTest(mutation=mutation["name"]):
                self.assertTrue(mutation["killed"], mutation["log"])
                self.assertGreaterEqual(mutation["tests_run"], 26)
                self.assertGreater(mutation["failure_count"], 0)
                self.assertEqual(mutation["error_count"], 0)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
