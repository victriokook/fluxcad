"""Planar and cylindrical face alignment in world space."""
from i18n import tr
import math
import re
import FreeCAD as App
import Part
import model
import model_transform as transforms
from browser import body_owner


def reference(doc, name, subname):
    obj=doc.getObject(name) if doc else None
    if not obj or not re.search(r'(^|\.)Face[1-9][0-9]*$',subname):
        raise ValueError(tr('平面または円筒の側面をクリックしてください。辺や頂点は選択できません。',
                            'Click a planar face or cylindrical side face. Edges and vertices are not supported.'))
    # Native selection can address a feature through its App::Part/Body path.
    resolved=obj.getSubObject(subname,1)
    obj=resolved or obj
    face_name=subname.rsplit('.',1)[-1]
    face(obj,face_name)
    return obj,face_name


def face(obj, name):
    if not re.fullmatch(r'Face[1-9][0-9]*',name) or not hasattr(obj,'Shape'):
        raise ValueError(tr('平面または円筒面を選択してください。','Select a planar or cylindrical face.'))
    try:
        result=model.world_shape(obj).getElement(name)
    except Exception:
        raise ValueError(tr('選択した面がありません。面を選び直してください。'))
    if not isinstance(result.Surface,(Part.Plane,Part.Cylinder)):
        raise ValueError(tr('平面または円筒の側面を選択してください。円すい・球面などには対応していません。',
                            'Select a planar face or cylindrical side face. Cones, spheres and other surfaces are not supported.'))
    return result


def kind(selected_face):
    if isinstance(selected_face.Surface,Part.Plane):return 'plane'
    if isinstance(selected_face.Surface,Part.Cylinder):return 'cylinder'
    raise ValueError(tr('平面または円筒面を選択してください。','Select a planar or cylindrical face.'))


def cylinder_axis(selected_face):
    """World-space axial midpoint and positive V direction, independent of face orientation."""
    if kind(selected_face)!='cylinder':
        raise ValueError(tr('円筒の側面を選択してください。','Select the cylindrical side face.'))
    u0,u1,v0,v1=selected_face.ParameterRange
    axis=selected_face.valueAt(u0,v1)-selected_face.valueAt(u0,v0)
    if axis.Length<1e-9:raise ValueError(tr('円筒面の軸を取得できません。','Could not determine the cylinder axis.'))
    axis.normalize()
    # Surface evaluations include the face's placement. Opposite points avoid
    # assumptions about an inner wall's reversed normal or a partial arc's centroid.
    origin=(selected_face.valueAt(u0,(v0+v1)/2)+selected_face.valueAt(u0+math.pi,(v0+v1)/2))*.5
    return origin,axis


def signature(obj):
    return obj.Shape.hashCode(),str(obj.getGlobalPlacement())


def normal(planar_face):
    u0,u1,v0,v1=planar_face.ParameterRange
    result=planar_face.normalAt((u0+u1)/2,(v0+v1)/2)
    result.normalize()
    return result


def rotation_between(source_normal,desired):
    cross=source_normal.cross(desired);dot=max(-1.0,min(1.0,source_normal.dot(desired)))
    # FreeCAD's vector-to-vector constructor can produce NaNs for nearly
    # parallel normalized vectors. atan2 also handles tiny angular differences.
    if cross.Length<1e-12:
        if dot>=0:turn=App.Rotation()
        else:
            helper=min((App.Vector(1,0,0),App.Vector(0,1,0),App.Vector(0,0,1)),key=lambda v:abs(v.dot(source_normal)))
            turn=App.Rotation(source_normal.cross(helper),180)
    else:turn=App.Rotation(cross,math.degrees(math.atan2(cross.Length,dot)))
    return turn


def placement(source_face, target_face, gap=0, angle=0, opposed=True, center=True):
    if not math.isfinite(gap) or not math.isfinite(angle):
        raise ValueError(tr('距離と角度には有限の数値を指定してください。','Distance and angle must be finite numbers.'))
    shape_kind=kind(source_face)
    if kind(target_face)!=shape_kind:
        raise ValueError(tr('平面どうし、または円筒面どうしを選択してください。','Select two planar faces or two cylindrical faces.'))
    if shape_kind=='cylinder':
        origin,source_axis=cylinder_axis(source_face);destination,target_axis=cylinder_axis(target_face)
        turn=rotation_between(source_axis,-target_axis if opposed else target_axis)
        turn=App.Rotation(target_axis,angle).multiply(turn)
        if not center:
            destination+=target_axis*(origin-destination).dot(target_axis)
        destination+=target_axis*gap
        return App.Placement(destination-turn.multVec(origin),turn)
    source_normal=normal(source_face);target_normal=normal(target_face)
    turn=rotation_between(source_normal,-target_normal if opposed else target_normal)
    turn=App.Rotation(target_normal,angle).multiply(turn)
    origin=source_face.CenterOfMass
    destination=target_face.CenterOfMass
    if not center:
        # Rotate around the source face's centroid, then shift only along the
        # target normal. Its coordinates in the target plane stay unchanged.
        destination=origin+target_normal*(destination-origin).dot(target_normal)
    destination+=target_normal*gap
    return App.Placement(destination-turn.multVec(origin),turn)


def prepare(doc, source, target, copy=False, **values):
    source_obj,source_name=source;target_obj,target_name=target
    if not doc or source_obj.Document!=doc or target_obj.Document!=doc:
        raise ValueError(tr('同じ文書内の面を選択してください。'))
    moving=transforms.targets(doc,[source_obj],copy)[0]
    fixed=body_owner(target_obj)
    if moving==fixed:
        raise ValueError(tr('移動するボディとは別のボディ、または構築平面を合わせ先に選択してください。'))
    if not copy and (target_obj in moving.InListRecursive or fixed in moving.InListRecursive):
        raise ValueError(tr('合わせ先が移動するボディに依存しています。「コピーを作成」を選ぶか、別の合わせ先を選択してください。'))
    pose=placement(face(source_obj,source_name),face(target_obj,target_name),**values)
    return moving,pose


def apply(doc, source, target, copy=False, **values):
    moving,pose=prepare(doc,source,target,copy,**values)
    return transforms.apply_placement(doc,[moving],pose,copy,
        label=tr('コピーを位置合わせ') if copy else tr('ボディを位置合わせ'),stationary=[target[0]])[0]
