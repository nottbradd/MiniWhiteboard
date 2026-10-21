"""Release guards reject incomplete, damaged or unintended package contents."""
import hashlib
import json
from pathlib import Path
import tempfile
import sys
import unittest

from scripts.build_support import verify_release_files


class ReleaseNoticeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.licenses = self.root / '_internal' / 'licenses'
        self.licenses.mkdir(parents=True)
        content = b'Example notice\n'
        (self.licenses / 'NOTICE.txt').write_bytes(content)
        (self.licenses / 'MANIFEST.json').write_text(json.dumps({'files':[
            {'path':'NOTICE.txt','sha256':hashlib.sha256(content).hexdigest()}]}))

    def test_missing_or_modified_notice_rejects_release(self):
        notice = self.licenses / 'NOTICE.txt'
        notice.write_text('Damaged notice')
        with self.assertRaisesRegex(RuntimeError, 'Missing or modified'):
            verify_release_files(self.root)
        notice.unlink()
        with self.assertRaisesRegex(RuntimeError, 'Missing or modified'):
            verify_release_files(self.root)

    def test_unintended_qt_product_rejects_release(self):
        for relative in ('Qt6VirtualKeyboard.dll', 'QtQml.framework/Versions/A/QtQml',
                         'icuuc.dll'):
            with self.subTest(relative=relative):
                path = self.root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
                with self.assertRaisesRegex(RuntimeError, 'Unused Qt products'):
                    verify_release_files(self.root)
                path.unlink()

    def test_manifest_path_cannot_escape_notice_directory(self):
        (self.licenses / 'MANIFEST.json').write_text(json.dumps({'files':[
            {'path':'../../outside.txt','sha256':'ignored'}]}))
        with self.assertRaisesRegex(RuntimeError, 'Unsafe license manifest'):
            verify_release_files(self.root)

    def test_verified_package_has_complete_notices(self):
        self.assertEqual(verify_release_files(self.root), {
            'license_files':1, 'licenses_verified':True, 'unused_qt_products_absent':True, 'ocr_payload_absent':True})

    def test_removed_ocr_payload_rejects_both_platform_packages(self):
        for relative in ('_internal/tesserocr/engine.dll', 'assets/ocr/eng.traineddata',
                         'Contents/Resources/Vision/_Vision.so', 'Contents/Resources/CoreML/_CoreML.so',
                         'licenses/upstream/ocr-tesseract.txt'):
            with self.subTest(relative=relative):
                path = self.root/relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
                with self.assertRaisesRegex(RuntimeError, 'Removed OCR payload'):
                    verify_release_files(self.root)
                path.unlink()

    @unittest.skipIf(sys.platform == 'win32', 'Real Mac bundle symlinks run on Mac CI')
    def test_mac_bundle_notice_alias_counts_physical_manifest_once(self):
        resources = self.root / 'Contents' / 'Resources'
        frameworks = self.root / 'Contents' / 'Frameworks'
        resources.mkdir(parents=True)
        frameworks.mkdir(parents=True)
        self.licenses.rename(resources / 'licenses')
        (frameworks / 'licenses').symlink_to('../Resources/licenses', target_is_directory=True)
        self.assertEqual(verify_release_files(self.root)['license_files'], 1)

    @unittest.skipIf(sys.platform == 'win32', 'Real Mac bundle symlinks run on Mac CI')
    def test_mac_bundle_notice_alias_cannot_point_outside_package(self):
        bundle = self.root / 'Mini Whiteboard.app'
        bundle.mkdir()
        (bundle / 'licenses').symlink_to(self.licenses, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'must stay inside the package'):
            verify_release_files(bundle)
