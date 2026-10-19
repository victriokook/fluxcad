"""Native analytic prism topology: original circles/lines, no triangulation fitting.

Recovered arc trims require independent saved-point validation before import.
"""
import math
import FreeCAD as App
import Part

def vector(data):return App.Vector(data['x'],data['y'],data['z'])

def unit(value):
    result=App.Vector(value)
    if result.Length<1e-12:raise ValueError('Degenerate native direction')
    result.normalize();return result

def native_wire(model, loop, tolerance=1e-6):
    byid={n['id']:n for field in ('coedges','edges','curves','vertices','points') for n in model[field]}
    records=[]
    for key in loop['boundary']['coedges']:
        coedge=byid[key];edge=byid[coedge['edge']];curve=byid[edge['carrier']['curve']]['geometry']
        points=[vector(byid[byid[edge[k]]['point']]['position']) for k in ('start','end')]
        if coedge['sense']=='reversed':points.reverse()
        if curve['kind'] not in ('line','circle'):raise ValueError('Native cap curve is not line/circle')
        records.append(dict(curve=curve,p0=points[0],p1=points[1],parameter_range=edge['carrier'].get('parameter_range')))
    if not records:raise ValueError('Empty native ring')
    for a,b in zip(records,records[1:]+records[:1]):
        if (a['p1']-b['p0']).Length>tolerance:raise ValueError('Native coedge ring endpoints do not connect')
    if all(rec['curve']['kind']=='circle' for rec in records):
        c=records[0]['curve'];center=vector(c['center']);axis=unit(vector(c['axis']));radius=c['radius']
        if all((vector(rec['curve']['center'])-center).Length<=tolerance and abs(rec['curve']['radius']-radius)<=tolerance and abs(abs(unit(vector(rec['curve']['axis'])).dot(axis))-1)<1e-12 for rec in records):
            if any(abs((rec[k]-center).Length-radius)>tolerance or abs((rec[k]-center).dot(axis))>tolerance for rec in records for k in ('p0','p1')):raise ValueError('Native circle vertices are off support')
            if any(rec['parameter_range'] is not None and abs(abs(rec['parameter_range'][1]-rec['parameter_range'][0])-2*math.pi)>1e-9 for rec in records):raise ValueError('Explicit native circle bounds cannot be normalized')
            return Part.Wire(Part.Circle(center,axis,radius).toShape())
    tangents={};signs={}
    for i,rec in enumerate(records):
        if rec['curve']['kind']=='line':
            direction=unit(rec['p1']-rec['p0']);carrier=rec['curve']
            if any((rec[k]-vector(carrier['origin'])).cross(unit(vector(carrier['direction']))).Length>tolerance for k in ('p0','p1')):raise ValueError('Native line vertex off support')
            tangents[i]=(direction,direction)
    for _ in records:
        changed=False
        for i,rec in enumerate(records):
            if i in tangents:continue
            c=rec['curve'];center=vector(c['center']);axis=unit(vector(c['axis']))
            if any(abs((rec[k]-center).Length-c['radius'])>tolerance or abs((rec[k]-center).dot(axis))>tolerance for k in ('p0','p1')):raise ValueError('Native arc vertex off circle')
            options=[]
            for sign in (-1,1):
                pair=(unit(axis.cross(rec['p0']-center))*sign,unit(axis.cross(rec['p1']-center))*sign)
                neighbors=[]
                if (i-1)%len(records) in tangents:neighbors.append(pair[0].dot(tangents[(i-1)%len(records)][1]))
                if (i+1)%len(records) in tangents:neighbors.append(pair[1].dot(tangents[(i+1)%len(records)][0]))
                if neighbors and min(neighbors)>1-1e-9:options.append((sign,pair))
            if len(options)==1:signs[i],tangents[i]=options[0];changed=True
        if not changed:break
    if len(tangents)!=len(records):raise ValueError('Native arc trim direction is not uniquely tangent-constrained')
    edges=[]
    for i,rec in enumerate(records):
        if rec['curve']['kind']=='line':edge=Part.makeLine(rec['p0'],rec['p1'])
        else:
            c=rec['curve'];circle=Part.Circle(vector(c['center']),unit(vector(c['axis']))*signs[i],c['radius']);first=circle.parameter(rec['p0']);last=circle.parameter(rec['p1'])
            while last<=first+1e-12:last+=2*math.pi
            edge=Part.ArcOfCircle(circle,first,last).toShape()
        if rec['parameter_range'] is not None:
            span=abs(rec['parameter_range'][1]-rec['parameter_range'][0]);length=span*(rec['curve']['radius'] if rec['curve']['kind']=='circle' else 1)
            if abs(edge.Length-length)>tolerance:raise ValueError('Native bounded-curve parameters disagree with reconstructed trim')
        edges.append(edge)
    wire=Part.Wire(edges)
    if not wire.isValid() or not wire.isClosed():raise ValueError('Reconstructed native ring is not valid and closed')
    return wire


