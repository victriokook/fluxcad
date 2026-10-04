"""Parametric instances and acyclic, as-built rigid/revolute/slider joints."""
import math
import FreeCAD as App
import Part
import model
from i18n import tr


def components(doc):
    return [o for o in doc.Objects if getattr(o,'FluxComponent',False)] if doc else []


def joints(doc):
    return [o for o in doc.Objects if getattr(o,'FluxJoint',False)] if doc else []


def valid_component(obj):
    if not obj or not getattr(obj,'FluxComponent',False) or obj.getParentGeoFeatureGroup():
        raise ValueError(tr('同じ文書のコンポーネントを選択してください。','Select components in the same document.'))
    if getattr(obj,'AssemblyError','') or obj.Shape.isNull() or not obj.Shape.isValid() or not obj.Shape.Solids or 'Invalid' in obj.State:
        raise ValueError(tr('コンポーネントの元形状にエラーがあります。','The component source has a geometry error.'))
    return obj


def local_shape(source):
    if not source or not hasattr(source,'Shape') or 'Invalid' in source.State:
        raise ValueError(tr('元のボディがありません。','The source body is missing or invalid.'))
    shape=source.Shape.copy();shape.Placement=App.Placement()
    if shape.isNull() or not shape.isValid() or not shape.Solids:
        raise ValueError(tr('有効なソリッドボディを選択してください。','Select a valid solid body.'))
    return Part.makeCompound(shape.Solids)


class Component:
    def execute(self,obj):
        pose=App.Placement(obj.Placement)
        try:
            if obj.Driver and not obj.Driver.Valid:
                raise ValueError(tr('ジョイントの参照や設定を修正してください。','Correct the joint references or settings.'))
            obj.Shape=local_shape(obj.Source);obj.Placement=pose;obj.AssemblyError=''
        except Exception as error:
            obj.Shape=Part.Shape();obj.Placement=pose
            obj.AssemblyError=str(error)
            # Do not abort recompute: dependent joints must also clear their geometry.
    def dumps(self):return None
    def loads(self,state):pass


def _component(doc,source,pose,label,grounded=False):
    obj=doc.addObject('Part::FeaturePython','Component');obj.Label=label
    for kind,name in [('App::PropertyBool','FluxComponent'),('App::PropertyLinkGlobal','Source'),
                      ('App::PropertyLink','Driver'),('App::PropertyBool','Grounded'),('App::PropertyPlacement','GroundPose'),
                      ('App::PropertyString','AssemblyError')]:
        obj.addProperty(kind,name,'Assembly')
    obj.FluxComponent=True;obj.Source=source;obj.Proxy=Component();obj.ViewObject.Proxy=0
    for name in ('FluxComponent','Driver','GroundPose'):obj.setEditorMode(name,2)
    for name in ('Source','Grounded','AssemblyError'):obj.setEditorMode(name,1)
    obj.Placement=pose;obj.GroundPose=pose;obj.Grounded=grounded
    if grounded:obj.setExpression('Placement','GroundPose')
    for prop in ('ShapeColor','LineColor','PointColor','Transparency'):
        setattr(obj.ViewObject,prop,getattr(source.ViewObject,prop))
    return obj


