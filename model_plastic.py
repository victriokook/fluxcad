"""Face-supported additive ribs and blind-bore mounting bosses."""
import math
import FreeCAD as App
import Part
import model
from i18n import tr

FIELDS = {'rib':('Length','Thickness','Height','Angle','U','V'), 'boss':('Diameter','Bore','Height','U','V'), 'snap':('Width','Thickness','Height','Projection','HookHeight','Angle','U','V'), 'gusset':('Length','Thickness','Height','Angle','U','V')}

DEFAULTS = {'rib':dict(Length=30,Thickness=2,Height=10,Angle=0,U=0,V=0), 'boss':dict(Diameter=10,Bore=3,Height=10,U=0,V=0), 'snap':dict(Width=8,Thickness=1.5,Height=15,Projection=1.5,HookHeight=2,Angle=0,U=0,V=0), 'gusset':dict(Length=20,Thickness=2,Height=15,Angle=0,U=0,V=0)}

TITLES = {'rib':('補強リブ','Reinforcing Rib'), 'boss':('取付ボス','Mounting Boss'), 'snap':('スナップフィット爪','Snap-fit Hook'), 'gusset':('三角リブ','Triangular Rib')}

OBJECT_NAMES = {'rib':'PlasticRib','boss':'PlasticBoss','snap':'PlasticSnap','gusset':'PlasticGusset'}

LABELS_EXTRA = {'Width':('幅','Width'),'Projection':('爪の張り出し','Hook Projection'),'HookHeight':('爪の高さ','Hook Height')}

def setup_boss_draft():
    FIELDS['boss'] = ('Diameter', 'Bore', 'Height', 'Draft', 'U', 'V')
    DEFAULTS['boss']['Draft'] = 0
    FIELDS['rib'] = ('Length', 'Thickness', 'Height', 'Draft', 'Angle', 'U', 'V')
    DEFAULTS['rib']['Draft'] = 0
    LABELS_EXTRA['Draft'] = ('抜き勾配', 'Draft Angle')

def normalize_boss_values(kind, values):
    if kind in ('boss', 'rib') and isinstance(values, dict) and 'Draft' not in values:
        values = dict(values, Draft=0)
    return values

def validate_boss_draft(p):
    if not math.isfinite(p['Draft']) or not 0 <= p['Draft'] <= 45:
        raise ValueError(tr('抜き勾配は0〜45°にしてください。','Draft angle must be between 0 and 45 degrees.'))
    radius = p['Diameter']/2
    top = radius-p['Height']*math.tan(math.radians(p['Draft']))
    if top < max(0.0005,p['Bore']/2+0.0005):
        raise ValueError(tr('先端の外径が小さすぎます。高さ・抜き勾配・下穴径を調整してください。','The top diameter is too small. Adjust height, draft angle or bore diameter.'))
    return radius, top

def make_boss_tool(p):
    radius, top = validate_boss_draft(p)
    cylindrical = radius-top <= 1e-7 or math.radians(p['Draft']) <= 1e-12
    tool = Part.makeCylinder(radius,p['Height']) if cylindrical else Part.makeCone(radius,top,p['Height'])
    if p['Bore']>0:
        tool = tool.cut(Part.makeCylinder(p['Bore']/2,p['Height']))
    footprint = Part.Face(Part.Wire([Part.makeCircle(radius)]))
    return tool, footprint

def ensure_boss_draft(obj):
    if obj.FluxPlastic in ('boss', 'rib') and 'Draft' not in obj.PropertiesList:
        obj.addProperty('App::PropertyAngle', 'Draft', 'Dimensions')
        obj.Draft = 0

def validate_rib_draft(p):
    if not math.isfinite(p['Draft']) or not 0 <= p['Draft'] <= 45:
        raise ValueError(tr('抜き勾配は0〜45°にしてください。','Draft angle must be between 0 and 45 degrees.'))
    top_length = p['Length'] - 2 * p['Height'] * math.tan(math.radians(p['Draft']))
    top_thickness = p['Thickness'] - 2 * p['Height'] * math.tan(math.radians(p['Draft']))
    if top_length < 0.001 or top_thickness < 0.001:
        raise ValueError(tr('先端の長さ・厚さは0.001 mm以上にしてください。高さ・抜き勾配を調整してください。','Top length and thickness must be at least 0.001 mm. Adjust height or draft angle.'))
    return top_length, top_thickness

