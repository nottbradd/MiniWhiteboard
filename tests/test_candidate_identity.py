"""Candidate verification must not silently accept changed or mismatched files."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mini_whiteboard import APP_VERSION
from scripts.candidate_identity import read, sha


class CandidateIdentityTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('scripts.candidate_identity.subprocess.check_output', return_value='a'*40))
        self.data = {'source_revision':'a'*40, 'version':APP_VERSION, 'exe_sha256':'b'*64, 'assets':[]}
        for name in ('test.exe', 'test.zip'):
            path = self.folder/name
            path.write_bytes(b'Harmless identity fixture, not an executable.')
            self.data['assets'].append({'name':name, 'bytes':path.stat().st_size, 'sha256':sha(path)})
        self.path = self.folder/'candidate-identity.json'

    def check(self):
        self.path.write_text(json.dumps(self.data))
        return read(self.path)

    def test_exact_pair_is_accepted(self):
        self.assertEqual(self.check(), self.data)

    def test_changed_file_is_rejected(self):
        (self.folder/'test.exe').write_bytes(b'Changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.check()

    def test_source_mismatch_is_rejected(self):
        self.data['source_revision']='c'*40
        with self.assertRaisesRegex(ValueError, 'source/version'):
            self.check()

    def test_path_escape_is_rejected_before_reading(self):
        self.data['assets'][0]['name']='../elsewhere.exe'
        with self.assertRaisesRegex(ValueError, 'beside'):
            self.check()