def create_components(doc,objects,name='',grounded=False,keep_sources=False,duplicate=False):
    objects=list(dict.fromkeys(objects))
    if not objects or any(o.Document!=doc for o in objects):
        raise ValueError(tr('同じ文書のボディを1つ以上選択してください。','Select at least one body in this document.'))
    sources=[]
    for obj in objects:
        if duplicate:
            valid_component(obj);source=obj.Source
        else:
            if getattr(obj,'FluxComponent',False) or getattr(obj,'FluxCADInternal',False) or obj.TypeId=='Sketcher::SketchObject':
                raise ValueError(tr('元ボディを選択してください。部品の複製は「コンポーネントを複製」を使います。',
                                    'Select source bodies. Use Duplicate Component for existing components.'))
            from browser import collect
            if obj not in [o for o,t in collect(doc)[0]]:
                raise ValueError(tr('ブラウザーの現在のボディを選択してください。','Select current bodies from the browser.'))
            source=obj
        local_shape(source);sources.append(source)
    visible=[(o,bool(o.Visibility)) for o in objects]
    try:
        with model.transaction(doc,tr('コンポーネントを複製','Duplicate Component') if duplicate else tr('コンポーネントを作成','Create Components')):
            result=[]
            for i,(original,source) in enumerate(zip(objects,sources)):
                label=name.strip() or original.Label+(tr(' (複製)',' (Instance)') if duplicate else tr(' 部品',' Component'))
                if name.strip() and len(objects)>1:label+=' %d'%(i+1)
                obj=_component(doc,source,App.Placement(original.getGlobalPlacement()),label,grounded)
                result.append(obj)
                if not keep_sources and not duplicate:original.Visibility=False
            doc.recompute()
            for obj,original in zip(result,objects):
                valid_component(obj)
                expected=model.world_shape(original);actual=model.world_shape(obj)
                if abs(expected.common(actual).Volume-expected.Volume)>max(1e-6,expected.Volume*1e-6):
                    raise ValueError(tr('元形状の位置を再現できません。','Could not preserve the source placement.'))
            return result
    except Exception:
        for obj,state in visible:
            if obj.Document:obj.Visibility=state
        raise


def edit_component(obj,name,grounded):
    valid_component(obj)
    if not name.strip():raise ValueError(tr('名前を入力してください。','Enter a name.'))
    if grounded and obj.Driver:
        raise ValueError(tr('ジョイントで動く部品は接地できません。先にジョイントを解除してください。',
                            'A driven component cannot be grounded. Release its joint first.'))
    with model.transaction(obj.Document,tr('コンポーネントを編集','Edit Component')):
        pose=App.Placement(obj.Placement);obj.Label=name.strip()
        if bool(obj.Grounded)!=bool(grounded):
            obj.setExpression('Placement',None);obj.GroundPose=pose;obj.Grounded=bool(grounded)
            if grounded:obj.setExpression('Placement','GroundPose')
            obj.Placement=pose
        obj.Document.recompute();valid_component(obj)
    return obj


def joint_label(kind):
    return {'rigid':tr('固定ジョイント','Rigid Joint'),'revolute':tr('回転ジョイント','Revolute Joint'),
            'slider':tr('スライダージョイント','Slider Joint')}[kind]


def parameters(kind='rigid',origin=(0,0,0),axis=(0,0,1),angle=0,limited=False,minimum=-90,maximum=90,
               distance=0,distance_limited=False,distance_minimum=-50,distance_maximum=50):
    if kind not in ('rigid','revolute','slider') or len(origin)!=3 or len(axis)!=3:
        raise ValueError(tr('有効なジョイントの種類と軸を指定してください。','Specify a valid joint type and axis.'))
    if not all(math.isfinite(v) for v in (*origin,*axis,angle,minimum,maximum,distance,distance_minimum,distance_maximum)):
        raise ValueError(tr('座標・角度・距離には有限の数値を指定してください。','Coordinates, angles and distances must be finite.'))
    direction=App.Vector(*axis)
    if direction.Length<1e-9:raise ValueError(tr('軸方向を0以外にしてください。','The axis direction must be nonzero.'))
    direction.normalize()
    if kind=='revolute' and limited and (minimum>maximum or not minimum<=angle<=maximum):
        raise ValueError(tr('角度を可動範囲の最小値と最大値の間にしてください。','Angle must be between the lower and upper limits.'))
    if abs(angle)>360000 or max(abs(minimum),abs(maximum))>360000:
        raise ValueError(tr('角度は±360000°以内にしてください。','Angles must be within ±360000 degrees.'))
    if kind=='slider' and distance_limited and (distance_minimum>distance_maximum or not distance_minimum<=distance<=distance_maximum):
        raise ValueError(tr('移動距離を可動範囲の最小値と最大値の間にしてください。','Distance must be between the lower and upper limits.'))
    if max(abs(v) for v in (distance,distance_minimum,distance_maximum))>1e6:
        raise ValueError(tr('距離は±1000000 mm以内にしてください。','Distances must be within ±1000000 mm.'))
    return dict(kind=kind,origin=tuple(origin),axis=tuple(direction),angle=angle,
                limited=bool(limited),minimum=minimum,maximum=maximum,distance=distance,
                distance_limited=bool(distance_limited),distance_minimum=distance_minimum,distance_maximum=distance_maximum)


