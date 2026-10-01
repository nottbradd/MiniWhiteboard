"""Generate the Windows resource from the same version used by the application."""
from pathlib import Path
import re
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct,
    VarFileInfo, VarStruct,
)
from mini_whiteboard import APP_VERSION


def main():
    parts = tuple(int(p) for p in APP_VERSION.split('.'))
    version = (parts + (0, 0, 0, 0))[:4]
    info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=version, prodvers=version, mask=0x3f, flags=0,
                          OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
        kids=[StringFileInfo([StringTable('040904B0', [
            StringStruct('FileDescription', 'Mini Whiteboard'),
            StringStruct('FileVersion', APP_VERSION),
            StringStruct('ProductName', 'Mini Whiteboard'),
            StringStruct('ProductVersion', APP_VERSION),
            StringStruct('OriginalFilename', 'Mini Whiteboard.exe'),
            StringStruct('InternalName', 'Mini Whiteboard'),
        ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])],
    )
    Path('assets/version_info.txt').write_text(str(info), encoding='utf-8')
    manifest = Path('assets/app.manifest')
    manifest.write_text(re.sub(r'(<assemblyIdentity version=")[^"]+',
                              lambda match: match.group(1)+'.'.join(map(str,version)),
                              manifest.read_text(encoding='utf-8')), encoding='utf-8')
    print(f'Windows executable version: {APP_VERSION}')


if __name__ == '__main__':
    main()