def native_planar_face(model, face, tolerance=1e-6):
    loops={n['id']:n for n in model['loops']};surfaces={n['id']:n['geometry'] for n in model['surfaces']};surface=surfaces[face['surface']]
    if surface['kind']!='plane':raise ValueError('Not a native planar face')
    wires=[native_wire(model,loops[key],tolerance) for key in face['loops']['loops']]
    result=Part.makeFace(wires,'Part::FaceMakerBullseye')
    if len(result.Faces)!=1 or not result.isValid():raise ValueError('Native planar face is not uniquely bounded')
    result=result.Faces[0];origin=vector(surface['origin']);normal=unit(vector(surface['normal']))
    if any(abs((v.Point-origin).dot(normal))>tolerance for v in result.Vertexes):raise ValueError('Native planar boundary is off surface')
    return result

def same_support(source, surface, tolerance=1e-6):
    kind=source['kind']
    if kind=='plane' and type(surface).__name__=='Plane':
        axis=unit(vector(source['normal']));return abs(abs(axis.dot(surface.Axis))-1)<1e-12 and abs((vector(source['origin'])-surface.Position).dot(axis))<=tolerance
    if kind=='cylinder' and type(surface).__name__=='Cylinder':
        axis=unit(vector(source['axis']));return abs(abs(axis.dot(surface.Axis))-1)<1e-12 and abs(source['radius']-surface.Radius)<=tolerance and (vector(source['origin'])-surface.Center).cross(axis).Length<=tolerance
    return False

def recover_native_prism(document,tolerance=1e-6):
    model=document['model'];surfaces={n['id']:n['geometry'] for n in model['surfaces']}
    if document['units']['length']!='millimeter' or len(model['bodies'])!=1 or model['bodies'][0]['kind']!='solid':raise ValueError('Only single native millimeter solids supported')
    if any(s['kind'] not in ('plane','cylinder') for s in surfaces.values()):raise ValueError('Non-prismatic native surface support')
    planes=[f for f in model['faces'] if surfaces[f['surface']]['kind']=='plane']
    attempted=set()
    for f in planes:
        normal=unit(vector(surfaces[f['surface']]['normal']));token=tuple(round(abs(x),10) for x in normal)
        if token in attempted:continue
        attempted.add(token)
        caps=[g for g in planes if abs(abs(unit(vector(surfaces[g['surface']]['normal'])).dot(normal))-1)<1e-12]
        if len(caps)!=2:continue
        if any(abs(unit(vector(s['axis'])).dot(normal))<1-1e-12 for s in surfaces.values() if s['kind']=='cylinder'):continue
        try:
            first=native_planar_face(model,caps[0],tolerance);second=native_planar_face(model,caps[1],tolerance);delta=vector(surfaces[caps[1]['surface']]['origin'])-vector(surfaces[caps[0]['surface']]['origin']);distance=delta.dot(normal)
            if abs(distance)<=tolerance:continue
            moved=first.copy();moved.translate(normal*distance)
            if moved.cut(second).Area>tolerance or second.cut(moved).Area>tolerance:continue
            result=first.extrude(normal*distance)
            if not result.isValid() or not result.isClosed() or len(result.Solids)!=1:continue
            if any(not any(same_support(s,g.Surface,tolerance) for g in result.Faces) for s in surfaces.values()):continue
            if any(not any(same_support(s,g.Surface,tolerance) for s in surfaces.values()) for g in result.Faces):continue
            points={n['id']:vector(n['position']) for n in model['points']};shell=result.Shells[0]
            if any(Part.Vertex(points[v['point']]).distToShape(shell)[0]>tolerance for v in model['vertices']):continue
            if abs(result.Volume-first.Area*abs(distance))>max(tolerance,abs(result.Volume)*1e-10):continue
            return result,dict(method='Native planar cap rings and unique analytic tangent trims',tolerance_mm=tolerance,cap_area_mm2=first.Area,thickness_mm=abs(distance),source_surfaces=len(surfaces),source_vertices=len(model['vertices']),all_source_supports_and_vertices_matched=True)
        except (RuntimeError,ValueError):continue
    raise ValueError('No unique matching native prism caps')