def make_rib_tool(p):
    top_length, top_thickness = validate_rib_draft(p)
    L, t, H = p['Length'], p['Thickness'], p['Height']
    if H * math.tan(math.radians(p['Draft'])) <= 1e-7 or math.radians(p['Draft']) <= 1e-12:
        tool = Part.makeBox(L, t, H, App.Vector(-L / 2, -t / 2, 0))
    else:
        bottom_corners = [App.Vector(-L / 2, -t / 2, 0), App.Vector(L / 2, -t / 2, 0), App.Vector(L / 2, t / 2, 0), App.Vector(-L / 2, t / 2, 0)]
        top_corners = [App.Vector(-top_length / 2, -top_thickness / 2, H), App.Vector(top_length / 2, -top_thickness / 2, H), App.Vector(top_length / 2, top_thickness / 2, H), App.Vector(-top_length / 2, top_thickness / 2, H)]
        bottom_wire = Part.makePolygon(bottom_corners + [bottom_corners[0]])
        top_wire = Part.makePolygon(top_corners + [top_corners[0]])
        tool = Part.makeLoft([bottom_wire, top_wire], True, True)
    return tool, Part.makePlane(L, t, App.Vector(-L / 2, -t / 2, 0))

setup_boss_draft()

def title(kind):
    return tr(*TITLES[kind])

def settings(obj):
    return {key:(0 if key=='Draft' and key not in obj.PropertiesList else getattr(obj,key).Value) for key in FIELDS[obj.FluxPlastic]}
def capture_snapshot(obj, source):
    if obj.ReferenceMapped:
        return
    local = source.Shape.copy()
    local.Placement = App.Placement()
    obj.addProperty('Part::PropertyPartShape', 'ReferenceShape', 'FluxCAD')
    obj.ReferenceShape = local
    obj.setEditorMode('ReferenceShape', 2)

def same_reference_shape(source, reference):
    try:
        current = source.Shape.copy()
        saved = reference.copy()
        current.Placement = App.Placement()
        saved.Placement = App.Placement()
        if current.isNull() or saved.isNull():
            return False
        for attr in ('Faces', 'Edges', 'Vertexes', 'Solids'):
            if len(getattr(current, attr)) != len(getattr(saved, attr)):
                return False
        for a, b in zip(current.Vertexes, saved.Vertexes):
            if (a.Point - b.Point).Length > 1e-7:
                return False
        for a, b in zip(current.Faces, saved.Faces):
            if type(a.Surface) != type(b.Surface) or a.Orientation != b.Orientation:
                return False
            tolerance = max(1e-10, max(a.Area, b.Area) * 1e-9)
            if abs(a.Area - b.Area) > tolerance:
                return False
            if abs(a.common(b).Area - a.Area) > tolerance:
                return False
        return True
    except Exception:
        return False

def capture_reference(obj, source, face_name):
    from model_face_offset_history import fingerprint
    obj.addProperty('App::PropertyLinkGlobal', 'Source', 'FluxCAD')
    obj.Source = source
    obj.setEditorMode('Source', 1)
    obj.addProperty('App::PropertyString', 'ReferenceMapped', 'FluxCAD')
    obj.ReferenceMapped = source.Shape.getElementMappedName(face_name)
    obj.setEditorMode('ReferenceMapped', 2)
    obj.addProperty('App::PropertyString', 'ReferenceFingerprint', 'FluxCAD')
    obj.ReferenceFingerprint = fingerprint(source)
    obj.setEditorMode('ReferenceFingerprint', 2)
    capture_snapshot(obj, source)

def read_support(obj):
    value = obj.Support
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(tr('参照面が変更されました。面を選び直して作り直してください。', 'The support face changed. Reselect the face and recreate the feature.'))
    source, names = value
    if source is None or not isinstance(names, (tuple, list)) or len(names) != 1:
        raise ValueError(tr('参照面が変更されました。面を選び直して作り直してください。', 'The support face changed. Reselect the face and recreate the feature.'))
    return source, names

def support(obj):
    from model_face_offset_history import fingerprint
    source, names = read_support(obj)
    if source is None or len(names) != 1:
        raise ValueError(tr('参照面が変更されました。面を選び直して作り直してください。', 'The support face changed. Reselect the face and recreate the feature.'))
    props = ['Source', 'ReferenceMapped', 'ReferenceFingerprint']
    for p in props:
        if p not in obj.PropertiesList:
            raise ValueError(tr('参照面が変更されました。面を選び直して作り直してください。', 'The support face changed. Reselect the face and recreate the feature.'))
    if source != obj.Source or source.Document != obj.Document:
        raise ValueError(tr('参照面が変更されました。面を選び直して作り直してください。', 'The support face changed. Reselect the face and recreate the feature.'))
    if obj.ReferenceMapped and source.Shape.getElementMappedName(names[0]) != obj.ReferenceMapped:
        raise ValueError(tr('参照面が変更されました。面を選び直して作り直してください。', 'The support face changed. Reselect the face and recreate the feature.'))
    if (not obj.ReferenceMapped and fingerprint(source) != obj.ReferenceFingerprint and
            ('ReferenceShape' not in obj.PropertiesList or not same_reference_shape(source, obj.ReferenceShape))):
        raise ValueError(tr('参照面が変更されました。面を選び直して作り直してください。', 'The support face changed. Reselect the face and recreate the feature.'))
    return (source, names[0])

