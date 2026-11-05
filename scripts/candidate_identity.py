"""Freeze and verify an unpublished installer/portable pair from one build."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile
from mini_whiteboard import APP_VERSION
from .build_support import verify_release_files, verify_frozen_modules
from .payload_manifest import verify_manifest


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    if data['source_revision'] != revision or data['version'] != APP_VERSION:
        raise ValueError('Candidate source/version does not match this checkout.')
    if len(data['assets']) != 2 or not re.fullmatch('[0-9a-f]{64}', data['exe_sha256']):
        raise ValueError('Invalid candidate identity.')
    for asset in data['assets']:
        name = asset['name']
        if not name or Path(name).name != name or '/' in name or '\\' in name:
            raise ValueError('Candidate files must be beside their identity receipt.')
        file = path.parent/name
        if file.stat().st_size != asset['bytes'] or sha(file) != asset['sha256']:
            raise ValueError('Candidate package hash mismatch: '+name)
    if not data['assets'][0]['name'].endswith('.exe') or not data['assets'][1]['name'].endswith('.zip'):
        raise ValueError('Expected installer then portable ZIP.')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--distribution', type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(read(args.verify), indent=2))
        return
    if args.directory is None or args.distribution is None:
        parser.error('Both build directory and distribution are required.')
    bundle = args.distribution
    identity = {'version': APP_VERSION, 'source_revision': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip(), 'unpublished': True,
        'exe_sha256': sha(bundle/'Mini Whiteboard.exe'), 'assets': [],
        'payload': {**verify_release_files(bundle), **verify_frozen_modules(bundle/'Mini Whiteboard.exe'),
                    **verify_manifest(bundle)}}
    for name in (f'MiniWhiteboard-{APP_VERSION}-Setup.exe', f'WinMiniWhiteboardV{APP_VERSION}.zip'):
        file = args.directory/name
        identity['assets'].append({'name':name, 'bytes':file.stat().st_size, 'sha256':sha(file)})
    with zipfile.ZipFile(args.directory/identity['assets'][1]['name']) as archive:
        if hashlib.sha256(archive.read('Mini Whiteboard/Mini Whiteboard.exe')).hexdigest()!=identity['exe_sha256']:
            raise ValueError('ZIP executable differs from the installer build payload.')
    path = args.directory/'candidate-identity.json'
    path.write_text(json.dumps(identity, indent=2)+'\n', encoding='utf-8')
    read(path)
    print(path)


if __name__ == '__main__':
    main()
