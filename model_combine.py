"""Editable multi-tool solid booleans in world coordinates."""
import FreeCAD as App
import Part
import model
from i18n import tr


def label(operation):
    return {'join':tr('結合','Combine'), 'cut':tr('切り取り','Cut'),
            'intersect':tr('交差部分を残す','Intersect')}[operation]


def solid(obj):
    if obj:
        for source in [obj]+obj.OutListRecursive:
            if ('Invalid' in source.State or
                    (getattr(source,'FluxSketchProfile',False) and source.Shape.isNull())):
                raise ValueError(tr('「%s」を更新できません。先にスケッチ領域や参照先を修正してください。',
                                    'Cannot update "%s". Fix its sketch profile or references first.')%source.Label)
    if (not obj or not hasattr(obj,'Shape') or hasattr(obj,'Mesh') or
            obj.TypeId=='Sketcher::SketchObject' or getattr(obj,'FluxCADInternal',False) or
            getattr(obj,'FluxSplit',False) or 'Invalid' in obj.State):
        raise ValueError(tr('有効なソリッドボディを選択してください。','Select a valid solid body.'))
    shape=model.world_shape(obj)
    if shape.isNull() or not shape.isValid() or not shape.Solids or shape.Volume<=1e-9:
        raise ValueError(tr('有効なソリッドボディを選択してください。','Select a valid solid body.'))
    return shape


def validate(doc,target,tools,existing=None):
    objects=[target]+list(tools)
    if not tools:
        raise ValueError(tr('工具ボディを1つ以上選択してください。','Select at least one tool body.'))
    if any(not obj or obj.Document!=doc for obj in objects) or (existing and existing.Document!=doc):
        raise ValueError(tr('同じ文書のボディを選択してください。','Select bodies in the same document.'))
    if len(set(objects))!=len(objects):
        raise ValueError(tr('対象と工具には異なるボディを指定してください。','Target and tools must be different bodies.'))
    if existing and (not getattr(existing,'FluxCombine',False) or target!=existing.FluxBodySource):
        raise ValueError(tr('編集時に対象ボディは変更できません。','The target body cannot be replaced during editing.'))
    for obj in objects:
        if existing and (obj==existing or existing in obj.OutListRecursive):
            raise ValueError(tr('結果や後の加工を工具に指定できません。','The result or downstream features cannot be used as tools.'))
        if any(other!=obj and other in obj.OutListRecursive for other in objects):
            raise ValueError(tr('加工前と加工後のボディを同時に指定できません。独立したボディを選択してください。',
                                'Do not combine a body with its own earlier or later feature. Choose independent bodies.'))
        solid(obj)


def preview(target,tools,operation='join'):
    if operation not in ('join','cut','intersect'):
        raise ValueError(tr('結合・切り取り・交差を選択してください。','Choose Combine, Cut or Intersect.'))
    if not tools:raise ValueError(tr('工具ボディを1つ以上選択してください。','Select at least one tool body.'))
    source=solid(target);shapes=[solid(obj) for obj in tools]
    # A union removes overlapping tool material before cutting/intersecting.
    tool=shapes[0].multiFuse(shapes[1:]) if len(shapes)>1 else shapes[0]
    result=source.fuse(tool) if operation=='join' else source.cut(tool) if operation=='cut' else source.common(tool)
    if result.isNull() or not result.isValid() or not result.Solids or result.Volume<=1e-9:
        raise ValueError(tr('結果に立体が残りません。工具の位置か操作を変更してください。',
                            'No solid remains. Change the tool positions or operation.'))
    if operation=='cut' and source.Volume-result.Volume<=max(1e-8,source.Volume*1e-9):
        raise ValueError(tr('工具が対象ボディに食い込んでいません。','The tools do not cut into the target body.'))
    result=result.removeSplitter()
    # Identity outer placement gives the result its own independent transform.
    return Part.makeCompound(result.Solids)


