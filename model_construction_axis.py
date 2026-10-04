"""Visible, linked construction axes for revolutions and circular patterns."""
import math
import FreeCAD as App
import Part
import model
import model_construction as references
from i18n import tr


def title(kind):
    return tr('円柱・円すいの中心軸','Axis Through Cylinder / Cone') if kind=='center' else tr('2点を通る軸','Axis Through Two Points')


def geometry(kind,reference_a=None,reference_b=None,reversed=False,**unused):
    if kind=='center':
        face=references.round_face(reference_a);surface=face.Surface
        u0,u1,v0,v1=face.ParameterRange
        def center(v):return (surface.value(u0,v)+surface.value(u0+math.pi,v))*.5
        origin=center(0);direction=center(1)-origin;display=center((v0+v1)*.5)
    elif kind=='two_points':
        origin=references.vertex(reference_a);second=references.vertex(reference_b)
        direction=second-origin;display=(origin+second)*.5
    else:raise ValueError('Unknown axis type')
    if direction.Length<1e-7 or not all(math.isfinite(v) for v in tuple(origin)+tuple(direction)+tuple(display)):
        raise ValueError(tr('位置の異なる2点、または有効な円柱・円すい面を選択してください。','Select two distinct points or a valid cylindrical or conical face.'))
    direction.normalize()
    if reversed:direction=-direction
    return origin,direction,display


def source_refs(kind,reference_a=None,reference_b=None,**unused):return [reference_a,reference_b] if kind=='two_points' else [reference_a]


def check_sources(doc,kind,existing=None,**values):
    if existing and (existing.Document!=doc or getattr(existing,'FluxConstructionAxis','')!=kind):
        raise ValueError(tr('同じ種類の構築軸を選択してください。','Select a construction axis of the same type.'))
    for ref in source_refs(kind,**values):
        if not ref or ref[0] is None:raise ValueError(tr('参照を選択してください。','Select a reference.'))
        obj=ref[0]
        if obj.Document!=doc:raise ValueError(tr('同じ文書内の参照を選択してください。','Select references in the same document.'))
        if existing and (obj==existing or existing in obj.OutListRecursive):
            raise ValueError(tr('この軸自身や後続の加工は参照できません。','Cannot reference this axis or its descendants.'))


def build(kind,size=80,**values):
    if not math.isfinite(size) or not .1<=size<=1000000:
        raise ValueError(tr('表示長さは0.1～1000000 mmで指定してください。','Enter a display length from 0.1 to 1000000 mm.'))
    origin,direction,center=geometry(kind,**values)
    return Part.makeLine(center-direction*size*.5,center+direction*size*.5)


def settings(obj):
    return dict(reference_a=references.unpack(obj.ReferenceA),reference_b=references.unpack(obj.ReferenceB),size=obj.Length.Value,reversed=obj.Reversed)


class ConstructionAxis:
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        try:
            values=settings(obj);shape=build(obj.FluxConstructionAxis,**values)
            origin,direction,center=geometry(obj.FluxConstructionAxis,**values)
            parent=obj.getGlobalPlacement().multiply(obj.Placement.inverse())
            obj.Placement=App.Placement();shape.Placement=parent.inverse();obj.Shape=shape
            obj.Origin=origin;obj.Direction=direction;obj.Error=''
        except Exception as error:
            obj.Shape=Part.Shape();obj.Direction=App.Vector();obj.Error=str(error)
    def dumps(self):return None
    def loads(self,state):pass


def create(doc,kind,existing=None,**values):
    check_sources(doc,kind,existing,**values);expected=build(kind,**values)
    solids={o.Name for o in existing.InListRecursive if hasattr(o,'Shape') and o.Shape.Solids} if existing else set()
    with model.transaction(doc,title(kind)):
        obj=existing
        if obj is None:
            obj=doc.addObject('Part::FeaturePython','CenterAxis' if kind=='center' else 'TwoPointAxis');obj.Label=title(kind)
            for typ,key in [('App::PropertyString','FluxConstructionAxis'),('App::PropertyLinkSubGlobal','ReferenceA'),('App::PropertyLinkSubGlobal','ReferenceB'),
                            ('App::PropertyLinkListGlobal','SourceContainers'),('App::PropertyLength','Length'),('App::PropertyBool','Reversed'),
                            ('App::PropertyVectorDistance','Origin'),('App::PropertyVector','Direction'),('App::PropertyString','Error')]:obj.addProperty(typ,key,'Construction')
            obj.FluxConstructionAxis=kind
            for key in ('FluxConstructionAxis','ReferenceA','ReferenceB','SourceContainers'):obj.setEditorMode(key,2)
            for key in ('Placement','Origin','Direction','Error'):obj.setEditorMode(key,1)
            ConstructionAxis(obj);obj.ViewObject.Proxy=0
        data=dict(reference_a=None,reference_b=None,size=80,reversed=False);data.update(values)
        if kind=='center':data['reference_b']=None
        for prop,key in (('ReferenceA','reference_a'),('ReferenceB','reference_b')):
            ref=data[key];setattr(obj,prop,(ref[0],[ref[1]]) if ref else None)
        parents=[]
        for ref in source_refs(kind,**data):
            parent=ref[0].getParentGeoFeatureGroup()
            while parent:
                if obj in parent.OutListRecursive:raise ValueError(tr('軸を含むグループは参照できません。','Cannot reference a group containing this axis.'))
                if parent not in parents:parents.append(parent)
                parent=parent.getParentGeoFeatureGroup()
        obj.SourceContainers=parents;obj.Length=data['size'];obj.Reversed=bool(data['reversed']);doc.recompute()
        if obj.Error:raise ValueError(obj.Error)
        if obj.Shape.isNull() or not obj.Shape.isValid() or abs(obj.Shape.Length-expected.Length)>1e-6:
            raise ValueError(tr('構築軸を作成できません。','Cannot create the construction axis.'))
        for dependent in obj.InListRecursive:
            if ('Invalid' in dependent.State or getattr(dependent,'Error','') or
                    (hasattr(dependent,'Shape') and ((dependent.Shape.isNull() and dependent.TypeId!='Sketcher::SketchObject') or
                    (not dependent.Shape.isNull() and not dependent.Shape.isValid()) or (dependent.Name in solids and not dependent.Shape.Solids)))):
                raise ValueError(tr('後続の加工が成立しないため変更を取り消しました。','The edit would invalidate a later feature and was cancelled.'))
        if not existing:
            obj.ViewObject.LineColor=(.88,.48,.12);obj.ViewObject.PointColor=(.88,.48,.12);obj.ViewObject.LineWidth=3
    return obj
