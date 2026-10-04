"""A plane split with two independently placed, source-driven solid outputs."""
import math
import re
import FreeCAD as App
import Part
import model
from i18n import tr


def operation(obj):
    return obj if getattr(obj,'FluxSplit',False) else obj.Source if getattr(obj,'FluxSplitPart',False) else None


def outputs(obj):
    return sorted((o for o in obj.InList if getattr(o,'FluxSplitPart',False) and o.Source==obj),key=lambda o:o.Side)


def settings(obj):
    ref,names=obj.Support or (None,[])
    return dict(mode=str(obj.PlaneMode),reference=ref,face=names[0] if names else '',offset=obj.Offset.Value)


def plane(mode='XY',reference=None,face='',offset=0):
    if not math.isfinite(offset) or abs(offset)>100000:
        raise ValueError(tr('切断位置は−100000～100000 mmで指定してください。','Enter an offset between -100000 and 100000 mm.'))
    if mode in ('XY','XZ','YZ'):
        normal={'XY':App.Vector(0,0,1),'XZ':App.Vector(0,1,0),'YZ':App.Vector(1,0,0)}[mode]
        origin=App.Vector()
    elif mode=='face':
        if not reference or not hasattr(reference,'Shape') or not re.fullmatch(r'Face[1-9][0-9]*',face):
            raise ValueError(tr('切断の基準となる平らな面を選択してください。','Select a planar reference face.'))
        try:surface=model.world_shape(reference).getElement(face)
        except Exception:raise ValueError(tr('参照面がありません。選び直してください。','The reference face is missing. Reselect it.')) from None
        if not isinstance(surface.Surface,Part.Plane):
            raise ValueError(tr('曲面では分割できません。平らな面を選択してください。','Select a planar face; curved splitting surfaces are not supported.'))
        a,b,c,d=surface.ParameterRange
        normal=surface.normalAt((a+b)/2,(c+d)/2);normal.normalize()
        origin=normal*surface.CenterOfMass.dot(normal)
    else:raise ValueError(tr('切断平面を指定してください。','Choose a splitting plane.'))
    return origin+normal*offset,normal


def preview(source,mode='XY',reference=None,face='',offset=0):
    if not source or not hasattr(source,'Shape') or hasattr(source,'Mesh'):
        raise ValueError(tr('分割するソリッドを選択してください。','Select a solid to split.'))
    shape=model.world_shape(source)
    if shape.isNull() or not shape.isValid() or len(shape.Solids)!=1:
        raise ValueError(tr('1つにつながったソリッドを選択してください。','Select one connected solid.'))
    origin,normal=plane(mode,reference,face,offset)
    rotation=App.Rotation(App.Vector(0,0,1),normal)
    pose=App.Placement(origin,rotation);bounds=shape.BoundBox
    corners=[pose.inverse().multVec(App.Vector(x,y,z)) for x in (bounds.XMin,bounds.XMax)
             for y in (bounds.YMin,bounds.YMax) for z in (bounds.ZMin,bounds.ZMax)]
    pad=max(1,bounds.DiagonalLength*.05)
    lo=[min(getattr(p,axis) for p in corners)-pad for axis in 'xyz']
    hi=[max(getattr(p,axis) for p in corners)+pad for axis in 'xyz']
    if lo[2]>=0 or hi[2]<=0:
        raise ValueError(tr('平面がボディを横切っていません。切断位置を調整してください。','The plane does not cross the body. Adjust the offset.'))
    pieces=[]
    for z,height in ((lo[2],-lo[2]),(0,hi[2])):
        tool=Part.makeBox(hi[0]-lo[0],hi[1]-lo[1],height,App.Vector(lo[0],lo[1],z))
        tool.Placement=pose.multiply(tool.Placement)
        result=shape.common(tool).removeSplitter()
        if result.isNull() or not result.isValid() or not result.Solids or result.Volume<=max(1e-9,shape.Volume*1e-10):
            raise ValueError(tr('平面がボディの内部を横切るように切断位置を調整してください。','Move the plane through the interior of the body.'))
        if len(result.Solids)!=1:
            raise ValueError(tr('この位置では3個以上に分かれます。今回は両側に1個ずつ残る位置を指定してください。',
                                'This cut creates more than two pieces. Choose a plane leaving one connected solid on each side.'))
        # Identity outer placement lets each output own its independent transform.
        pieces.append(Part.makeCompound([result.Solids[0]]))
    tolerance=max(1e-7,shape.Volume*1e-7)
    if abs(sum(s.Volume for s in pieces)-shape.Volume)>tolerance or pieces[0].common(pieces[1]).Volume>tolerance:
        raise ValueError(tr('分割結果を検証できません。切断位置を変更してください。','Could not validate the split. Change the plane offset.'))
    marker=Part.makePlane(hi[0]-lo[0],hi[1]-lo[1],App.Vector(lo[0],lo[1],0))
    marker.Placement=pose.multiply(marker.Placement)
    return pieces,marker


class SplitFeature:
    def execute(self,obj):
        try:
            parts,_=preview(obj.FluxBodySource,**settings(obj))
            obj.Shape=Part.makeCompound(parts)
        except Exception:
            obj.Shape=Part.Shape()
            # FreeCAD can skip a dependent's execute after its source failed.
            # Clear our outputs now so obsolete solids are never shown as valid.
            for part in outputs(obj):
                pose=App.Placement(part.Placement)
                part.Shape=Part.Shape();part.Placement=pose
            raise
    def dumps(self):return None
    def loads(self,state):pass


