"""Inventory the Windows runtime for verified replacement and owned-file cleanup."""
import argparse
import hashlib
from pathlib import Path, PurePosixPath
from mini_whiteboard import APP_VERSION

NAME = 'MiniWhiteboard.payload'
HEADER = 'MiniWhiteboard payload v1 {94CAAC15-1695-4601-9CA3-67F10E2A8A32}'


def safe_relative(name):
    path = PurePosixPath(name)
    return (bool(name) and not path.is_absolute() and '\\' not in name
            and not any(part in ('', '.', '..') or part.endswith(('.', ' ')) for part in name.split('/'))
            and not any(c in name for c in ':*?<>|"\r\n') and str(path) == name)


def read_manifest(text):
    lines = text.splitlines()
    if len(lines) < 3 or lines[0] != HEADER or not lines[1].startswith('version='):
        raise ValueError('Invalid payload manifest.')
    entries = {}
    for line in lines[2:]:
        digest, name = line[:64], line[66:]
        if (line[64:66] != '  ' or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)
                or not safe_relative(name) or name.casefold() in {p.casefold() for p in entries}):
            raise ValueError('Invalid payload entry: ' + line)
        entries[name] = digest
    if 'Mini Whiteboard.exe' not in entries:
        raise ValueError('Missing application executable.')
    return entries


def write_manifest(directory):
    directory = Path(directory).resolve()
    lines = [HEADER, 'version=' + APP_VERSION]
    for path in sorted(directory.rglob('*')):
        if path.is_symlink() or not path.resolve().is_relative_to(directory):
            raise ValueError('Payload links are not supported.')
        if path.is_file() and path.name != NAME:
            name = path.relative_to(directory).as_posix()
            if not safe_relative(name):
                raise ValueError('Unsafe payload path: ' + name)
            lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + name)
    text = '\n'.join(lines) + '\n'
    read_manifest(text)
    (directory / NAME).write_text(text, encoding='utf-8')
    return len(lines) - 2


def verify_manifest(directory):
    directory = Path(directory).resolve()
    entries = read_manifest((directory / NAME).read_text(encoding='utf-8'))
    files = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and p.name != NAME}
    if files != set(entries):
        raise ValueError('Payload file set differs from the inventory.')
    for name, digest in entries.items():
        path = directory / name
        if path.is_symlink() or not path.resolve().is_relative_to(directory) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Payload hash mismatch: ' + name)
    return {'payload_inventory_verified': True, 'payload_files': len(entries)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    print('Inventoried files:', write_manifest(parser.parse_args().directory))
