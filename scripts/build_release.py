"""Build deterministic application/source ZIPs with manifests and SHA256 sums."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile
from check_source import ROOT, check

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT / 'dist')
parser.add_argument('--cadmpeg', type=Path, help='Pinned decoder to include in the Windows asset only')
args = parser.parse_args()
files = check()
version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
args.output.mkdir(parents=True, exist_ok=True)
release_files = []

for kind in ('windows', 'source'):
    data = {}
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        parts = Path(name).parts
        if parts[0].startswith('.') and parts[0] != '.github':
            if kind == 'windows':continue
        if kind == 'windows' and parts[0] in ('.github', 'scripts', 'tests'):continue
        data[name] = path.read_bytes()
    if kind == 'windows' and args.cadmpeg:
        decoder = args.cadmpeg.read_bytes()
        pin = json.loads((ROOT/'vendor/cadmpeg/SOURCE.json').read_text())['binary_sha256']
        assert hashlib.sha256(decoder).hexdigest() == pin, 'Decoder hash mismatch'
        data['vendor/cadmpeg/cadmpeg.exe'] = decoder
    manifest = {name: hashlib.sha256(value).hexdigest() for name, value in sorted(data.items())}
    data['MANIFEST.json'] = json.dumps(dict(version=version, files=manifest), indent=2).encode('utf-8')
    archive = args.output / ('FluxCAD-v' + version + '-' + kind + '.zip')
    prefix = 'FluxCAD-' + version + '/'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for name, value in sorted(data.items()):
            info = zipfile.ZipInfo(prefix + name, (2026, 10, 4, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, value)
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        for name, digest in manifest.items():
            assert hashlib.sha256(output.read(prefix + name)).hexdigest() == digest
    release_files.append(archive)
    print(archive.name, len(data), 'files,', archive.stat().st_size, 'bytes')
sums = '\n'.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name for p in release_files) + '\n'
(args.output / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8')
