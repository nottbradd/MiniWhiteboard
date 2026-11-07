import unittest
from scripts.early_release_matrix import case_group, cases_for


class DiagnosticGroupsTests(unittest.TestCase):
    def test_split_preserves_each_full_workload_and_original_case_order(self):
        mode='early-default-full'
        groups=[case_group(mode,start,3) for start in range(0,15,3)]
        flattened=[entry for group in groups for entry in group]
        self.assertEqual(flattened,list(enumerate(cases_for(mode))))
        self.assertTrue(all(case['prelude']=='full' for _,case in flattened))
        self.assertEqual({case['action'] for _,case in flattened},{'W','Q'})

    def test_invalid_subset_is_not_silently_truncated(self):
        for start,count in ((-1,3),(15,1),(14,3),(0,0)):
            with self.subTest(start=start,count=count),self.assertRaises(ValueError):
                case_group('early-default-full',start,count)
