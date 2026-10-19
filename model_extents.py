"""Associative extrusion with start offset, taper and end extents."""
import math
import re
import FreeCAD as App
import Part
import model
import model_taper
from i18n import tr


def reference(doc, name, subname):
    obj=doc.getObject(name) if doc else None
    if not obj or not re.search(r'(^|\.)Face[1-9][0-9]*$',subname):
        raise ValueError(tr('終点にする平らな面を選択してください。','Select a planar end face.'))
    obj=obj.getSubObject(subname,1) or obj
    face_name=subname.rsplit('.',1)[-1]
    plane(obj,face_name)
    return obj,face_name


def plane(obj, name):
    if not obj or not hasattr(obj,'Shape') or not re.fullmatch(r'Face[1-9][0-9]*',name):
        raise ValueError(tr('終点の面を選択してください。','Select the end face.'))
    try:face=model.world_shape(obj).getElement(name)
    except Exception:raise ValueError(tr('終点の面がありません。選び直してください。','The end face is missing. Select it again.')) from None
    if not isinstance(face.Surface,Part.Plane):
        raise ValueError(tr('「面まで」は平面に対応しています。曲面は選択できません。','To Face supports planar faces. Curved faces are not supported.'))
    lo,hi,bottom,top=face.ParameterRange
    return face.CenterOfMass,face.normalAt((lo+hi)/2,(bottom+top)/2)


def project_range(shape, axis, origin):
    rotated=shape.copy()
    transform=App.Placement(App.Vector(),App.Rotation(axis,App.Vector(0,0,1)))
    rotated.Placement=transform.multiply(rotated.Placement)
    bounds=rotated.BoundBox
    offset=origin.dot(axis)
    return bounds.ZMin-offset,bounds.ZMax-offset


def tapered_reach(faces, travel, angle, point, normal, reach, low):
    """Find a cap wholly past the end plane, including the expanded profile."""
    merged=faces[0].multiFuse(faces[1:]).removeSplitter() if len(faces)>1 else faces[0]
    margin=max(.001,merged.BoundBox.DiagonalLength*1e-6)
    slope=math.tan(math.radians(angle))
    for attempt in range(12):
        ends=[]
        for face in merged.Faces:
            _,wires=model_taper.section_wires(face,reach*slope)
            for wire in wires:wire.translate(travel*reach);ends.append(wire)
        minimum,_=project_range(Part.makeCompound(ends),normal,point)
        if minimum>=margin*.9:return reach
        rate=(minimum-low)/reach
        if rate<=1e-8:break
        reach+=(margin-minimum)/rate*1.05
        if not math.isfinite(reach) or reach>1e7:break
    raise ValueError(tr('この勾配では終点面まで閉じた形状を作れません。勾配角か終点面の傾きを小さくしてください。',
                        'This taper cannot form a closed shape up to the end plane. Reduce the taper or the end-plane tilt.'))


def clip_to_plane(shape, point, normal):
    center=shape.BoundBox.Center
    center-=normal*((center-point).dot(normal))
    span=shape.BoundBox.DiagonalLength+(shape.BoundBox.Center-center).Length+1
    seed=App.Vector(1,0,0) if abs(normal.x)<.99 else App.Vector(0,1,0)
    u=seed-normal*seed.dot(normal);u.normalize();v=normal.cross(u)
    corners=[center+u*x*span+v*y*span for x,y in ((-1,-1),(1,-1),(1,1),(-1,1),(-1,-1))]
    slab=Part.Face(Part.makePolygon(corners)).extrude(-normal*(2*span))
    return shape.common(slab).removeSplitter()


