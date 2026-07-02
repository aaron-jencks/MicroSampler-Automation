import logging
from pathlib import Path
import unittest

from simulation.microsampler.pc_finder import find_pcs, UUTPCAddresses

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class PCFinderTestCase(unittest.TestCase):
    def run_testcase(
            self,
            obj_file: Path, roi_func: str, uut: str,
            expected_pcs: UUTPCAddresses, warmup: bool
    ):
        self.assertTrue(obj_file.exists(), "test case object file doesn't exist, did you compile the test cases?")
        actual_pcs = find_pcs(obj_file, roi_func, uut, warmup)
        self.assertIsNotNone(actual_pcs)
        self.assertEqual(actual_pcs, expected_pcs)

    def test_ct_ccopy(self):
        obj_file = Path("smoke_data/ct_ccopy.dump")
        expected_pcs = UUTPCAddresses(
            roi_start=0x80000120,
            roi_end=0x80000124,
            calling_address=0x80000196,
            return_address=0x8000019a,
            start_address=0x80000130,
        )
        self.run_testcase(obj_file, "test_ccopy_loop", "ccopy", expected_pcs, True)

    def test_prebuilt_testcases(self):
        prefix = Path("../apps/bearssl-0.6/microsampler_tests/build")
        tcs = [
            ("v1.dump", "br_i31_modpow_v1", "br_ccopy_v1", [65968, 65972, 67396, 66220, 67400], False),
            ("v1_warmup.dump", "br_i31_modpow_v1", "br_ccopy_v1", [66004, 66008, 67432, 66256, 67436], True),
            ("v1_fence.dump", "br_i31_modpow_v1_fence", "br_ccopy_v1", [65968, 65972, 67606, 66220, 67610], False),
            ("v2.dump", "br_i31_modpow_v2", "br_ccopy_v2", [65972, 65976, 67828, 66202, 67832], False),
            ("v2_warmup.dump", "br_i31_modpow_v2", "br_ccopy_v2", [66012, 66016, 67868, 66242, 67872], True),
            ("v2_fence.dump", "br_i31_modpow_v2_fence", "br_ccopy_v2", [65972, 65976, 68046, 66202, 68050], False),
            ("v3.dump", "br_i31_modpow", "br_ccopy", [65968, 65972, 66976, 66236, 66980], False),
            ("v3_warmup.dump", "br_i31_modpow", "br_ccopy", [66004, 66008, 67012, 66272, 67016], True),
            ("v3_fence.dump", "br_i31_modpow_fence", "br_ccopy", [65968, 65972, 67186, 66236, 67190], False)
        ]
        for obj_file, roi_func, uut, pcs_ints, warmup in tcs:
            self.assertEqual(len(pcs_ints), 5, "expected 5 pcs in the test case definition")
            expected_pcs = UUTPCAddresses(
                roi_start=pcs_ints[0],
                roi_end=pcs_ints[1],
                calling_address=pcs_ints[2],
                start_address=pcs_ints[3],
                return_address=pcs_ints[4],
            )
            logger.debug(f"testing dump file: {obj_file}")
            self.run_testcase(prefix / obj_file, roi_func, uut, expected_pcs, warmup)



if __name__ == '__main__':
    unittest.main()
