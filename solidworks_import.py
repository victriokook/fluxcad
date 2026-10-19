"""Read SolidWorks saved display meshes and assembly occurrences locally.

This is a tessellation importer, not a Parasolid/BRep or feature-history reader.
Third-party strip/container decoding: solidworks_reader/LICENSE and SOURCE.json.
Selected parsing helpers originate from recorded local-Qwen API templates.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
import hashlib
import json
import math
import zlib

from solidworks_reader.blocks import read_blocks, find_block
from solidworks_reader.savedmesh import iter_tables, mesh_from_tables
from solidworks_reader.assembly import rigid_transform, compose, IDENTITY


def prepare(path, configuration=None):
    """Read-only preparation; a failed decode never creates a document."""
    path = Path(path).resolve()
    records, report = read_scene(path, configuration)
    from solidworks_cache import prepare_cached
    cached = prepare_cached(path, records, report)
    if cached is not None:
        return cached
    index = {}
    for item in path.parent.iterdir():
        if item.is_file() and item.suffix.lower() in ('.sldprt', '.sldasm'):
            index.setdefault(item.name.casefold(), []).append(item)
    cache = {}
    report.update(source=str(path), geometry_mode='SavedDisplayMesh',
                  imported=0, missing=[], bbox_warnings=[], hidden=0,
                  exact_brep=False, source_colors_preserved=False,
                  part_configuration_geometry_verified=False, source_hashes={},
                  limitations=['Display triangulation only; exact Parasolid/BRep and feature history are not decoded.',
                               'Source colors are not decoded; neutral gray is used.',
                               'Companion-part saved configurations can differ from the assembly cache; bounding-box discrepancies are reported.'])
    for record in records:
        if record['kind'] != 'part':
            continue
        filename = record['file']
        key = filename.casefold()
        if key not in cache:
            candidates = index.get(key, [])
            if path.suffix.lower() == '.sldprt':
                candidates = [path]
            try:
                if len(candidates) != 1:
                    raise ValueError('Referenced file missing or ambiguous in source folder')
                source = candidates[0]
                mesh = read_part_mesh(source)
                report['source_hashes'][source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
                cache[key] = (mesh, None)
            except (ValueError, OSError, zlib.error) as error:
                cache[key] = (None, str(error))
        mesh, error = cache[key]
        if error:
            record['error'] = error
            report['missing'].append(dict(instance=record['name'], file=filename, reason=error))
            continue
        record['mesh_key'] = key
        report['imported'] += 1
        report['hidden'] += int(record['hidden'])
        if record['bbox']:
            try:
                expected = [float(v) * 1000 for v in record['bbox'].split()]
                lo, hi = mesh.bbox()
                delta = max(abs(a-b) for a, b in zip(expected, (*lo, *hi)))
                if len(expected) != 6 or not math.isfinite(delta):
                    raise ValueError('Invalid saved bounding box')
                if delta > .1:
                    warning = dict(file=filename, configuration=record['configuration'], max_bbox_delta_mm=delta)
                    if warning not in report['bbox_warnings']:
                        report['bbox_warnings'].append(warning)
            except (ValueError, TypeError):
                report['warnings'].append(filename + ': saved bounding box could not be compared')
    report['expected'] = sum(r['kind'] == 'part' for r in records)
    report['complete_geometry'] = not report['missing'] and not report['warnings'] and not report['bbox_warnings']
    if not report['imported']:
        raise ValueError('No readable saved display meshes. No document was created.')
    report['source_hashes'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return records, cache, report


def _matrix(values):
    import FreeCAD as App
    matrix = App.Matrix()
    for row in range(3):
        for col in range(3):
            setattr(matrix, 'A%d%d' % (row+1, col+1), values[col*4+row])
        setattr(matrix, 'A%d4' % (row+1), values[12+row] * 1000)
    return matrix


def build(doc, prepared):
    """Insert one undoable mesh assembly, retaining missing-instance markers."""
    import FreeCAD as App
    import Mesh
    import model
    records, cache, report = prepared
    native = {}
    for key, (mesh, error) in cache.items():
        if mesh is not None:
            native[key] = Mesh.Mesh([(mesh.vertices[a], mesh.vertices[b], mesh.vertices[c])
                                     for a, b, c in mesh.triangles])
    with model.transaction(doc, 'Import SolidWorks Saved Mesh'):
        root = doc.addObject('App::Part', 'SolidWorksImport')
        status = 'Saved mesh' if report['complete_geometry'] else 'Partial / warnings'
        root.Label = Path(report['source']).stem + ' [' + status + ']'
        for kind, name, value in (
            ('App::PropertyString', 'GeometryMode', 'SavedDisplayMesh — not BRep'),
            ('App::PropertyString', 'SourceFile', report['source']),
            ('App::PropertyString', 'ImportStatus', status),
            ('App::PropertyInteger', 'ExpectedInstances', report['expected']),
            ('App::PropertyInteger', 'ImportedInstances', report['imported']),
            ('App::PropertyString', 'ImportReport', json.dumps(report, ensure_ascii=False)),
        ):
            root.addProperty(kind, name, 'SolidWorks Import')
            setattr(root, name, value)
            root.setEditorMode(name, 1)
        groups = {'': root}
        for record in records:
            parent = groups[record['parent']]
            if record['kind'] == 'assembly':
                obj = doc.addObject('App::Part', 'Subassembly')
                obj.Label = record['name']
                parent.addObject(obj)
                groups[record['key']] = obj
                continue
            if record.get('reference_only'):
                obj = doc.addObject('App::FeaturePython', 'SWReference')
                obj.Label = '[Reference only] ' + record['name']
                obj.addProperty('App::PropertyString', 'GeometryMode', 'SolidWorks Import')
                obj.GeometryMode = 'Explicit zero-body saved part; no mesh or source sketch reconstruction'
                obj.setEditorMode('GeometryMode', 1)
                obj.addProperty('App::PropertyPlacement', 'Placement', 'SolidWorks Import')
                obj.Placement = App.Placement(_matrix(record['matrix']))
                if obj.ViewObject:
                    obj.ViewObject.Visibility = not record['hidden']
            elif 'error' in record:
                obj = doc.addObject('App::FeaturePython', 'MissingComponent')
                obj.Label = '[Missing mesh] ' + record['name']
                obj.addProperty('App::PropertyString', 'ImportError', 'SolidWorks Import')
                obj.ImportError = record['error']
            else:
                obj = doc.addObject('Mesh::Feature', 'SWMesh')
                obj.Label = record['name']
                mesh = native[record['mesh_key']].copy()
                transform = _matrix(record['matrix'])
                mesh.transformGeometry(transform)
                if transform.determinant() < 0:
                    mesh.flipNormals()
                obj.Mesh = mesh
                if obj.ViewObject:
                    obj.ViewObject.ShapeColor = (.78, .8, .83)
                    obj.ViewObject.Visibility = not record['hidden']
            parent.addObject(obj)
            for name, value in (('SourceFile', record['file']), ('SourceConfiguration', record['configuration']),
                                ('SavedWorldTransform', json.dumps(record['matrix']))):
                obj.addProperty('App::PropertyString', name, 'SolidWorks Import')
                setattr(obj, name, value)
                obj.setEditorMode(name, 1)
        return root


def open(filename):
    import FreeCAD as App
    prepared = prepare(filename)
    doc = App.newDocument('SolidWorks')
    try:
        root = build(doc, prepared)
    except Exception:
        App.closeDocument(doc.Name)
        raise
    if App.GuiUp:
        import FreeCADGui as Gui
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
        App.Console.PrintWarning('SolidWorks: saved display mesh, not editable BRep. ' +
                                 str(root.ImportedInstances) + '/' + str(root.ExpectedInstances) +
                                 ' instances. Inspect SolidWorksImport.ImportReport for missing/configuration warnings.\n')
    return doc


def insert(filename, docname):
    import FreeCAD as App
    prepared = prepare(filename)
    doc = App.getDocument(docname)
    if doc is None:
        raise ValueError('Target document is no longer open')
    build(doc, prepared)
    return doc


def register():
    import FreeCAD as App
    if not getattr(App, '_flux_solidworks_registered', False):
        App.addImportType('SolidWorks saved display mesh (*.sldprt *.sldasm)', 'solidworks_import')
        App._flux_solidworks_registered = True


def show(ws):
    import FreeCAD as App
    import FreeCADGui as Gui
    from PySide import QtWidgets as W
    from i18n import tr
    if ws.current_sketch() or Gui.Control.activeDialog():
        raise ValueError(tr('先に編集中の操作を終了してください。', 'Finish the active edit first.'))
    path, _ = W.QFileDialog.getOpenFileName(ws.main, tr('SolidWorksを読み込み（表示メッシュ）', 'Import SolidWorks (Saved Display Mesh)'), '',
                                           'SolidWorks (*.sldprt *.sldasm *.SLDPRT *.SLDASM)')
    if not path:
        return
    doc = open(path)
    ws.refresh()
    root = doc.getObject('SolidWorksImport')
    report = json.loads(root.ImportReport)
    text = tr('保存表示データから %d / %d 部品を読み込みました。\n加工可能な厳密ソリッドや元の履歴ではありません。表示色は仮の単色です。\n未読込: %d、境界範囲の警告: %d。詳細は読込ルートのImportReportを確認してください。',
              'Imported %d / %d saved component records.\nThese are saved display meshes or explicit zero-body references, not exact solids or source feature history. Neutral display colors are used.\nMissing records: %d; bounding-envelope warnings: %d. See the import root ImportReport for details.') % (
                  report['imported'], report['expected'], len(report['missing']), len(report['bbox_warnings']))
    text += tr('\n参照のみ（保存された面なし）: %d。スケッチ形状の再構築は行いません。',
               '\nReference only (no saved faces): %d. Source sketch geometry is not reconstructed.') % len(report.get('reference_only', []))
    W.QMessageBox.information(ws.main, tr('SolidWorks読込結果', 'SolidWorks Import Result'), text)
    return doc


def block_data(block):
    if block.expanded > 536870912:
        raise ValueError('Saved SolidWorks block exceeds the 512 MiB limit')
    raw = block.raw()
    for mode in (-15, 15):
        try:
            decoder = zlib.decompressobj(mode)
            data = decoder.decompress(raw, block.expanded + 1)
        except zlib.error:
            continue
        if decoder.eof and len(data) == block.expanded and zlib.crc32(data) & 0xffffffff == block.crc:
            return data
    if len(raw) == block.expanded and zlib.crc32(raw) & 0xffffffff == block.crc:
        return raw
    raise ValueError('SolidWorks block length or CRC check failed: ' + block.name)

def source_blocks(path):
    path = Path(path)
    if path.stat().st_size > 1073741824:
        raise ValueError('SolidWorks source exceeds the 1 GiB file limit')
    blocks = read_blocks(path.read_bytes())
    if not blocks:
        raise ValueError('Unsupported SolidWorks container: no modern named blocks')
    return blocks


def read_scene(path, configuration=None):
    path = Path(path).resolve()
    if path.suffix.lower() == '.sldprt':
        return [dict(kind='part', name=path.stem, file=path.name, parent='', key='part', matrix=list(IDENTITY), hidden=False, configuration='', bbox='')], dict(configuration='', suppressed=0, warnings=[])
    if path.suffix.lower() != '.sldasm':
        raise ValueError('Choose a .SLDPRT or .SLDASM file')
    block = find_block(source_blocks(path), 'swXmlContents/COMPINSTANCETREE')
    if block is None:
        raise ValueError('This assembly has no saved component instance tree')
    data = block_data(block)
    if len(data) > 33554432 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Unsupported or oversized SolidWorks XML')
    root = ET.fromstring(data)
    local = lambda node: node.tag.rsplit('}', 1)[-1]
    def section(name):
        matches = [e for e in root if local(e) == name]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous assembly section: ' + name)
        return matches[0]
    files = {e.get('id'): e for e in section('swHeader') if local(e) == 'swFile'}
    models = {e.get('id'): e for e in section('swModelList') if local(e) == 'swModel'}
    configs = [e for e in section('swConfigurationList') if local(e) == 'swConfiguration']
    if not configs:
        raise ValueError('No saved assembly configuration')
    if configuration is not None:
        chosen = next((e for e in configs if e.get('swName') == configuration), None)
        if chosen is None:
            raise ValueError('Requested assembly configuration is unavailable')
    else:
        chosen = next((e for e in configs if e.get('swMostRecentConfiguration') == 'YES'), configs[0])
    model = models.get(chosen.get('swModelRef'))
    if model is None:
        raise ValueError('Saved root assembly model is missing')
    report = dict(configuration=chosen.get('swName', ''), configurations=[e.get('swName', '') for e in configs], suppressed=0, warnings=[])
    records = []
    def walk(node, matrix, parent, hidden, stack):
        if len(stack) > 32 or node.get('id') in stack:
            raise ValueError('Assembly cycle or nesting limit exceeded')
        stack = stack + (node.get('id'),)
        for ref in node:
            if local(ref) != 'swReference':
                continue
            if ref.get('swSuppressed') == 'YES':
                report['suppressed'] += 1
                continue
            key = str(len(records))
            name = (ref.get('swName') or 'Component') + '-' + (ref.get('swReferenceNumber') or key)
            child = models.get(ref.get('swModelRef'))
            if child is None:
                report['warnings'].append(name + ': missing model record')
                continue
            placement, mirrored = rigid_transform(ref.get('swTransform'))
            world = compose(placement, matrix)
            file = files.get(child.get('swFileRef'))
            if file is None:
                report['warnings'].append(name + ': missing file record')
                continue
            filename = (file.get('swPath') or '').replace(chr(92), '/').rsplit('/', 1)[-1]
            kind = 'assembly' if file.get('swDocType') == 'ASSEMBLY' else 'part'
            record = dict(kind=kind, name=name, file=filename, parent=parent, key=key, matrix=world, hidden=hidden or ref.get('swHidden') == 'YES', configuration=child.get('swConfigurationName', ''), bbox=child.get('swBoundingBox', ''))
            records.append(record)
            if len(records) > 20000:
                raise ValueError('Assembly exceeds 20000 saved occurrences')
            if kind == 'assembly':
                walk(child, world, key, record['hidden'], stack)
    walk(model, list(IDENTITY), '', False, ())
    return records, report


def read_part_mesh(path):
    blocks = source_blocks(path)
    for name in ('Contents/DisplayLists', 'FaceTessellations'):
        block = find_block(blocks, name)
        if block is None:
            continue
        data = block_data(block)
        tables = list(iter_tables(data))
        count = sum(t.triangles for t in tables)
        if count > 6000000:
            raise ValueError('Saved mesh exceeds 6 million triangles')
        if not count:
            continue
        mesh = mesh_from_tables(data, tables).weld(0.000001)
        if any(not math.isfinite(v) or abs(v) > 10000000 for point in mesh.vertices for v in point):
            raise ValueError('Saved mesh contains invalid coordinates')
        return mesh
    raise ValueError('No supported saved display mesh in this file')
