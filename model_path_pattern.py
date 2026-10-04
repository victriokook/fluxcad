"""Body patterns spaced by arc length on a linked wire or sketch."""
import bisect
import math
import FreeCAD as App
import Part
import model
import model_sections
from i18n import tr


def title():return tr('パスに沿ったパターン','Pattern on Path')


class Path:
    def __init__(self,obj,wire=None):
        if obj is None or 'Invalid' in obj.State or getattr(obj,'Error',''):
            raise ValueError(tr('有効な経路を選んでください。','Select a valid path.'))
        self.wire=model_sections.wire(obj,False) if wire is None else wire
        self.edges=self.wire.OrderedEdges
        self.ends=[];self.length=0
        if len(self.edges)!=len(self.wire.Edges):raise ValueError(tr('枝分かれのない経路を選んでください。','Select a path without branches.'))
        previous=None;first=None
        for edge in self.edges:
            start,end=(edge.LastParameter,edge.FirstParameter) if edge.Orientation=='Reversed' else (edge.FirstParameter,edge.LastParameter)
            if edge.Length<1e-7 or (previous is not None and (edge.valueAt(start)-previous).Length>1e-6):
                raise ValueError(tr('経路の線を端点でつないでください。','Connect the path edges at their endpoints.'))
            if first is None:first=edge.valueAt(start)
            previous=edge.valueAt(end);self.length+=edge.Length;self.ends.append(self.length)
        if not self.edges:raise ValueError(tr('経路が空です。','The path is empty.'))
        self.closed=self.wire.isClosed()
        if self.closed and (first-previous).Length>1e-6:raise ValueError('Invalid closed path')

    def at(self,distance,reverse=False):
        s=self.length-distance if reverse else distance
        s=max(0,min(self.length,s))
        # At a corner use the outgoing edge in the selected traversal direction.
        index=(bisect.bisect_left(self.ends,s) if reverse else bisect.bisect_right(self.ends,s))
        index=min(index,len(self.edges)-1)
        edge=self.edges[index];local=s-(self.ends[index-1] if index else 0)
        backwards=edge.Orientation=='Reversed'
        local=edge.Length-local if backwards else local
        parameter=edge.getParameterByLength(max(0,min(edge.Length,local)))
        tangent=edge.tangentAt(parameter)*(-1 if backwards else 1)*(-1 if reverse else 1)
        tangent.normalize()
        return edge.valueAt(parameter),tangent


def validate(count=4,mode='full',distance=10,orientation='fixed',reverse=False):
    if not math.isfinite(count) or int(count)!=count or not 2<=count<=200:
        raise ValueError(tr('個数は元を含めて2～200個で指定してください。','Enter 2 to 200 instances, including the original.'))
    if mode not in ('full','spacing','extent') or orientation not in ('fixed','tangent'):
        raise ValueError(tr('配置方法と向きを選んでください。','Select a distribution and orientation.'))
    if not math.isfinite(distance) or not .001<=distance<=1000000:
        raise ValueError(tr('距離は0.001～1000000 mmで指定してください。','Enter a distance from 0.001 to 1000000 mm.'))
    return dict(count=int(count),mode=mode,distance=distance,orientation=orientation,reverse=bool(reverse))


def distances(path,count,mode,distance):
    tolerance=max(1e-7,path.length*1e-9)
    extent=path.length if mode=='full' else distance*(count-1) if mode=='spacing' else distance
    if extent>path.length+tolerance:
        raise ValueError(tr('配置の距離が経路の長さを超えています。個数か距離を減らしてください。',
                            'The pattern exceeds the path length. Reduce quantity or distance.'))
    full_circle=path.closed and abs(extent-path.length)<=tolerance
    if mode=='spacing' and full_circle:
        raise ValueError(tr('最後の複製が始点と重なります。間隔を小さくするか「経路全体」を選んでください。',
                            'The last instance repeats the start. Reduce spacing or choose Entire Path.'))
    step=min(extent,path.length)/(count if full_circle else count-1)
    return [i*step for i in range(count)]


def placements(path,positions,orientation,reverse,up=None):
    origin,initial=path.at(0,reverse)
    if orientation=='fixed':return [App.Placement(path.at(s,reverse)[0]-origin,App.Rotation()) for s in positions]
    # Transport the frame in short steps. This avoids arbitrary half-turn flips
    # on circles and keeps the up direction continuous through 3D curves.
    end=positions[-1];events=set(positions)
    steps=max(1,int(math.ceil(end/path.length*128)))
    events.update(end*i/steps for i in range(steps+1))
    epsilon=max(1e-8,path.length*1e-10)
    for boundary in path.ends[:-1]:
        s=path.length-boundary if reverse else boundary
        events.update(v for v in (s-epsilon,s,s+epsilon) if 0<v<end)
    rotation=App.Rotation();previous=initial;frames={}
    up=App.Vector(up) if up is not None else App.Vector(0,0,1) if abs(initial.z)<.9 else App.Vector(0,1,0)
    up-=initial*up.dot(initial);up.normalize()
    for s in sorted(events):
        point,tangent=path.at(s,reverse)
        if previous.dot(tangent)<-1+1e-9:
            delta=App.Rotation(rotation.multVec(up),180)
        else:delta=App.Rotation(previous,tangent)
        rotation=delta.multiply(rotation);previous=tangent
        if s in positions:frames[s]=App.Placement(point-rotation.multVec(origin),rotation)
    return [frames[s] for s in positions]


