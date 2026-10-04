"""World-space body transforms and independent native shape copies."""
from i18n import tr
import math
import FreeCAD as App
import model


def targets(doc, objects, copy=False):
    result = model.movable_solids(doc,objects)
    if not copy:
        for obj in result:
            if hasattr(obj,'MapMode') and obj.MapMode!='Deactivated':
                raise ValueError(tr('%s は面などに固定されています。コピーを作成するか、アタッチメントを解除してください。')%obj.Label)
            if any(other!=obj and other in obj.InListRecursive for other in result):
                raise ValueError(tr('加工前と加工後のボディを同時に移動できません。ブラウザーで現在のボディを選択してください。'))
    return result


def transform(mode='rotate', axis='Z', angle=0, center=(0,0,0), delta=(0,0,0)):
    values = [angle,*center,*delta]
    if len(center)!=3 or len(delta)!=3 or not all(math.isfinite(v) for v in values):
        raise ValueError(tr('座標と角度には有限の数値を指定してください。'))
    if mode=='translate':
        return App.Placement(App.Vector(*delta),App.Rotation())
    if mode!='rotate' or axis not in ('X','Y','Z'):
        raise ValueError(tr('回転軸はX・Y・Zから選択してください。'))
    vector = App.Vector(*{'X':(1,0,0),'Y':(0,1,0),'Z':(0,0,1)}[axis])
    rotation = App.Rotation(vector,angle)
    pivot = App.Vector(*center)
    return App.Placement(pivot-rotation.multVec(pivot),rotation)


def changed(placement):
    return placement.Base.Length>1e-10 or abs(math.sin(placement.Rotation.Angle/2))>1e-10


def shapes(objects, placement):
    result = []
    for obj in objects:
        shape = model.world_shape(obj)
        shape.Placement = placement.multiply(shape.Placement)
        result.append(shape)
    return result


def selection_center(objects):
    bounds = App.BoundBox()
    for obj in objects:
        bounds.add(model.world_shape(obj).BoundBox)
    return tuple(bounds.Center)


def apply(doc, objects, copy=False, **values):
    placement = transform(**values)
    return apply_placement(doc,objects,placement,copy)


def apply_placement(doc, objects, placement, copy=False, label=None, stationary=()):
    objects = targets(doc,objects,copy)
    if not copy and not changed(placement):
        raise ValueError(tr('移動量または回転角度を指定してください。'))
    expected = shapes(objects,placement)
    import model_assembly as assembly
    driven=assembly.affected_poses(doc,{o:placement.multiply(o.getGlobalPlacement()) for o in objects if getattr(o,'FluxComponent',False)}) if not copy else {}
    fixed = [(obj,obj.Shape.hashCode(),str(obj.getGlobalPlacement())) for obj in stationary]
    results = []
    with model.transaction(doc,label or (tr('ボディをコピー') if copy else tr('ボディを移動 / 回転'))):
        for obj,shape in zip(objects,expected):
            if copy:
                # A native Part::Feature stores the complete snapshot without
                # a Python proxy or a dependency on the original document.
                result = doc.addObject('Part::Feature','BodyCopy')
                result.Label = obj.Label+tr(' (コピー)')
                result.Shape = shape
                for prop in ('ShapeColor','LineColor','PointColor','Transparency','DisplayMode'):
                    setattr(result.ViewObject,prop,getattr(obj.ViewObject,prop))
                result.Visibility = True
            else:
                local = App.Placement(obj.Placement)
                global_placement = obj.getGlobalPlacement()
                parent = global_placement.multiply(local.inverse())
                obj.Placement = parent.inverse().multiply(placement).multiply(global_placement)
                result = obj
            results.append(result)
        doc.recompute()
        assembly.verify(driven)
        for obj,shape_hash,pose in fixed:
            if obj.Shape.hashCode()!=shape_hash or str(obj.getGlobalPlacement())!=pose:
                raise ValueError(tr('合わせ先の形状も変更されるため、操作を取り消しました。'))
        for obj,shape in zip(results,expected):
            actual = model.world_shape(obj)
            tolerance = max(1e-7,shape.Volume*1e-7)
            if (actual.isNull() or not actual.isValid() or
                    abs(actual.Volume-shape.Volume)>tolerance or
                    abs(actual.common(shape).Volume-shape.Volume)>tolerance):
                raise ValueError(tr('プレビューどおりに配置できないため、操作を取り消しました。'))
    return results
