import logging
from pathlib import Path
import unittest

from simulation.microsampler.pc_finder import find_pcs, UUTPCAddresses

logging.basicConfig(level=logging.DEBUG)


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

    def test_prebuild_testcases(self):
        prefix = Path("../apps/bearssl-0.6/microsampler_tests/build")
        tcs = [
            ("v1.dump", "br_i31_modpow_v1", "br_ccopy_v1", " 0x0000010128 0x000001012c 0x00000106d2 0x000001022c 0x00000106d6 ", False),
            ("v1_warmup.dump", "br_i31_modpow_v1", "br_ccopy_v1", " 0x000001014a 0x000001014e 0x00000106f4 0x000001024e 0x00000106f8 ", True),
            ("v1_fence.dump", "br_i31_modpow_v1_fence", "br_ccopy_v1", " 0x0000010128 0x000001012c 0x00000107a4 0x000001022c 0x00000107a8 ", False)
        ]
        for obj_file, roi_func, uut, pcs_string, warmup in tcs:
            parsed_pcs = [int(pc, 16) for pc in pcs_string.strip().split(" ")]
            self.assertEqual(len(parsed_pcs), 5, "expected 5 pcs in the test case definition")
            expected_pcs = UUTPCAddresses(
                roi_start=parsed_pcs[0],
                roi_end=parsed_pcs[1],
                calling_address=parsed_pcs[2],
                start_address=parsed_pcs[3],
                return_address=parsed_pcs[4],
            )
            self.run_testcase(prefix / obj_file, roi_func, uut, expected_pcs, warmup)



if __name__ == '__main__':
    unittest.main()
