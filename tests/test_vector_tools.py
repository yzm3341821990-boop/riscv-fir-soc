"""Integration checks for reproducible, independently audited RTL vectors."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import generate_vectors, verify_vectors

ROOT = Path(__file__).resolve().parents[1]


class VectorToolTests(unittest.TestCase):
    def setUp(self):
        self.generator = generate_vectors
        self.verifier = verify_vectors
        self.temporary = tempfile.TemporaryDirectory(prefix="fir-vectors-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "vectors"

    def _generate(self):
        self.generator.generate_vectors(self.directory)
        return json.loads((self.directory / "manifest.json").read_text())

    def _replace_and_rehash(self, manifest, name, key, new_text):
        entry = next(item for item in manifest["cases"] if item["name"] == name)
        record = entry["files"][key]
        path = self.directory / record["path"]
        path.write_text(new_text, encoding="ascii", newline="\n")
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.directory / "manifest.json").write_text(json.dumps(manifest))

    def test_boundary_vectors_have_hand_checked_values(self):
        manifest = self._generate()
        self.assertEqual((self.directory / "positive_ties/expected.hex").read_text(),
                         "00000001\n00000002\n00000003\n00004000\n")
        self.assertEqual((self.directory / "negative_ties/expected.hex").read_text(),
                         "FFFFFFFF\nFFFFFFFE\nFFFFFFFD\nFFFFC000\n")
        self.assertEqual((self.directory / "empty_block/input.hex").read_bytes(), b"")
        self.assertEqual((self.directory / "empty_block/expected.hex").read_bytes(), b"")
        self.assertEqual(len(manifest["cases"]), 13)
        self.assertIn("34359738368", (self.directory / "accumulator_extreme/trace.csv").read_text())

    def test_generation_is_byte_reproducible(self):
        self._generate()
        other = self.directory.parent / "other"
        self.generator.generate_vectors(other)
        for path in self.directory.rglob("*"):
            if path.is_file():
                relative = path.relative_to(self.directory)
                with self.subTest(file=str(relative)):
                    self.assertEqual(path.read_bytes(), (other / relative).read_bytes())

    def test_generated_suite_passes_independent_rational_audit(self):
        self._generate()
        report = self.verifier.verify_vectors(self.directory)
        self.assertEqual(report["case_count"], 13)
        self.assertGreater(report["sample_count"], 1500)
        self.assertEqual(report["output_mismatches"], 0)
        self.assertEqual(report["max_abs_accumulator"], 34359738368)

    def test_hash_change_is_rejected(self):
        self._generate()
        path = self.directory / "positive_ties/expected.hex"
        path.write_text("00000000\n", encoding="ascii")
        with self.assertRaisesRegex(ValueError, "hash"):
            self.verifier.verify_vectors(self.directory)

    def test_wrong_output_is_detected_even_with_updated_hash(self):
        manifest = self._generate()
        self._replace_and_rehash(manifest, "positive_ties", "outputs",
                                 "00000000\n00000002\n00000003\n00004000\n")
        with self.assertRaisesRegex(ValueError, "output mismatch"):
            self.verifier.verify_vectors(self.directory)

    def test_wrong_accumulator_is_detected_even_with_updated_hash(self):
        manifest = self._generate()
        path = self.directory / "positive_ties/accumulators.hex"
        lines = path.read_text().splitlines()
        lines[0] = "0000000000"
        self._replace_and_rehash(manifest, "positive_ties", "accumulators",
                                 "\n".join(lines) + "\n")
        with self.assertRaisesRegex(ValueError, "accumulator mismatch"):
            self.verifier.verify_vectors(self.directory)

    def test_trace_corruption_is_detected_even_with_updated_hash(self):
        manifest = self._generate()
        text = (self.directory / "positive_ties/trace.csv").read_text()
        self._replace_and_rehash(manifest, "positive_ties", "trace",
                                 text.replace("0,1,16384,1", "0,1,0,1"))
        with self.assertRaisesRegex(ValueError, "trace mismatch"):
            self.verifier.verify_vectors(self.directory)

    def test_missing_file_is_rejected(self):
        self._generate()
        (self.directory / "step/input.hex").unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.verifier.verify_vectors(self.directory)

    def test_generation_and_verification_cli_work(self):
        generated = subprocess.run(
            [sys.executable, "-m", "tools.generate_vectors", "--output", str(self.directory)],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        checked = subprocess.run(
            [sys.executable, "-m", "tools.verify_vectors", str(self.directory)],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["case_count"], 13)
        (self.directory / "positive_ties/expected.hex").write_text("00000000\n")
        rejected = subprocess.run(
            [sys.executable, "-m", "tools.verify_vectors", str(self.directory)],
            cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("hash", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
