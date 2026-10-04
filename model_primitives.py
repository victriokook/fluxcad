"""Dimensioned spheres, ring tori, round-wire coils and hollow pipes."""
import math
import FreeCAD as App
import Part
import model
import model_sections
from i18n import tr

KINDS=('sphere','torus','coil','pipe')


def title(kind):
    return {'sphere':tr('球','Sphere'),'torus':tr('トーラス','Torus'),
            'coil':tr('コイル','Coil'),'pipe':tr('パイプ','Pipe')}[kind]


def defaults(kind):
    return dict(sphere=dict(diameter=20),torus=dict(diameter=30,section=6),
                coil=dict(diameter=30,section=3,pitch=6,turns=4,left=False),
                pipe=dict(diameter=10,wall=1,length=30,path=None))[kind].copy()


def settings(obj):
    kind=obj.FluxPrimitive
    if kind=='sphere':return dict(diameter=obj.Radius.Value*2)
    if kind=='torus':return dict(diameter=obj.Radius1.Value*2,section=obj.Radius2.Value*2)
    if kind=='coil':return dict(diameter=obj.Diameter.Value,section=obj.Section.Value,
                                pitch=obj.Pitch.Value,turns=obj.Turns,left=obj.LeftHanded)
    return dict(diameter=obj.Diameter.Value,wall=obj.Wall.Value,length=obj.Length.Value,path=obj.FluxPath)


def number(value,label,minimum=.001,maximum=100000):
    value=float(value)
    if not math.isfinite(value) or not minimum<=value<=maximum:
        raise ValueError(tr('%s：%g～%g の値を指定してください。','%s: enter a value from %g to %g.')%(label,minimum,maximum))
    return value


def validate(kind,values):
    if kind not in KINDS:raise ValueError('Unknown primitive: '+str(kind))
    result=defaults(kind)
    if set(values)-set(result):raise ValueError('Unknown primitive parameters')
    result.update(values)
    for key in set(result)-{'left','path'}:
        result[key]=number(result[key],key,.25 if key=='turns' else .001,50 if key=='turns' else 100000)
    if kind in ('torus','coil') and result['section']>=result['diameter']:
        raise ValueError(tr('断面の直径は中心径より小さくしてください。','Section diameter must be smaller than the centerline diameter.'))
    if kind=='coil':
        circumference=math.pi*result['diameter']
        separation=result['pitch']*circumference/math.hypot(circumference,result['pitch'])
        if separation<=result['section']*1.01:
            raise ValueError(tr('巻き同士が接触します。ピッチを増やすか線径を小さくしてください。',
                                'Coil turns touch. Increase the pitch or reduce the wire diameter.'))
        number(result['pitch']*result['turns'],tr('コイルの高さ','Coil height'))
    if kind=='pipe' and result['wall']*2>=result['diameter']:
        raise ValueError(tr('肉厚は外径の半分より小さくしてください。','Wall thickness must be less than half the outside diameter.'))
    return result


def check_solid(shape):
    if shape.isNull() or not shape.isValid() or len(shape.Solids)!=1 or shape.Volume<=1e-9:
        raise ValueError(tr('有効な立体を作成できません。寸法や経路の曲がり・自己交差を確認してください。',
                            'Cannot create a valid solid. Check dimensions, path bends and self-intersections.'))
    return shape


def swept_disk(spine,radius,frenet=False):
    edge=spine.OrderedEdges[0]
    # Respect reversed first edges (e.g. joined sketch geometry drawn backwards).
    parameter=edge.LastParameter if edge.Orientation=='Reversed' else edge.FirstParameter
    start=edge.valueAt(parameter);normal=edge.tangentAt(parameter)
    section=Part.Wire([Part.makeCircle(radius,start,normal)])
    return check_solid(spine.makePipeShell([section],True,frenet,1))


def shape(kind,**values):
    p=validate(kind,values);radius=p['diameter']/2
    try:
        if kind=='sphere':result=Part.makeSphere(radius)
        elif kind=='torus':result=Part.makeTorus(radius,p['section']/2)
        elif kind=='coil':
            spine=Part.Wire(Part.makeHelix(p['pitch'],p['pitch']*p['turns'],radius,0,p['left']).Edges)
            result=swept_disk(spine,p['section']/2,True)
        elif p['path'] is None:
            result=Part.makeCylinder(radius,p['length']).cut(Part.makeCylinder(radius-p['wall'],p['length']))
        else:
            spine=model_sections.wire(p['path'],False)
            outer=swept_disk(spine,radius);inner=swept_disk(spine,radius-p['wall'])
            result=outer.cut(inner)
        return check_solid(result)
    except (RuntimeError,Part.OCCError):
        raise ValueError(tr('この寸法・経路では作成できません。曲がりを緩くするか直径を小さくしてください。',
                            'Cannot build this geometry. Use gentler bends or a smaller diameter.')) from None


def placement(position=(0,0,0),axis='Z'):
    if axis not in ('X','Y','Z'):raise ValueError('Unknown axis')
    values=[number(v,tr('位置','Position'),-100000,100000) for v in position]
    if len(values)!=3:raise ValueError('Expected XYZ position')
    return App.Placement(App.Vector(*values),App.Rotation(App.Vector(0,0,1),
                         {'X':App.Vector(1,0,0),'Y':App.Vector(0,1,0),'Z':App.Vector(0,0,1)}[axis]))


