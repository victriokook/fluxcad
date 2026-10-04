"""Drafted extrusions using planar offsets and ruled side faces."""
import math
import Part
from i18n import tr


def error():
    return ValueError(tr('この距離と勾配角では輪郭や穴がつぶれるか交差します。距離または角度を小さくしてください。',
                         'The profile or a hole collapses or intersects at this distance and taper. Reduce the distance or angle.'))


def validate(taper, taper_second, extent):
    if not all(math.isfinite(v) and -89<=v<=89 for v in (taper,taper_second)):
        raise ValueError(tr('勾配角は−89°から89°で指定してください。','Taper angles must be between -89° and 89°.'))


def offset_wire(wire, amount):
    original=Part.Face(wire);area=original.Area
    # OCC's offset sign can invert for reversed edges inside a Forward wire
    # (notably circles produced by Boolean cuts). Verify geometric expansion
    # or contraction instead of inferring it from the wire orientation alone.
    for signed in (amount,-amount):
        try:
            shape=wire.makeOffset2D(signed,join=2)
            if len(shape.Wires)!=1 or len(shape.Edges)!=len(wire.Edges):continue
            result=shape.Wires[0];cap=Part.Face(result)
            if not result.isClosed() or not result.isValid() or cap.Area<=1e-9:continue
            if (cap.Area-area)*amount<=0:continue
            if abs(original.common(cap).Area-min(area,cap.Area))>max(1e-7,area*1e-8):continue
            return result
        except (Part.OCCError,RuntimeError,ValueError):pass
    raise error()


def section_wires(face, amount):
    """Return matching start/end wires, rejecting collapsed or merged holes."""
    try:
        if not isinstance(face.Surface,Part.Plane):raise error()
        outer=face.OuterWire
        wires=[outer]+[w for w in face.Wires if not w.isSame(outer)]
        ends=[offset_wire(w,amount if i==0 else -amount) for i,w in enumerate(wires)] if amount else [w.copy() for w in wires]
        # Reject disappearing/merging holes rather than silently changing topology.
        end_faces=[Part.Face(w) for w in ends]
        for i,hole in enumerate(end_faces[1:],1):
            if ends[0].distToShape(ends[i])[0]<=1e-7:raise error()
            if abs(end_faces[0].common(hole).Area-hole.Area)>max(1e-7,hole.Area*1e-8):raise error()
            if any(hole.distToShape(other)[0]<=1e-7 for other in end_faces[1:i]):raise error()
        return wires,ends
    except (Part.OCCError,RuntimeError,ValueError):raise error() from None


def half(face, travel, angle):
    if not angle:return face.extrude(travel)
    try:
        wires,ends=section_wires(face,travel.Length*math.tan(math.radians(angle)))
        shapes=[]
        for wire,end in zip(wires,ends):
            end.translate(travel)
            shape=Part.makeLoft([wire,end],True,True)
            if shape.Volume<0:shape.reverse()
            if not shape.isValid() or len(shape.Solids)!=1 or shape.Volume<=1e-9:raise error()
            shapes.append(shape)
        result=shapes[0].cut(Part.makeCompound(shapes[1:])).removeSplitter() if len(shapes)>1 else shapes[0]
        if not result.isValid() or len(result.Solids)!=1 or result.Volume<=1e-9:raise error()
        return result
    except (Part.OCCError,RuntimeError,ValueError):
        raise error() from None


def extrude(faces, normal, forward, backward, taper, taper_second):
    # Adjacent selected cells form one profile before offsetting, so the shared
    # sketch edge never introduces a groove or an extra drafted wall.
    merged=faces[0].multiFuse(faces[1:]).removeSplitter() if len(faces)>1 else faces[0]
    shapes=[]
    for face in merged.Faces:
        halves=[]
        if forward>0:halves.append(half(face,normal*forward,taper))
        if backward>0:halves.append(half(face,-normal*backward,taper_second))
        shapes.append(halves[0].fuse(halves[1]).removeSplitter() if len(halves)>1 else halves[0])
    return shapes[0].multiFuse(shapes[1:]).removeSplitter() if len(shapes)>1 else shapes[0]
