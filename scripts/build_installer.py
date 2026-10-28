"""Compile a per-user installer from the verified one-directory runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from mini_whiteboard import APP_VERSION
from .build_support import verify_release_files, verify_frozen_modules


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--compiler',type=Path,required=True)
    parser.add_argument('--distribution',type=Path,default=Path('dist/windows-v133-review02/Mini Whiteboard'))
    parser.add_argument('--output',type=Path,default=Path('build/candidates/v1.3.3/review-02'))
    args=parser.parse_args()
    project=Path(__file__).resolve().parents[1]
    distribution=args.distribution.resolve();output=args.output.resolve()
    if not output.is_relative_to(project):raise ValueError('Installer output must stay inside the project.')
    notices=verify_release_files(distribution)
    modules=verify_frozen_modules(distribution/'Mini Whiteboard.exe')
    output.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(args.compiler.resolve()),'/Qp','/DAppVersion='+APP_VERSION,
                    '/DBundleDir='+str(distribution),'/DOutputDir='+str(output),
                    str(project/'installer/MiniWhiteboard.iss')],check=True)
    installer=output/f'MiniWhiteboard-{APP_VERSION}-Setup.exe'
    report={'version':APP_VERSION,'installer':str(installer),'bytes':installer.stat().st_size,
            'sha256':hashlib.sha256(installer.read_bytes()).hexdigest(),'distribution':str(distribution),
            'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'compiler':str(args.compiler.resolve()),**notices,**modules}
    Path('verification/v133-review02/installer-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
