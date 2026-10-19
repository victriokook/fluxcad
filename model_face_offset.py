"""Parametric signed-mm offsetting along the source's world axes."""
import math
import json
import hashlib
import FreeCAD as App
import Part
import model
from i18n import tr

def fingerprint(source):
    if source.TypeId in ('Part::Box','Part::Cylinder','Part::Cone','Part::Sphere','Part::Torus'):
        faces = [(type(f.Surface).__name__, f.Orientation) for f in source.Shape.Faces]
        return json.dumps((source.TypeId, faces))
    local = source.Shape.copy()
    local.Placement = App.Placement()
    return hashlib.sha256(local.exportBrepToString().encode('utf-8')).hexdigest()

def capture(source, names):
       mapped = [source.Shape.getElementMappedName(n) for n in names]
       return mapped, fingerprint(source)

def resolve(obj):
    if not hasattr(obj, 'MappedFaces') or not hasattr(obj, 'SourceFingerprint'):
        raise ValueError(tr('面を選択してください。', 'Reselect faces'))
    if len(obj.MappedFaces) != len(obj.FaceNames):
        raise ValueError(tr('面の数が一致しません。', 'Reselect faces'))
    if any(not m for m in obj.MappedFaces) and fingerprint(obj.Source) != obj.SourceFingerprint:
        raise ValueError(tr('ソースのジオメトリが変更されました; 面を再選択してください。', 'Source geometry changed; reselect faces'))
    return [m if m else f for m, f in zip(obj.MappedFaces, obj.FaceNames)]

def offset(shape, face_names, distance):
    distance = float(distance)
    if not math.isfinite(distance) or abs(distance) < 1e-12:
        raise ValueError("Invalid distance")
    if not face_names or len(face_names) != len(set(face_names)):
        raise ValueError("Invalid face names")
    if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1:
        raise ValueError("Invalid shape")
    faces = []
    for name in face_names:
        elem = shape.getElement(name)
        if elem.ShapeType != 'Face':
            raise ValueError("Invalid face element")
        faces.append(elem)
    result = shape.offsetFaces(tuple(faces), distance).removeSplitter()
    if result.isNull() or not result.isValid() or len(result.Solids) != 1 or result.Volume <= 1e-9:
        raise ValueError("Offset failed")
    return result

def source_shape(obj):
    from model_combine import solid
    return solid(obj)

def containers(obj):
    result = []
    parent = obj.getParentGeoFeatureGroup()
    while parent and parent not in result:
        result.append(parent)
        parent = parent.getParentGeoFeatureGroup()
    return result

class FaceOffset:
    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        placement = App.Placement(obj.Placement)
        try:
            result = offset(source_shape(obj.Source), resolve(obj), obj.Distance.Value)
            obj.Shape = Part.makeCompound([result])
            obj.Placement = placement
            obj.Error = ''
        except Exception as error:
            obj.Shape = Part.Shape()
            obj.Placement = placement
            obj.Error = str(error)
            raise

    def dumps(self): return None
    def loads(self, state): pass

def preview(source, face_names, distance, existing=None):
    resolved_faces = resolve(existing) if existing else face_names
    result = offset(source_shape(source), resolved_faces, distance)
    if existing:
        result.Placement = existing.getGlobalPlacement().multiply(result.Placement)
    return result

def apply(doc, source, face_names, distance, existing=None):
    if not source or source.Document != doc:
        raise ValueError(tr('現在の文書のボディを選択してください。', 'Select a body in the current document.'))
    if existing and (existing.Document != doc or not getattr(existing, 'FluxFaceOffset', False)
                     or existing.Source != source):
        raise ValueError(tr('面オフセットの履歴を選択してください。', 'Select an Offset Face feature.'))
    if existing and any(path in ('Distance',) for path, value in existing.ExpressionEngine):
        raise ValueError(tr('距離は式で制御されています。先にその式を編集してください。',
                            'Distance is controlled by expressions. Edit those expressions first.'))
    if existing is not None and list(face_names) != list(existing.FaceNames):
        raise ValueError('異なる面に対して新しいフィーチャを作成してください')
    previous = (existing.FaceNames, existing.Distance.Value) if existing else ((), 0.0)
    if existing is not None and list(face_names) == list(previous[0]) and abs(distance - previous[1]) < 1e-12:
        raise ValueError(tr('オフセット設定を変更してください。', 'Change the offset settings.'))
    expected = preview(source, face_names, distance, existing)
    downstream = {o.Name for o in existing.InListRecursive if hasattr(o, 'Shape') and o.Shape.Solids} if existing else set()
    visible = bool(source.Visibility)
    try:
        with model.transaction(doc, tr('面をオフセット','Offset Face')):
            obj = existing
            if obj is None:
                obj = doc.addObject('Part::FeaturePython', 'FaceOffset')
                obj.Label = tr('面オフセット', 'Face Offset')
                obj.addProperty('App::PropertyBool', 'FluxFaceOffset', 'FluxCAD')
                obj.FluxFaceOffset = True
                obj.setEditorMode('FluxFaceOffset', 2)
                obj.addProperty('App::PropertyLinkGlobal', 'Source', 'FluxCAD')
                obj.Source = source
                obj.setEditorMode('Source', 1)
                obj.addProperty('App::PropertyLinkListGlobal', 'SourceContainers', 'FluxCAD')
                obj.SourceContainers = containers(source)
                obj.setEditorMode('SourceContainers', 2)
                obj.addProperty('App::PropertyStringList', 'FaceNames', 'Faces')
                obj.setEditorMode("FaceNames",1)
                obj.addProperty('App::PropertyStringList', 'MappedFaces', 'Faces')
                obj.setEditorMode('MappedFaces', 2)
                obj.addProperty('App::PropertyString', 'SourceFingerprint', 'Faces')
                obj.setEditorMode('SourceFingerprint', 2)
                obj.addProperty('App::PropertyDistance', 'Distance', 'Dimensions',
                                'Offset distance, in mm, relative to Source')
                obj.addProperty('App::PropertyString', 'Error', 'FluxCAD')
                obj.setEditorMode('Error', 1)
                FaceOffset(obj)
                obj.ViewObject.Proxy = 0
                for prop in ('ShapeColor', 'LineColor', 'PointColor', 'Transparency', 'DisplayMode'):
                    setattr(obj.ViewObject, prop, getattr(source.ViewObject, prop))
            obj.FaceNames = face_names
            if existing is None:
                obj.MappedFaces, obj.SourceFingerprint = capture(source, face_names)
            obj.Distance = distance
            doc.recompute()
            actual = model.world_shape(obj)
            tolerance = max(1e-6, expected.Volume*1e-7)
            if (obj.Error or actual.isNull() or not actual.isValid() or 'Invalid' in obj.State
                    or abs(actual.Volume-expected.Volume) > tolerance):
                raise ValueError(obj.Error or tr('プレビューと作成結果が一致しません。', 'Preview and result do not match.'))
            for dependent in obj.InListRecursive:
                if ('Invalid' in dependent.State or getattr(dependent, 'Error', '') or
                    (hasattr(dependent, 'Shape') and (dependent.Shape.isNull() or not dependent.Shape.isValid()
                        or (dependent.Name in downstream and not dependent.Shape.Solids)))):
                    raise ValueError(tr('後続の加工が成立しないため変更を取り消しました。',
                                        'The edit was cancelled because a later feature would become invalid.'))
            if not existing:
                source.Visibility = False
                obj.Visibility = True
        return obj
    except Exception:
        source.Visibility = visible
        raise
