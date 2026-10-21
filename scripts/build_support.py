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
    root = Path(project) / 'build' / 'candidates' / 'v1.3.1' / 'review-03' / 'license-notices'
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
    removed = [p.relative_to(root).as_posix() for p in root.rglob('*')
               if p.is_file() and removed_component(p.relative_to(root).as_posix())]
    if removed:
        raise RuntimeError('Removed OCR payload found in package: ' + ', '.join(removed))
    return {'license_files': len(report['files']), 'licenses_verified': True,
            'unused_qt_products_absent': True, 'ocr_payload_absent': True}


def removed_component(name):
    name = name.lower().replace('\\', '/').replace('.', '/')
    return any(token in name for token in ('tesserocr','tesseract','leptonica','cysignals',
        'traineddata')) or bool({'ocr','ocr_worker','ocr_panel','vision','coreml'} & set(name.split('/')))


def verify_frozen_modules(executable):
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(executable))
    modules = archive.open_embedded_archive('PYZ.pyz').toc
    removed = [name for name in modules if removed_component(name)]
    if removed:
        raise RuntimeError('Removed OCR modules found in executable: ' + ', '.join(removed))
    return {'frozen_ocr_modules_absent': True, 'frozen_module_count': len(modules)}