def settings(joint):
    def length(name,default):
        value=getattr(joint,name,default)
        return getattr(value,'Value',value)
    return dict(kind=str(joint.Kind),origin=tuple(joint.AxisOrigin),axis=tuple(joint.AxisDirection),angle=joint.Angle.Value,
                limited=joint.Limited,minimum=joint.Minimum.Value,maximum=joint.Maximum.Value,
                distance=length('Distance',0),distance_limited=getattr(joint,'DistanceLimited',False),
                distance_minimum=length('MinimumDistance',-50),distance_maximum=length('MaximumDistance',50))


def _slider_properties(obj):
    """Upgrade only inside a confirmed edit, leaving older documents untouched on open."""
    for kind,name,default in [('App::PropertyDistance','Distance',0),('App::PropertyBool','DistanceLimited',False),
                              ('App::PropertyDistance','MinimumDistance',-50),('App::PropertyDistance','MaximumDistance',50)]:
        if name not in obj.PropertiesList:
            obj.addProperty(kind,name,'Joint');setattr(obj,name,default)
    if 'slider' not in obj.getEnumerationsOfProperty('Kind'):
        previous=str(obj.Kind);obj.Kind=['rigid','revolute','slider'];obj.Kind=previous


def pose(target_pose,relative,**values):
    values=parameters(**values)
    rotation=App.Rotation(App.Vector(*values['axis']),values['angle']) if values['kind']=='revolute' else App.Rotation()
    center=App.Vector(*values['origin'])
    motion=App.Placement(center-rotation.multVec(center),rotation)
    if values['kind']=='slider':motion=App.Placement(App.Vector(*values['axis'])*values['distance'],App.Rotation())
    return target_pose.multiply(motion).multiply(relative)


def validate_joint(doc,follower,target,existing=None):
    if not doc or any(not o or o.Document!=doc for o in (follower,target)):
        raise ValueError(tr('同じ文書のコンポーネントを2つ選択してください。','Select two components in the same document.'))
    if existing and getattr(follower,'FluxComponent',False) and follower.Driver==existing:
        local_shape(follower.Source)  # Permit repairing a joint that cleared its follower shape.
    else:valid_component(follower)
    valid_component(target)
    if follower==target or follower in target.OutListRecursive:
        raise ValueError(tr('循環する接続は作成できません。別の基準部品を選んでください。','This connection would form a cycle. Choose another anchor.'))
    if follower.Grounded:raise ValueError(tr('動く部品の接地を解除してください。','Unground the moving component first.'))
    if follower.Driver and follower.Driver!=existing:
        raise ValueError(tr('この部品は既にジョイントで接続されています。既存ジョイントを編集してください。','This component already has a joint. Edit the existing joint.'))
    if existing and (existing.Document!=doc or follower.Driver!=existing or existing.Target!=target):
        raise ValueError(tr('編集時は接続先を変更できません。解除して作り直してください。','Endpoints cannot be changed during editing. Release and recreate the joint.'))
    if follower.getParentGeoFeatureGroup() or target.getParentGeoFeatureGroup():
        raise ValueError(tr('ルート階層のコンポーネントを選択してください。','Select root-level components.'))


class Joint:
    def execute(self,obj):
        try:
            valid_component(obj.Target)
            obj.OutputPose=pose(obj.Target.getGlobalPlacement(),obj.Relative,**settings(obj));obj.Valid=True;obj.AssemblyError=''
        except Exception as error:
            obj.Valid=False;obj.AssemblyError=str(error)
            # Raising here leaves downstream shapes stale because FreeCAD stops recompute.
    def dumps(self):return None
    def loads(self,state):pass


def follower_of(joint):
    return next((o for o in components(joint.Document) if o.Driver==joint),None)


def relative_pose(follower,target,existing=None):
    return App.Placement(existing.Relative) if existing else target.getGlobalPlacement().inverse().multiply(follower.getGlobalPlacement())


