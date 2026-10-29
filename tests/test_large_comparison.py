"""Reject comparisons whose actual execution evidence is incomplete or mismatched."""
import copy,json,unittest
from pathlib import Path
from tools.compare_large_blocks import compare


class LargeComparisonTests(unittest.TestCase):
    def setUp(self):
        self.report=json.loads((Path(__file__).resolve().parents[1]/'reports/step20-large-block/system-validation.json').read_text())

    def test_actual_matrix_pairs_all_36_hardware_calls(self):
        rows=compare(self.report);self.assertEqual(len(rows),36)
        row=next(r for r in rows if (r['sample_count'],r['mode'],r['lanes'],r['dma_wait'])==(1024,'hardware_cold',4,'none'))
        self.assertEqual((row['software_cycles'],row['complete_call_cycles']),(489233,13608))

    def test_missing_case_is_rejected(self):
        self.report['measurements'].pop()
        with self.assertRaisesRegex(ValueError,'incomplete'):compare(self.report)

    def test_changed_compiler_is_rejected(self):
        self.report['measurements'][1]['compiler_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'compiler'):compare(self.report)

    def test_different_inputs_are_rejected(self):
        self.report['measurements'][1]['initial_memory_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'RAM'):compare(self.report)

    def test_different_firmware_across_lanes_is_rejected(self):
        self.report['measurements'][1]['program_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'firmware'):compare(self.report)

    def test_unchecked_tail_outputs_are_rejected(self):
        self.report['measurements'][0]['outputs_checked']=8
        with self.assertRaisesRegex(ValueError,'audit'):compare(self.report)


if __name__=='__main__':unittest.main()
