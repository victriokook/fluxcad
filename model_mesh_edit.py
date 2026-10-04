"""Separate connected regions and plane-cut native meshes, retaining the source."""
import math
import FreeCAD as App
import Mesh
import Part
from i18n import tr
import model
import model_mesh


def signed_volume(mesh):
    # Mesh.Volume accumulates in single precision. Use a nearby origin and a
    # compensated double-precision sum for cut validation on dense meshes.
    vertices,triangles=mesh.Topology
    origin=mesh.BoundBox.Center
    vertices=[v-origin for v in vertices]
    return math.fsum(vertices[a].dot(vertices[b].cross(vertices[c])) for a,b,c in triangles)/6


def separate(mesh):
    parts=mesh.getSeparateComponents()
    # Stable spatial order, independent of STL triangle ordering.
    parts.sort(key=lambda part:tuple(part.BoundBox.Center))
    if len(parts)<2:
        raise ValueError(tr('このメッシュは1つにつながっています。分けるには「平面で切断」を使ってください。',
                            'This mesh is connected. Use Plane Cut to divide it.'))
    return [(part,tr('部品 %d','Part %d')%(i+1)) for i,part in enumerate(parts)]


def cap(mesh,axis,coordinate,direction):
    """Cap only the new planar boundary, using nested wires to preserve holes.

    Only the boundary becomes a temporary planar face. The full mesh is never
    converted to a BRep. Keep every boundary vertex so cap triangles join the
    clipped triangles without T-junctions.
    """
    if mesh.isSolid():return
    vertices,triangles=mesh.Topology
    epsilon=max(1e-6,abs(coordinate)*3e-7,mesh.BoundBox.DiagonalLength*3e-7)
    planar={i for i,v in enumerate(vertices) if abs(tuple(v)[axis]-coordinate)<epsilon}
    edges={}
    for tri in triangles:
        for a,b in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])):
            if a in planar and b in planar:
                key=(min(a,b),max(a,b));edges[key]=edges.get(key,0)+1
    edges={edge for edge,count in edges.items() if count==1}
    if not edges:raise ValueError(tr('切断面の輪郭が見つかりません。','No cut boundary was found.'))
    neighbors={}
    for a,b in edges:
        neighbors.setdefault(a,[]).append(b);neighbors.setdefault(b,[]).append(a)
    if any(len(v)!=2 for v in neighbors.values()):
        raise ValueError(tr('切断位置で輪郭が分岐しています。切断位置を少しずらしてください。',
                            'The cut boundary branches. Move the cutting plane slightly.'))
    wires=[]
    while edges:
        start,current=min(edges);previous=start;loop=[start,current];edges.remove((start,current))
        while current!=start:
            nxt=next(v for v in neighbors[current] if v!=previous)
            key=(min(current,nxt),max(current,nxt))
            if key not in edges:raise ValueError(tr('切断面の輪郭を閉じられません。','The cut boundary cannot be closed.'))
            edges.remove(key);loop.append(nxt);previous,current=current,nxt
        wires.append(Part.makePolygon([vertices[i] for i in loop]))
    face=Part.makeFace(wires,'Part::FaceMakerBullseye')
    points,facets=face.tessellate(.01)
    normal=App.Vector();normal[axis]=direction
    oriented=[]
    for a,b,c in facets:
        if (points[b]-points[a]).cross(points[c]-points[a]).dot(normal)<0:b,c=c,b
        oriented.append((a,b,c))
    mesh.addMesh(Mesh.Mesh((points,oriented)))
    mesh.removeDuplicatedPoints()
    if not mesh.isSolid() or mesh.hasNonUniformOrientedFacets():
        raise ValueError(tr('切断面を正しく閉じられませんでした。位置をずらすか「切断面を閉じる」をオフにしてください。',
                            'The cut could not be capped correctly. Move the plane or turn off Close Cut Faces.'))


def cut(mesh,axis='Z',coordinate=0,side='both',close=True):
    if axis not in 'XYZ' or len(axis)!=1 or side not in ('both','negative','positive') or not math.isfinite(coordinate):
        raise ValueError(tr('切断平面の指定が正しくありません。','Invalid cutting plane.'))
    index='XYZ'.index(axis);box=mesh.BoundBox
    low,high=getattr(box,axis+'Min'),getattr(box,axis+'Max')
    if coordinate<=low+1e-7 or coordinate>=high-1e-7:
        raise ValueError(tr('切断位置はメッシュの内側（%.6g～%.6g mm）にしてください。',
                            'Place the cutting plane inside the mesh (%.6g to %.6g mm).')%(low,high))
    if close and (not mesh.isSolid() or mesh.hasNonUniformOrientedFacets()):
        raise ValueError(tr('元のメッシュが閉じていないか、面の向きが不揃いです。「切断面を閉じる」をオフにして切断できます。',
                            'The source is open or has inconsistent face orientations. Turn off Close Cut Faces to cut it.'))
    base=App.Vector();base[index]=coordinate
    source_volume=signed_volume(mesh) if close else 0
    orientation=-1 if source_volume<0 else 1
    prepared=mesh.copy()
    # Treat floating-point residues at an existing on-plane vertex as exactly
    # on-plane; otherwise the native clipper may drop a sliver near a seam.
    epsilon=max(1e-8,abs(coordinate)*1e-7,box.DiagonalLength*1e-9)
    for i,point in enumerate(prepared.Topology[0]):
        if abs(point[index]-coordinate)<epsilon:
            point[index]=coordinate;prepared.setPoint(i,point)
    results=[]
    for key,direction,title in [('negative',1,tr('負側','Negative side')),('positive',-1,tr('正側','Positive side'))]:
        if side not in ('both',key):continue
        normal=App.Vector();normal[index]=direction
        result=prepared.copy();result.trimByPlane(base,normal);result.removeDuplicatedPoints()
        # A plane through an existing vertex can leave zero-area fragments
        # after welding the intersections. Remove those before tracing loops.
        result.fixDegenerations();result.removeDuplicatedFacets()
        if not result.CountFacets:raise ValueError(tr('切断後のメッシュが空になりました。','The cut result is empty.'))
        if close:cap(result,index,coordinate,direction*orientation)
        results.append((result,title))
    if close and side=='both':
        volume=abs(source_volume)
        if abs(sum(abs(signed_volume(part)) for part,title in results)-volume)>max(.001,volume*1e-5):
            raise ValueError(tr('切断前後の体積が一致しません。切断位置をずらしてください。',
                                'The cut does not preserve volume. Move the cutting plane.'))
    return results


def create_results(doc,source,results,label):
    model_mesh.targets(doc,[source])
    if not results or any(not part.CountFacets for part,title in results):
        raise ValueError(tr('作成するメッシュがありません。','There are no result meshes.'))
    created=[]
    with model.transaction(doc,label):
        for part,title in results:
            obj=doc.addObject('Mesh::Feature','MeshResult');obj.Label=source.Label+' - '+title;obj.Mesh=part.copy()
            for prop in ('ShapeColor','LineColor','PointColor','Transparency','DisplayMode'):
                if prop in source.ViewObject.PropertiesList and prop in obj.ViewObject.PropertiesList:
                    setattr(obj.ViewObject,prop,getattr(source.ViewObject,prop))
            obj.Visibility=True;created.append(obj)
        source.Visibility=False
    return created