class SplitPart:
    def execute(self,obj):
        pose=App.Placement(obj.Placement)
        try:
            if not obj.Source or 'Invalid' in obj.Source.State:raise ValueError('Invalid split source')
            parts=obj.Source.Shape.childShapes()
            if len(parts)!=2:raise ValueError('Missing split results')
            obj.Shape=parts[obj.Side].copy();obj.Placement=pose
        except Exception:
            obj.Shape=Part.Shape();obj.Placement=pose
            raise
    def dumps(self):return None
    def loads(self,state):pass


def check_reference(doc,source,reference,existing=None):
    if source.Document!=doc or (reference and reference.Document!=doc) or (existing and existing.Document!=doc):
        raise ValueError(tr('同じ文書内のボディと平面を選択してください。','Select a body and plane in the same document.'))
    if existing:
        if source!=existing.FluxBodySource:raise ValueError(tr('分割元のボディは変更できません。','The original split body cannot be replaced.'))
        if reference and (reference==existing or existing in reference.OutListRecursive):
            raise ValueError(tr('分割結果やその後の加工は切断の基準にできません。','A split result or downstream feature cannot be its splitting reference.'))


def create(doc,source,mode='XY',reference=None,face='',offset=0,existing=None):
    if mode!='face':reference=None;face=''
    check_reference(doc,source,reference,existing)
    expected,_=preview(source,mode,reference,face,offset)
    visible=[(o,bool(o.Visibility)) for o in doc.Objects if hasattr(o,'Visibility')]
    dependents={o.Name for o in existing.InListRecursive if hasattr(o,'Shape') and o.Shape.Solids} if existing else set()
    try:
        with model.transaction(doc,tr('ボディ分割を編集','Edit Split Body') if existing else tr('ボディを分割','Split Body')):
            obj=existing
            if obj is None:
                obj=doc.addObject('Part::FeaturePython','Split');obj.Label=tr('ボディを分割','Split Body')
                obj.addProperty('App::PropertyBool','FluxSplit','FluxCAD');obj.FluxSplit=True
                obj.addProperty('App::PropertyLinkGlobal','FluxBodySource','Split');obj.FluxBodySource=source
                obj.addProperty('App::PropertyEnumeration','PlaneMode','Split');obj.PlaneMode=['XY','XZ','YZ','face']
                obj.addProperty('App::PropertyLinkSubGlobal','Support','Split')
                obj.addProperty('App::PropertyDistance','Offset','Split')
                obj.addProperty('App::PropertyLinkListGlobal','SourceContainers','Split')
                obj.Proxy=SplitFeature();obj.ViewObject.Proxy=0
                obj.setEditorMode('FluxSplit',2);obj.setEditorMode('SourceContainers',2);obj.setEditorMode('Placement',1)
                for side in (0,1):
                    part=doc.addObject('Part::FeaturePython','SplitBody');part.Label=tr('分割ボディ %d','Split Body %d')%(side+1)
                    part.addProperty('App::PropertyBool','FluxSplitPart','FluxCAD');part.FluxSplitPart=True
                    part.addProperty('App::PropertyLink','Source','Split');part.Source=obj
                    part.addProperty('App::PropertyInteger','Side','Split');part.Side=side
                    for prop in ('FluxSplitPart','Source','Side'):part.setEditorMode(prop,2)
                    part.Proxy=SplitPart();part.ViewObject.Proxy=0
                    part.ViewObject.ShapeColor=source.ViewObject.ShapeColor;part.ViewObject.LineColor=source.ViewObject.LineColor
            parents=[]
            for input_obj in [source]+([reference] if reference else []):
                parent=input_obj.getParentGeoFeatureGroup()
                while parent:
                    if parent not in parents:parents.append(parent)
                    parent=parent.getParentGeoFeatureGroup()
            obj.SourceContainers=parents;obj.PlaneMode=mode;obj.Support=(reference,[face]) if reference else None;obj.Offset=offset
            doc.recompute()
            for feature in [obj]+obj.InListRecursive:
                if hasattr(feature,'Shape') and (feature.Shape.isNull() or not feature.Shape.isValid() or 'Invalid' in feature.State
                                                  or (feature.Name in dependents and not feature.Shape.Solids)):
                    raise ValueError(tr('分割または後の加工を更新できないため、変更を取り消しました。','The split or a later operation could not update. The change was cancelled.'))
            for part in outputs(obj):
                target=expected[part.Side].copy();target.Placement=part.getGlobalPlacement().multiply(target.Placement)
                actual=model.world_shape(part);tol=max(1e-7,target.Volume*1e-7)
                if abs(actual.Volume-target.Volume)>tol or abs(actual.common(target).Volume-target.Volume)>tol:
                    raise ValueError(tr('プレビューと分割結果が一致しません。','The split result differs from the preview.'))
            obj.Visibility=False;source.Visibility=False
            if not existing:
                for part in outputs(obj):part.Visibility=True
        return obj
    except Exception:
        for obj,state in visible:
            if obj.Document:obj.Visibility=state
        raise