def tool_shape(faces, normal, extent='face', direction='forward', distance=12, second=6,
               target=None, limit=None, face_name='', taper=0, taper_second=0, start_offset=0, end_offset=0):
    model_taper.validate(taper,taper_second,extent)
    if not math.isfinite(start_offset) or abs(start_offset)>100000:
        raise ValueError(tr('開始オフセットは−100000～100000 mmの数値で指定してください。',
                            'Start Offset must be a finite number between -100000 and 100000 mm.'))
    if not math.isfinite(end_offset) or abs(end_offset)>100000:
        raise ValueError(tr('終点オフセットは−100000～100000 mmの数値で指定してください。',
                            'End Offset must be a finite number between -100000 and 100000 mm.'))
    if end_offset and extent!='face':
        raise ValueError(tr('終点オフセットは範囲「面まで」で使用してください。','End Offset is available with the To Face extent.'))
    if not faces or any(not face.isValid() or face.Area<=1e-9 for face in faces):
        raise ValueError(tr('押し出す閉じた領域を選択してください。','Select a closed profile to extrude.'))
    if direction not in ('forward','reverse','symmetric','two') or extent not in ('distance','face','through'):
        raise ValueError(tr('押し出しの範囲と方向を選択してください。','Select the extrusion extent and direction.'))
    if not all(math.isfinite(v) and v>0 for v in (distance,second)):
        raise ValueError(tr('距離は0より大きい数値で指定してください。','Distances must be positive finite numbers.'))
    normal=App.Vector(normal);normal.normalize()
    if start_offset:
        # Move copies before calculating extents: the sketch and its profile
        # binders stay in place, while distance/taper use the new neutral plane.
        faces=[face.copy() for face in faces]
        for face in faces:face.translate(normal*start_offset)
    profile=Part.makeCompound(faces);origin=faces[0].CenterOfMass
    clipping=None
    if extent=='distance':
        forward,backward=model.extrusion_lengths(distance,direction,second)
    elif extent=='through':
        if not target or not hasattr(target,'Shape') or not target.Shape.Solids:
            raise ValueError(tr('貫通する対象ボディを選択してください。','Select the body to cut through.'))
        shape=model.world_shape(target)
        low,high=project_range(shape,normal,origin)
        # Stay clear of the native Boolean's near-coincident-face tolerance.
        margin=max(.001,shape.BoundBox.DiagonalLength*1e-6)
        if (direction=='forward' and high<=1e-7) or (direction=='reverse' and low>=-1e-7):
            raise ValueError(tr('この方向に対象ボディがありません。逆方向か両方向を選んでください。',
                                'There is no target in this direction. Choose Reverse or Both Directions.'))
        forward=0 if direction=='reverse' else max(0,high)+margin
        backward=0 if direction=='forward' else max(0,-low)+margin
    else:
        if direction not in ('forward','reverse'):
            raise ValueError(tr('「面まで」は片側または逆方向を選択してください。','To Face requires One Side or Reverse.'))
        point,n=plane(limit,face_name);n.normalize()
        travel=normal*(-1 if direction=='reverse' else 1)
        # Offset along the chosen extrusion direction, preserving the end
        # plane's tilt and the original reference face's geometry/placement.
        point=point+travel*end_offset
        dot=n.dot(travel)
        if abs(dot)<1e-7:
            raise ValueError(tr('終点の面と押し出し方向が平行です。別の面を選択してください。',
                                'The end plane is parallel to the extrusion direction. Select another face.'))
        if dot<0:n=-n;dot=-dot
        low,high=project_range(profile,n,point)
        if high>=-1e-7:
            raise ValueError(tr('オフセット後の終点が開始位置の輪郭と交差するか、手前にあります。方向・面・オフセットを確認してください。',
                                'The offset end plane crosses the starting profile or lies behind it. Check the direction, face and offsets.'))
        reach=-low/dot+max(1e-5,profile.BoundBox.DiagonalLength*1e-7)
        if taper:reach=tapered_reach(faces,travel,taper,point,n,reach,low)
        forward,backward=(reach,0) if direction=='forward' else (0,reach)
        clipping=(point,n)
    if taper or (direction=='two' and taper_second):
        result=model_taper.extrude(faces,normal,forward,backward,taper,taper_second if direction=='two' else taper)
        if clipping:result=clip_to_plane(result,*clipping)
        if result.isNull() or not result.isValid() or not result.Solids or result.Volume<=1e-9:raise model_taper.error()
        return result
    shapes=[]
    for face in faces:
        shifted=face.copy();shifted.translate(-normal*backward)
        shape=shifted.extrude(normal*(forward+backward))
        if clipping:shape=clip_to_plane(shape,*clipping)
        shapes.append(shape)
    result=shapes[0].multiFuse(shapes[1:]).removeSplitter() if len(shapes)>1 else shapes[0]
    if result.isNull() or not result.isValid() or not result.Solids or result.Volume<=1e-9:
        raise ValueError(tr('押し出し形状を作成できません。面と輪郭を確認してください。','Could not build the extrusion. Check the face and profile.'))
    return result


def profile_faces(sketch, regions, indices):
    parent=sketch.getGlobalPlacement().multiply(sketch.Placement.inverse())
    faces=[]
    for i in model.profile_indices(regions,indices):
        face=regions[i]['face'].copy();face.Placement=parent.multiply(face.Placement);faces.append(face)
    return faces


