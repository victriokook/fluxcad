"""Occurrence-owned legacy assembly display cache; no BRep reconstruction."""
from pathlib import Path
import struct,bisect,math,hashlib
from solidworks_reader.blocks import find_block
from solidworks_reader.savedmesh import iter_tables,mesh_from_tables

def cstrings(data):
    """Bounded MFC UTF-16 strings, retaining byte ranges for framed ownership."""
    output = []
    pos = 0
    while True:
        at = data.find(b'\xff\xfe\xff', pos)
        if at < 0:
            return output
        pos = at + 3
        try:
            count = data[pos]
            pos += 1
            if count == 255:
                count = struct.unpack_from('<H', data, pos)[0]
                pos += 2
                if count == 65535:
                    count = struct.unpack_from('<I', data, pos)[0]
                    pos += 4
            if not 0 < count <= 4096 or pos + count * 2 > len(data):
                continue
            value = data[pos:pos + count * 2].decode('utf-16-le')
            if all(c.isprintable() for c in value):
                output.append((at, pos + count * 2, value))
        except (IndexError, struct.error, UnicodeError):
            continue

def occurrence_paths(path, records):
    by_key = {record['key']: record for record in records}
    result = {}
    for record in records:
        lineage = [record]
        parent = record['parent']
        while parent:
            if len(lineage) > 32 or parent not in by_key:
                raise ValueError('Invalid assembly lineage')
            lineage.append(by_key[parent])
            parent = by_key[parent]['parent']
        parent_name = Path(path).stem
        parts = []
        for node in reversed(lineage):
            parts.append(node['name'] + '@' + parent_name)
            parent_name = node['file'].rsplit('.', 1)[0]
        name = '/'.join(parts)
        if name in result:
            raise ValueError('Ambiguous saved occurrence path')
        result[name] = record
    return result

def read_cache(path, records):
    """Decode only explicitly framed occurrence-owned assembly display tables."""
    from solidworks_import import source_blocks, block_data
    block = find_block(source_blocks(path), 'Contents/DisplayLists')
    if block is None:
        return None
    data = block_data(block)
    if b'uoTempAssemblySHDData_c' not in data:
        return None
    strings = cstrings(data)
    positions = [s[0] for s in strings]
    marker = '@' + Path(path).stem
    frames = [s for s in strings if marker in s[2] and
              (struct.unpack_from('<H', data, s[0]-2)[0] & 32768 or
               data[max(0, s[0]-23):s[0]] == b'uoTempAssemblySHDData_c')]
    if not frames or len(frames) > 40000:
        return None
    expected = occurrence_paths(path, records)
    tables = list(iter_tables(data))
    if sum(t.triangles for t in tables) > 6000000:
        raise ValueError('Assembly saved mesh exceeds six million triangles')
    starts = [t.start for t in tables]
    meshes = {}
    pending_empty = []
    part_tokens = set()
    audit = []
    seen = set()
    for i, (at, end, name) in enumerate(frames):
        stop = frames[i+1][0] if i+1 < len(frames) else len(data)
        record = expected.get(name)
        if record is None or record['kind'] != 'part':
            continue
        if name in seen:
            raise ValueError('Duplicate cached occurrence')
        seen.add(name)
        owned = tables[bisect.bisect_left(starts, end):bisect.bisect_left(starts, stop)]
        metadata_end = min(owned[0].start if owned else stop, end + 16384)
        meta = strings[bisect.bisect_left(positions, end):bisect.bisect_left(positions, metadata_end)]
        files = [j for j, item in enumerate(meta) if item[2].replace(chr(92), '/').rsplit('/', 1)[-1].casefold() == record['file'].casefold() and chr(92) in item[2]]
        if len(files) != 1:
            raise ValueError('Cached source identity is missing or ambiguous: ' + name)
        configs = [s for s in meta[files[0]+1:] if s[2] == record['configuration']]
        if not configs:
            raise ValueError('Cached source configuration mismatch: ' + name)
        flag = data[end]
        if flag == 1:
            values = struct.unpack_from('<13d', data, end+1)
            target = [record['matrix'][j] for j in (0,1,2,4,5,6,8,9,10,12,13,14,15)]
            if any(not math.isfinite(a) or abs(a-b) > 1e-8 for a,b in zip(values,target)):
                raise ValueError('Cached/XML placement mismatch: ' + name)
        elif flag != 0:
            raise ValueError('Unsupported cached occurrence frame')
        key = record['file'].casefold() + '\n' + record['configuration']
        token_at = configs[0][1] + 62
        token = struct.unpack_from('<H', data, token_at)[0] if token_at+4 <= stop else 0
        if owned:
            if token & 32768 and token != 65535:
                part_tokens.add(token)
            if key in meshes:
                raise ValueError('Multiple saved geometries for one source/configuration')
            mesh = mesh_from_tables(data, owned).weld(.000001)
            if any(not math.isfinite(v) or abs(v)>10000000 for point in mesh.vertices for v in point):
                raise ValueError('Invalid saved mesh coordinate')
            meshes[key] = (mesh, None)
            audit.append(dict(file=record['file'], configuration=record['configuration'], occurrence=name, tables=len(owned), triangles=len(mesh.triangles), first_table=owned[0].start, last_table_end=owned[-1].end))
        elif token & 32768 and token != 65535 and data[token_at+2:token_at+4] == b'\0\0':
            pending_empty.append((key, token, name))
    empty = {key: name for key, token, name in pending_empty if token in part_tokens and key not in meshes}
    return meshes, empty, audit, seen

