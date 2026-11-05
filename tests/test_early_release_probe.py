"""Do not convert missing acceptance evidence or delayed cancellation into passes."""
import unittest
from scripts.early_release_probe import classify


class EarlyReleaseJudgementTests(unittest.TestCase):
    def result(self, **changes):
        values=dict(cancelled=False,zero=False,prepared_before_move=True,count=1,exact=True,focused=True,clean=True)
        values.update(changes)
        return classify(**values)

    def test_missing_result_requires_acceptance_evidence(self):
        self.assertEqual(self.result(count=0),'FAIL')
        self.assertTrue(self.result(count=0,prepared_before_move=False).startswith('UNRESOLVED'))

    def test_late_result_after_cancel_or_zero_is_a_failure(self):
        for flag in ('cancelled','zero'):
            with self.subTest(flag=flag):
                self.assertEqual(self.result(**{flag:True}),'FAIL')
                self.assertEqual(self.result(**{flag:True},count=0),'PASS')

    def test_duplicate_wrong_geometry_focus_or_stuck_input_fails(self):
        for change in ({'count':2},{'exact':False},{'focused':False},{'clean':False}):
            with self.subTest(change=change): self.assertEqual(self.result(**change),'FAIL')

    def test_correct_single_result_is_distinct_from_observed_acceptance(self):
        self.assertEqual(self.result(),'PASS')
        self.assertEqual(self.result(prepared_before_move=False),'PASS')