def check_sources(doc,source,path,existing=None):
    if source is None or path is None:
        raise ValueError(tr('ボディと経路を選んでください。','Select a body and a path.'))
    if source.Document!=doc or path.Document!=doc or (existing and existing.Document!=doc):
        raise ValueError(tr('同じ文書内のボディと経路を選んでください。','Select the body and path in the same document.'))
    if existing and (not getattr(existing,'FluxPathPattern',False) or any(o==existing or existing in o.OutListRecursive for o in (source,path))):
        raise ValueError(tr('このパターン自身や後続の加工は参照できません。','Cannot reference this pattern or its descendants.'))
    shape=model.world_shape(source)
    if shape.isNull() or not shape.isValid() or not shape.Solids or 'Invalid' in source.State or getattr(source,'Error',''):
        raise ValueError(tr('有効なソリッドボディを選んでください。','Select a valid solid body.'))
    return shape,Path(path)


def build(source,path,**values):
    p=validate(**values);base,curve=check_sources(source.Document if source else None,source,path)
    if len(base.Solids)*p['count']>2000:
        raise ValueError(tr('結果の立体は合計2000個以内にしてください。','Use at most 2000 solids in the result.'))
    positions=distances(curve,p['count'],p['mode'],p['distance'])
    shapes=[]
    for pose in placements(curve,positions,p['orientation'],p['reverse']):
        shape=base.copy();shape.Placement=pose.multiply(shape.Placement);shapes.append(shape)
    result=Part.makeCompound(shapes)
    if not result.isValid():raise ValueError(tr('パターンを作成できません。','Cannot create this pattern.'))
    return result,curve.length,positions[-1]


def settings(obj):
    return dict(count=obj.Count,mode=str(obj.Distribution),distance=obj.Distance.Value,
                orientation=str(obj.Orientation),reverse=obj.Reverse)


class PathPattern:
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        pose=App.Placement(obj.Placement)
        try:
            if obj.FluxBodySource is None or obj.FluxPath is None:
                raise ValueError(tr('元のボディまたは経路がありません。参照を選び直してください。','The source body or path is missing. Select new references.'))
            result,length,extent=build(obj.Source,obj.Path,**settings(obj))
            obj.Shape=result;obj.Placement=pose;obj.PathLength=length;obj.Extent=extent;obj.Error=''
        except Exception as error:
            obj.Shape=Part.Shape();obj.Placement=pose;obj.PathLength=0;obj.Extent=0;obj.Error=str(error)
    def dumps(self):return None
    def loads(self,state):pass


def create(doc,source,path,existing=None,**values):
    p=validate(**values);check_sources(doc,source,path,existing)
    expected,_,_=build(source,path,**p)
    pose=App.Placement(existing.Placement) if existing else App.Placement()
    expected.Placement=pose.multiply(expected.Placement)
    solid_dependents={o.Name for o in existing.InListRecursive if hasattr(o,'Shape') and o.Shape.Solids} if existing else set()
    with model.transaction(doc,title()):
        obj=existing
        if obj is None:
            obj=doc.addObject('Part::FeaturePython','PathPattern');obj.Label=title()
            for typ,key in [('App::PropertyBool','FluxPathPattern'),('App::PropertyLinkGlobal','Source'),
                ('App::PropertyLinkGlobal','FluxBodySource'),('App::PropertyLinkGlobal','Path'),('App::PropertyLinkGlobal','FluxPath'),
                ('App::PropertyInteger','Count'),('App::PropertyEnumeration','Distribution'),('App::PropertyLength','Distance'),
                ('App::PropertyEnumeration','Orientation'),('App::PropertyBool','Reverse'),
                ('App::PropertyLength','PathLength'),('App::PropertyLength','Extent'),('App::PropertyString','Error')]:
                obj.addProperty(typ,key,'Pattern')
            obj.FluxPathPattern=True;obj.Distribution=['full','spacing','extent'];obj.Orientation=['fixed','tangent']
            for key in ('FluxPathPattern','Source','FluxBodySource','Path','FluxPath'):obj.setEditorMode(key,2)
            for key in ('PathLength','Extent','Error'):obj.setEditorMode(key,1)
            PathPattern(obj);obj.ViewObject.Proxy=0
        old=[obj.Source,obj.Path]
        obj.Source=obj.Source if obj.FluxBodySource==source and obj.Source else model._world_source(doc,source)
        obj.Path=obj.Path if obj.FluxPath==path and obj.Path else model._world_source(doc,path)
        obj.FluxBodySource=source;obj.FluxPath=path
        obj.Count=p['count'];obj.Distribution=p['mode'];obj.Distance=p['distance'];obj.Orientation=p['orientation'];obj.Reverse=p['reverse']
        obj.Placement=pose;doc.recompute()
        if obj.Error:raise ValueError(obj.Error)
        if obj.Shape.isNull() or not obj.Shape.isValid() or len(obj.Shape.Solids)!=len(expected.Solids) or abs(obj.Shape.Volume-expected.Volume)>max(1e-6,expected.Volume*1e-7):
            raise ValueError(tr('プレビューと結果が一致しないため変更を取り消しました。','The result differs from the preview; the edit was cancelled.'))
        for dependent in obj.InListRecursive:
            if hasattr(dependent,'Shape') and (dependent.Shape.isNull() or not dependent.Shape.isValid() or 'Invalid' in dependent.State or getattr(dependent,'Error','') or (dependent.Name in solid_dependents and not dependent.Shape.Solids)):
                raise ValueError(tr('後続の加工が成立しないため変更を取り消しました。','The edit would invalidate a later feature and was cancelled.'))
        if not existing:
            for prop in ('ShapeColor','LineColor','PointColor','Transparency','DisplayMode'):setattr(obj.ViewObject,prop,getattr(source.ViewObject,prop))
        for item in (source,path,obj.Source,obj.Path):item.Visibility=False
        for item in old:
            if item and item not in (obj.Source,obj.Path) and getattr(item,'FluxCADInternal',False) and not item.InList:doc.removeObject(item.Name)
    return obj
