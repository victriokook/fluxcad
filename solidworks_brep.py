"""Local native SolidWorks BRep import. Never promotes display triangles to solids."""
from pathlib import Path
from xml.etree import ElementTree as ET
import collections
import copy
import hashlib
import json
import math
import subprocess

ROOT = Path(__file__).resolve().parent
DECODER_SHA256 = 'cb0b4d119a4b6ef1b68942de86ad7136cd6f2cf23c2025daf9756105ceb22fd1'
ENGINE_ID = 'native-brep-analytic-4'
CACHE = ROOT / 'cache' / 'solidworks-brep'
_decoder_checked = False


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cache_key(source_hash, configuration):
    return hashlib.sha256((source_hash+'\0'+configuration+'\0'+DECODER_SHA256+'\0'+ENGINE_ID).encode()).hexdigest()


def feature_models(path):
    import solidworks_import as sw
    block = next((b for b in sw.source_blocks(path) if b.name == 'swXmlContents/Features'), None)
    if block is None:
        raise ValueError('Native part configuration metadata is unavailable')
    data = sw.block_data(block)
    if len(data) > 33554432 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Unsupported native configuration XML')
    return [(e.get('swConfigurationName',''), e.get('swLastModifiedStamp',''))
            for e in ET.fromstring(data).iter() if e.tag.rsplit('}',1)[-1] == 'swModel']


