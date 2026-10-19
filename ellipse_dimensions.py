import math
import FreeCAD as App
import Part, Sketcher
from i18n import tr
def add(sketch,width,height):
    if getattr(sketch,'TypeId',None)!='Sketcher::SketchObject':raise ValueError(tr('先にスケッチの編集を開始してください。','Start sketch editing first'))
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and .002<=v<=1000000 for v in (width,height)):raise ValueError(tr('寸法は0.002〜1000000 mmの有限値にしてください。','Dimensions must be finite and between 0.002 and 1000000 mm'))
    if abs(width-height)<=1e-7*max(width,height):raise ValueError(tr('同寸法またはほぼ同寸法の場合は円を使ってください。','Equal or nearly equal dimensions: use Circle'))
    a,b=max(width,height)/2,min(width,height)/2
    ellipse=Part.Ellipse(App.Vector(),a,b)
    vertical=height>width
    if vertical:ellipse.AngleXU=math.pi/2
    index=sketch.addGeometry(ellipse,False)
    p=App.Vector(0,a,0) if vertical else App.Vector(a,0,0)
    q=App.Vector(-b,0,0) if vertical else App.Vector(0,b,0)
    major=sketch.addGeometry(Part.LineSegment(p,-p),True)
    minor=sketch.addGeometry(Part.LineSegment(q,-q),True)
    constraints=[Sketcher.Constraint('InternalAlignment:EllipseMajorDiameter',major,index),Sketcher.Constraint('InternalAlignment:EllipseMinorDiameter',minor,index),Sketcher.Constraint('Vertical' if vertical else 'Horizontal',major),Sketcher.Constraint('Coincident',index,3,-1,1)]
    for c in constraints:
        if sketch.addConstraint(c)<0:raise ValueError(tr('楕円の寸法拘束を作成できません。','Cannot constrain ellipse'))
    existing={c.Name for c in sketch.Constraints}
    for line,value,base in ((major,2*a,'EllipseHeight' if vertical else 'EllipseWidth'),(minor,2*b,'EllipseWidth' if vertical else 'EllipseHeight')):
        ci=sketch.addConstraint(Sketcher.Constraint('Distance',line,value))
        if ci<0:raise ValueError(tr('楕円の寸法拘束を作成できません。','Cannot constrain ellipse'))
        name=base;suffix=2
        while name in existing:name=base+str(suffix);suffix+=1
        sketch.renameConstraint(ci,name);existing.add(name)
    if sketch.solve()!=0:raise ValueError(tr('楕円の寸法が成立しません。','Cannot solve ellipse'))
    return index


def show(ws):
    from PySide import QtWidgets as W
    import model
    import ellipse_positioned
    sketch=ws.current_sketch()
    if not sketch:raise ValueError(tr('スケッチの編集を開始してください','Start sketch editing first'))
    doc=sketch.Document;name=sketch.Name
    ws.select_sketch_geometry()
    dialog=W.QDialog(ws.main);dialog.setWindowTitle(tr('楕円：横幅・縦高さ','Ellipse: Width / Height'))
    dialog.setObjectName('FluxEllipseDimensions');dialog.setMinimumWidth(420)
    form=W.QFormLayout(dialog)
    width=W.QDoubleSpinBox();height=W.QDoubleSpinBox()
    for field,value,key in ((width,100,'FluxEllipseWidth'),(height,60,'FluxEllipseHeight')):
        field.setObjectName(key);field.setDecimals(3);field.setRange(.002,1000000);field.setSuffix(' mm');field.setValue(value)
    form.addRow(tr('横幅（全長）','Width (full length)'),width);form.addRow(tr('縦高さ（全長）','Height (full length)'),height)
    center_x,center_y=ellipse_positioned.add_fields(form)
    note=W.QLabel(ellipse_positioned.note());note.setWordWrap(True);form.addRow(note)
    buttons=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel);form.addRow(buttons)
    buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
    if not dialog.exec_():return
    if App.ActiveDocument is not doc or doc.getObject(name) is not sketch or ws.current_sketch() is not sketch:raise ValueError(tr('編集されたスケッチが変更されています','The edited sketch has changed'))
    with model.transaction(doc,tr('寸法指定の楕円','Dimensioned ellipse')):ellipse_positioned.add(sketch,width.value(),height.value(),center_x.value(),center_y.value())
    ws.refresh()
