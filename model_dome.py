import math
import FreeCAD as App
import Part
from i18n import tr

def outer_shape(**values):
    p=validate(values)
    m=App.Matrix();m.A11=p['width']/2;m.A22=p['depth']/2;m.A33=p['height']
    pieces=[]
    for angle in (0,90,180,270):
        quarter=Part.makeSphere(1,App.Vector(),App.Vector(0,0,1),0,90,90)
        quarter.rotate(App.Vector(),App.Vector(0,0,1),angle)
        pieces.append(quarter.transformGeometry(m))
    result=pieces[0].multiFuse(pieces[1:])
    expected=math.pi*p['width']*p['depth']*p['height']/6
    if result.isNull() or not result.isValid() or not result.isClosed() or len(result.Solids)!=1 or abs(result.Volume-expected)>max(1e-8,expected*1e-6):raise ValueError(tr('これらの寸法では正確な閉じたドームを作成できません','Cannot create an accurate closed dome with these dimensions'))
    return result


def validate(values):
    import model_dome_hollow
    p=dict(width=60.,depth=40.,height=15.,thickness=0.)
    if not isinstance(values,dict) or set(values)-set(p):raise ValueError(tr('ドームの寸法名を確認してください。','Unknown dome dimensions'))
    p.update(values)
    if not all(isinstance(p[k],(int,float)) and not isinstance(p[k],bool) and math.isfinite(p[k]) and .01<=p[k]<=100000 for k in ('width','depth','height')):raise ValueError(tr('ドームの寸法は0.01〜100000 mmの有限値にしてください。','Dome dimensions must be finite numbers from 0.01 to 100000 mm'))
    p['thickness']=model_dome_hollow.validate_thickness(p)
    return {k:float(v) for k,v in p.items()}
def shape(**values):
    import model_dome_hollow
    p=validate(values);outer=outer_shape(**p)
    return model_dome_hollow.hollow(outer,p['thickness']) if p['thickness'] else outer
def settings(obj):
    return dict(width=obj.BaseWidth.Value,depth=obj.BaseHeight.Value,height=obj.DomeHeight.Value,thickness=obj.WallThickness.Value if 'WallThickness' in obj.PropertiesList else 0.)
def setup(obj):
    for prop in ('BaseWidth','BaseHeight','DomeHeight','WallThickness'):obj.addProperty('App::PropertyLength',prop,'Dimensions')
    obj.addProperty('App::PropertyString','Error','FluxCAD');obj.setEditorMode('Error',1)
def assign(obj,p):
    if 'WallThickness' not in obj.PropertiesList:obj.addProperty('App::PropertyLength','WallThickness','Dimensions')
    expressions=dict(obj.ExpressionEngine)
    for key,prop in (('width','BaseWidth'),('depth','BaseHeight'),('height','DomeHeight'),('thickness','WallThickness')):
        if expressions.get(prop):
            if abs(getattr(obj,prop).Value-p[key])>1e-7:raise ValueError(tr('連動中の寸法はパラメータ画面で変更してください。','Edit the linked parameter instead of this dimension'))
        else:setattr(obj,prop,p[key])
def lock_fields(obj,fields):
    import parameters
    parameters.lock_fields(obj,{prop:fields[key] for key,prop in (('width','BaseWidth'),('depth','BaseHeight'),('height','DomeHeight'),('thickness','WallThickness'))})
def add_dimensions(obj,add):
    for prop,ja,en in (('BaseWidth','底面の横幅','Base Width'),('BaseHeight','底面の縦高さ','Base Height'),('DomeHeight','ドームの高さ','Dome Height'),('WallThickness','肉厚','Wall Thickness')):
        if prop in obj.PropertiesList:add(obj,obj,prop,'length',tr(ja,en))
def note():
    return tr('横幅・縦高さは底面の全長です。\n肉厚0は中実、正の肉厚は底面が開く中空です。\n外寸を保ち、曲面に沿った一定肉厚にします。','Width/height are full base lengths.\nZero thickness: solid; positive: hollow, open base.\nPreserves outside size with uniform normal thickness.')


def thickness_hint(values):
    try:
        axes=(float(values['width'])/2,float(values['depth'])/2,float(values['height']))
        if not all(math.isfinite(v) and v>0 for v in axes):return ''
        limit=.95*min(axes)**2/max(axes)
    except (KeyError,TypeError,ValueError,OverflowError):return ''
    entry=math.floor(limit*1000)/1000
    if entry>=limit:entry=round(entry-.001,3)
    if entry<.01:return tr('この寸法では肉厚0（中実）を使ってください。','Use zero thickness (solid) for these dimensions.')
    return tr('この寸法の肉厚上限：%.3f mm','Maximum wall entry for these dimensions: %.3f mm')%entry


def remember_editor(fields):
    for key in ('width','depth','height','thickness','x','y','z'):
        fields[key]._flux_dome_start_value=fields[key].value()

def editor_values(obj,fields,values):
    result=dict(values)
    if obj is None:return result
    original=settings(obj);expressions=dict(obj.ExpressionEngine)
    lock_fields(obj,fields)
    for key,prop in (('width','BaseWidth'),('depth','BaseHeight'),('height','DomeHeight'),('thickness','WallThickness')):
        if expressions.get(prop):
            widget=fields[key];blocked=widget.blockSignals(True)
            try:widget.setValue(original[key])
            finally:widget.blockSignals(blocked)
            widget._flux_dome_start_value=widget.value();result[key]=original[key]
        elif values[key]==getattr(fields[key],'_flux_dome_start_value',None):result[key]=original[key]
    return result

def editor_position(obj,fields,values):
    if obj is None:return tuple(values)
    original=tuple(obj.Placement.Base)
    return tuple(original[i] if values[i]==getattr(fields[key],'_flux_dome_start_value',None) else values[i] for i,key in enumerate(('x','y','z')))


def material_volume_note(shape):
    if shape.isNull() or not shape.isValid():
        return ''
    volume = float(shape.Volume)
    if not math.isfinite(volume) or volume < 0:
        return ''
    return tr('材料体積: %.3f mm³', 'Material volume: %.3f mm³') % volume
