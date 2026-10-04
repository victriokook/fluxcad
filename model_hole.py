"""Face-normal plain, recessed and metric threaded holes with a native cut."""
import math
import re
import FreeCAD as App
import Part
import model
import model_thread as threads
from i18n import tr


KINDS = ('simple', 'counterbore', 'countersink', 'threaded')
DEFAULTS = dict(u=0, v=0, diameter=8, depth=10, through=True, kind='simple',
                head_diameter=14, head_depth=3, angle=90)


def recess_depth(kind, diameter, head_diameter, head_depth, angle):
    """Depth below the entry face; countersink angle is the full included angle."""
    if kind not in KINDS:
        raise ValueError(tr('穴の種類を選択してください。', 'Select a hole type.'))
    if kind in ('simple','threaded'):return 0
    if not math.isfinite(head_diameter) or head_diameter <= diameter:
        raise ValueError(tr('入口の直径は穴の直径より大きくしてください。',
                            'The entrance diameter must be larger than the hole diameter.'))
    if kind == 'counterbore':
        if not math.isfinite(head_depth) or head_depth <= 0:
            raise ValueError(tr('ザグリ深さには0より大きい数値を指定してください。',
                                'Counterbore depth must be a positive finite number.'))
        return head_depth
    if not math.isfinite(angle) or not 0 < angle < 180:
        raise ValueError(tr('皿角度は0°より大きく180°より小さくしてください。',
                            'Countersink angle must be between 0 and 180 degrees, exclusive.'))
    return (head_diameter-diameter)/2/math.tan(math.radians(angle/2))


def signature(obj):
    return obj.Shape.hashCode(), str(obj.getGlobalPlacement())


def reference(doc, objname, subname):
    obj = doc.getObject(objname) if doc else None
    if not obj or not re.search(r'(^|\.)Face[1-9][0-9]*$', subname):
        raise ValueError(tr('ソリッドの平らな面を選択してください。', 'Select a planar face of a solid.'))
    obj = obj.getSubObject(subname, 1) or obj
    name = subname.rsplit('.', 1)[-1]
    frame(obj, name)
    return obj, name


def frame(source, face_name):
    if not source or not hasattr(source, 'Shape') or not source.Shape.Solids:
        raise ValueError(tr('穴あけするソリッドを選択してください。メッシュには適用できません。',
                            'Select a solid for drilling. Meshes are not supported.'))
    if not re.fullmatch(r'Face[1-9][0-9]*', face_name):
        raise ValueError(tr('平らな面を選択してください。', 'Select a planar face.'))
    shape = source.Shape.copy()
    shape.Placement = App.Placement()
    try:
        face = shape.getElement(face_name)
    except Exception:
        raise ValueError(tr('参照面がありません。面を選び直してください。', 'The reference face is missing. Select it again.')) from None
    if not isinstance(face.Surface, Part.Plane):
        raise ValueError(tr('穴あけの基準には平面を選択してください。曲面は未対応です。',
                            'Select a planar drilling face. Curved faces are not supported yet.'))
    lo, hi, bottom, top = face.ParameterRange
    normal = face.normalAt((lo+hi)/2, (bottom+top)/2); normal.normalize()
    seed = App.Vector(1,0,0) if abs(normal.x) < .99 else App.Vector(0,1,0)
    u = seed-normal*seed.dot(normal); u.normalize()
    v = normal.cross(u); v.normalize()
    # Project the source object's local origin onto the plane. Unlike a face
    # centroid this origin does not drift when its width or outline changes.
    origin = normal*face.CenterOfMass.dot(normal)
    return face, origin, u, v, normal


def coordinates(source, face_name, world_point):
    face, origin, u, v, normal = frame(source, face_name)
    local = source.getGlobalPlacement().inverse().multVec(world_point)
    delta = local-origin
    return delta.dot(u), delta.dot(v)


def placement_frame(source, face_name, u=0, v=0):
    face, origin, a, b, normal = frame(source, face_name)
    center = origin+a*u+b*v
    if not face.isInside(center, 1e-6, True):
        raise ValueError(tr('穴の中心を選択した面の内側に置いてください。', 'Place the hole center inside the selected face.'))
    pose = source.getGlobalPlacement()
    return pose.multVec(center), pose.Rotation.multVec(a), pose.Rotation.multVec(b), pose.Rotation.multVec(normal)


