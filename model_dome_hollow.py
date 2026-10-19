import math
import FreeCAD as App
import Part
from i18n import tr
def validate_thickness(p):
    t=p.get('thickness',0.)
    if not isinstance(t,(int,float)) or isinstance(t,bool) or not math.isfinite(t) or t<0 or (0<t<.01):raise ValueError(tr('肉厚は0（中実）または0.01 mm以上にしてください。','Thickness must be zero or at least 0.01 mm'))
    axes=(p['width']/2,p['depth']/2,p['height'])
    limit=.95*min(axes)**2/max(axes)
    if t and t>=limit:raise ValueError(tr('この曲率に対して肉厚が大きすぎます。肉厚を減らすか、小さい寸法を大きくしてください。','Thickness is too large for this dome curvature; reduce thickness or increase the smallest dimension'))
    return float(t)
def cavity(outer,t):
    faces=[f for f in outer.Faces if any(v.Point.z>1e-7 for v in f.Vertexes)]
    inside=[]
    for f in faces:
        surface=Part.OffsetSurface(f.Surface,-t if f.Orientation=='Forward' else t)
        inside.append(surface.toShape(*f.ParameterRange))
    shell=Part.makeShell(inside);shell.sewShape()
    edges=[e for e in shell.Edges if e.Length>1e-7 and e.Vertexes and all(abs(v.Point.z)<1e-6 for v in e.Vertexes) and len(shell.ancestorsOfType(e,Part.Face))==1]
    chains=Part.sortEdges(edges)
    if len(chains)!=1:raise ValueError(tr('ドーム内側の境界を閉じられません。','Cannot close the inner dome boundary'))
    wire=Part.Wire(chains[0])
    if not wire.isClosed():raise ValueError(tr('ドーム内側の境界を閉じられません。','Cannot close the inner dome boundary'))
    cap=Part.Face(wire)
    if cap.normalAt(0,0).z>0:cap.reverse()
    closed=Part.makeShell(shell.Faces+[cap]);closed.sewShape()
    result=Part.makeSolid(closed);result.fix(1e-7,1e-7,1e-5)
    if not result.isValid() or not result.isClosed() or len(result.Solids)!=1 or result.Volume<=0:raise ValueError(tr('有効なドーム内側を作成できません。','Cannot create a valid inner dome'))
    return result
def hollow(outer,t):
    raw=outer.cut(cavity(outer,t))
    result=raw.toNurbs()
    if not result.isValid() or not result.isClosed() or len(result.Solids)!=1 or not 0<result.Volume<outer.Volume:raise ValueError(tr('有効な中空ドームを作成できません。','Cannot create a valid hollow dome'))
    if abs(result.Volume-raw.Volume)>max(1e-6,abs(raw.Volume)*1e-5):raise ValueError(tr('中空曲面の変換誤差が許容値を超えました。','Hollow dome surface conversion exceeds tolerance'))
    return result