def preview(faces, sketch, operation='new', **values):
    if values['extent']=='through' and operation!='cut':
        raise ValueError(tr('貫通は「切り取り」で使用してください。','Through All is available for Cut.'))
    tool=tool_shape(faces,sketch.getGlobalPlacement().Rotation.multVec(App.Vector(0,0,1)),**values)
    return model.extrusion_result(tool,values.get('target'),operation)


def tool(obj):return obj if hasattr(obj,'SourceSketch') else obj.Tool


def settings(obj):
    source=tool(obj);limit,names=source.Limit or (None,[])
    return dict(extent=str(source.Extent),direction=str(source.Direction),distance=source.Distance.Value,
                second=source.Second.Value,target=source.Target,limit=limit,face_name=names[0] if names else '',
                taper=float(getattr(source,'TaperAngle',0)),taper_second=float(getattr(source,'TaperAngleRev',0)),
                start_offset=float(getattr(source,'StartOffset',0)),
                end_offset=float(getattr(source,'EndOffset',0)),
                operation={'Part::Cut':'cut','Part::Fuse':'join','Part::Common':'intersect'}.get(obj.TypeId,'new'))


def stored_faces(obj):
    faces=[]
    for source in tool(obj).Profiles:faces.extend(model.world_shape(source).Faces)
    return faces


def signature(objects):
    return tuple((o.Name,o.Shape.hashCode(),str(o.getGlobalPlacement())) for o in objects if o)


class ExtentTool:
    def execute(self,obj):
        try:
            limit,names=obj.Limit or (None,[])
            shape=tool_shape(stored_faces(obj),obj.SourceSketch.getGlobalPlacement().Rotation.multVec(App.Vector(0,0,1)),
                                 extent=str(obj.Extent),direction=str(obj.Direction),distance=obj.Distance.Value,second=obj.Second.Value,
                                 target=obj.Target,limit=limit,face_name=names[0] if names else '',
                                 taper=float(getattr(obj,'TaperAngle',0)),taper_second=float(getattr(obj,'TaperAngleRev',0)),
                                 start_offset=float(getattr(obj,'StartOffset',0)),end_offset=float(getattr(obj,'EndOffset',0)))
            # Keep world-space child geometry separate from the feature's own
            # movable placement, including when an attached sketch is tilted.
            shape=Part.makeCompound([shape]);shape.Placement=App.Placement(obj.Placement)
            obj.Shape=shape
        except Exception:
            obj.Shape=Part.Shape()
            raise
    def dumps(self):return None
    def loads(self,state):pass


def dependencies(obj, sources):
    parents=[]
    for source in sources:
        parent=source.getParentGeoFeatureGroup() if source else None
        while parent:
            if parent not in parents:parents.append(parent)
            parent=parent.getParentGeoFeatureGroup()
    obj.SourceContainers=parents


