"""Even equiangular polygons with alternating, editable native lengths."""
import math
import FreeCAD as App
import Part, Sketcher
from i18n import tr

def add(sketch, count, length_a, length_b):
    if not isinstance(count,int) or count < 4 or count > 120 or count % 2:
        raise ValueError(tr('辺数は4〜120の偶数にしてください。','Choose an even side count from 4 to 120.'))
    if not all(math.isfinite(v) and v >= .001 for v in (length_a,length_b)):
        raise ValueError(tr('辺の長さは0.001 mm以上にしてください。','Side lengths must be at least 0.001 mm.'))
    offset=sketch.GeometryCount
    points=[App.Vector(0,0,0)]
    for i in range(count):
        angle=2*math.pi*i/count;length=length_a if i%2==0 else length_b
        points.append(points[-1]+App.Vector(length*math.cos(angle),length*math.sin(angle),0))
    points[-1]=points[0]
    # The vertex mean is the rotational center, including 6/10/... sides
    # whose alternating lengths do not give opposite-vertex symmetry.
    center=sum(points[:-1],App.Vector())/count
    points=[point-center for point in points]
    for i in range(count):sketch.addGeometry(Part.LineSegment(points[i],points[i+1]),False)
    for i in range(count):
        sketch.addConstraint(Sketcher.Constraint('Coincident',offset+i,2,offset+(i+1)%count,1))
    # Fix all directions; closure determines the final two lengths. Omitting
    # their Equal constraints avoids redundancy and mirrored solver branches.
    for i in range(2,count-2):sketch.addConstraint(Sketcher.Constraint('Equal',offset+i,offset+i%2))
    for i in range(count):
        if i==0:sketch.addConstraint(Sketcher.Constraint('Horizontal',offset))
        else:sketch.addConstraint(Sketcher.Constraint('Angle',offset+i,2*math.pi*i/count))
    existing={c.Name for c in sketch.Constraints}
    names=[]
    for i,length in enumerate((length_a,length_b)):
        index=sketch.addConstraint(Sketcher.Constraint('Distance',offset+i,length))
        name='SideA' if i==0 else 'SideB';suffix=2
        while name in existing:
            name=('SideA' if i==0 else 'SideB')+str(suffix);suffix+=1
        sketch.renameConstraint(index,name)
        names.append(name);existing.add(name)
    # Anchor the first vertex through expressions in A/B rather than fixing
    # its coordinates: dimension edits must keep the center at the origin.
    coefficients=[]
    for parity in (0,1):
        point=App.Vector();total=App.Vector()
        for i in range(count):
            total+=point
            if i%2==parity:
                angle=2*math.pi*i/count
                point+=App.Vector(math.cos(angle),math.sin(angle),0)
        coefficients.append(-total/count)
    for coordinate,kind in (('x','DistanceX'),('y','DistanceY')):
        index=sketch.addConstraint(Sketcher.Constraint(kind,offset,1,getattr(points[0],coordinate)))
        formula=' + '.join('(%0.17g) * Constraints.%s'%(getattr(c,coordinate),name)
                           for c,name in zip(coefficients,names))
        sketch.setExpression('Constraints[%d]'%index,formula)
    if sketch.solve()!=0:raise ValueError(tr('多角形の寸法が成立しません。','Cannot solve the polygon dimensions.'))
    sketch.Document.recompute()
    return sketch

def show(ws):
    from PySide import QtWidgets as W
    import model
    if ws.current_sketch():
        raise ValueError(tr('スケッチ編集を終了してから作成してください。','Finish sketch editing before creating this polygon.'))
    dialog=W.QDialog(ws.main);dialog.setWindowTitle(tr('2種類の辺の多角形','Alternating Side Polygon'))
    form=W.QFormLayout(dialog)
    count=W.QSpinBox();count.setRange(4,120);count.setSingleStep(2);count.setValue(12)
    a=W.QDoubleSpinBox();b=W.QDoubleSpinBox()
    for field,value in ((a,30),(b,15)):
        field.setDecimals(3);field.setRange(.001,1000000);field.setSuffix(' mm');field.setValue(value)
    form.addRow(tr('辺数（偶数）','Sides (even)'),count)
    form.addRow(tr('辺の長さ A','Side Length A'),a);form.addRow(tr('辺の長さ B','Side Length B'),b)
    note=W.QLabel(tr('A・Bを交互に配置し、内角を揃えます。\n中心を作業平面のX=0・Y=0に配置します。最初の辺は+X方向です。\nSideA・SideB寸法を変更しても中心は原点を保ちます。',
                        'Alternates A/B with equal interior angles.\nCentered at work plane X=0, Y=0; first edge along +X.\nEditing SideA/SideB keeps the center at the origin.'))
    form.addRow(note)
    buttons=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel)
    form.addRow(buttons);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
    if not dialog.exec_():return
    ws.grid.update();doc=ws.doc()
    with model.transaction(doc,tr('2種類の辺の多角形','Alternating Side Polygon')):
        sketch=doc.addObject('Sketcher::SketchObject','AlternatingPolygon')
        sketch.Label=tr('2種類の辺の多角形','Alternating Side Polygon')
        sketch.Placement=App.Placement(ws.grid.plane)
        add(sketch,count.value(),a.value(),b.value())
    import FreeCADGui as Gui
    Gui.Selection.clearSelection();Gui.Selection.addSelection(sketch);ws.refresh()