def validate(kind, values):
    values = normalize_boss_values(kind, values)
    if not isinstance(kind, str) or kind not in FIELDS or (not isinstance(values, dict)) or (set(values) != set(FIELDS[kind])):
        raise ValueError(tr('寸法の種類と項目を確認してください。', 'Check feature type and dimension fields.'))
    result = {}
    for key in FIELDS[kind]:
        if isinstance(values[key], bool):
            raise ValueError(tr('bool 型は許容されません。', 'Boolean values are not allowed.'))
        try:
            number = float(values[key])
        except (TypeError, ValueError, OverflowError):
            raise ValueError(tr('寸法には有限の数値（±100000 以内）を指定してください。', 'Enter finite numeric dimensions within ±100000.'))
        if not math.isfinite(number) or abs(number) > 100000:
            raise ValueError(tr('寸法には有限の数値（±100000 以内）を指定してください。', 'Enter finite numeric dimensions within ±100000.'))
        result[key] = number
    for key in ('Length', 'Thickness', 'Height', 'Diameter', 'Width', 'Projection', 'HookHeight'):
        if key in result and result[key] < 0.001:
            raise ValueError(tr('寸法は 0.001 mm 以上にしてください。', 'Dimensions must be at least 0.001 mm.'))
    if kind == 'boss' and (not 0 <= result['Bore'] <= result['Diameter'] - 0.001):
        raise ValueError(tr('下穴径を 0 以上、外径未満にしてください。', 'Bore must be nonnegative and smaller than the outside diameter.'))
    if kind == 'boss': validate_boss_draft(result)
    if kind == 'rib': validate_rib_draft(result)
    if kind in ('rib', 'snap', 'gusset') and (not -360 <= result['Angle'] <= 360):
        raise ValueError(tr('回転角は -360〜360 度にしてください。', 'Angle must be between -360 and 360 degrees.'))
    if kind == 'snap' and result['HookHeight'] >= result['Height']:
        raise ValueError(tr('爪の高さは全体の高さ未満にしてください。', 'Hook height must be smaller than the overall height.'))
    return result

def make_gusset_tool(p):
    L = p['Length']
    t = p['Thickness']
    H = p['Height']
    
    if not math.isfinite(L) or not math.isfinite(t) or not math.isfinite(H):
        raise ValueError(tr("寸法には有限の数値を指定してください。", "Dimensions must be finite numbers."))
    
    if L < 0.001 or t < 0.001 or H < 0.001:
        raise ValueError(tr("寸法は0.001 mm以上にしてください。", "Dimensions must be at least 0.001 mm."))
    
    points = [App.Vector(-L/2, -t/2, 0), App.Vector(L/2, -t/2, 0), App.Vector(-L/2, -t/2, H)]
    points.append(points[0])
    poly = Part.makePolygon(points)
    
    try:
        tool = Part.Face(Part.Wire(poly.Edges)).extrude(App.Vector(0, t, 0))
    except Exception:
        raise ValueError(tr("有効な三角リブを作成できません。", "Cannot create a valid triangular rib."))
    
    if tool.isNull() or not tool.isValid() or len(tool.Solids) != 1 or tool.Volume <= 1e-9:
        raise ValueError(tr("有効な三角リブを作成できません。", "Cannot create a valid triangular rib."))
    
    footprint = Part.makePlane(L, t, App.Vector(-L/2, -t/2, 0))
    
    return tool, footprint

