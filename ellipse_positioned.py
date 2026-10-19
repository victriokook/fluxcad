import math
import FreeCAD as App
import Sketcher
from i18n import tr

def add(sketch,width,height,x=0.,y=0.):
    import ellipse_dimensions
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and -1000000<=v<=1000000 and math.isfinite(v) for v in (x,y)):raise ValueError(tr('中心X/Yは±1000000 mm以内の有限値にしてください。','Center X/Y must be finite numbers within±1000000 mm.'))
    index=ellipse_dimensions.add(sketch,width,height)
    if x==0 and y==0:return index
    centers=[i for i,c in enumerate(sketch.Constraints) if c.Type=='Coincident' and c.First==index and c.FirstPos==3 and c.Second==-1 and c.SecondPos==1]
    if len(centers)!=1:raise ValueError(tr('中心拘束を特定できません。','Cannot identify center constraint.'))
    sketch.delConstraint(centers[0]);existing={c.Name for c in sketch.Constraints}
    for kind,value,base in (('DistanceX',x,'EllipseCenterX'),('DistanceY',y,'EllipseCenterY')):
        ci=sketch.addConstraint(Sketcher.Constraint(kind,index,3,float(value)))
        if ci<0:raise ValueError(tr('中心位置を拘束できません。','Cannot constrain ellipse center.'))
        name=base;suffix=2
        while name in existing:name=base+str(suffix);suffix+=1
        sketch.renameConstraint(ci,name);existing.add(name)
    if sketch.solve()!=0:raise ValueError(tr('楕円の中心位置が成立しません。','Cannot solve ellipse center position.'))
    return index

def add_fields(form):
    from PySide import QtWidgets as W
    fields=[]
    for key,label in (('X',tr('中心X（スケッチ座標）','Center X (sketch coordinates)')),('Y',tr('中心Y（スケッチ座標）','Center Y (sketch coordinates)'))):
        field=W.QDoubleSpinBox();field.setObjectName('FluxEllipseCenter'+key);field.setDecimals(3);field.setRange(-1000000,1000000);field.setSuffix(' mm');field.setValue(0);form.addRow(label,field);fields.append(field)
    return tuple(fields)

def note():
    return tr('横X・縦Yの全長と中心位置をスケッチ座標で指定します。\n中心X/Yの既定は0（原点）です。\n長短軸の入替は再作成、同寸法は円を使ってください。','Enter full local X/Y lengths and the center in sketch coordinates.\nDefault center X/Y is0 (origin).\nRecreate to swap major/minor axes; use Circle for equal sizes.')


def label(entry):
    return tr('楕円 %d — %.3f × %.3f mm（中心 %.3f, %.3f）','Ellipse %d — %.3f × %.3f mm (center %.3f, %.3f)')%(entry['index']+1,entry['width'],entry['height'],entry['center_x'],entry['center_y'])
