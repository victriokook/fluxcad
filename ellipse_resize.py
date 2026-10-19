import math,re
import FreeCAD as App
import Part
from i18n import tr
import model,parameters

def anchored_center(sketch,index):
    axes=set()
    for ci,c in enumerate(sketch.Constraints):
        if not c.IsActive:continue
        if c.Type=='Coincident' and c.First==index and c.FirstPos==3 and c.Second==-1 and c.SecondPos==1:return True
        if c.Type in ('DistanceX','DistanceY') and c.First==index and c.FirstPos==3 and c.Second==-2000 and sketch.getDriving(ci):axes.add(c.Type)
    return axes=={'DistanceX','DistanceY'}

def candidates(sketch):
    if getattr(sketch,'TypeId',None)!='Sketcher::SketchObject':raise ValueError(tr('スケッチを選んでください。','Select a sketch.'))
    result=[];geometry=sketch.Geometry;constraints=sketch.Constraints
    for index,geo in enumerate(geometry):
        if not isinstance(geo,Part.Ellipse) or sketch.getConstruction(index) or abs(geo.Center.z)>1e-7 or not anchored_center(sketch,index):continue
        bounds=geo.toShape().BoundBox;found={'width':[],'height':[]}
        lines={c.First for c in constraints if c.Type=='InternalAlignment' and c.IsActive and c.Second==index and 0<=c.First<len(geometry)}
        for ci,c in enumerate(constraints):
            if c.Type!='Distance' or not c.IsActive or not sketch.getDriving(ci) or c.First not in lines:continue
            line=geometry[c.First]
            if not isinstance(line,Part.LineSegment) or not sketch.getConstruction(c.First):continue
            delta=line.EndPoint-line.StartPoint
            if ((line.EndPoint+line.StartPoint)*.5-geo.Center).Length>1e-7:continue
            for key,size,aligned in (('width',bounds.XLength,abs(delta.y)<1e-7 and abs(delta.z)<1e-7),('height',bounds.YLength,abs(delta.x)<1e-7 and abs(delta.z)<1e-7)):
                if not aligned or not re.fullmatch('Ellipse'+('Width' if key=='width' else 'Height')+r'\d*',c.Name):continue
                value=sketch.getDatum(ci).Value
                if abs(value-size)<=max(1e-7,abs(size)*1e-7) and abs(delta.Length-value)<=max(1e-7,abs(value)*1e-7):found[key].append((ci,value,c.Name))
        if len(found['width'])==len(found['height'])==1:
            w,h=found['width'][0],found['height'][0]
            result.append(dict(index=index,width_index=w[0],height_index=h[0],width=w[1],height=h[1],width_name=w[2],height_name=h[2],center_x=geo.Center.x,center_y=geo.Center.y))
    return result

def fingerprint(sketch):
    return (sketch.GeometryCount,tuple(c.Content for c in sketch.Constraints),tuple(sketch.ExpressionEngine))

def resize(sketch,index,width,height,expected=None):
    doc=sketch.Document;name=sketch.Name
    if doc is None or not isinstance(name,str) or App.getDocument(doc.Name) is not doc or doc.getObject(name) is not sketch:raise ValueError(tr('対象スケッチが閉じられました。','The sketch is no longer available.'))
    if expected is not None and fingerprint(sketch)!=expected:raise ValueError(tr('スケッチが変更されました。開き直してください。','Sketch changed; reopen the dialog.'))
    entry=next((p for p in candidates(sketch) if p['index']==index),None)
    if entry is None:raise ValueError(tr('対応する数値楕円がありません。','No supported dimensioned ellipse.'))
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and .002<=v<=1000000 and math.isfinite(v) for v in (width,height)):raise ValueError(tr('寸法は0.002〜1000000 mmにしてください。','Dimensions must be finite, from0.002 to1000000 mm.'))
    if abs(width-height)<=1e-7*max(width,height) or (width>height)!=(entry['width']>entry['height']):raise ValueError(tr('長短軸の入替や同寸法は再作成してください。','Recreate to swap axes or use equal sizes.'))
    values=dict(width=float(width),height=float(height));changes={}
    for key in ('width','height'):
        ci=entry[key+'_index'];expr=parameters.expression(sketch,'Constraints[%d]'%ci)
        if expr:
            if abs(values[key]-entry[key])>1e-7:raise ValueError(tr('連動中の寸法はパラメータ画面で変更してください。','Edit linked dimensions in Change Parameters.'))
        elif values[key]!=entry[key]:changes[key]=ci
    if not changes:return index
    healthy={o.Name:bool(o.Shape.Solids) for o in sketch.InListRecursive if hasattr(o,'Shape') and not o.Shape.isNull() and o.Shape.isValid()}
    major,minor=('width','height') if entry['width']>entry['height'] else ('height','width')
    order=(minor,major) if values[major]<entry[minor] else (major,minor)
    with model.transaction(doc,tr('楕円の寸法を変更','Resize Ellipse')):
        for key in order:
            if key in changes:sketch.setDatum(changes[key],App.Units.Quantity(str(values[key])+' mm'))
        if sketch.solve()!=0:raise ValueError(tr('楕円の寸法が成立しません。','Cannot solve ellipse dimensions.'))
        doc.recompute()
        if sketch.Shape.isNull() or not sketch.Shape.isValid():raise ValueError(tr('スケッチ形状が成立しません。','Invalid sketch shape.'))
        for name,solid in healthy.items():
            other=doc.getObject(name)
            if other is None or other.Shape.isNull() or not other.Shape.isValid() or 'Invalid' in other.State or getattr(other,'Error','') or (solid and not other.Shape.Solids):raise ValueError(tr('後続の加工が成立しないため変更を取り消しました。','Edit cancelled because a later feature is invalid.'))
    return index


def selected_candidate(sketch, items):
    import FreeCADGui as Gui
    import re
    selected = set()
    supported = {entry['index']: position for position, entry in enumerate(items)}
    for entry in Gui.Selection.getSelectionEx():
        if entry.Object is not sketch:
            continue
        for name in entry.SubElementNames:
            match = re.fullmatch(r'Edge([1-9][0-9]*)', name)
            if match:
                index = int(match.group(1)) - 1
                if index in supported:
                    selected.add(index)
    return supported[next(iter(selected))] if len(selected) == 1 else 0