def make_tool(kind,p):
    if kind=='gusset':return make_gusset_tool(p)
    if kind not in ('snap','rib','boss'): raise ValueError(tr('形状の種類が不明です。','Unknown feature type.'))
    if kind=='snap':
        for key in ('Width','Thickness','Height','Projection','HookHeight'):
            if p[key]<0.001: raise ValueError(tr('爪の寸法を確認してください。','Check the snap-hook dimensions.'))
        if p['HookHeight']>=p['Height']: raise ValueError(tr('爪の寸法を確認してください。','Check the snap-hook dimensions.'))
        if not(-360<=p['Angle']<=360): raise ValueError(tr('爪の寸法を確認してください。','Check the snap-hook dimensions.'))
        t,w,h,d,k = p['Thickness'],p['Width'],p['Height'],p['Projection'],p['HookHeight']
        points=[App.Vector(x,-w/2,z) for x,z in [(-t/2,0),(t/2,0),(t/2,h-k),(t/2+d,h-k),(t/2,h),(-t/2,h)]]
        points.append(points[0])
        poly=Part.makePolygon(points)
        wire=Part.Wire(poly.Edges)
        tool=Part.Face(wire).extrude(App.Vector(0,w,0))
        footprint=Part.makePlane(t,w,App.Vector(-t/2,-w/2,0))
    elif kind=='rib':
        tool,footprint=make_rib_tool(p)
    elif kind=='boss':
        tool,footprint=make_boss_tool(p)
    if tool.isNull() or not tool.isValid() or len(tool.Solids)!=1 or tool.Volume<=1e-9: raise ValueError(tr('有効な立体を作成できません。','Cannot create a valid solid.'))
    return tool,footprint

def check_footprint(face, footprint):
    area = footprint.Area
    if area <= 0:
        raise ValueError(tr('底面全体が選択面の内側に入るよう、位置・寸法を調整してください。', 'Adjust position/size so the whole footprint lies inside the selected face.'))
    covered = footprint.common(face).Area
    missing = max(0.0, area - covered)
    tolerance = max(1e-12, area * 1e-7)
    if missing > tolerance:
        raise ValueError(tr('底面全体が選択面の内側に入るよう、位置・寸法を調整してください。', 'Adjust position/size so the whole footprint lies inside the selected face.'))

def coordinate_pose(source):
    missing = tr('参照面が変更されました。面を選び直して作り直してください。', 'The support face changed. Reselect the face and recreate the feature.')
    if source is None:
        raise ValueError(missing)
    pose = App.Placement()
    current = source
    seen = set()
    while current is not None:
        try:
            doc = current.Document
            if doc is None or doc.getObject(current.Name) != current:
                raise ValueError(missing)
            key = (doc.Name, current.Name)
            placement = current.getGlobalPlacement()
        except (RuntimeError, ReferenceError, AttributeError, TypeError):
            raise ValueError(missing) from None
        if key in seen:
            raise ValueError(tr('参照が循環しています。', 'The support references form a cycle.'))
        seen.add(key)
        pose = pose.multiply(placement)
        if (getattr(current,'FluxPlastic',False) or getattr(current,'FluxFaceOffset',False) or
                (getattr(current,'FluxDimensionScale',False) and bool(getattr(current,'InheritSourceFrame',False)))):
            current=getattr(current,'Source',None)
        elif getattr(current,'FluxHole',False) and bool(getattr(getattr(current,'Tool',None),'StableSupportFrame',False)):
            current=getattr(current,'FluxBodySource',None)
        else:
            break
        if current is None:
            raise ValueError(missing)
    return pose

def reference_frame(source, face_name, stable=True):
    from model_hole import frame
    from types import SimpleNamespace
    if not stable:
        frame_result = frame(source, face_name)
        return (*frame_result, source.getGlobalPlacement())
    else:
        pose = coordinate_pose(source)
        local = model.world_shape(source)
        local.Placement = pose.inverse().multiply(local.Placement)
        holder = SimpleNamespace(Shape=Part.makeCompound([local]))
        frame_result = frame(holder, face_name)
        return (*frame_result, pose)

def use_stable_frame(existing=None):
    return True if existing is None else bool(getattr(existing, 'StableFrame', False))

def mark_stable_frame(obj):
    obj.addProperty('App::PropertyBool', 'StableFrame', 'FluxCAD')
    obj.StableFrame = True
    obj.setEditorMode('StableFrame', 2)


def shape(source,face_name,kind,values,stable=True):
    from model_hole import frame
    from model_combine import solid
    p=validate(kind,values)
    base=solid(source)
    if len(base.Solids)!=1:raise ValueError(tr('単一ソリッドの平面を選択してください。','Select a planar face of one solid.'))
    face,origin,u,v,normal,base_pose=reference_frame(source,face_name,stable)
    tool,footprint=make_tool(kind,p)
    pose=base_pose.multiply(App.Placement(origin+u*p['U']+v*p['V'],App.Rotation(u,v,normal,'ZXY')))
    pose=pose.multiply(App.Placement(App.Vector(),App.Rotation(App.Vector(0,0,1),p.get('Angle',0))))
    tool.Placement=pose;footprint.Placement=pose
    face.Placement=base_pose.multiply(face.Placement)
    check_footprint(face,footprint)
    result=base.fuse(tool).removeSplitter()
    if result.isNull() or not result.isValid() or len(result.Solids)!=1 or result.Volume<=base.Volume+1e-7:
        raise ValueError(tr('元のボディと一体になる形状を作成できません。','Cannot create a valid addition joined to the source body.'))
    return result
