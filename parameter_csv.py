import csv
import io
import copy

VALID_KINDS = {'length', 'angle', 'number'}

def _validate_name(name):
    if not name or not name.isidentifier() or name.startswith('_'):
        raise ValueError(f'Invalid name: {name}')

def _validate_kind(kind):
    if kind not in VALID_KINDS:
        raise ValueError(f'Invalid kind: {kind}')

def _validate_formula(formula):
    if not formula or not formula.strip():
        raise ValueError('Empty formula')

def validate_entries(entries):
    seen_names = set()
    result = []
    for entry in entries:
        name = entry['name']
        kind = entry['kind']
        formula = entry['formula']
        _validate_name(name)
        _validate_kind(kind)
        _validate_formula(formula)
        if name in seen_names:
            raise ValueError(f'Duplicate name: {name}')
        seen_names.add(name)
        result.append({'name': name, 'kind': kind, 'formula': formula})
    return result

def read_csv(path):
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        content = f.read()
    reader = csv.reader(io.StringIO(content), strict=True)
    rows = list(reader)
    if not rows:
        raise ValueError('Empty file')
    header = rows[0]
    if header != ['name', 'kind', 'formula']:
        raise ValueError(f'Bad header: {header}')
    entries = []
    seen_names = set()
    for i, row in enumerate(rows[1:], 2):
        if len(row) != 3:
            raise ValueError(f'Row {i} has {len(row)} columns, expected 3')
        name, kind, formula = row
        _validate_name(name)
        _validate_kind(kind)
        _validate_formula(formula)
        if name in seen_names:
            raise ValueError(f'Duplicate name: {name}')
        seen_names.add(name)
        entries.append({'name': name, 'kind': kind, 'formula': formula})
    return entries

def write_csv(path, entries):
    import os
    import tempfile
    from pathlib import Path
    validate_entries(entries)
    target = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='', dir=target.parent, prefix='.fluxcad-parameters-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream, strict=True)
            writer.writerow(['name', 'kind', 'formula'])
            for entry in entries:
                writer.writerow([entry['name'], entry['kind'], entry['formula']])
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

def merge_entries(current, incoming):
    # Validate incoming entries first
    validate_entries(incoming)
    
    # Create independent copies to avoid mutation of inputs
    current_copies = validate_entries([copy.deepcopy(e) for e in current])
    incoming_copies = validate_entries([copy.deepcopy(e) for e in incoming])
    
    result_map = {e['name']: e for e in current_copies}
    order = [e['name'] for e in current_copies]
    
    for inc in incoming_copies:
        name = inc['name']
        if name in result_map:
            existing = result_map[name]
            if existing['kind'] != inc['kind']:
                raise ValueError(f'Kind mismatch for {name}: {existing["kind"]} vs {inc["kind"]}')
            result_map[name] = {'name': name, 'kind': inc['kind'], 'formula': inc['formula']}
        else:
            result_map[name] = {'name': name, 'kind': inc['kind'], 'formula': inc['formula']}
            order.append(name)
            
    return [result_map[name] for name in order]