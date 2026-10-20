"""Check local Markdown links and documentation paths in tracked project files."""
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


def check(project):
    project = Path(project).resolve()
    if (project / '.git').exists():
        names = subprocess.check_output(
            ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
            cwd=project).decode('utf-8').split('\0')
        files = sorted({project / name for name in names if name and (project / name).is_file()})
    else:  # GitHub source archives also support rebuilding without Git metadata.
        files = sorted(path for root in (project, project / 'docs', project / 'assets/licenses',
                       project / 'scripts', project / '.github') if root.is_dir()
                       for path in (root.glob('*') if root == project else root.rglob('*'))
                       if path.is_file())
    failures, count = [], 0
    for source in files:
        if source.suffix.lower() not in ('.md', '.py', '.sh', '.ps1', '.yml', '.yaml'):
            continue
        content = source.read_text(encoding='utf-8')
        targets = []
        if source.suffix.lower() == '.md':
            # Code examples can contain brackets that are not Markdown links.
            prose = re.sub(r'^```.*?^```[^\n]*', '', content, flags=re.M | re.S)
            targets.extend((value, source.parent) for value in
                           re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', prose))
        targets.extend((value, project) for value in
                       re.findall(r'\b(?:docs|assets/licenses)/[\w./-]+\.md\b', content))
        for value, base in targets:
            value = value.strip().strip('<>')
            parts = urlsplit(value)
            if parts.scheme or parts.netloc:
                continue
            target = (base / unquote(parts.path)).resolve() if parts.path else source
            count += 1
            if not target.is_relative_to(project) or not target.is_file():
                failures.append(f'{source.relative_to(project)}: missing target {value}')
                continue
            if parts.fragment and target.suffix.lower() == '.md':
                headings = re.findall(r'^#{1,6}\s+(.+?)\s*#*$', target.read_text(encoding='utf-8'), re.M)
                slugs = {re.sub(r'[^\w\s-]', '', title.lower()).replace(' ', '-') for title in headings}
                if unquote(parts.fragment) not in slugs:
                    failures.append(f'{source.relative_to(project)}: missing heading {value}')
    return count, failures


def main():
    count, failures = check(Path(__file__).resolve().parents[1])
    if failures:
        raise SystemExit('\n'.join(failures))
    print(f'PASSED: {count} local documentation links/references')


if __name__ == '__main__':
    main()
