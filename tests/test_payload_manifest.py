import hashlib
from pathlib import Path
import tempfile
import unittest
from scripts.payload_manifest import HEADER, NAME, read_manifest, write_manifest, verify_manifest


class PayloadTests(unittest.TestCase):
    def test_rebuild_inventory_detects_modified_missing_and_extra_payloads(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'Mini Whiteboard.exe').write_bytes(b'application')
            (root / 'runtime.dll').write_bytes(b'runtime')
            self.assertEqual(write_manifest(root), 2)
            self.assertEqual(verify_manifest(root)['payload_files'], 2)
            (root / 'runtime.dll').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                verify_manifest(root)
            (root / 'runtime.dll').unlink()
            with self.assertRaisesRegex(ValueError, 'file set'):
                verify_manifest(root)
            (root / 'runtime.dll').write_bytes(b'runtime')
            (root / 'extra.dll').write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError, 'file set'):
                verify_manifest(root)

    def test_inventory_rejects_traversal_absolute_streams_duplicates_and_invalid_owner(self):
        valid = HEADER + '\nversion=1.3.4\n' + 'a' * 64 + '  Mini Whiteboard.exe\n'
        for path in ('../outside.txt', 'C:/outside', '/outside', 'dir/../outside', 'dir//file',
                     'file:stream', 'dir\\file', 'folder./file', 'folder /file', 'Mini Whiteboard.EXE'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                read_manifest(valid + 'b' * 64 + '  ' + path + '\n')
        with self.assertRaises(ValueError):
            read_manifest(valid.replace(HEADER, 'Some other application'))

    def test_legacy_inventory_is_bound_to_the_published_v133_payload(self):
        root = Path(__file__).resolve().parents[1]
        legacy = read_manifest((root / 'installer/legacy-v1.3.3.payload').read_text(encoding='utf-8'))
        self.assertEqual(len(legacy), 200)
        self.assertIn('Mini Whiteboard.exe', legacy)
        self.assertTrue(any('licenses/MANIFEST.json' in name for name in legacy))
