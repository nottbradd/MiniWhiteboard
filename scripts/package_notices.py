"""Stage reproducible upstream notices and installed-package license texts."""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import sys
from urllib.request import urlopen

PROJECT = Path(__file__).resolve().parents[1]


def stage(project=PROJECT, destination=None):
    project = Path(project)
    destination = Path(destination or project / 'build' / 'license-notices')
    if not destination.resolve().is_relative_to(project.resolve()):
        raise RuntimeError('Notice staging must stay inside the project.')
    destination.mkdir(parents=True, exist_ok=True)
    files = {}

    def add(name, data):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files[name] = {'path': name, 'sha256': hashlib.sha256(data).hexdigest()}

    add('MiniWhiteboard-MIT.txt', (project / 'LICENSE').read_bytes())
    add('THIRD_PARTY_NOTICES.md', (project / 'docs' / 'THIRD_PARTY_NOTICES.md').read_bytes())
    for source in sorted((project / 'assets' / 'licenses').glob('*')):
        if source.is_file():
            if source.name.startswith('pyobjc-') and sys.platform != 'darwin':
                continue
            add('upstream/' + source.name, source.read_bytes())
    required = {'qtbase-6.11.2.txt', 'qtsvg-6.11.2.txt', 'qtimageformats-6.11.2.txt',
                'pyside-setup-6.11.2.txt', 'SOURCES.md'}
    if sys.platform == 'darwin':
        required.add('pyobjc-12.2.2.txt')
    if not required.issubset({p.name for p in (project / 'assets' / 'licenses').glob('*')}):
        raise RuntimeError('The versioned upstream notices are incomplete.')

    candidates = [Path(sys.base_prefix) / name for name in
                  ('LICENSE.txt', 'LICENSE', 'Resources/LICENSE.txt', 'Resources/LICENSE')]
    python_license = next((p.read_bytes() for p in candidates if p.is_file()), None)
    if python_license is None:
        url = f'https://raw.githubusercontent.com/python/cpython/v{platform.python_version()}/LICENSE'
        with urlopen(url, timeout=30) as response:
            python_license = response.read()
    add('Python-LICENSE.txt', python_license)
    packages = ['PySide6','PySide6-Essentials','PySide6-Addons','shiboken6','PyInstaller']
    if sys.platform == 'darwin':
        packages += ['pyobjc-core','pyobjc-framework-Cocoa','pyobjc-framework-Quartz',
                     'pyobjc-framework-ScreenCaptureKit','pyobjc-framework-CoreMedia']
    versions = {}
    for name in packages:
        dist = metadata.distribution(name)
        versions[name] = dist.version
        for entry in dist.files or ():
            # Include original wheel notices, not source modules named licenses.
            relative = Path(str(entry))
            if '.dist-info' not in str(relative) or not any(
                    term in relative.name.lower() for term in ('license','copying','notice','copyright')):
                continue
            source = Path(dist.locate_file(entry))
            if source.is_file():
                add('packages/' + name + '/' + relative.name, source.read_bytes())
    readme = ('Mini Whiteboard 1.1 dependency notices\n\n'
              'The app source is MIT licensed. Qt/PySide libraries are dynamically loaded.\n'
              'See THIRD_PARTY_NOTICES.md and upstream/SOURCES.md for versioned source access\n'
              'and instructions for replacing/rebuilding those libraries.\n'
              'PyInstaller is a packaging tool; its bootloader distribution exception is included.\n'
              'Installed wheel notices are retained verbatim, including alternative commercial terms;\n'
              'those notices do not change the open-source LGPL terms used for this release.\n')
    add('README.txt', readme.encode())
    # Remove obsolete generated notices so a changed environment cannot carry stale data.
    for path in destination.rglob('*'):
        if path.is_file() and path.relative_to(destination).as_posix() not in files and path.name != 'MANIFEST.json':
            if not path.resolve().is_relative_to(destination.resolve()):
                raise RuntimeError('Refusing to remove a notice outside staging.')
            path.unlink()
    report = {'python': platform.python_version(), 'platform': sys.platform,
              'packages': versions, 'files': sorted(files.values(), key=lambda item:item['path'])}
    (destination / 'MANIFEST.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    report = stage()
    print(json.dumps({'notice_files':len(report['files']), 'packages':report['packages']}))


if __name__ == '__main__':
    main()
