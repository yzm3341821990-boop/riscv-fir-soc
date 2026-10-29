"""Reject incomparable lane experiments instead of producing plausible ratios."""
import unittest

from tools.parallel_comparison import compare_lanes


def measurements():
    rows=[]
    for lanes, cold, resident in [(1,590,331),(2,462,203),(4,398,139)]:
        for mode,cycles in [('software',769),('hardware_cold',cold),('hardware_resident',resident)]:
            rows.append(dict(lanes=lanes,case='base',wait_policy='none',mode=mode,cycles=cycles,
                initial_memory_sha256='input',compiler_configuration='compiler',layout_sha256='layout',
                cpu_sha256='cpu',firmware_sha256=mode,hardware_cycles=0 if mode=='software' else resident-34))
    return rows


class ParallelComparisonTests(unittest.TestCase):
    def test_uses_actual_completed_call_intervals(self):
        result=compare_lanes(measurements())
        row=next(x for x in result if x['lanes']==4)
        self.assertEqual(row['software_cycles'],769)
        self.assertEqual(row['hardware_cold_cycles'],398)
        self.assertEqual(row['hardware_resident_cycles'],139)
        self.assertAlmostEqual(row['resident_vs_single_lane'],331/139)

    def test_refuses_missing_lane(self):
        with self.assertRaisesRegex(ValueError,'lane'):
            compare_lanes([x for x in measurements() if x['lanes']!=2])

    def test_refuses_changed_cpu_or_input(self):
        for key in ['cpu_sha256','initial_memory_sha256','compiler_configuration','layout_sha256','firmware_sha256']:
            rows=measurements();rows[-1][key]='changed'
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'mismatch'):
                compare_lanes(rows)

    def test_refuses_duplicate_mode(self):
        rows=measurements()
        with self.assertRaisesRegex(ValueError,'duplicate'):
            compare_lanes(rows+[rows[0].copy()])

    def test_refuses_changed_software_cycles(self):
        rows=measurements();rows[3]['cycles']=770
        with self.assertRaisesRegex(ValueError,'software'):
            compare_lanes(rows)


if __name__=='__main__':unittest.main()
