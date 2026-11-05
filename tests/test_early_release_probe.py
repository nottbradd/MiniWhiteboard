"""Do not convert missing acceptance evidence or delayed cancellation into passes."""
import unittest
from scripts.early_release_probe import classify, capture_pixels_match


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

    def test_capture_comparison_requires_original_pixels_and_clear_export_gutter(self):
        from PySide6.QtGui import QImage, QPainter, QColor
        from PySide6.QtCore import Qt
        expected=QImage(12,10,QImage.Format.Format_RGBA8888);expected.fill(QColor('#3186cb'))
        exported=QImage(16,14,QImage.Format.Format_RGBA8888);exported.fill(Qt.GlobalColor.transparent)
        painter=QPainter(exported);painter.drawImage(2,2,expected);painter.end()
        self.assertTrue(all(capture_pixels_match(expected,expected,exported).values()))
        corrupted=expected.copy();corrupted.setPixelColor(0,0,QColor('red'))
        self.assertFalse(capture_pixels_match(expected,corrupted,exported)['original_pixels_equal'])
        exported.setPixelColor(0,0,QColor('red'))
        self.assertFalse(capture_pixels_match(expected,expected,exported)['clipboard_transparent_gutter'])