class CombineFeature:
    def execute(self,obj):
        pose=App.Placement(obj.Placement)
        try:
            result=preview(obj.FluxBodySource,list(obj.Tools),str(obj.Operation))
            obj.Shape=result;obj.Placement=pose
        except Exception:
            obj.Shape=Part.Shape();obj.Placement=pose
            raise
    def dumps(self):return None
    def loads(self,state):pass


def placed(shape,existing=None):
    if existing:shape.Placement=existing.getGlobalPlacement().multiply(shape.Placement)
    return shape


def create(doc,target,tools,operation='join',keep_tools=False,existing=None):
    tools=list(tools);validate(doc,target,tools,existing)
    expected=placed(preview(target,tools,operation),existing)
    visible=[(o,bool(o.Visibility)) for o in doc.Objects if hasattr(o,'Visibility')]
    previous_tools=list(existing.Tools) if existing else []
    previous_label=label(str(existing.Operation)) if existing else ''
    dependents={o.Name for o in existing.InListRecursive if hasattr(o,'Shape') and o.Shape.Solids} if existing else set()
    try:
        with model.transaction(doc,tr('結合を編集','Edit Combine') if existing else label(operation)):
            obj=existing
            if obj is None:
                obj=doc.addObject('Part::FeaturePython','Combine')
                obj.addProperty('App::PropertyBool','FluxCombine','FluxCAD');obj.FluxCombine=True
                obj.addProperty('App::PropertyLinkGlobal','FluxBodySource','Combine');obj.FluxBodySource=target
                obj.addProperty('App::PropertyLinkListGlobal','Tools','Combine')
                obj.addProperty('App::PropertyEnumeration','Operation','Combine');obj.Operation=['join','cut','intersect']
                obj.addProperty('App::PropertyBool','KeepTools','Combine')
                obj.addProperty('App::PropertyLinkListGlobal','SourceContainers','Combine')
                obj.setEditorMode('FluxCombine',2);obj.setEditorMode('SourceContainers',2);obj.setEditorMode('FluxBodySource',1)
                obj.Proxy=CombineFeature();obj.ViewObject.Proxy=0
                for prop in ('ShapeColor','LineColor','PointColor','Transparency'):
                    setattr(obj.ViewObject,prop,getattr(target.ViewObject,prop))
            if not existing or obj.Label==previous_label:obj.Label=label(operation)
            parents=[]
            for source in [target]+tools:
                parent=source.getParentGeoFeatureGroup()
                while parent:
                    if parent not in parents:parents.append(parent)
                    parent=parent.getParentGeoFeatureGroup()
            obj.SourceContainers=parents;obj.Tools=tools;obj.Operation=operation;obj.KeepTools=bool(keep_tools)
            doc.recompute()
            for feature in [obj]+obj.InListRecursive:
                if hasattr(feature,'Shape') and (feature.Shape.isNull() or not feature.Shape.isValid() or 'Invalid' in feature.State
                                                 or (feature.Name in dependents and not feature.Shape.Solids)):
                    raise ValueError(tr('結果や後の加工を更新できないため、変更を取り消しました。',
                                        'The result or a later feature cannot update. The change was cancelled.'))
            actual=model.world_shape(obj);tolerance=max(1e-6,expected.Volume*1e-6)
            if (abs(actual.Volume-expected.Volume)>tolerance or
                    abs(actual.common(expected).Volume-expected.Volume)>tolerance):
                raise ValueError(tr('プレビューと結果が一致しません。','The result differs from the preview.'))
            from browser import collect
            current={o for o,title in collect(doc)[0]}
            target.Visibility=False
            for tool in set(previous_tools+tools):
                # Do not reveal an old tool that another downstream operation consumes.
                tool.Visibility=tool in current
            if not existing:obj.Visibility=True
        return obj
    except Exception:
        for obj,state in visible:
            if obj.Document:obj.Visibility=state
        raise