def tool_shape(source, face_name, u=0, v=0, diameter=8, depth=10, through=True,
               kind='simple', head_diameter=14, head_depth=3, angle=90, **thread_values):
    if not all(math.isfinite(x) for x in (u,v,diameter,depth)) or diameter <= 0 or depth <= 0:
        raise ValueError(tr('直径・深さには0より大きい数値を指定してください。', 'Diameter and depth must be positive finite numbers.'))
    recess = recess_depth(kind, diameter, head_diameter, head_depth, angle)
    if not through and recess >= depth:
        raise ValueError(tr('穴全体の深さを、ザグリ・皿穴部分の深さより大きくしてください。',
                            'Total hole depth must be greater than the counterbore or countersink depth.'))
    center, a, b, normal = placement_frame(source, face_name, u, v)
    bounds = model.world_shape(source).BoundBox
    # Extend clear of the native Cut's fuzzy tolerance. An almost coincident
    # exit face can otherwise be merged below the body and disagree with preview.
    epsilon = max(1e-4 if through else 1e-5, bounds.DiagonalLength*1e-7)
    if through:
        corners = (App.Vector(x,y,z) for x in (bounds.XMin,bounds.XMax)
                   for y in (bounds.YMin,bounds.YMax) for z in (bounds.ZMin,bounds.ZMax))
        depth = max((center-p).dot(normal) for p in corners)+epsilon
    start = center+normal*epsilon
    if kind=='threaded':
        values=dict(threads.DEFAULTS,**thread_values)
        info,length=threads.validate(depth,**values)
        if values['model_thread']:
            tool=threads.cutter(depth,**values)
            tool.Placement=App.Placement(center,App.Rotation(App.Vector(0,0,1),normal))
            # FeaturePython owns its root Placement. Keep the cutter's world
            # placement below an identity compound so recompute cannot drop it.
            return Part.makeCompound([tool])
        # Lightweight mode stores designation/depth and uses the native tap drill
        # diameter; only modeled mode cuts a helical thread into the solid.
        diameter=info[3]
    stem = Part.makeCylinder(diameter/2, depth+epsilon, start, -normal)
    if kind in ('simple','threaded'):return stem
    if kind == 'counterbore':
        head = Part.makeCylinder(head_diameter/2, recess+epsilon, start, -normal)
    else:
        # Extend the frustum above the face along its slope, so its diameter at
        # the actual face and its shoulder depth remain exact (also after tilt).
        extra_radius = epsilon*math.tan(math.radians(angle/2))
        head = Part.makeCone(head_diameter/2+extra_radius, diameter/2,
                             recess+epsilon, start, -normal)
    return stem.fuse(head).removeSplitter()


def preview(source, face_name, **values):
    base = model.world_shape(source)
    if base.isNull() or not base.isValid() or not base.Solids:
        raise ValueError(tr('有効なソリッドを選択してください。', 'Select a valid solid.'))
    tool = tool_shape(source, face_name, **values)
    result = base.cut(tool).removeSplitter()
    tolerance = max(1e-8, base.Volume*1e-9)
    if result.isNull() or not result.isValid() or not result.Solids or result.Volume <= tolerance:
        raise ValueError(tr('穴あけ後の立体が残りません。直径・深さを小さくしてください。',
                            'No valid solid would remain. Reduce the diameter or depth.'))
    if base.Volume-result.Volume <= tolerance:
        raise ValueError(tr('穴がボディと交差していません。位置・直径を確認してください。',
                            'The hole does not intersect the body. Check its position and diameter.'))
    return result


class HoleTool:
    """Recompute from the linked face, including through depth after source edits."""
    def execute(self, obj):
        try:
            source, names = obj.Support
            obj.Shape = tool_shape(source, names[0], **tool_settings(obj))
        except Exception:
            obj.Shape = Part.Shape()  # Never leave an apparently valid stale tool.
            raise

    def dumps(self): return None
    def loads(self, state): pass


def tool_settings(tool):
    values = dict(u=tool.U.Value, v=tool.V.Value, diameter=tool.Diameter.Value,
                depth=tool.Depth.Value, through=tool.Through,
                kind=str(tool.HoleType) if 'HoleType' in tool.PropertiesList else 'simple',
                head_diameter=tool.HeadDiameter.Value if 'HeadDiameter' in tool.PropertiesList else DEFAULTS['head_diameter'],
                head_depth=tool.HeadDepth.Value if 'HeadDepth' in tool.PropertiesList else DEFAULTS['head_depth'],
                angle=tool.SinkAngle.Value if 'SinkAngle' in tool.PropertiesList else DEFAULTS['angle'])
    if values['kind']=='threaded':values.update(threads.settings(tool))
    return values


