"""Linked planar references driving native Part::Mirroring properties."""
import math
import FreeCAD as App
from i18n import tr


def frame(plane='YZ',offset=0,reference=None,subelement=''):
    if not math.isfinite(offset) or abs(offset)>100000:
        raise ValueError(tr('面の位置・オフセットは−100000～100000 mmで指定してください。',
                            'Plane position or offset must be between -100000 and 100000 mm.'))
    if reference is not None:
        import model_construction as references
        origin,normal=references.face((reference,subelement or ('Face1' if getattr(reference,'FluxPlane',False) else '')))
    elif plane in ('XY','XZ','YZ'):
        origin=App.Vector();normal=App.Vector(*{'XY':(0,0,1),'XZ':(0,1,0),'YZ':(1,0,0)}[plane])
    else:
        raise ValueError(tr('ミラーの基準となる平らな面・構築平面を選択してください。',
                            'Select a planar face or construction plane for the mirror.'))
    if normal.Length<1e-9 or not all(math.isfinite(v) for v in tuple(origin)+tuple(normal)):
        raise ValueError(tr('有効な平面を選択してください。','Select a valid plane.'))
    normal.normalize()
    return origin+normal*offset,normal


def validate(doc,reference,subelement,existing=None):
    if reference is None or reference.Document!=doc:
        raise ValueError(tr('同じ文書内の面・構築平面を選択してください。','Select a face or construction plane in the same document.'))
    if existing and (existing.Document!=doc or reference==existing or existing in reference.OutListRecursive):
        raise ValueError(tr('ミラー自身や後続の加工は基準面にできません。','The mirror itself or its descendants cannot define its reference plane.'))
    parent=reference.getParentGeoFeatureGroup()
    while parent:
        if existing and existing in parent.OutListRecursive:
            raise ValueError(tr('ミラーを含むグループは参照できません。','Cannot reference a group containing the mirror.'))
        parent=parent.getParentGeoFeatureGroup()
    return frame(reference=reference,subelement=subelement)


def resolve(doc,name,subelement,existing=None):
    import model_construction as references
    ref,sub=references.resolve(doc,name,subelement)
    validate(doc,ref,sub,existing)
    return ref,sub


def signature(obj):return obj.Shape.hashCode(),str(obj.getGlobalPlacement()),str(getattr(obj,'Error','')),tuple(obj.State)


class MirrorPlane:
    def execute(self,obj):
        try:
            ref,names=obj.Support or (None,[])
            if ref is None:raise ValueError(tr('ミラーの基準面がありません。選び直してください。','The mirror reference plane is missing. Select it again.'))
            origin,normal=frame(offset=obj.Offset.Value,reference=ref,subelement=names[0] if names else '')
            obj.Origin=origin;obj.Normal=normal;obj.Error=''
        except Exception as error:
            obj.Normal=App.Vector();obj.Error=str(error)
            raise
    def dumps(self):return None
    def loads(self,state):pass


def bind(obj,plane='YZ',offset=0,reference=None,subelement=''):
    old=getattr(obj,'FluxMirrorSupport',None)
    for prop in ('Base','Normal'):
        for component in 'xyz':obj.setExpression(prop+'.'+component,None)
    if reference is None:
        obj.Base,obj.Normal=frame(plane,offset)
        if old:
            obj.FluxMirrorSupport=None
            if not old.InList:obj.Document.removeObject(old.Name)
        return
    validate(obj.Document,reference,subelement,obj)
    helper=old
    if helper is None:
        helper=obj.Document.addObject('App::FeaturePython','MirrorPlane');helper.Label=tr('ミラー基準面','Mirror Reference Plane')
        for typ,key in [('App::PropertyBool','FluxCADInternal'),('App::PropertyLinkSubGlobal','Support'),
                        ('App::PropertyLinkListGlobal','SourceContainers'),('App::PropertyDistance','Offset'),
                        ('App::PropertyVectorDistance','Origin'),('App::PropertyVector','Normal'),('App::PropertyString','Error')]:
            helper.addProperty(typ,key,'Mirror')
        helper.FluxCADInternal=True;helper.Proxy=MirrorPlane()
        for key in helper.PropertiesList:helper.setEditorMode(key,2)
        if 'FluxMirrorSupport' not in obj.PropertiesList:obj.addProperty('App::PropertyLink','FluxMirrorSupport','FluxCAD')
        obj.FluxMirrorSupport=helper;obj.setEditorMode('FluxMirrorSupport',2)
    parents=[];parent=reference.getParentGeoFeatureGroup()
    while parent:
        parents.append(parent);parent=parent.getParentGeoFeatureGroup()
    helper.Support=(reference,[subelement or 'Face1']);helper.SourceContainers=parents;helper.Offset=offset;helper.touch()
    obj.Document.recompute()
    if helper.Error or 'Invalid' in helper.State:raise ValueError(helper.Error or tr('ミラーの基準面を更新できません。','Cannot update the mirror reference plane.'))
    for prop,value in (('Base','Origin'),('Normal','Normal')):
        for component in 'xyz':obj.setExpression(prop+'.'+component,helper.Name+'.'+value+'.'+component)


def settings(obj):
    helper=getattr(obj,'FluxMirrorSupport',None)
    if not helper:return None
    ref,names=helper.Support or (None,[])
    return dict(plane='reference',reference=ref,subelement=names[0] if names else '',offset=helper.Offset.Value)
