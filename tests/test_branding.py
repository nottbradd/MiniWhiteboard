"""Shipping icon sizes, native ICO decoding and readable status symbols."""
from pathlib import Path
from PySide6.QtGui import QIcon
from tests.qt_case import QtCase
from mini_whiteboard.branding import app_icon, tray_icon


class BrandingTests(QtCase):
    def test_windows_ico_contains_and_decodes_small_and_large_native_frames(self):
        icon=QIcon(str(Path(__file__).resolve().parents[1]/'assets/mini_whiteboard.ico'))
        self.assertFalse(icon.isNull())
        sizes={side.width() for side in icon.availableSizes()}
        self.assertTrue({16,20,24,32,48,64,128,256}.issubset(sizes))
        for side in (16,32,48,256):
            image=icon.pixmap(side,side).toImage()
            self.assertEqual((image.width(),image.height()),(side,side))
            self.assertEqual(image.pixelColor(0,0).alpha(),0)
            self.assertGreater(image.pixelColor(side//2,side//2).alpha(),240)

    def test_application_icon_includes_high_resolution_without_rerendering(self):
        self.assertTrue({16,32,256,512,1024}.issubset({s.width() for s in app_icon().availableSizes()}))
        self.assertEqual(app_icon().cacheKey(),app_icon().cacheKey())
        self.assertNotEqual(app_icon().pixmap(20,20).toImage(),tray_icon().pixmap(20,20).toImage())

    def test_tray_symbols_retain_matching_silhouettes_and_contrast_at_small_sizes(self):
        for side in (16,20,24,32):
            dark=tray_icon(light_background=True).pixmap(side,side).toImage()
            light=tray_icon(light_background=False).pixmap(side,side).toImage()
            core=0
            for y in range(side):
                for x in range(side):
                    a,b=dark.pixelColor(x,y),light.pixelColor(x,y)
                    self.assertEqual(a.alpha(),b.alpha())
                    if a.alpha()>240:
                        core+=1
                        self.assertLess(a.lightness(),70)
                        self.assertGreater(b.lightness(),235)
            self.assertGreater(core,side)

    def test_mac_status_icon_is_a_template_mask(self):
        self.assertTrue(tray_icon(template=True).isMask())
        self.assertFalse(tray_icon(light_background=False).isMask())