def native_arc_evidence(document, shape, tolerance=1e-6):
    model=document['model'];byid={n['id']:n for field in ('coedges','edges','curves','vertices','points') for n in model[field]};full=set()
    for loop in model['loops']:
        edges=[byid[byid[key]['edge']] for key in loop['boundary']['coedges']]
        curves=[byid[e['carrier']['curve']]['geometry'] for e in edges]
        if curves and all(c['kind']=='circle' for c in curves):
            c=curves[0]
            if all((vector(g['center'])-vector(c['center'])).Length<=tolerance and abs(g['radius']-c['radius'])<=tolerance and abs(abs(unit(vector(g['axis'])).dot(unit(vector(c['axis']))))-1)<1e-12 for g in curves):full.update(e['id'] for e in edges)
    for e in shape.Edges:
        if type(e.Curve).__name__=='Circle' and e.Length/e.Curve.Radius>2*math.pi+1e-8:raise ValueError('Native circle edge wraps more than one revolution')
    choices=[]
    for edge in model['edges']:
        c=byid[edge['carrier']['curve']]['geometry']
        if c['kind']!='circle' or edge['id'] in full:continue
        p0,p1=[vector(byid[byid[edge[key]]['point']]['position']) for key in ('start','end')]
        if (p0-p1).Length<=tolerance:continue
        center=vector(c['center']);axis=unit(vector(c['axis']));radius=c['radius'];matches=[]
        for e in shape.Edges:
            curve=e.Curve
            if type(curve).__name__!='Circle' or abs(curve.Radius-radius)>tolerance or (curve.Center-center).Length>tolerance:continue
            ends=[v.Point for v in e.Vertexes]
            if len(ends)==2 and any((ends[i]-p0).Length<=tolerance and (ends[1-i]-p1).Length<=tolerance for i in (0,1)):matches.append(e)
        if len(matches)!=1:raise ValueError('Native arc identity/trim is missing or ambiguous')
        e=matches[0];mid=e.valueAt((e.FirstParameter+e.LastParameter)/2);interval=edge['carrier'].get('parameter_range')
        if interval is not None:
            u=vector(c['ref_direction']);v=axis.cross(u);angle=(interval[0]+interval[1])/2;expected=center+(u*math.cos(angle)+v*math.sin(angle))*radius
            if (mid-expected).Length>tolerance:raise ValueError('Native explicit arc interval changed')
        else:choices.append(dict(edge=edge['id'],center=list(center),axis=list(axis),radius=radius,start=list(p0),end=list(p1),midpoint=list(mid)))
    return choices