class PlasticProxy:
    def __init__(self,obj):obj.Proxy=self
    def execute(self,obj):
        pose=App.Placement(obj.Placement)
        try:
            source,face=support(obj)
            result=shape(source,face,obj.FluxPlastic,settings(obj),stable=use_stable_frame(obj))
            obj.Shape=Part.makeCompound([result]);obj.Placement=pose;obj.Error=''
        except Exception as error:
            obj.Shape=Part.Shape();obj.Placement=pose;obj.Error=str(error)
    def dumps(self):return None
    def loads(self,state):pass
def preview(source,face,kind,values,existing=None):
    result=shape(source,face,kind,values,stable=use_stable_frame(existing))
    if existing:result.Placement=existing.getGlobalPlacement().multiply(result.Placement)
    return result
def apply(doc,source,face,kind,values,existing=None):
    if not source or source.Document!=doc:raise ValueError(tr('現在の文書の面を選択してください。','Select a face in the current document.'))
    if existing and (existing.Document!=doc or existing.FluxPlastic!=kind or support(existing)!=(source,face)):
        raise ValueError(tr('元のプラスチック加工を選択してください。','Select the original plastic feature.'))
    from parameters import expression
    if existing and any(expression(existing,k) and abs(float(v)-getattr(existing,k).Value)>1e-10 for k,v in values.items()):
        raise ValueError(tr('式で連動する寸法はパラメータ画面で変更してください。','Edit linked dimensions in Change Parameters.'))
    expected=preview(source,face,kind,values,existing)
    healthy={o.Name for o in existing.InListRecursive if hasattr(o,'Shape') and o.Shape.Solids} if existing else set()
    with model.transaction(doc,title(kind)):
        obj=existing
        if obj is None:
            obj=doc.addObject('Part::FeaturePython',OBJECT_NAMES[kind]);obj.Label=title(kind)
            mark_stable_frame(obj)
            obj.addProperty('App::PropertyString','FluxPlastic','FluxCAD');obj.FluxPlastic=kind;obj.setEditorMode('FluxPlastic',2)
            obj.addProperty('App::PropertyLinkSubGlobal','Support','FluxCAD');obj.Support=(source,[face]);obj.setEditorMode('Support',1)
            capture_reference(obj,source,face)
            from model_scale_dimensions import containers
            obj.addProperty('App::PropertyLinkListGlobal','SourceContainers','FluxCAD');obj.SourceContainers=containers(source);obj.setEditorMode('SourceContainers',2)
            for key in FIELDS[kind]:
                obj.addProperty('App::PropertyAngle' if key in ('Angle','Draft') else 'App::PropertyDistance',key,'Dimensions')
            obj.addProperty('App::PropertyString','Error','FluxCAD');obj.setEditorMode('Error',1)
            PlasticProxy(obj);obj.ViewObject.Proxy=0
            for key in ('ShapeColor','LineColor','Transparency'):setattr(obj.ViewObject,key,getattr(source.ViewObject,key))
        ensure_boss_draft(obj)
        for key,value in normalize_boss_values(kind,values).items():
            if not expression(obj,key):setattr(obj,key,value)
        doc.recompute();actual=model.world_shape(obj);tol=max(1e-6,expected.Volume*1e-7)
        if obj.Error or actual.isNull() or abs(actual.common(expected).Volume-expected.Volume)>tol or abs(actual.Volume-expected.Volume)>tol:
            raise ValueError(obj.Error or tr('プレビューと結果が一致しません。','Preview and result do not match.'))
        for child in obj.InListRecursive:
            if 'Invalid' in child.State or getattr(child,'Error','') or (hasattr(child,'Shape') and
                    (child.Shape.isNull() or not child.Shape.isValid() or (child.Name in healthy and not child.Shape.Solids))):
                raise ValueError(tr('後続の加工が成立しないため取り消しました。','Cancelled because a downstream feature would become invalid.'))
        if not existing:source.Visibility=False;obj.Visibility=True
    return obj
