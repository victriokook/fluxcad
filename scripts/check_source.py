"""Static checks for the public tree; no FreeCAD installation is needed."""
from pathlib import Path
import ast
import io
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '__pycache__', 'config', 'runtime', 'work', 'test-results', 'dist'}
PERSONAL_PATH = re.compile(r'(?i)[a-z]:[\\/](?:Users|Documents and Settings)[\\/]')
TOKEN = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')

def public_files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file()
                  and not set(p.relative_to(ROOT).parts) & EXCLUDED)

def check():
    files = public_files()
    failures = []
    def scan_text(name, data):
        text = data.decode('utf-8-sig')
        if PERSONAL_PATH.search(text):failures.append(name + ': local user path')
        if TOKEN.search(text):failures.append(name + ': credential-like content')
        return text
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        if path.suffix in ('.py', '.FCMacro', '.md', '.ps1', '.cmd', '.svg', '.json', '.yml') or not path.suffix:
            text = scan_text(name, path.read_bytes())
            if path.suffix in ('.py', '.FCMacro'):
                ast.parse(text, name, feature_version=(3, 11))
            if path.suffix == '.svg':ET.fromstring(text)
            if path.suffix == '.md':
                for link in re.findall(r'\]\(([^)]+)\)', text):
                    if '://' in link or link.startswith(('#', 'mailto:')):continue
                    target = (path.parent / link.split('#')[0]).resolve()
                    if not target.exists():failures.append(name + ': missing link ' + link)
        if path.suffix == '.FCStd':
            with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as model:
                if model.testzip():failures.append(name + ': invalid archive')
                for part in model.namelist():
                    if part.endswith(('.xml', '.svg')):scan_text(name + '/' + part, model.read(part))
                tree = ET.fromstring(model.read('Document.xml'))
                license_value = tree.find('./Properties/Property[@name="License"]/String')
                if license_value is None or license_value.get('value') != 'MIT':
                    failures.append(name + ': sample license metadata')
        if path.suffix in ('.log', '.out', '.err', '.FCBak', '.FCStd1', '.zip'):
            failures.append(name + ': development artifact')
    for required in ('LICENSE', 'VERSION', 'README.md', 'README-en.md', 'THIRD_PARTY_NOTICES.md',
                     'FluxCAD.FCMacro', 'Start-FluxCAD.cmd', 'Start-FluxCAD.ps1'):
        if not (ROOT / required).is_file():failures.append('Missing ' + required)
    assert not failures, '\n'.join(failures)
    print('PASS:', len(files), 'public files; Python 3.11 syntax, links, SVG, samples and path/token checks')
    return files

if __name__ == '__main__':check()
