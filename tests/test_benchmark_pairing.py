"""A cycle ratio is valid only for matching workload/platform/build conditions."""
import importlib.util
import unittest


class BenchmarkPairingTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.fir_benchmark'),
                             'the fair benchmark pairing gate must exist')
        from tools.fir_benchmark import pair_measurements
        return pair_measurements

    def rows(self):
        shared=dict(case='base',wait_policy='none',initial_memory_sha256='same-input',
                    compiler_configuration='same-compiler',layout_sha256='same-layout',platform_sha256='same-rtl')
        return [{**shared,'mode':mode,'cycles':cycles,'hardware_cycles':kernel}
                for mode,cycles,kernel in [('software',1000,0),('hardware_cold',500,100),('hardware_resident',250,100)]]

    def test_primary_ratio_uses_complete_call_not_kernel_time(self):
        result=self.api()(self.rows())[0]
        self.assertEqual(result['cold_cycle_ratio'],2.0)
        self.assertEqual(result['resident_cycle_ratio'],4.0)
        self.assertEqual(result['hardware_cold_cycles'],500)

    def test_input_build_layout_and_platform_mismatches_are_rejected(self):
        api=self.api()
        for field in ('initial_memory_sha256','compiler_configuration','layout_sha256','platform_sha256'):
            with self.subTest(field=field):
                rows=self.rows();rows[1][field]='different'
                with self.assertRaises(ValueError): api(rows)

    def test_missing_duplicate_and_failed_measurements_are_rejected(self):
        api=self.api()
        for rows in (self.rows()[:2],self.rows()+[self.rows()[1]],
                     [dict(r,cycles=0) for r in self.rows()],
                     [dict(r,cycles=-1) for r in self.rows()]):
            with self.assertRaises(ValueError): api(rows)

    def test_slow_hardware_result_is_retained(self):
        rows=self.rows();rows[1]['cycles']=2000
        self.assertEqual(self.api()(rows)[0]['cold_cycle_ratio'],0.5)


if __name__=='__main__': unittest.main()