def check_path(doc,path,existing=None):
    if path is None:return
    if path.Document!=doc:raise ValueError(tr('同じ文書内の経路を選んでください。','Select a path in the same document.'))
    if existing and (path==existing or existing in path.OutListRecursive):
        raise ValueError(tr('このパイプに依存する形状は経路に指定できません。','The path must not depend on this pipe.'))
    model_sections.wire(path,False)


class PrimitiveProxy:
    def __init__(self,obj):obj.Proxy=self

    def execute(self,obj):
        pose=App.Placement(obj.Placement)
        try:
            values=settings(obj)
            if obj.FluxPrimitive=='pipe':
                if obj.UsePath and obj.Path is None:
                    raise ValueError(tr('パイプの経路がありません。経路を選び直してください。','The pipe path is missing. Select a new path.'))
                values['path']=obj.Path
            local=shape(obj.FluxPrimitive,**values)
            # Identity root keeps a moved feature's transform separate from its geometry.
            obj.Shape=Part.makeCompound([local]);obj.Placement=pose;obj.Error=''
        except Exception as error:
            obj.Shape=Part.Shape();obj.Placement=pose;obj.Error=str(error)

    def dumps(self):return None
    def loads(self,state):pass


def create(doc,kind,existing=None,pose=None,**values):
    p=validate(kind,values)
    if existing and (existing.Document!=doc or getattr(existing,'FluxPrimitive',None)!=kind):
        raise ValueError(tr('同じ種類の形状を編集してください。','Edit a primitive of the same type.'))
    if kind=='pipe':check_path(doc,p['path'],existing)
    local=shape(kind,**p)
    pose=App.Placement(pose if pose is not None else existing.Placement if existing else App.Placement())
    if not all(math.isfinite(v) for v in tuple(pose.Base)+tuple(pose.Rotation.Q)):
        raise ValueError(tr('位置に有限の数値を指定してください。','Placement must contain finite numbers.'))
    expected=local.copy();expected.Placement=pose.multiply(expected.Placement)
    solid_dependents={o.Name for o in existing.InListRecursive if hasattr(o,'Shape') and o.Shape.Solids} if existing else set()
    with model.transaction(doc,title(kind)):
        obj=existing
        if obj is None:
            obj=doc.addObject({'sphere':'Part::Sphere','torus':'Part::Torus'}.get(kind,'Part::FeaturePython'),kind.title())
            obj.Label=title(kind)
            obj.addProperty('App::PropertyString','FluxPrimitive','FluxCAD');obj.FluxPrimitive=kind;obj.setEditorMode('FluxPrimitive',2)
            if kind in ('coil','pipe'):
                for typ,key in [('App::PropertyLength','Diameter')]+(
                    [('App::PropertyLength','Section'),('App::PropertyLength','Pitch'),('App::PropertyFloat','Turns'),('App::PropertyBool','LeftHanded')]
                    if kind=='coil' else [('App::PropertyLength','Wall'),('App::PropertyLength','Length'),('App::PropertyBool','UsePath'),('App::PropertyLinkGlobal','Path'),('App::PropertyLinkGlobal','FluxPath')]):
                    obj.addProperty(typ,key,'Dimensions')
                obj.addProperty('App::PropertyString','Error','FluxCAD');obj.setEditorMode('Error',1)
                if kind=='pipe':obj.setEditorMode('Path',2);obj.setEditorMode('FluxPath',2);obj.setEditorMode('UsePath',2)
                PrimitiveProxy(obj);obj.ViewObject.Proxy=0
        if kind=='sphere':obj.Radius=p['diameter']/2;obj.Angle1=-90;obj.Angle2=90;obj.Angle3=360
        elif kind=='torus':obj.Radius1=p['diameter']/2;obj.Radius2=p['section']/2;obj.Angle1=-180;obj.Angle2=180;obj.Angle3=360
        elif kind=='coil':
            obj.Diameter=p['diameter'];obj.Section=p['section'];obj.Pitch=p['pitch'];obj.Turns=p['turns'];obj.LeftHanded=p['left']
        else:
            previous=obj.Path
            obj.Path=(previous if obj.FluxPath==p['path'] else model._world_source(doc,p['path'])) if p['path'] else None
            obj.FluxPath=p['path'];obj.UsePath=p['path'] is not None;obj.Diameter=p['diameter'];obj.Wall=p['wall'];obj.Length=p['length']
            if previous and previous!=obj.Path and getattr(previous,'FluxCADInternal',False) and not previous.InList:doc.removeObject(previous.Name)
        obj.Placement=pose;doc.recompute()
        check_solid(obj.Shape)
        if getattr(obj,'Error',''):raise ValueError(obj.Error)
        if abs(obj.Shape.Volume-expected.Volume)>max(1e-6,expected.Volume*1e-6):raise ValueError('Primitive preview/result mismatch')
        for dependent in obj.InListRecursive:
            if hasattr(dependent,'Shape') and (dependent.Shape.isNull() or not dependent.Shape.isValid() or 'Invalid' in dependent.State or getattr(dependent,'Error','')
                                               or (dependent.Name in solid_dependents and not dependent.Shape.Solids)):
                raise ValueError(tr('後続の加工が成立しないため変更を取り消しました。','The edit was cancelled because a later feature would become invalid.'))
        if not existing:
            obj.ViewObject.ShapeColor=(.72,.79,.85);obj.ViewObject.LineColor=(.18,.23,.29)
        if kind=='pipe' and p['path']:p['path'].Visibility=False;obj.Path.Visibility=False
    return obj
