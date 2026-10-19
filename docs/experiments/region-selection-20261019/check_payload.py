"""Portable payload integrity and pure helper checks, not a CAD UI test."""
from pathlib import Path
import ast
import hashlib
import json
import math

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
for name, info in manifest['files'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == info['sha256'], name
patch = (root / 'selection-fixes.patch').read_text(encoding='utf-8')
assert [line[6:] for line in patch.splitlines() if line.startswith('+++ b/')] == [
    'sketch_regions.py', 'region_picker.py', 'extrude_panel.py']
assert len(list(root.rglob('*.FCStd'))) == 4
tree = ast.parse((root / 'region_picker.py').read_text(encoding='utf-8'))
helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'format_region_area')
ns = {'math': math}
exec(compile(ast.Module(body=[helper], type_ignores=[]), '<helper>', 'exec'), ns)
for area in (1e-9, 6.502193672596959e-5, .001464321575002237, .0098):
    assert float(ns['format_region_area'](area)) > 0
assert ns['format_region_area'](.12) == '0.12'
assert ns['format_region_area'](0) == '0.00'
print('PASS: payload hashes, three-file patch scope, four models, nonzero tiny-area formatting')
