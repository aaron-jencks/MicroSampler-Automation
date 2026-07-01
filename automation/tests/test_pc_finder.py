from pathlib import Path
import unittest

from simulation.microsampler.pc_finder import find_pcs


class PCFinderTestCase(unittest.TestCase):
    def test_ct_ccopy(self):
        obj_file = Path("smoke_data/ct_ccopy.dump")
        pcs = find_pcs(obj_file, "test_ccopy_loop", "ccopy", warmup=True)
        self.assertIsNotNone(pcs)
        self.assertEqual(pcs.roi_start, 0x80000120)
        self.assertEqual(pcs.roi_end, 0x80000124)
        self.assertEqual(pcs.calling_address, 0x80000196)
        self.assertEqual(pcs.return_address, 0x8000019a)
        self.assertEqual(pcs.start_address, 0x80000130)



if __name__ == '__main__':
    unittest.main()