def affected_poses(doc,overrides):
    """Propagate a preview through a joint tree without mutating the document."""
    result=dict(overrides);pending=[o for o in components(doc) if o not in result and o.Driver]
    for _ in range(len(pending)+1):
        changed=False
        for obj in pending[:]:
            joint=obj.Driver
            if joint.Target in result:
                result[obj]=pose(result[joint.Target],joint.Relative,**settings(joint))
                pending.remove(obj);changed=True
        if not changed:break
    return result


def posed_shapes(poses):
    result=[]
    for obj,placement in poses.items():
        shape=local_shape(obj.Source if getattr(obj,'FluxComponent',False) else obj)
        shape.Placement=placement;result.append(shape)
    return result


def preview(doc,follower,target,existing=None,**values):
    validate_joint(doc,follower,target,existing)
    placement=pose(target.getGlobalPlacement(),relative_pose(follower,target,existing),**values)
    return affected_poses(doc,{follower:placement})


def verify(poses):
    for obj,expected in poses.items():
        valid_component(obj)
        actual=obj.getGlobalPlacement()
        if (actual.Base-expected.Base).Length>1e-6 or abs(math.sin(actual.Rotation.multiply(expected.Rotation.inverted()).Angle/2))>1e-6:
            raise ValueError(tr('ジョイントの配置を更新できません。','The joint placement did not update.'))


def create_joint(doc,follower,target,existing=None,**values):
    values=parameters(**values);expected=preview(doc,follower,target,existing,**values)
    relative=relative_pose(follower,target,existing)
    with model.transaction(doc,tr('ジョイントを編集','Edit Joint') if existing else joint_label(values['kind'])):
        obj=existing
        if obj is None:
            obj=doc.addObject('App::FeaturePython','Joint')
            for kind,name in [('App::PropertyBool','FluxJoint'),('App::PropertyLinkGlobal','Target'),
                              ('App::PropertyPlacement','Relative'),('App::PropertyPlacement','OutputPose'),
                              ('App::PropertyBool','Valid'),('App::PropertyEnumeration','Kind'),('App::PropertyString','AssemblyError'),
                              ('App::PropertyVectorDistance','AxisOrigin'),('App::PropertyVector','AxisDirection'),
                              ('App::PropertyAngle','Angle'),('App::PropertyBool','Limited'),
                              ('App::PropertyAngle','Minimum'),('App::PropertyAngle','Maximum')]:obj.addProperty(kind,name,'Joint')
            obj.FluxJoint=True;obj.Target=target;obj.Relative=relative;obj.Kind=['rigid','revolute']
            obj.Proxy=Joint();obj.ViewObject.Proxy=0
            for name in ('FluxJoint','OutputPose','Valid','Relative'):obj.setEditorMode(name,2)
            obj.setEditorMode('Target',1)
            obj.setEditorMode('AssemblyError',1)
        _slider_properties(obj)
        obj.Label=joint_label(values['kind'])
        for key,prop in [('kind','Kind'),('origin','AxisOrigin'),('axis','AxisDirection'),('angle','Angle'),
                         ('limited','Limited'),('minimum','Minimum'),('maximum','Maximum'),('distance','Distance'),
                         ('distance_limited','DistanceLimited'),('distance_minimum','MinimumDistance'),('distance_maximum','MaximumDistance')]:
            setattr(obj,prop,App.Vector(*values[key]) if key in ('origin','axis') else values[key])
        follower.Driver=obj;follower.setExpression('Placement',obj.Name+'.OutputPose')
        doc.recompute()
        if not obj.Valid or 'Invalid' in obj.State:raise ValueError(tr('ジョイントを更新できません。','Could not update the joint.'))
        verify(expected)
        return obj


def release_joint(joint):
    obj=follower_of(joint)
    if not obj:raise ValueError(tr('接続されたコンポーネントがありません。','No connected component was found.'))
    pose=App.Placement(obj.Placement)
    with model.transaction(joint.Document,tr('ジョイントを解除','Release Joint')):
        obj.setExpression('Placement',None);obj.Driver=None;obj.Placement=pose
        joint.Document.removeObject(joint.Name);obj.Document.recompute();valid_component(obj)
    return obj
