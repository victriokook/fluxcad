"""World-space axes linked to an edge, cylindrical face or construction axis."""
import math
import re
import FreeCAD as App
import Part
import model
from i18n import tr


def geometry(reference, subelement):
    if reference and getattr(reference,'FluxConstructionAxis',''):
        if subelement not in ('','Edge1') or 'Invalid' in reference.State or reference.Error or reference.Shape.isNull() or reference.Direction.Length<1e-9:
            raise ValueError(tr('構築軸にエラーがあります。参照を修復してください。','The construction axis has an error. Repair its references.'))
        return App.Vector(reference.Origin),App.Vector(reference.Direction),'construction'
    if (not reference or not hasattr(reference,'Shape') or
            not re.fullmatch(r'(Edge|Face)[1-9][0-9]*',subelement)):
        raise ValueError(tr('直線の辺、または円筒の側面を選択してください。',
                            'Select a straight edge or a cylindrical side face.'))
    if 'Invalid' in reference.State:
        raise ValueError(tr('軸の参照元にエラーがあります。','The axis reference has an error.'))
    try:shape=model.world_shape(reference).getElement(subelement)
    except Exception:
        raise ValueError(tr('参照した辺・面がありません。軸を選び直してください。',
                            'The referenced edge or face is missing. Reselect the axis.')) from None
    if shape.ShapeType=='Edge' and isinstance(shape.Curve,Part.Line):
        first=shape.valueAt(shape.FirstParameter);last=shape.valueAt(shape.LastParameter)
        origin=(first+last)*.5;direction=last-first;kind='line'
    elif shape.ShapeType=='Face' and isinstance(shape.Surface,Part.Cylinder):
        from model_align import cylinder_axis
        origin,direction=cylinder_axis(shape);kind='cylinder'
    else:
        raise ValueError(tr('直線の辺、または円筒の側面を選択してください。円弧・平面・円すいは軸にできません。',
                            'Choose a straight edge or cylindrical side face. Arcs, planes and cones cannot define an axis.'))
    if direction.Length<1e-9 or not all(math.isfinite(v) for v in tuple(origin)+tuple(direction)):
        raise ValueError(tr('軸を取得できません。','Could not determine the axis.'))
    direction.normalize()
    return origin,direction,kind


def reference(doc,name,subname,existing=None):
    obj=doc.getObject(name) if doc else None
    if obj and not subname and getattr(obj,'FluxConstructionAxis',''):subname='Edge1'
    if not obj or not re.search(r'(^|\.)(Edge|Face)[1-9][0-9]*$',subname):
        raise ValueError(tr('直線の辺、円筒の側面、または構築軸を選択してください。',
                            'Select a straight edge, cylindrical side face or construction axis.'))
    obj=obj.getSubObject(subname,1) or obj
    subname=subname.rsplit('.',1)[-1]
    validate(doc,obj,subname,existing)
    return obj,subname


def validate(doc,ref,subelement,existing=None):
    if not ref or ref.Document!=doc:
        raise ValueError(tr('同じ文書内の辺・面を選択してください。','Select an edge or face in the same document.'))
    if existing and (existing.Document!=doc or ref==existing or existing in ref.OutListRecursive):
        raise ValueError(tr('この回転・パターンの結果や、その後の加工は軸にできません。',
                            'The result of this operation or a downstream feature cannot be its axis.'))
    return geometry(ref,subelement)


def signature(ref):return ref.Shape.hashCode(),str(ref.getGlobalPlacement())


def values(axis,center,reverse=False,reference=None,subelement=''):
    if reference:
        origin,direction,_=geometry(reference,subelement)
    else:
        direction=App.Vector(*({'X':(1,0,0),'Y':(0,1,0),'Z':(0,0,1)}[axis] if isinstance(axis,str) else tuple(axis)))
        origin=App.Vector(*center)
        if not all(math.isfinite(v) for v in tuple(origin)+tuple(direction)) or direction.Length<1e-9:
            raise ValueError(tr('有効な軸と通過点を指定してください。','Specify a valid axis and origin.'))
        direction.normalize()
    return origin,direction*(-1 if reverse else 1)


class LinkedAxis:
    def execute(self,obj):
        try:
            ref,names=obj.Support or (None,[])
            origin,direction,kind=geometry(ref,names[0] if names else '')
            if kind!=obj.GeometryKind:
                raise ValueError(tr('参照形状の種類が変わりました。軸を選び直してください。',
                                    'The reference geometry type changed. Reselect the axis.'))
            obj.Origin=origin;obj.Direction=direction*(-1 if obj.Reversed else 1)
        except Exception:
            obj.Direction=App.Vector()
            raise
    def dumps(self):return None
    def loads(self,state):pass


def bind(obj,axis,center,reverse=False,reference=None,subelement=''):
    """Drive native Revolution/Array properties; no replacement of their proxies."""
    center_property='Base' if obj.TypeId=='Part::Revolution' else 'Center'
    old=getattr(obj,'FluxAxis',None)
    for prop in ('Axis',center_property):
        for component in 'xyz':obj.setExpression(prop+'.'+component,None)
    if not reference:
        origin,direction=values(axis,center,reverse)
        obj.Axis=direction;setattr(obj,center_property,origin)
        if old:
            obj.FluxAxis=None
            if not old.InList:obj.Document.removeObject(old.Name)
        return
    origin,direction,kind=validate(obj.Document,reference,subelement,obj)
    helper=old
    if helper is None:
        helper=obj.Document.addObject('App::FeaturePython','RotationAxis')
        helper.Label=tr('回転軸','Rotation Axis')
        helper.addProperty('App::PropertyBool','FluxCADInternal','FluxCAD');helper.FluxCADInternal=True
        helper.addProperty('App::PropertyLinkSubGlobal','Support','Axis')
        helper.addProperty('App::PropertyLinkListGlobal','SourceContainers','Axis')
        helper.addProperty('App::PropertyString','GeometryKind','Axis')
        helper.addProperty('App::PropertyBool','Reversed','Axis')
        helper.addProperty('App::PropertyVectorDistance','Origin','Axis')
        helper.addProperty('App::PropertyVector','Direction','Axis')
        helper.Proxy=LinkedAxis()
        for prop in helper.PropertiesList:helper.setEditorMode(prop,2)
        if 'FluxAxis' not in obj.PropertiesList:obj.addProperty('App::PropertyLink','FluxAxis','FluxCAD')
        obj.FluxAxis=helper;obj.setEditorMode('FluxAxis',2)
    parents=[];parent=reference.getParentGeoFeatureGroup()
    while parent:
        parents.append(parent);parent=parent.getParentGeoFeatureGroup()
    helper.Support=(reference,[subelement]);helper.SourceContainers=parents
    helper.GeometryKind=kind;helper.Reversed=reverse;helper.touch()
    obj.Document.recompute()
    if 'Invalid' in helper.State:raise ValueError(tr('軸を更新できません。','Could not update the axis.'))
    for prop,value in (('Axis','Direction'),(center_property,'Origin')):
        for component in 'xyz':obj.setExpression(prop+'.'+component,helper.Name+'.'+value+'.'+component)


def settings(obj):
    helper=getattr(obj,'FluxAxis',None)
    if not helper:return None
    ref,names=helper.Support or (None,[])
    return dict(reference=ref,subelement=names[0] if names else '',reverse=bool(helper.Reversed),axis_mode='reference')
