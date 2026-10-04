"""Constant-radius fillets and one/two-distance chamfers using native features."""
import math
import re
import FreeCAD as App
import Part
import model
from i18n import tr

TYPES={'fillet':'Part::Fillet','chamfer':'Part::Chamfer'}


def kind(obj):
    return next((key for key,value in TYPES.items() if obj and obj.TypeId==value),None)


def title(operation,edit=False):
    if operation=='fillet':return tr('フィレットを編集','Edit Fillet') if edit else tr('フィレット','Fillet')
    return tr('面取りを編集','Edit Chamfer') if edit else tr('面取り','Chamfer')


def source_shape(base,existing=None):
    # A native edge feature consumes its Base's shape in its own coordinate
    # frame. Newly created features use a world-space binder for nested inputs.
    shape=base.Shape.copy() if existing else model.world_shape(base)
    if shape.isNull() or not shape.isValid() or len(shape.Solids)!=1:
        raise ValueError(tr('1つにつながったソリッドを選択してください。','Select one connected solid.'))
    return shape


def pose(shape,existing=None):
    if existing:shape.Placement=existing.getGlobalPlacement().multiply(shape.Placement)
    return shape


def settings(obj):
    if not kind(obj) or not obj.Base:raise ValueError(tr('フィレット・面取りの履歴を選択してください。','Select a fillet or chamfer history entry.'))
    entries=list(obj.Edges)
    if (not entries or any(abs(float(entry[i])-float(entries[0][i]))>1e-9 for entry in entries for i in (1,2))
            or (kind(obj)=='fillet' and abs(float(entries[0][1])-float(entries[0][2]))>1e-9)):
        raise ValueError(tr('辺ごとに異なる寸法や可変半径の加工は、標準UIで編集してください。',
                            'Edit per-edge dimensions or variable-radius fillets in the standard UI.'))
    values=dict(edges=['Edge%d'%entry[0] for entry in entries],size=float(entries[0][1]))
    if kind(obj)=='chamfer' and (getattr(obj,'FluxChamferMode','')=='two' or abs(float(entries[0][1])-float(entries[0][2]))>1e-9):
        values['size2']=float(entries[0][2])
    return values


def indices(shape,edges):
    result=[]
    for name in dict.fromkeys(edges):
        if not re.fullmatch(r'Edge[1-9][0-9]*',name) or int(name[4:])>len(shape.Edges):
            raise ValueError(tr('加工する辺を選び直してください。','Reselect the edges to modify.'))
        result.append(int(name[4:])-1)
    if not result:raise ValueError(tr('加工する辺を1つ以上選択してください。','Select at least one edge to modify.'))
    return result


def preview(base,operation,edges,size,existing=None,size2=None):
    if operation not in TYPES:raise ValueError('Unknown edge operation')
    if operation!='chamfer' and size2 is not None:raise ValueError(tr('2つの距離は面取りで指定してください。','Two distances are supported for chamfers.'))
    if any(not math.isfinite(v) or not .001<=v<=100000 for v in ((size,) if size2 is None else (size,size2))):
        raise ValueError(tr('寸法は0.001～100000 mmで指定してください。','Enter a dimension between 0.001 and 100000 mm.'))
    shape=source_shape(base,existing);chosen=[shape.Edges[i] for i in indices(shape,edges)]
    try:
        result=shape.makeFillet(size,chosen) if operation=='fillet' else shape.makeChamfer(size,chosen) if size2 is None else shape.makeChamfer(size,size2,chosen)
        if result.isNull() or not result.isValid() or len(result.Solids)!=1 or result.Volume<=1e-9:
            raise ValueError('No valid edge treatment')
        tolerance=max(1e-8,shape.Volume*1e-10)
        if abs(result.Volume-shape.Volume)<tolerance and abs(result.common(shape).Volume-shape.Volume)<tolerance:
            raise ValueError('The shape did not change')
    except (Part.OCCError,RuntimeError,ValueError):
        raise ValueError(tr('この辺と寸法では加工できません。半径・距離を小さくするか、辺を変更してください。',
                            'These edges cannot be modified at this size. Reduce the radius/distance or change the edges.')) from None
    return pose(result,existing)


def signature(base):return base.Shape.hashCode(),str(base.getGlobalPlacement())


def create(doc,base,operation,edges,size,existing=None,size2=None):
    if base.Document!=doc or (existing and existing.Document!=doc):
        raise ValueError(tr('同じ文書内のボディを選択してください。','Select a body in the same document.'))
    if existing and (kind(existing)!=operation or existing.Base!=base):
        raise ValueError(tr('再編集する加工と参照元を確認してください。','Check the feature and its original source.'))
    expected=preview(base,operation,edges,size,existing,size2)
    visible=[(o,bool(o.Visibility)) for o in doc.Objects if hasattr(o,'Visibility')]
    dependents={o.Name for o in existing.InListRecursive if hasattr(o,'Shape') and o.Shape.Solids} if existing else set()
    try:
        with model.transaction(doc,title(operation,bool(existing))):
            obj=existing
            if obj is None:
                source=model._world_source(doc,base)
                obj=doc.addObject(TYPES[operation],'Fillet' if operation=='fillet' else 'Chamfer')
                obj.Label=title(operation);obj.Base=source
                obj.addProperty('App::PropertyLinkGlobal','FluxBodySource','FluxCAD');obj.FluxBodySource=base
                obj.setEditorMode('FluxBodySource',2)
            obj.Edges=[(i+1,size,size if size2 is None else size2) for i in indices(source_shape(base,existing),edges)]
            if operation=='chamfer':
                if 'FluxChamferMode' not in obj.PropertiesList:obj.addProperty('App::PropertyString','FluxChamferMode','FluxCAD')
                obj.FluxChamferMode='equal' if size2 is None else 'two';obj.setEditorMode('FluxChamferMode',2)
            if existing:
                doc.recompute()
                if obj.Shape.isNull() or not obj.Shape.isValid() or not obj.Shape.Solids or 'Invalid' in obj.State:
                    raise ValueError(tr('加工結果を更新できません。','Could not update the edge treatment.'))
            else:model.check(obj)
            actual=model.world_shape(obj);tolerance=max(1e-6,expected.Volume*1e-7)
            if abs(actual.Volume-expected.Volume)>tolerance or abs(actual.common(expected).Volume-expected.Volume)>tolerance:
                raise ValueError(tr('プレビューと作成結果が一致しないため、操作を取り消しました。',
                                    'The created shape differs from the preview. The operation was cancelled.'))
            for later in obj.InListRecursive:
                if hasattr(later,'Shape') and (later.Shape.isNull() or not later.Shape.isValid() or 'Invalid' in later.State
                                               or (later.Name in dependents and not later.Shape.Solids)):
                    raise ValueError(tr('後の加工を更新できないため、変更を取り消しました。',
                                        'A later operation could not be updated. The change was cancelled.'))
            if not existing:base.Visibility=False;obj.Base.Visibility=False;obj.Visibility=True
        return obj
    except Exception:
        for obj,state in visible:
            if obj.Document:obj.Visibility=state
        raise