def verify_saved_arc_choices(choices, points, tolerance=1e-4):
    if choices and not points:raise ValueError('Native unbounded arc trims need configuration-matched saved-point evidence')
    proof=[]
    for choice in choices:
        center,axis,radius=choice['center'],choice['axis'],choice['radius'];u=[(a-b)/radius for a,b in zip(choice['start'],center)];v=[axis[1]*u[2]-axis[2]*u[1],axis[2]*u[0]-axis[0]*u[2],axis[0]*u[1]-axis[1]*u[0]]
        def angle(point):
            d=[a-b for a,b in zip(point,center)];return math.atan2(sum(a*b for a,b in zip(d,v)),sum(a*b for a,b in zip(d,u)))%(2*math.pi)
        end=angle(choice['end']);mid=angle(choice['midpoint']);selected_positive=mid<end;selected=0;opposite=0;epsilon=max(1e-7,2*tolerance/radius)
        if end<epsilon or 2*math.pi-end<epsilon:raise ValueError('Native arc endpoints cannot disambiguate a trim')
        for sample in points:
            point=sample['point']
            d=[a-b for a,b in zip(point,center)]
            if abs(sum(a*b for a,b in zip(d,axis)))>tolerance or abs(math.sqrt(sum(a*a for a in d))-radius)>tolerance:continue
            radial=[x/radius for x in d]
            if not any(abs(sum(a*b for a,b in zip(normal,radial)))>.98 and abs(sum(a*b for a,b in zip(normal,axis)))<.01 for normal in sample['normals']):continue
            value=angle(point)
            if min(value,2*math.pi-value,abs(value-end))<=epsilon:continue
            if (value<end)==selected_positive:selected+=1
            else:opposite+=1
        if not selected or opposite:raise ValueError('Saved boundary points do not uniquely confirm the native analytic arc trim')
        proof.append(dict(edge=choice['edge'],interior_points=selected,opposite_points=opposite,point_tolerance_mm=tolerance))
    return proof

def saved_curve_samples(mesh):
    normals=[[] for _ in mesh.vertices]
    for triangle in mesh.triangles:
        a,b,c=[App.Vector(*mesh.vertices[i]) for i in triangle]
        normal=(b-a).cross(c-a)
        if normal.Length<1e-12:continue
        normal.normalize()
        for i in triangle:
            if not any(abs(normal.dot(existing))>1-1e-6 for existing in normals[i]):normals[i].append(normal)
    return [dict(point=list(point),normals=[list(n) for n in normals[i]])
            for i,point in enumerate(mesh.vertices) if len(normals[i])>1]