def prepare_cached(path, records, initial_report):
    """Prefer assembly-owned saved geometry; never resize it to loose XML boxes."""
    if Path(path).suffix.lower() != '.sldasm':
        return None
    result = read_cache(path, records)
    if result is None:
        return None
    meshes, empty, audit, seen = result
    parts = [record for record in records if record['kind'] == 'part']
    paths = occurrence_paths(path, records)
    if any(name not in seen for name, record in paths.items() if record['kind'] == 'part'):
        return None
    if any(record['file'].casefold()+'\n'+record['configuration'] not in meshes and record['file'].casefold()+'\n'+record['configuration'] not in empty for record in parts):
        return None
    report = dict(initial_report)
    report.update(source=str(path), geometry_mode='AssemblySavedDisplayMesh', imported=0, expected=len(parts), missing=[], bbox_warnings=[], hidden=0, reference_only=[], exact_brep=False, source_colors_preserved=False, part_configuration_geometry_verified=True, source_hashes={Path(path).name: hashlib.sha256(Path(path).read_bytes()).hexdigest()}, cache_geometry=audit, bounding_box_diagnostics=[], limitations=['Saved triangulation only; exact BRep, feature history, mates and original colors are not decoded.', 'Reference-only entries preserve zero-face saved objects; source sketch geometry is not reconstructed.'])
    for record in parts:
        key = record['file'].casefold()+'\n'+record['configuration']
        record['mesh_key'] = key
        report['imported'] += 1
        report['hidden'] += int(record['hidden'])
        if key in empty:
            record['reference_only'] = True
            report['reference_only'].append(dict(file=record['file'], instance=record['name'], evidence='Explicit zero-body saved part tessellation object', occurrence=empty[key]))
            continue
        if record['bbox']:
            bounds = [float(v)*1000 for v in record['bbox'].split()]
            if len(bounds) != 6 or not all(math.isfinite(v) for v in bounds):
                raise ValueError('Invalid saved source bounding box')
            lo, hi = meshes[key][0].bbox()
            tight = (*lo,*hi)
            outside = max([bounds[j]-lo[j] for j in range(3)]+[hi[j]-bounds[j+3] for j in range(3)])
            delta = max(abs(a-b) for a,b in zip(tight,bounds))
            item = dict(file=record['file'], configuration=record['configuration'], max_bbox_delta_mm=delta, max_outside_mm=max(0,outside))
            if outside > .1:
                if item not in report['bbox_warnings']:
                    report['bbox_warnings'].append(item)
            elif delta > .1 and item not in report['bounding_box_diagnostics']:
                report['bounding_box_diagnostics'].append(item)
    report['mesh_instances'] = len(parts)-len(report['reference_only'])
    report['complete_geometry'] = not report['missing'] and not report['warnings'] and not report['bbox_warnings']
    report['complete_exact_model'] = False
    return records, meshes, report
