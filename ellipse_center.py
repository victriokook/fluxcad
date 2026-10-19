import math
import FreeCAD as App
import Sketcher
from i18n import tr
import ellipse_resize as core
import parameters,model

def settings(sketch,index):
    entry=next((p for p in core.candidates(sketch) if p['index']==index),None)
    if entry is None:raise ValueError(tr('対応する数値楕円がありません。','No supported dimensioned ellipse.'))
    origin=[];axes={'x':[],'y':[]}
    for ci,c in enumerate(sketch.Constraints):
        if not c.IsActive:continue
        if c.Type=='Coincident' and c.First==index and c.FirstPos==3 and c.Second==-1 and c.SecondPos==1:origin.append(ci)
        for key,kind in (('x','DistanceX'),('y','DistanceY')):
            if c.Type==kind and c.First==index and c.FirstPos==3 and c.Second==-2000 and sketch.getDriving(ci):axes[key].append(ci)
    if len(origin)==1 and not axes['x'] and not axes['y']:return dict(index=index,x=0.,y=0.,x_index=None,y_index=None,x_expression='',y_expression='',origin_index=origin[0])
    if origin or len(axes['x'])!=1 or len(axes['y'])!=1:raise ValueError(tr('中心拘束が不完全または重複しています。','Center constraints are incomplete or ambiguous.'))
    result=dict(index=index,origin_index=None)
    for key in ('x','y'):
        ci=axes[key][0];result[key]=sketch.getDatum(ci).Value;result[key+'_index']=ci;result[key+'_expression']=parameters.expression(sketch,'Constraints[%d]'%ci)
    return result

def move(sketch,index,x,y,expected=None):
    doc=sketch.Document;name=sketch.Name
    if doc is None or not isinstance(name,str) or App.getDocument(doc.Name) is not doc or doc.getObject(name) is not sketch:raise ValueError(tr('対象スケッチが閉じられました。','The sketch is no longer available.'))
    if expected is not None and core.fingerprint(sketch)!=expected:raise ValueError(tr('スケッチが変更されました。開き直してください。','Sketch changed; reopen the dialog.'))
    if type(index) is not int or not all(isinstance(v,(int,float)) and not isinstance(v,bool) and -1000000<=v<=1000000 and math.isfinite(v) for v in (x,y)):raise ValueError(tr('中心X/Yは±1000000 mm以内の有限値にしてください。','Center X/Y must be finite numbers within±1000000 mm.'))
    state=settings(sketch,index);values=dict(x=float(x),y=float(y));changes=[]
    for key in ('x','y'):
        if state[key+'_expression']:
            if abs(values[key]-state[key])>1e-7:raise ValueError(tr('連動中の位置はパラメータ画面で変更してください。','Edit linked coordinates in Change Parameters.'))
        elif values[key]!=state[key]:changes.append(key)
    if not changes:return index
    healthy={o.Name:bool(o.Shape.Solids) for o in sketch.InListRecursive if hasattr(o,'Shape') and not o.Shape.isNull() and o.Shape.isValid()}
    identities=[sketch.getGeometryId(i) for i in range(sketch.GeometryCount)]
    with model.transaction(doc,tr('楕円の中心位置を変更','Move Ellipse Center')):
        if state['origin_index'] is not None:
            sketch.delConstraint(state['origin_index']);names={c.Name for c in sketch.Constraints}
            for key,kind,base in (('x','DistanceX','EllipseCenterX'),('y','DistanceY','EllipseCenterY')):
                ci=sketch.addConstraint(Sketcher.Constraint(kind,index,3,values[key]))
                if ci<0:raise ValueError(tr('中心位置を拘束できません。','Cannot constrain ellipse center.'))
                name=base;suffix=2
                while name in names:name=base+str(suffix);suffix+=1
                sketch.renameConstraint(ci,name);names.add(name)
        else:
            for key in changes:sketch.setDatum(state[key+'_index'],App.Units.Quantity(str(values[key])+' mm'))
        if sketch.solve()!=0:raise ValueError(tr('楕円の中心位置が成立しません。','Cannot solve ellipse center.'))
        doc.recompute()
        if identities!=[sketch.getGeometryId(i) for i in range(sketch.GeometryCount)] or sketch.Shape.isNull() or not sketch.Shape.isValid():raise ValueError(tr('スケッチ形状が成立しません。','Invalid sketch shape.'))
        for name,solid in healthy.items():
            other=doc.getObject(name)
            if other is None or other.Shape.isNull() or not other.Shape.isValid() or 'Invalid' in other.State or getattr(other,'Error','') or (solid and not other.Shape.Solids):raise ValueError(tr('後続の加工が成立しないため変更を取り消しました。','Edit cancelled because a later feature is invalid.'))
    return index
