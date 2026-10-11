"""Stage or verify the runtime-only ZIP against the verified distribution."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import pefile
from mini_whiteboard import APP_VERSION
from .build_support import verify_release_files


def version_strings(executable):
    pe = pefile.PE(data=executable)
    result = {}
    for group in pe.FileInfo:
        for entry in group:
            for table in getattr(entry,'StringTable',()):
                result.update({k.decode():v.decode() for k,v in table.entries.items()})
    pe.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify',type=Path)
    parser.add_argument('--distribution', type=Path, default=Path('dist/windows-v11/Mini Whiteboard'))
    parser.add_argument('--archive', type=Path, default=Path('build/WinMiniWhiteboardV1.1.zip'))
    args = parser.parse_args()
    distribution = args.distribution.resolve()
    license_report = verify_release_files(distribution)
    files = sorted(p for p in distribution.rglob('*') if p.is_file())
    if not files:
        raise RuntimeError('Build the distribution first.')
    expected = {'Mini Whiteboard/'+p.relative_to(distribution).as_posix():p for p in files}
    for name in expected:
        path = Path(name)
        if path.suffix.lower() in ('.py','.pyc','.log','.tmp') or any(
                p in ('__pycache__','.venv','tests','verification','.test-artifacts') for p in path.parts):
            raise RuntimeError('Development file found in distribution: '+name)
    archive = args.verify or args.archive
    if args.verify is None:
        archive.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
            for name,path in expected.items():
                zipped.write(path,name)
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise RuntimeError('ZIP contents differ from the current distribution.')
        if zipped.testzip() is not None:
            raise RuntimeError('ZIP CRC verification failed.')
        entries = []
        for name,path in expected.items():
            content = zipped.read(name)
            checksum = hashlib.sha256(content).hexdigest()
            if checksum != hashlib.sha256(path.read_bytes()).hexdigest():
                raise RuntimeError('ZIP content hash mismatch: '+name)
            entries.append({'path':name,'bytes':len(content),'sha256':checksum})
        executable = zipped.read('Mini Whiteboard/Mini Whiteboard.exe')
        info = version_strings(executable)
        if info.get('ProductVersion') != APP_VERSION or info.get('FileVersion') != APP_VERSION:
            raise RuntimeError('The ZIP does not contain the requested version.')
    result = {'version':APP_VERSION,**license_report,'archive':str(archive.resolve()),'archive_bytes':archive.stat().st_size,
              'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
              'executable':str(distribution/'Mini Whiteboard.exe'),'executable_bytes':len(executable),
              'executable_sha256':hashlib.sha256(executable).hexdigest(),
              'file_count':len(entries),'all_crcs_and_sha256_match':True,'metadata':info,'files':entries}
    output = Path('verification/windows-v11-release-verified.json' if args.verify else 'verification/windows-v11-release-staged.json')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key != 'files'},indent=2))


if __name__ == '__main__':
    main()
