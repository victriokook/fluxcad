"""Parametric signed-mm resizing along the source's world X/Y/Z axes."""
import math
import FreeCAD as App
import Part
import model
from i18n import tr

AXES = ('X', 'Y', 'Z')


def source_shape(obj):
    from model_combine import solid
    return solid(obj)


def bounds(shape):
    # Tight bounds matter after non-uniform scaling converts circles to splines.
    return shape.optimalBoundingBox(False, False)


def dimensions(shape):
    box = bounds(shape)
    return (box.XLength, box.YLength, box.ZLength)


def resize(shape, delta):
    original = dimensions(shape)
    if len(delta) != 3 or not all(math.isfinite(v) for v in delta):
        raise ValueError(tr('増減量には有限の数値を指定してください。', 'Enter finite dimension changes.'))
    target = tuple(a + b for a, b in zip(original, delta))
    if any(a <= 1e-7 or b < .001 for a, b in zip(original, target)):
        raise ValueError(tr('変更後の各寸法を0.001 mm以上にしてください。',
                            'Each resulting dimension must be at least 0.001 mm.'))
    if not any(abs(v) > 1e-12 for v in delta):
        return shape.copy()
    factors = tuple(b / a for a, b in zip(original, target))
    center = bounds(shape).Center
    matrix = App.Matrix()
    matrix.A11, matrix.A22, matrix.A33 = factors
    matrix.A14, matrix.A24, matrix.A34 = tuple(c * (1 - f) for c, f in zip(center, factors))
    result = shape.transformGeometry(matrix)
    if (result.isNull() or not result.isValid() or len(result.Solids) != len(shape.Solids)
            or result.Volume <= 1e-9):
        raise ValueError(tr('この寸法では有効な立体を作成できません。', 'These dimensions cannot produce a valid solid.'))
    if any(abs(a-b) > max(1e-5, b*1e-7) for a, b in zip(dimensions(result), target)):
        raise ValueError(tr('指定した寸法と変形結果が一致しません。', 'The resized shape does not match the requested dimensions.'))
    return result


def changes(obj):
    return tuple(getattr(obj, 'Delta'+axis).Value for axis in AXES)


def containers(obj):
    result = []
    parent = obj.getParentGeoFeatureGroup()
    while parent and parent not in result:
        result.append(parent)
        parent = parent.getParentGeoFeatureGroup()
    return result


def mark_reference_frame(obj):
    obj.addProperty('App::PropertyBool', 'InheritSourceFrame', 'FluxCAD')
    obj.InheritSourceFrame = True
    obj.setEditorMode('InheritSourceFrame', 2)

class DimensionScale:
    def __init__(self, obj):
        obj.Proxy = self

    def execute(self, obj):
        placement = App.Placement(obj.Placement)
        try:
            result = resize(source_shape(obj.Source), changes(obj))
            # Keep a subsequently moved result's Placement separate from geometry.
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


def preview(source, delta, existing=None):
    result = resize(source_shape(source), delta)
    if existing:
        result.Placement = existing.getGlobalPlacement().multiply(result.Placement)
    return result


def apply(doc, source, delta, existing=None):
    if not source or source.Document != doc:
        raise ValueError(tr('現在の文書のボディを選択してください。', 'Select a body in the current document.'))
    if existing and (existing.Document != doc or not getattr(existing, 'FluxDimensionScale', False)
                     or existing.Source != source):
        raise ValueError(tr('寸法変更の履歴を選択してください。', 'Select a Resize by Dimensions feature.'))
    previous = changes(existing) if existing else (0, 0, 0)
    from parameters import expression
    if existing and any(expression(existing, 'Delta'+axis) and abs(value-old) > 1e-12
                        for axis, value, old in zip(AXES, delta, previous)):
        raise ValueError(tr('増減量は式で制御されています。先にその式を編集してください。',
                            'The changes are controlled by expressions. Edit those expressions first.'))
    if all(abs(a-b) < 1e-12 for a, b in zip(delta, previous)):
        raise ValueError(tr('変更する増減量を入力してください。', 'Enter a dimension change.'))
    expected = preview(source, delta, existing)
    downstream = {o.Name for o in existing.InListRecursive if hasattr(o, 'Shape') and o.Shape.Solids} if existing else set()
    visible = bool(source.Visibility)
    try:
        with model.transaction(doc, tr('寸法で拡大・縮小', 'Resize by Dimensions')):
            obj = existing
            if obj is None:
                obj = doc.addObject('Part::FeaturePython', 'DimensionScale')
                mark_reference_frame(obj)
                obj.Label = tr('寸法変更', 'Dimension Resize')
                obj.addProperty('App::PropertyBool', 'FluxDimensionScale', 'FluxCAD')
                obj.FluxDimensionScale = True
                obj.setEditorMode('FluxDimensionScale', 2)
                obj.addProperty('App::PropertyLinkGlobal', 'Source', 'FluxCAD')
                obj.Source = source
                obj.setEditorMode('Source', 1)
                obj.addProperty('App::PropertyLinkListGlobal', 'SourceContainers', 'FluxCAD')
                obj.SourceContainers = containers(source)
                obj.setEditorMode('SourceContainers', 2)
                for axis in AXES:
                    obj.addProperty('App::PropertyDistance', 'Delta'+axis, 'Dimensions',
                                    'Signed change in total '+axis+' dimension, in mm, relative to Source')
                obj.addProperty('App::PropertyString', 'Error', 'FluxCAD')
                obj.setEditorMode('Error', 1)
                DimensionScale(obj)
                obj.ViewObject.Proxy = 0
                for prop in ('ShapeColor', 'LineColor', 'PointColor', 'Transparency', 'DisplayMode'):
                    setattr(obj.ViewObject, prop, getattr(source.ViewObject, prop))
            for axis, value in zip(AXES, delta):
                if not expression(obj, 'Delta'+axis):
                    setattr(obj, 'Delta'+axis, value)
            doc.recompute()
            actual = model.world_shape(obj)
            tolerance = max(1e-6, expected.Volume*1e-7)
            if (obj.Error or actual.isNull() or not actual.isValid() or 'Invalid' in obj.State
                    or abs(actual.Volume-expected.Volume) > tolerance
                    or abs(actual.common(expected).Volume-expected.Volume) > tolerance):
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