def add_recess_properties(tool):
    # Add lazily inside an edit transaction. Loading/recomputing an old simple
    # hole reads defaults without modifying its schema or document history.
    if 'HoleType' not in tool.PropertiesList:
        tool.addProperty('App::PropertyEnumeration', 'HoleType', 'Hole')
        tool.HoleType = list(KINDS)
    elif tool.getEnumerationsOfProperty('HoleType')!=list(KINDS):
        previous=str(tool.HoleType);tool.HoleType=list(KINDS);tool.HoleType=previous
    for name, prop, value in (('HeadDiameter','App::PropertyLength',DEFAULTS['head_diameter']),
                              ('HeadDepth','App::PropertyLength',DEFAULTS['head_depth']),
                              ('SinkAngle','App::PropertyAngle',DEFAULTS['angle'])):
        if name not in tool.PropertiesList:
            tool.addProperty(prop, name, 'Hole'); setattr(tool,name,value)


def link_containers(tool, source):
    # The tool is built in world coordinates. A change to an App::Part's
    # placement does not necessarily touch its child, so depend on ancestors
    # directly as well as on the source face.
    if 'SourceContainers' not in tool.PropertiesList:
        tool.addProperty('App::PropertyLinkListGlobal','SourceContainers','Hole')
        tool.setEditorMode('SourceContainers',2)
    containers=[]
    parent=source.getParentGeoFeatureGroup()
    while parent:
        containers.append(parent);parent=parent.getParentGeoFeatureGroup()
    tool.SourceContainers=containers


def settings(obj):
    return tool_settings(obj.Tool)


def source_face(obj):
    source, names = obj.Tool.Support
    return source, names[0]


def create(doc, source, face_name, existing=None, **values):
    values = dict(DEFAULTS, **values)
    if source.Document != doc or (existing and existing.Document != doc):
        raise ValueError(tr('同じ文書内の形状を選択してください。', 'Select geometry in the same document.'))
    if existing and (source == existing or source in existing.InListRecursive):
        raise ValueError(tr('後の加工を穴の参照元にすることはできません。', 'A downstream feature cannot be the hole source.'))
    expected = preview(source, face_name, **values)
    if existing:
        expected.Placement = existing.Placement.multiply(expected.Placement)
    visibility = [(obj, bool(obj.Visibility)) for obj in doc.Objects if hasattr(obj, 'Visibility')]
    try:
        with model.transaction(doc, tr('穴を編集', 'Edit Hole') if existing else tr('穴', 'Hole')):
            if existing:
                obj, tool = existing, existing.Tool
            else:
                base = model._world_source(doc, source)
                tool = model._internal(doc.addObject('Part::FeaturePython', 'HoleTool'))
                tool.Label = tr('穴の工具', 'Hole Tool')
                tool.addProperty('App::PropertyLinkSubGlobal', 'Support', 'Hole')
                for name in ('U','V'):
                    tool.addProperty('App::PropertyDistance', name, 'Hole')
                for name in ('Diameter','Depth'):
                    tool.addProperty('App::PropertyLength', name, 'Hole')
                tool.addProperty('App::PropertyBool', 'Through', 'Hole')
                tool.Proxy = HoleTool()
                tool.ViewObject.Proxy = 0
                obj = doc.addObject('Part::Cut', 'Hole')
                obj.Label = tr('穴', 'Hole')
                obj.Base = base
                obj.Tool = tool
                obj.Refine = True
                obj.addProperty('App::PropertyBool', 'FluxHole', 'FluxCAD'); obj.FluxHole = True
                obj.setEditorMode('FluxHole', 2)
                obj.addProperty('App::PropertyLinkGlobal', 'FluxBodySource', 'FluxCAD')
                obj.FluxBodySource = source; obj.setEditorMode('FluxBodySource', 2)
            add_recess_properties(tool)
            if values['kind']=='threaded':threads.assign(tool,values)
            link_containers(tool,source)
            tool.Support = (source, [face_name])
            for key, prop in [('u','U'),('v','V'),('diameter','Diameter'),('depth','Depth'),('through','Through'),
                             ('kind','HoleType'),('head_diameter','HeadDiameter'),('head_depth','HeadDepth'),('angle','SinkAngle')]:
                setattr(tool, prop, values[key])
            from model_features import verify_result
            verify_result(obj, expected)
            source.Visibility = obj.Base.Visibility = tool.Visibility = False
            if not existing: obj.Visibility = True
        return obj
    except Exception:
        for obj, visible in visibility:
            if obj.Document: obj.Visibility = visible
        raise