def create(doc, sketch, indices=None, existing=None, operation='new', **values):
    refs=[sketch,values.get('target'),values.get('limit')]
    if any(o and o.Document!=doc for o in refs) or (existing and existing.Document!=doc):
        raise ValueError(tr('同じ文書内の形状を選択してください。','Select geometry in the same document.'))
    if existing:
        if any(o and (o==existing or o in existing.InListRecursive) for o in refs):
            raise ValueError(tr('自分自身や後の加工を参照することはできません。','Cannot reference this extrusion or a downstream feature.'))
        if operation!=settings(existing)['operation']:
            raise ValueError(tr('再編集では操作の種類を変更できません。','The operation cannot be changed while editing.'))
        faces=stored_faces(existing);groups=[None];regions=None
    else:
        regions=model.profiles(sketch);indices=model.profile_indices(regions,indices)
        faces=profile_faces(sketch,regions,indices)
        groups=model._connected_profiles(regions,indices) if operation=='new' else [indices]
    expected=preview(faces,sketch,operation,**values)
    if existing:expected.Placement=existing.Placement.multiply(expected.Placement)
    visibility=[(o,bool(o.Visibility)) for o in doc.Objects if hasattr(o,'Visibility')]
    solid_dependents={o.Name for o in existing.InListRecursive if hasattr(o,'Shape') and o.Shape.Solids} if existing else set()
    try:
        with model.transaction(doc,tr('押し出しを編集','Edit Extrusion') if existing else tr('押し出し','Extrude')):
            results=[]
            for group in groups:
                if existing:result=existing;feature=tool(existing)
                else:
                    sources=[]
                    for i in group:
                        region=regions[i]
                        source=model._split_profile_source(doc,sketch,region)
                        sources.append(source)
                    base=model._world_source(doc,values['target']) if operation!='new' else None
                    doc.recompute()
                    feature=doc.addObject('Part::FeaturePython','ExtentExtrude');feature.Label=tr('押し出し','Extrude')
                    for name,prop in (('SourceSketch','App::PropertyLinkGlobal'),('Profiles','App::PropertyLinkListGlobal'),
                                      ('SourceContainers','App::PropertyLinkListGlobal'),('Limit','App::PropertyLinkSubGlobal'),
                                      ('Target','App::PropertyLinkGlobal'),('Distance','App::PropertyLength'),('Second','App::PropertyLength'),
                                      ('Extent','App::PropertyEnumeration'),('Direction','App::PropertyEnumeration')):
                        feature.addProperty(prop,name,'Extrusion')
                    feature.Extent=['distance','face','through'];feature.Direction=['forward','reverse','symmetric','two']
                    feature.SourceSketch=sketch;feature.Profiles=sources
                    feature.Proxy=ExtentTool();feature.ViewObject.Proxy=0
                    for prop in ('SourceSketch','Profiles','SourceContainers'):feature.setEditorMode(prop,2)
                    result=feature
                    if base:
                        model._internal(feature)
                        result=doc.addObject({'cut':'Part::Cut','join':'Part::Fuse','intersect':'Part::Common'}[operation],'ExtentOperation')
                        result.Label=tr('押し出し（%s）')%{'cut':tr('切り取り'),'join':tr('結合'),'intersect':tr('交差')}[operation]
                        result.Base=base;result.Tool=feature;result.Refine=True
                        result.addProperty('App::PropertyLinkGlobal','FluxBodySource','FluxCAD');result.FluxBodySource=values['target']
                        result.setEditorMode('FluxBodySource',2)
                    result.addProperty('App::PropertyBool','FluxExtent','FluxCAD');result.FluxExtent=True;result.setEditorMode('FluxExtent',2)
                for name,key in (('TaperAngle','taper'),('TaperAngleRev','taper_second')):
                    if name not in feature.PropertiesList:feature.addProperty('App::PropertyAngle',name,'Extrusion')
                    setattr(feature,name,values.get(key,0))
                if 'StartOffset' not in feature.PropertiesList:
                    feature.addProperty('App::PropertyDistance','StartOffset','Extrusion',
                                        tr('スケッチの片側方向を正とする開始位置の距離。','Start plane distance along the sketch forward normal.'))
                feature.StartOffset=values.get('start_offset',0)
                if 'EndOffset' not in feature.PropertiesList:
                    feature.addProperty('App::PropertyDistance','EndOffset','Extrusion',
                                        tr('終点面から押し出し方向に測る距離。正で延長、負で手前に停止。',
                                           'Distance from the end face along the extrusion direction. Positive extends; negative stops short.'))
                feature.EndOffset=values.get('end_offset',0)
                feature.Extent=values['extent'];feature.Direction=values['direction']
                feature.Distance=values['distance'];feature.Second=values['second']
                feature.Target=values.get('target') if operation!='new' else None
                feature.Limit=(values['limit'],[values['face_name']]) if values['extent']=='face' else None
                dependencies(feature,[sketch,feature.Target,feature.Limit[0] if feature.Limit else None])
                model.check(result)
                if not existing:result.Visibility=True
                results.append(result)
                for source in feature.Profiles:source.Visibility=False
                if operation!='new':feature.Visibility=False;result.Base.Visibility=False;feature.Target.Visibility=False
            actual=Part.makeCompound([o.Shape for o in results])
            tolerance=max(1e-6,expected.Volume*1e-7)
            if abs(actual.Volume-expected.Volume)>tolerance or abs(actual.common(expected).Volume-expected.Volume)>tolerance:
                raise ValueError(tr('プレビューと作成結果が一致しないため、操作を取り消しました。'))
            for result in results:
                for later in result.InListRecursive:
                    if hasattr(later,'Shape') and (later.Shape.isNull() or not later.Shape.isValid() or 'Invalid' in later.State
                                                   or (later.Name in solid_dependents and not later.Shape.Solids)):
                        raise ValueError(tr('後の加工を更新できないため、変更を取り消しました。'))
            if not existing:sketch.Visibility=len(indices)<len(regions)
        return results
    except Exception:
        for obj,visible in visibility:
            if obj.Document:obj.Visibility=visible
        raise
