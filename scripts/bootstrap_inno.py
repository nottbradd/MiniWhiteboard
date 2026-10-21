"""Extract a pinned official compiler in portable mode, without OS registration."""
import hashlib
from pathlib import Path
import subprocess
from urllib.request import urlopen

URL='https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe'
SHA256='9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732'


def main():
    project=Path(__file__).resolve().parents[1]
    root=project/'verification/tools/innosetup-6.7.3'
    root.mkdir(parents=True,exist_ok=True)
    archive=root/'innosetup-6.7.3.exe';destination=root/'compiler'
    if not archive.is_file():
        archive.write_bytes(urlopen(URL,timeout=60).read())
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:
        raise RuntimeError('Official compiler archive hash mismatch.')
    compiler=destination/'ISCC.exe'
    if not compiler.is_file():
        # Upstream's isportable.iss disables the uninstaller, registry entries
        # and shortcuts for /PORTABLE=1. This extracts only into our tool folder.
        subprocess.run([str(archive),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
                        '/CURRENTUSER','/PORTABLE=1','/NOICONS','/TASKS=',
                        '/DIR='+str(destination)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if not compiler.is_file():raise RuntimeError('Portable compiler extraction failed.')
    print(compiler)


if __name__=='__main__':main()
