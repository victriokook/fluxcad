"""Offset construction planes and attached sketches using native features."""
from i18n import tr
import FreeCAD as App
import Part
import model


def placement(base='XY',offset=10):
    if base not in ('XY','XZ','YZ'):raise ValueError(tr('基準平面を選択してください。'))
    normal={'XY':App.Vector(0,0,1),'XZ':App.Vector(0,1,0),'YZ':App.Vector(1,0,0)}[base]
    return App.Placement(normal*offset,App.Rotation(App.Vector(0,0,1),normal))


def preview(base='XY',offset=10,size=80):
    face=Part.makePlane(size,size)
    face.Placement=placement(base,offset)
    return face


def create(doc,base='XY',offset=10,existing=None):
    pose=placement(base,offset)
    if existing and existing.Document!=doc:raise ValueError(tr('同じ文書内の平面を選択してください。'))
    with model.transaction(doc,tr('オフセット平面を編集') if existing else tr('オフセット平面')):
        obj=existing
        if obj is None:
            # A finite native plane keeps Fit All and scene bounds well-defined.
            obj=doc.addObject('Part::Plane','OffsetPlane');obj.Label=tr('オフセット平面')
            obj.addProperty('App::PropertyBool','FluxPlane','FluxCAD');obj.FluxPlane=True;obj.setEditorMode('FluxPlane',2)
            obj.addProperty('App::PropertyEnumeration','BasePlane','Plane');obj.BasePlane=['XY','XZ','YZ']
            obj.setEditorMode('BasePlane',1)
            obj.addProperty('App::PropertyDistance','Offset','Plane')
            obj.Length=80;obj.Width=80
        for axis in 'xyz':obj.setExpression('Placement.Base.'+axis,None)
        obj.BasePlane=base;obj.Offset=offset;obj.Placement=pose
        obj.setExpression('Placement.Base.'+{'XY':'z','XZ':'y','YZ':'x'}[base],'Offset')
        doc.recompute()
        for feature in [obj]+obj.InListRecursive:
            if ('Invalid' in feature.State or (hasattr(feature,'Shape') and
                    ((feature.Shape.isNull() and feature.TypeId!='Sketcher::SketchObject') or
                     (not feature.Shape.isNull() and not feature.Shape.isValid())))):
                raise ValueError(tr('平面に従う形状を更新できないため、変更を取り消しました。'))
        obj.ViewObject.Transparency=75
        obj.ViewObject.ShapeColor=(0.96,0.68,0.28)
        obj.ViewObject.LineColor=(0.72,0.44,0.14)
        if not existing:obj.Visibility=True
    return obj


def sketch_on_plane(doc,plane):
    if not getattr(plane,'FluxPlane',False) or plane.Document!=doc:
        raise ValueError(tr('同じ文書内の構築平面を選択してください。'))
    if ('Invalid' in plane.State or getattr(plane,'Error','') or plane.Shape.isNull() or not plane.Shape.isValid() or
            len(plane.Shape.Faces)!=1 or not isinstance(plane.Shape.Faces[0].Surface,Part.Plane)):
        raise ValueError(tr('構築平面の参照を修正してからスケッチを作成してください。','Repair the construction plane references before creating a sketch.'))
    with model.transaction(doc,tr('平面上にスケッチを作成')):
        obj=doc.addObject('Sketcher::SketchObject','Sketch');obj.Label=tr('スケッチ')
        obj.AttachmentSupport=[(plane,['Face1'])];obj.MapMode='FlatFace'
        doc.recompute();plane.Visibility=False
    return obj