def recover_native_drilled_prism(document,tolerance=1e-6):
    m=document['model'];lookup={n['id']:n for field in ('surfaces','loops','coedges','edges','curves','vertices','points') for n in m[field]}
    if document['units']['length']!='millimeter' or len(m['bodies'])!=1 or m['bodies'][0]['kind']!='solid':raise ValueError('Single native solid required')
    surfaces={n['id']:n['geometry'] for n in m['surfaces']}
    if any(s['kind'] not in ('plane','cylinder') for s in surfaces.values()):raise ValueError('Unsupported support')
    planar={f['id']:native_planar_face(m,f,tolerance) for f in m['faces'] if surfaces[f['surface']]['kind']=='plane'}
    cylinders=[]
    for f in m['faces']:
        s=surfaces[f['surface']]
        if s['kind']!='cylinder':continue
        axis=unit(vector(s['axis']));origin=vector(s['origin']);radius=s['radius'];circles=[];lines=[]
        if len(f['loops']['loops'])!=1:raise ValueError('Only full seam cylinder loops supported')
        for lk in f['loops']['loops']:
            for ck in lookup[lk]['boundary']['coedges']:
                edge=lookup[lookup[ck]['edge']];curve=lookup[edge['carrier']['curve']]['geometry']
                points=[vector(lookup[lookup[edge[k]]['point']]['position']) for k in ('start','end')]
                if curve['kind']=='circle':
                    if (points[0]-points[1]).Length>tolerance:raise ValueError('Partial circle cylinder refused')
                    if abs(curve['radius']-radius)>tolerance or (vector(curve['center'])-origin).cross(axis).Length>tolerance or abs(abs(unit(vector(curve['axis'])).dot(axis))-1)>1e-12:raise ValueError('Cylinder boundary support differs')
                    interval=edge['carrier'].get('parameter_range')
                    if interval and abs(abs(interval[1]-interval[0])-2*math.pi)>1e-9:raise ValueError('Non-full explicit cylinder circle')
                    circles.append((vector(curve['center'])-origin).dot(axis))
                elif curve['kind']=='line':
                    if abs(abs(unit(vector(curve['direction'])).dot(axis))-1)>1e-12:raise ValueError('Cylinder seam is not axial')
                    if any(abs((p-origin).cross(axis).Length-radius)>tolerance for p in points):raise ValueError('Seam off cylinder')
                    lines.append(points)
                else:raise ValueError('Cylinder boundary is not analytic circle/line')
        if len(circles)!=2 or len(lines)!=2:raise ValueError('Not a full cylindrical native face')
        low,high=sorted(circles)
        if high-low<=tolerance:raise ValueError('Zero cylinder span')
        if any(min(abs((p-origin).dot(axis)-low),abs((p-origin).dot(axis)-high))>tolerance for line in lines for p in line):raise ValueError('Seam span differs')
        cylinders.append((f,s,axis,origin,radius,low,high))
    for f in m['faces']:
        if f['id'] not in planar:continue
        s=surfaces[f['surface']];normal=unit(vector(s['normal']))
        caps=[g for g in m['faces'] if g['id'] in planar and abs(abs(unit(vector(surfaces[g['surface']]['normal'])).dot(normal))-1)<1e-12]
        if len(caps)!=2 or f is not caps[0]:continue
        delta=vector(surfaces[caps[1]['surface']]['origin'])-vector(s['origin']);distance=delta.dot(normal)
        if abs(distance)<=tolerance:continue
        first=planar[f['id']];second=planar[caps[1]['id']];translated=first.copy();translated.translate(normal*distance)
        if translated.cut(second).Area>tolerance or second.cut(translated).Area>tolerance:continue
        result=first.extrude(normal*distance)
        failed=False;tools=[]
        for cf,cs,axis,origin,radius,low,high in cylinders:
            if abs(abs(axis.dot(normal))-1)<1e-12:continue
            if cf['sense']!='reversed':failed=True;break
            tools.append(Part.makeCylinder(radius,high-low+2*tolerance,origin+axis*(low-tolerance),axis))
        if failed or not tools:continue
        for tool in tools:result=result.cut(tool)
        result=result.removeSplitter()
        if not result.isValid() or not result.isClosed() or len(result.Solids)!=1:continue
        matched=[]
        for nf in m['faces']:
            support=surfaces[nf['surface']];actual=[g for g in result.Faces if same_support(support,g.Surface,tolerance)]
            if not actual:failed=True;break
            if support['kind']=='plane':
                expected=planar[nf['id']];relevant=[g for g in actual if expected.common(g).Area>tolerance]
                if len(relevant)!=1 or expected.cut(relevant[0]).Area>tolerance or relevant[0].cut(expected).Area>tolerance:failed=True;break
                matched.append(relevant[0])
            else:
                _,_,axis,origin,radius,low,high=next(c for c in cylinders if c[0]['id']==nf['id'])
                expected_area=2*math.pi*radius*(high-low);relevant=[]
                for g in actual:
                    levels=[(v.Point-origin).dot(axis) for v in g.Vertexes]
                    if levels and abs(min(levels)-low)<=tolerance and abs(max(levels)-high)<=tolerance and abs(g.Area-expected_area)<=tolerance:relevant.append(g)
                if len(relevant)!=1:failed=True;break
                matched.append(relevant[0])
        if failed or len(matched)!=len(result.Faces) or any(not any(g.isSame(h) for h in matched) for g in result.Faces):continue
        points={n['id']:vector(n['position']) for n in m['points']}
        if any(Part.Vertex(points[v['point']]).distToShape(result.Shells[0])[0]>tolerance for v in m['vertices']):continue
        return result,dict(native_planar_faces=len(planar),native_cylindrical_faces=len(cylinders),all_faces_matched=True,tolerance_mm=tolerance)
    raise ValueError('No cap extrusion with exact native face coverage')
