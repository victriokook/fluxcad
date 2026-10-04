"""Native loft and sweep features driven by whole, single-wire sketches."""
from i18n import tr
import Part
import model
from model_features import solid, placed_preview, verify_result


def wire(obj, profile=True):
    shape = model.world_shape(obj)
    if (shape.isNull() or not shape.isValid() or shape.Solids or len(shape.Wires)!=1
            or len(shape.Wires[0].Edges)!=len(shape.Edges)):
        raise ValueError(tr('%s：つながった輪郭が1つだけのスケッチを指定してください。')%obj.Label)
    result = shape.Wires[0]
    if profile:
        if not result.isClosed():
            raise ValueError(tr('%s：断面の輪郭を閉じてください。')%obj.Label)
        face = Part.Face(result)
        if not face.isValid() or face.Area<=1e-9:
            raise ValueError(tr('%s：断面の重複・自己交差を取り除いてください。')%obj.Label)
    return result


def loft_shape(sections, ruled=False):
    if len(sections)<2:
        raise ValueError(tr('つなぐ順番に、断面スケッチを2つ以上追加してください。'))
    if len(set(sections))!=len(sections):
        raise ValueError(tr('同じ断面は繰り返し指定できません。'))
    wires = [wire(obj) for obj in sections]
    try:
        result = solid(Part.makeLoft(wires,True,ruled,False,5))
        if len(result.Solids)!=1:raise ValueError('separated solids')
        return result
    except (RuntimeError,ValueError):
        raise ValueError(tr('この断面ではロフトを作成できません。断面の位置・順序・輪郭を確認してください。')) from None


def sweep_shape(profile, path, frenet=False, transition=1):
    if not profile or not path:
        raise ValueError(tr('断面と経路のスケッチを指定してください。'))
    if profile==path:
        raise ValueError(tr('断面と経路は別々のスケッチを指定してください。'))
    if transition not in (0,1,2):
        raise ValueError(tr('角のつなぎ方を選択してください。'))
    section = wire(profile)
    spine = wire(path,False)
    try:
        result = solid(spine.makePipeShell([section],True,frenet,transition))
        if len(result.Solids)!=1:raise ValueError('separated solids')
        return result
    except (RuntimeError,ValueError):
        raise ValueError(tr('この断面と経路ではスイープを作成できません。断面を経路の端に配置し、経路の接続や曲がりを確認してください。')) from None


def sources(obj):
    sections = list(getattr(obj,'FluxSections',obj.Sections))
    path = getattr(obj,'FluxPath',None)
    if path is None and obj.TypeId=='Part::Sweep':path=obj.Spine[0]
    return sections,path


def create(doc, kind, sections, path=None, ruled=False, frenet=False, transition=1, existing=None):
    if kind not in ('loft','sweep'):raise ValueError(tr('作成方法を選択してください。'))
    inputs = list(sections)+([path] if path is not None else [])
    if (any(obj.Document!=doc for obj in inputs) or (existing and existing.Document!=doc)):
        raise ValueError(tr('同じ文書内のスケッチを指定してください。'))
    if existing and any(obj==existing or existing in obj.OutListRecursive for obj in inputs):
        raise ValueError(tr('この加工に依存する形状は断面・経路に指定できません。'))
    if kind=='sweep' and len(sections)!=1:
        raise ValueError(tr('スイープの断面を1つ指定してください。'))
    shape = loft_shape(sections,ruled) if kind=='loft' else sweep_shape(sections[0],path,frenet,transition)
    expected = placed_preview(shape,existing)
    title = tr('ロフト') if kind=='loft' else tr('スイープ')
    with model.transaction(doc,title+(tr('を編集') if existing else '')):
        previous = {}
        if existing:
            old_sections,old_path = sources(existing)
            previous.update(zip(old_sections,existing.Sections))
            if old_path:previous[old_path]=existing.Spine[0]
        def reference(source):
            return previous[source] if source in previous else model._world_source(doc,source)
        refs = [reference(source) for source in sections]
        path_ref = reference(path) if path else None
        obj = existing
        if obj is None:
            obj = doc.addObject('Part::Loft' if kind=='loft' else 'Part::Sweep','Loft' if kind=='loft' else 'Sweep')
            obj.Label = title
            obj.addProperty('App::PropertyBool','FluxLoft' if kind=='loft' else 'FluxSweep','FluxCAD')
            setattr(obj,'FluxLoft' if kind=='loft' else 'FluxSweep',True)
            obj.addProperty('App::PropertyLinkListGlobal','FluxSections','FluxCAD')
            if kind=='sweep':obj.addProperty('App::PropertyLinkGlobal','FluxPath','FluxCAD')
            for name in ('FluxLoft','FluxSweep','FluxSections','FluxPath'):
                if name in obj.PropertiesList:obj.setEditorMode(name,2)
        obj.Sections = refs
        obj.FluxSections = list(sections)
        obj.Solid = True
        if kind=='loft':
            obj.Ruled = ruled
            obj.Closed = False
            obj.MaxDegree = 5
        else:
            obj.Spine = (path_ref,[])
            obj.FluxPath = path
            obj.Frenet = frenet
            obj.Transition = transition
        verify_result(obj,expected)
        for source in inputs+refs+([path_ref] if path_ref else []):source.Visibility=False
        if not existing:obj.Visibility=True
        for old in set(previous.values())-set(refs)-{path_ref}:
            if getattr(old,'FluxCADInternal',False) and not old.InList:doc.removeObject(old.Name)
    return obj
