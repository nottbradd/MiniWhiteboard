"""Shared PyInstaller policy for the desktop widget application."""
from pathlib import Path
import sys


def configure_qt_plugins():
    """Filter unused plugins before their Qt library dependencies are collected."""
    from PyInstaller.utils.hooks.qt import pyside6_library_info
    original = pyside6_library_info.collect_plugins

    def collect(plugin_type):
        if plugin_type == 'platforminputcontexts':
            # Native IME is handled by the Windows/Cocoa platform plugins.
            # Qt Virtual Keyboard is a separate QML product we do not use.
            return []
        return [(source, target) for source, target in original(plugin_type)
                if 'qpdf' not in Path(source).name.lower()]

    pyside6_library_info.collect_plugins = collect


def notice_data(project):
    root = Path(project) / 'build' / 'license-notices'
    if not (root / 'MANIFEST.json').is_file():
        raise RuntimeError('Run python -m scripts.package_notices before packaging.')
    return [(str(root), 'licenses')]


def verify_release_files(root):
    """Fail a distribution with missing notices or an unintended Qt product."""
    import json
    import hashlib
    root = Path(root)
    # PyInstaller exposes Mac data through both Resources and a Frameworks
    # symlink. Count the physical manifest once, while rejecting external links.
    manifests = {p.resolve() for p in root.rglob('licenses/MANIFEST.json')}
    if any(not p.is_relative_to(root.resolve()) for p in manifests):
        raise RuntimeError('License manifest must stay inside the package.')
    if len(manifests) != 1:
        raise RuntimeError('The package needs one license manifest.')
    manifest = next(iter(manifests))
    base = manifest.parent
    report = json.loads(manifest.read_text(encoding='utf-8'))
    for entry in report['files']:
        path = base / entry['path']
        if not path.resolve().is_relative_to(base.resolve()):
            raise RuntimeError('Unsafe license manifest path.')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise RuntimeError('Missing or modified license notice: ' + entry['path'])
    forbidden = ('virtualkeyboard', 'qt6pdf', 'qtpdf.framework', 'qpdf', 'qt6qml',
                 'qtqml.framework', 'qt6quick', 'qtquick.framework', 'icuuc.dll')
    unexpected = [p.relative_to(root).as_posix() for p in root.rglob('*')
                  if p.is_file() and any(name in p.relative_to(root).as_posix().lower()
                                        for name in forbidden)]
    if unexpected:
        raise RuntimeError('Unused Qt products found in package: ' + ', '.join(unexpected))
    return {'license_files': len(report['files']), 'licenses_verified': True,
            'unused_qt_products_absent': True}


def verify_ocr_runtime(root):
    import hashlib
    import json
    root = Path(root)
    if sys.platform == 'win32':
        resources = next(root.rglob('assets/ocr/MANIFEST.json'), None)
        if resources is None:
            raise RuntimeError('Missing bundled OCR resources.')
        ocr = json.loads(resources.read_text(encoding='utf-8'))
        data = resources.parent / ocr['data']['path']
        if hashlib.sha256(data.read_bytes()).hexdigest() != ocr['data']['sha256']:
            raise RuntimeError('English OCR data hash mismatch.')
        for entry in ocr['files']:
            matches = [path for path in root.rglob(Path(entry['path']).name) if path.is_file()]
            if not matches or any(hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256'] for path in matches):
                raise RuntimeError('OCR binary missing or changed: ' + entry['path'])
            import pefile
            for path in matches:
                binary = pefile.PE(str(path), fast_load=True)
                if binary.FILE_HEADER.Machine != 0x8664:
                    raise RuntimeError('OCR needs x64 binaries: ' + entry['path'])
                binary.close()
    return True