def run_command(args, timeout, folder, name):
    result = subprocess.run([str(x) for x in args], capture_output=True, timeout=timeout,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (folder/(name+'.stdout.txt')).write_bytes(result.stdout)
    (folder/(name+'.stderr.txt')).write_bytes(result.stderr)
    if result.returncode:
        raise ValueError('%s refused (exit %s); see %s' % (name,result.returncode,folder))


def convert_part(path, configuration, cache_dir=None):
    global _decoder_checked
    path = Path(path).resolve()
    if path.stat().st_size > 1073741824:
        raise ValueError('Native part exceeds the 1 GiB limit')
    source_hash = digest(path)
    folder = Path(cache_dir or CACHE) / cache_key(source_hash, configuration)
    folder.mkdir(parents=True, exist_ok=True)
    entry_file = folder/'entry.json'
    if entry_file.exists():
        entry = json.loads(entry_file.read_text(encoding='utf-8'))
        if (entry['source_sha256'],entry['configuration'],entry['decoder_sha256']) != (source_hash,configuration,DECODER_SHA256):
            raise ValueError('Native BRep cache identity mismatch')
        if entry.get('engine')!=ENGINE_ID:raise ValueError('Native BRep cache engine changed')
        if entry['status'] != 'PASS':
            raise ValueError(entry['error'])
        if digest(folder/'shape.brep') != entry['brep_sha256']:
            raise ValueError('Native BRep cache content changed')
        if 'native_arc_choices' not in entry:raise ValueError('Native analytic arc verification metadata missing')
        return folder, entry
    entry = dict(source_sha256=source_hash, configuration=configuration,
                 decoder_sha256=DECODER_SHA256, engine=ENGINE_ID, status='REJECTED')
    try:
        decoder = ROOT/'vendor/cadmpeg/cadmpeg.exe'
        if not _decoder_checked:
            if digest(decoder) != DECODER_SHA256:
                raise ValueError('Native converter binary hash mismatch')
            _decoder_checked = True
        raw, decode = folder/'source.cadir.json', folder/'decode.json'
        try:
            run_command([decoder,'dump',path,'-o',raw,'--report',decode,'--limits','service'],45,folder,'decode')
            entry['decode_limits']='service'
        except ValueError:
            refusal=(folder/'decode.stderr.txt').read_text(encoding='utf-8',errors='replace')
            if 'resource limit on' not in refusal or 'BudgetExceeded' not in refusal:raise
            raw,decode=folder/'source-desktop.cadir.json',folder/'decode-desktop.json'
            try:
                run_command([decoder,'dump',path,'-o',raw,'--report',decode,'--limits','desktop'],45,folder,'decode-desktop')
                entry['decode_limits']='desktop-after-measured-service-budget-refusal'
            except ValueError:
                refusal=(folder/'decode-desktop.stderr.txt').read_text(encoding='utf-8',errors='replace')
                if 'resource limit on' not in refusal or 'BudgetExceeded' not in refusal:raise
                derived,entry['geometry_input_provenance']=geometry_only_copy(path,folder)
                raw,decode=folder/'source-geometry-only.cadir.json',folder/'decode-geometry-only.json'
                run_command([decoder,'dump',derived,'-o',raw,'--report',decode,'--limits','desktop'],45,folder,'decode-geometry-only')
                entry['decode_limits']='desktop-after-byte-preserving-feature-stream-isolation'
        if raw.stat().st_size > 536870912:
            raise ValueError('Decoded native BRep exceeds the 512 MiB limit')
        losses = geometry_losses(json.loads(decode.read_text(encoding='utf-8')))
        if losses:
            raise ValueError('Native geometry/topology loss: '+json.dumps(losses,ensure_ascii=False))
        document = json.loads(raw.read_text(encoding='utf-8'))
        if document['units']['length'] != 'millimeter':
            raise ValueError('Native BRep units are not millimeters')
        snapshot, evidence = geometry_snapshot(document,configuration)
        geometry, step = folder/'geometry.cadir.json', folder/'geometry.step'
        geometry.write_text(json.dumps(snapshot),encoding='utf-8')
        strict_step=True
        try:run_command([decoder,'convert',geometry,'-o',step,'--report',folder/'export.json',
                         '--reject-lossy','--limits','service'],45,folder,'export')
        except ValueError as error:strict_step=False;entry['step_export_refusal']=str(error)
        import FreeCAD as App
        python = Path(App.getHomePath())/'bin/python.exe'
        run_command([python,ROOT/'tools/solidworks_brep_native_worker.py',step,evidence['bodies'],folder,
                     'strict' if strict_step else 'refused'],60,folder,'native')
        native = json.loads((folder/'native.json').read_text(encoding='utf-8'))
        if native['status'] != 'PASS':
            raise ValueError(native['error'])
        if digest(path) != source_hash:
            raise ValueError('Native part changed during conversion')
        stamps = [stamp for name,stamp in feature_models(path) if name==configuration]
        if len(stamps) != 1 or not stamps[0]:
            raise ValueError('Native configuration revision is missing or ambiguous')
        entry.update(status='PASS', geometry=evidence, metrics=native['metrics'], stamp=stamps[0],
                     brep_sha256=digest(folder/'shape.brep'),native_method=native['method'],
                     native_arc_choices=native['arc_choices'],native_recovery=native.get('recovery'))
    except (ValueError,OSError,KeyError,subprocess.TimeoutExpired) as error:
        entry['error'] = str(error)
    temporary = folder/'entry.tmp.json'
    temporary.write_text(json.dumps(entry,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(entry_file)
    if entry['status'] != 'PASS':
        raise ValueError(entry['error'])
    return folder, entry


def assembly_revisions(path):
    import solidworks_import as sw
    block = next(b for b in sw.source_blocks(path) if b.name=='swXmlContents/COMPINSTANCETREE')
    root = ET.fromstring(sw.block_data(block))
    local = lambda e:e.tag.rsplit('}',1)[-1]
    files = {e.get('id'):e for e in root.iter() if local(e)=='swFile'}
    revisions = collections.defaultdict(set)
    for e in root.iter():
        if local(e)=='swModel' and e.get('swFileRef') in files:
            filename = files[e.get('swFileRef')].get('swPath','').replace(chr(92),'/').rsplit('/',1)[-1]
            revisions[(filename.casefold(),e.get('swConfigurationName',''))].add(e.get('swLastModifiedStamp',''))
    return revisions


def convert_linked_step(path, configuration, linked, cache_dir=None):
    import FreeCAD as App
    step,provenance=linked
    source_hash=digest(path);step_hash=digest(step)
    key=cache_key(source_hash+'\0linked-step\0'+step_hash,configuration)
    folder=Path(cache_dir or CACHE)/key;folder.mkdir(parents=True,exist_ok=True)
    entry_file=folder/'entry.json'
    if entry_file.exists():
        entry=json.loads(entry_file.read_text(encoding='utf-8'))
        if (entry.get('source_sha256'),entry.get('linked_step_sha256'),entry.get('configuration'),entry.get('engine'))!=(source_hash,step_hash,configuration,ENGINE_ID):raise ValueError('Linked STEP cache identity changed')
        if entry['status']!='PASS':raise ValueError(entry['error'])
        if digest(folder/'shape.brep')!=entry['brep_sha256']:raise ValueError('Linked native BRep cache changed')
        return folder,entry
    entry=dict(source_sha256=source_hash,linked_step_sha256=step_hash,configuration=configuration,engine=ENGINE_ID,decoder_sha256=DECODER_SHA256,status='REJECTED',linked_step_provenance=provenance)
    try:
        run_command([Path(App.getHomePath())/'bin/python.exe',ROOT/'tools/solidworks_linked_step_worker.py',step,folder],60,folder,'native-linked-step')
        native=json.loads((folder/'native.json').read_text(encoding='utf-8'))
        if native['status']!='PASS':raise ValueError(native['error'])
        stamps=[stamp for name,stamp in feature_models(path) if name==configuration]
        if len(stamps)!=1 or not stamps[0]:raise ValueError('Native linked configuration revision is ambiguous')
        if digest(path)!=source_hash or digest(step)!=step_hash:raise ValueError('Linked native sources changed during conversion')
        entry.update(status='PASS',geometry=dict(configuration=configuration,bodies=native['metrics']['bodies']),stamp=stamps[0],metrics=native['metrics'],brep_sha256=digest(folder/'shape.brep'),native_method='ManifestLinkedNativeSTEP',native_arc_choices=[],native_recovery=None)
    except (ValueError,OSError,KeyError,subprocess.TimeoutExpired) as error:entry['error']=str(error)
    entry_file.write_text(json.dumps(entry,indent=2),encoding='utf-8')
    if entry['status']!='PASS':raise ValueError(entry['error'])
    return folder,entry


class IncompleteImportError(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__('Exact native solids available: %d/%d. Inspect report.missing; no document was created.' % (report['imported'],report['expected']))


def assembly_saved_geometry(path, records, source_hash, cache_dir=None):
    import solidworks_cache
    folder = Path(cache_dir or CACHE)/'assembly-sanity'
    folder.mkdir(parents=True,exist_ok=True)
    target = folder/(source_hash+'.json')
    if target.exists():
        data=json.loads(target.read_text(encoding='utf-8'))
        if data['source_sha256']!=source_hash:raise ValueError('Assembly sanity cache identity changed')
        return data['parts']
    cached=solidworks_cache.read_cache(path,records)
    if cached is None:raise ValueError('No independent saved assembly geometry for native BRep comparison')
    meshes,empty,audit,seen=cached
    parts={}
    for key,(mesh,error) in meshes.items():
        parts[key]=saved_mesh_metrics(mesh)
    target.write_text(json.dumps(dict(source_sha256=source_hash,parts=parts)),encoding='utf-8')
    return parts


def assembly_curve_samples(path,records,source_hash,keys,cache_dir=None):
    import solidworks_cache
    from solidworks_prism import saved_curve_samples
    folder=Path(cache_dir or CACHE)/'assembly-arc-samples'/source_hash
    folder.mkdir(parents=True,exist_ok=True)
    result={};pending=[]
    for key in keys:
        target=folder/(hashlib.sha256(key.encode()).hexdigest()+'.json')
        if target.exists():result[key]=json.loads(target.read_text(encoding='utf-8'))
        else:pending.append((key,target))
    if pending:
        cached=solidworks_cache.read_cache(path,records)
        if cached is None:raise ValueError('Configuration-matched saved arc samples unavailable')
        meshes=cached[0]
        for key,target in pending:
            samples=saved_curve_samples(meshes[key][0]);result[key]=samples
            target.write_text(json.dumps(samples),encoding='utf-8')
    return result


def prepare(path, configuration=None, allow_partial=False, cache_dir=None, progress=None):
    import solidworks_import as sw
    path = Path(path).resolve()
    source_hash = digest(path)
    if path.suffix.lower()=='.sldprt' and configuration is None:
        choices = sorted(set(name for name,stamp in feature_models(path) if name and stamp))
        if len(choices)!=1:
            raise ValueError('Specify the exact native part configuration: '+', '.join(choices))
        configuration = choices[0]
    records, scene = sw.read_scene(path, configuration if path.suffix.lower()=='.sldasm' else None)
    if path.suffix.lower()=='.sldprt':
        records[0]['configuration']=configuration
    revisions = assembly_revisions(path) if path.suffix.lower()=='.sldasm' else None
    saved = assembly_saved_geometry(path,records,source_hash,cache_dir) if revisions is not None else None
    single_saved=None;single_mesh=None
    if revisions is None and len(set(name for name,stamp in feature_models(path) if name and stamp))==1:
        try:single_mesh=sw.read_part_mesh(path);single_saved=saved_mesh_metrics(single_mesh)
        except (ValueError,OSError):pass
    sources = collections.defaultdict(list)
    for p in path.parent.iterdir():
        if p.is_file() and p.suffix.lower() in ('.sldprt','.sldasm'):sources[p.name.casefold()].append(p)
    parts = [rec for rec in records if rec['kind']=='part']
    groups={rec['key']:rec for rec in records if rec['kind']=='assembly'}
    embedded_memo={};embedded_sources={}
    cache, missing, hashes, comparisons = {}, [], {str(path):source_hash}, {}
    for index,rec in enumerate(parts):
        if progress:progress(index,len(parts),rec['file'])
        key = (rec['file'].casefold(),rec['configuration'])
        if key not in cache:
            try:
                candidates = [path] if path.suffix.lower()=='.sldprt' else sources[key[0]]
                if not candidates and revisions is not None:
                    containers=[];parent=rec['parent'];visited=set()
                    while parent:
                        if parent in visited:raise ValueError('Cyclic native assembly ancestry')
                        visited.add(parent);group=groups[parent]
                        owners=sources[group['file'].casefold()]
                        if len(owners)==1:containers.append(owners[0])
                        parent=group['parent']
                    containers.append(path)
                    for container in dict.fromkeys(containers):
                        memo=(str(container),key)
                        if memo not in embedded_memo:embedded_memo[memo]=embedded_part(container,rec['file'],key[1],cache_dir)
                        extracted=embedded_memo[memo]
                        if extracted is not None:
                            original,evidence=extracted;candidates=[original]
                            if revisions[key]!={evidence['stamp']}:raise ValueError('Embedded revision differs from saved assembly revision')
                            hashes[evidence['container']]=evidence['container_sha256']
                            embedded_sources[key[0]+'\n'+key[1]]=evidence
                            break
                if len(candidates)!=1:raise ValueError('Original or embedded native part file is missing or ambiguous')
                original = candidates[0]
                linked=linked_step_source(original,key[1])
                if linked is not None:
                    folder,entry=convert_linked_step(original,key[1],linked,cache_dir)
                    hashes[str(linked[0])]=entry['linked_step_sha256']
                else:folder,entry = convert_part(original,key[1],cache_dir)
                hashes[str(original)] = entry['source_sha256']
                if revisions is not None and revisions[key]!={entry['stamp']}:
                    raise ValueError('Part revision differs from saved assembly revision')
                if saved is not None:
                    comparison=matching_saved_geometry(entry['metrics'],saved[key[0]+'\n'+key[1]])
                    if not comparison['accepted']:
                        raise ValueError('Native BRep differs from saved assembly geometry: '+json.dumps(comparison))
                    comparisons[key[0]+'\n'+key[1]]=comparison
                elif single_saved is not None:
                    comparison=matching_saved_geometry(entry['metrics'],single_saved)
                    if not comparison['accepted']:
                        raise ValueError('Native BRep differs from the single saved configuration: '+json.dumps(comparison))
                    comparisons[key[0]+'\n'+key[1]]=comparison
                cache[key] = dict(folder=str(folder),entry=entry)
            except (ValueError,OSError,KeyError) as error:
                cache[key] = dict(error=str(error))
        rec['native_key'] = key
        if 'error' in cache[key]:missing.append(dict(instance=rec['name'],file=rec['file'],configuration=key[1],reason=cache[key]['error']))
    from solidworks_prism import verify_saved_arc_choices,saved_curve_samples
    proof_keys=[key for key,item in cache.items() if 'error' not in item and item['entry']['native_arc_choices']]
    if saved is not None:
        samples=assembly_curve_samples(path,records,source_hash,[key[0]+'\n'+key[1] for key in proof_keys],cache_dir)
    else:
        samples={key[0]+'\n'+key[1]:saved_curve_samples(single_mesh) if single_mesh is not None else [] for key in proof_keys}
    proofs={}
    for key in proof_keys:
        try:proofs[key[0]+'\n'+key[1]]=verify_saved_arc_choices(cache[key]['entry']['native_arc_choices'],samples[key[0]+'\n'+key[1]])
        except ValueError as error:cache[key]=dict(error=str(error))
    missing=[dict(instance=rec['name'],file=rec['file'],configuration=rec['configuration'],reason=cache[rec['native_key']]['error']) for rec in parts if 'error' in cache[rec['native_key']]]
    if digest(path)!=source_hash:raise ValueError('Assembly changed during native import preparation')
    report = dict(source=str(path),configuration=scene['configuration'],expected=len(parts),
                  imported=len(parts)-len(missing),missing=missing,warnings=scene['warnings'],
                  source_hashes=hashes,exact_brep=True,complete_exact_model=not missing and not scene['warnings'],
                  geometry_mode='NativeBRep',feature_history_preserved=False,source_colors_preserved=False,
                  decoder_sha256=DECODER_SHA256,engine=ENGINE_ID,saved_geometry_checks=comparisons,native_arc_proofs=proofs,
                  native_methods={key[0]+'\n'+key[1]:item['entry']['native_method'] for key,item in cache.items() if 'error' not in item},
                    embedded_sources=embedded_sources,
                  saved_geometry_note='Triangulation bounds/volume sanity checks are not exact dimension measurements')
    if not report['imported'] or (not allow_partial and not report['complete_exact_model']):
        raise IncompleteImportError(report)
    return records,cache,report


def build(doc, prepared):
    import Part
    import model
    import solidworks_import as sw
    records, cache, report = prepared
    for name,expected in report['source_hashes'].items():
        if digest(name)!=expected:raise ValueError('Native source changed before insertion')
    shapes = {}
    for key,item in cache.items():
        if 'error' in item:continue
        source = Path(item['folder'])/'shape.brep'
        if digest(source)!=item['entry']['brep_sha256']:raise ValueError('Prepared native BRep changed')
        shape = Part.Shape();shape.read(str(source));shape_metrics(shape,item['entry']['geometry']['bodies']);shapes[key]=shape
    with model.transaction(doc,'Import SolidWorks Native BRep'):
        root = doc.addObject('App::Part','SolidWorksBRep')
        status = 'Complete native BRep' if report['complete_exact_model'] else 'PARTIAL native BRep %d/%d'%(report['imported'],report['expected'])
        root.Label = Path(report['source']).stem+' ['+status+']'
        for name,value in [('GeometryMode','Native BRep; never mesh fitting'),('ImportStatus',status),('SourceFile',report['source']),('ImportReport',json.dumps(report,ensure_ascii=False))]:
            root.addProperty('App::PropertyString',name,'SolidWorks Import');setattr(root,name,value);root.setEditorMode(name,1)
        groups = {'':root}
        for rec in records:
            parent = groups[rec['parent']]
            if rec['kind']=='assembly':
                obj=doc.addObject('App::Part','Subassembly');groups[rec['key']]=obj
            elif rec['native_key'] in shapes:
                obj=doc.addObject('Part::Feature','SWNativeSolid');shape=shapes[rec['native_key']].copy()
                shape.transformShape(sw._matrix(rec['matrix']),True)
                shape_metrics(shape,cache[rec['native_key']]['entry']['geometry']['bodies']);obj.Shape=shape
            else:
                obj=doc.addObject('App::FeaturePython','UnresolvedNativePart')
                obj.addProperty('App::PropertyString','ImportError','SolidWorks Import');obj.ImportError=cache[rec['native_key']]['error']
            obj.Label=rec['name'];parent.addObject(obj)
            if obj.ViewObject:obj.ViewObject.Visibility=not rec['hidden']
            for name,value in [('SourceFile',rec['file']),('SourceConfiguration',rec['configuration']),('SavedWorldTransform',json.dumps(rec['matrix']))]:
                obj.addProperty('App::PropertyString',name,'SolidWorks Import');setattr(obj,name,value);obj.setEditorMode(name,1)
    return root


def open_file(filename, configuration=None, allow_partial=False, cache_dir=None, progress=None):
    import FreeCAD as App
    prepared = prepare(filename,configuration,allow_partial,cache_dir,progress)
    doc = App.newDocument('SolidWorksNative');doc.UndoMode=1
    try:build(doc,prepared)
    except Exception:
        App.closeDocument(doc.Name)
        raise
    return doc


def show(ws):
    import FreeCADGui as Gui
    from PySide import QtCore,QtWidgets as W
    from i18n import tr
    if ws.current_sketch() or Gui.Control.activeDialog():raise ValueError(tr('先に編集中の操作を終了してください。','Finish the active edit first.'))
    filename,_=W.QFileDialog.getOpenFileName(ws.main,tr('SolidWorks厳密ソリッドを読み込み','Import SolidWorks native solids'),'','SolidWorks (*.sldprt *.sldasm *.SLDPRT *.SLDASM)')
    if not filename:return
    configuration=None
    if Path(filename).suffix.lower()=='.sldprt':
        choices=sorted(set(name for name,stamp in feature_models(filename) if name and stamp))
        if len(choices)>1:
            configuration,ok=W.QInputDialog.getItem(ws.main,tr('構成','Configuration'),tr('読み込む構成','Configuration to import'),choices,0,False)
            if not ok:return
    progress=W.QProgressDialog(tr('ネイティブBRepを変換・検証しています。','Converting and validating native BRep.'),'',0,0,ws.main);progress.setCancelButton(None);progress.setWindowModality(QtCore.Qt.WindowModal);progress.show();W.QApplication.processEvents()
    def update(index,total,name):
        progress.setRange(0,total);progress.setValue(index);progress.setLabelText('%d/%d  %s'%(index+1,total,name));W.QApplication.processEvents()
    try:doc=open_file(filename,configuration,True,progress=update)
    finally:progress.close()
    ws.refresh();Gui.activeDocument().activeView().viewAxonometric();ws.fit()
    report=json.loads(doc.getObject('SolidWorksBRep').ImportReport)
    text=tr('厳密ソリッド: %d / %d 出現。未読込: %d。\n未読込の部品はマーカーのみで、加工できません。元の履歴と色は復元しません。詳細はImportReportを確認してください。','Native solid occurrences: %d / %d. Unresolved: %d.\nUnresolved parts are markers and cannot be machined. Source history and colors are not reconstructed. See ImportReport.')%(report['imported'],report['expected'],len(report['missing']))
    W.QMessageBox.information(ws.main,tr('ネイティブBRep読込結果','Native BRep import result'),text)
    return doc


def geometry_snapshot(document, configuration):
    document=copy.deepcopy(document);model=document['model']
    configs=[c for c in model['configurations'] if c['name']==configuration]
    if len(configs)!=1:raise ValueError('Requested assembly configuration is not uniquely decoded')
    selected=configs[0]['bodies']
    if not selected:raise ValueError('Configuration has no decoded native BRep bodies')
    fields=('bodies','regions','shells','faces','loops','coedges','edges','vertices','points','surfaces','curves','pcurves')
    byid={};fieldof={}
    for field in fields:
        for node in model[field]:
            if node['id'] in byid:raise ValueError('Duplicate native BRep identity')
            byid[node['id']]=node;fieldof[node['id']]=field
    if any(key not in byid or fieldof[key]!='bodies' or byid[key]['kind']!='solid' for key in selected):raise ValueError('Requested configuration contains a non-solid or missing native body')
    def strings(value):
        if isinstance(value,str):yield value
        elif isinstance(value,dict):
            for v in value.values():yield from strings(v)
        elif isinstance(value,list):
            for v in value:yield from strings(v)
    pending=list(selected);keep=set()
    while pending:
        key=pending.pop()
        if key in keep:continue
        keep.add(key);pending.extend(s for s in strings(byid[key]) if s in byid and s not in keep)
    for key in keep:
        if fieldof[key]=='bodies' and key not in selected:raise ValueError('BRep graph reaches another configuration body')
    empty={key for key in keep if fieldof[key]=='regions' and not byid[key]['shells']}
    for body in selected:
        byid[body]['regions']=[key for key in byid[body]['regions'] if key not in empty]
        if not byid[body]['regions']:raise ValueError('Native body has no bounded region')
    keep-=empty
    for field in model:
        model[field]=[node for node in model[field] if node['id'] in keep] if field in fields else []
    document['native']={}
    return document,dict(configuration=configuration,bodies=len(selected),faces=len(model['faces']),surfaces=collections.Counter(n['geometry']['kind'] for n in model['surfaces']),omitted_boundaryless_regions=len(empty))

def geometry_losses(report):
    return [loss for loss in report['decode_report']['losses']
            if loss['code'].get('kind') != 'feature_history_retained'
            and loss['code'].get('code') != 'tessellation.face-ownership-unresolved']

def shape_metrics(shape, expected_bodies):
    if shape.isNull() or not shape.isValid() or not shape.isClosed():
        raise ValueError('Decoded native BRep is null, invalid or open')
    if len(shape.Solids) != expected_bodies or len(shape.Faces) != sum(len(s.Faces) for s in shape.Solids):
        raise ValueError('Decoded native BRep has unexpected bodies or loose faces')
    if not math.isfinite(shape.Volume) or shape.Volume <= 0:
        raise ValueError('Decoded native BRep has invalid volume')
    box = shape.BoundBox
    return dict(bodies=len(shape.Solids), faces=len(shape.Faces), volume_mm3=shape.Volume,
                bbox_mm=[box.XMin,box.YMin,box.ZMin,box.XMax,box.YMax,box.ZMax],
                surfaces=dict(collections.Counter(type(f.Surface).__name__ for f in shape.Faces)))


def matching_saved_geometry(metrics, saved, bbox_tolerance=.1, volume_tolerance=.01):
    native, display = metrics['bbox_mm'], saved['bbox_mm']
    if len(native) != 6 or len(display) != 6 or not all(math.isfinite(x) for x in native+display):
        raise ValueError('Invalid native or saved geometry bounds')
    volume = abs(saved['volume_mm3'])
    if not math.isfinite(volume) or volume <= 1e-12:
        raise ValueError('Saved geometry has no usable independent volume')
    bounds_delta = max(abs(a-b) for a,b in zip(native,display))
    volume_delta = abs(metrics['volume_mm3']-volume)/volume
    return dict(accepted=bounds_delta<=bbox_tolerance and volume_delta<=volume_tolerance,
                bbox_delta_mm=bounds_delta, volume_relative_delta=volume_delta,
                bbox_tolerance_mm=bbox_tolerance, volume_tolerance=volume_tolerance,
                note='Saved triangulation sanity check, not an exact dimension oracle')


def saved_mesh_metrics(mesh):
    low, high = mesh.bbox()
    volume = 0.0
    for i,j,k in mesh.triangles:
        a,b,c = mesh.vertices[i],mesh.vertices[j],mesh.vertices[k]
        volume += a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0])
    return dict(bbox_mm=[*low,*high],volume_mm3=abs(volume/6))


def geometry_only_copy(path, folder):
    import solidworks_import as sw
    path=Path(path);data=path.read_bytes();original=hashlib.sha256(data).hexdigest();blocks=sw.source_blocks(path)
    removed=[]
    for block in reversed(blocks):
        if block.name.endswith('-ResolvedFeatures'):
            removed.append(dict(name=block.name,sha256=hashlib.sha256(sw.block_data(block)).hexdigest()))
            data=data[:block.offset]+data[block.data_offset+block.compressed:]
    if not removed:raise ValueError('No expensive feature stream can be isolated')
    target=Path(folder)/'native-geometry-input.SLDPRT';target.write_bytes(data)
    retained=[(b.name,hashlib.sha256(sw.block_data(b)).hexdigest()) for b in blocks if not b.name.endswith('-ResolvedFeatures')]
    actual=[(b.name,hashlib.sha256(sw.block_data(b)).hexdigest()) for b in sw.source_blocks(target)]
    if retained!=actual or digest(path)!=original:raise ValueError('Native retained block identity changed')
    if not any(name.endswith('-Partition') for name,sha in retained):raise ValueError('No final configuration partition retained')
    return target,dict(source_sha256=original,derived_sha256=digest(target),omitted_feature_streams=removed,retained_blocks=retained)

def embedded_part(container, filename, configuration, cache_dir=None):
    import solidworks_import as sw
    container=Path(container).resolve();before=digest(container);filename=Path(filename).name
    names={'ImportedComp/'+filename}
    suffix='^'+container.stem+'.SLDPRT'
    if filename.casefold().endswith(suffix.casefold()):names.add('VirtualComp/'+filename[:-len(suffix)])
    matches=[b for b in sw.source_blocks(container) if b.name.casefold() in {name.casefold() for name in names}]
    payloads={}
    for block in matches:
        payload=sw.block_data(block);sha=hashlib.sha256(payload).hexdigest();payloads[sha]=(block.name,payload)
    if not payloads:return None
    if len(payloads)!=1:raise ValueError('Embedded native part payload is ambiguous within its container')
    sha,(name,payload)=next(iter(payloads.items()));folder=Path(cache_dir or CACHE)/'embedded-native';folder.mkdir(parents=True,exist_ok=True)
    target=folder/(sha+'.SLDPRT')
    if target.exists():
        if digest(target)!=sha:raise ValueError('Extracted native source changed')
    else:target.write_bytes(payload)
    stamps=[stamp for config,stamp in feature_models(target) if config==configuration]
    if len(stamps)!=1 or not stamps[0]:raise ValueError('Embedded configuration is missing or ambiguous')
    if digest(container)!=before:raise ValueError('Embedded source container changed during extraction')
    return target,dict(container=str(container),container_sha256=before,block=name,payload_sha256=sha,configuration=configuration,stamp=stamps[0])


def linked_step_source(path, configuration):
    import solidworks_import as sw
    from pathlib import Path
    import hashlib
    
    path=Path(path).resolve()
    block=next((b for b in sw.source_blocks(path) if b.name=='swXmlContents/Features'),None)
    if block is None:return None
    data=sw.block_data(block)
    if len(data)>33554432 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('Unsafe native feature manifest')
    import xml.etree.ElementTree as ET
    root=ET.fromstring(data);local=lambda e:e.tag.rsplit('}',1)[-1]
    features=[e for e in root.iter() if local(e)=='swExtFeature' and e.get('swConfigurationName')==configuration and e.get('swSuppressed')=='0']
    if len(features)!=1 or features[0].get('swFeatureType')!='MBimport':return None
    models=[e for e in root.iter() if local(e)=='swModel' and e.get('id')==features[0].get('swModelRef')]
    if len(models)!=1:return None
    files=[e for e in root.iter() if local(e)=='swFile' and e.get('id')==models[0].get('swFileRef')]
    if len(files)!=1:return None
    name=files[0].get('swPath','').replace(chr(92),'/').rsplit('/',1)[-1]
    if Path(name).suffix.casefold() not in ('.step','.stp'):return None
    candidates=[p for p in path.parent.iterdir() if p.is_file() and p.name.casefold()==name.casefold()]
    if len(candidates)!=1:return None
    candidate=candidates[0]
    if candidate.stat().st_size>1073741824:raise ValueError('Linked STEP exceeds input limit')
    
    def digest(p):
        h=hashlib.sha256()
        with open(p,'rb') as f:
            while chunk:=f.read(65536):
                h.update(chunk)
        return h.hexdigest()
        
    return candidate,dict(native_source=str(path),native_sha256=digest(path),configuration=configuration,feature=features[0].get('swName',''),feature_type='MBimport',linked_source=str(candidate),linked_sha256=digest(candidate),binding='Native feature manifest model/file reference; no filename guessing')


def precise_shape_metrics(shape, expected_bodies):
    metrics=shape_metrics(shape,expected_bodies)
    box=shape.optimalBoundingBox(False,False)
    values=[box.XMin,box.YMin,box.ZMin,box.XMax,box.YMax,box.ZMax]
    if not all(math.isfinite(x) for x in values) or any(values[i]>values[i+3] for i in range(3)):
        raise ValueError('Native geometric bounds are invalid')
    metrics['bbox_mm']=values
    metrics['bbox_method']='OCC geometric extrema, triangulation disabled, shape-tolerance enlargement disabled'
    return metrics
