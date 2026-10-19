"""Exact planar cells for sketch networks containing open curves.

The temporary enclosing face is never selectable. Persistent profiles follow
Sketcher geometry IDs and oriented boundaries rather than volatile Edge/Face
numbers. New unrelated geometry cannot redirect an existing feature.
"""
import json
import FreeCAD as App
import Part
from i18n import tr


# Native curve creation/solving can leave endpoints a few nanometres off an
# intended edge. Use the same small fuzzy tolerance for picking and the saved
# Slice feature; never scale it with zoom or the enclosing plane's size.
INTERSECTION_TOLERANCE = 1e-5  # mm (0.01 micrometres)


def _extent(sketch):
    box, origin = sketch.Shape.BoundBox, sketch.Placement.Base
    return 10 + sum(abs(getattr(box, axis + end) - getattr(origin, axis.lower()))
                    for axis in 'XYZ' for end in ('Min', 'Max'))


def _boundary_edges(face):
    # OCC includes dangling lines as internal wires or twice in a boundary
    # walk. They do not bound any area and must not enter the solid profile.
    result = []
    for wire in face.Wires:
        if not wire.isClosed():
            continue
        edges = wire.OrderedEdges
        result.extend(edge for edge in edges
                      if sum(edge.isSame(other) for other in edges) == 1)
    return result


def _boundary(face):
    edges = _boundary_edges(face)
    loops = [Part.Wire(chain) for chain in Part.sortEdges(edges)] if edges else []
    return [w for w in loops if w.isClosed() and Part.Face(w).Area > 1e-9]


def profiles(sketch, closed_regions, closed_wires=None):
    from BOPTools.SplitAPI import slice
    extent = _extent(sketch)
    frame = Part.makePlane(2 * extent, 2 * extent, App.Vector(-extent, -extent, 0))
    frame.Placement = sketch.Placement.multiply(frame.Placement)
    split = slice(frame, sketch.Shape.Edges, 'Standard', INTERSECTION_TOLERANCE)
    if not split.isValid():
        raise ValueError(tr('曲線の交点で領域を分割できません。重複する線や微小な隙間を確認してください。',
                            'Cannot split regions at curve intersections. Check for duplicate edges or small gaps.'))
    border = Part.makeCompound(frame.Edges)
    # Preserve intact nested holes. Once a line/curve divides a hole, its cells
    # are intentional bounded profiles too (e.g. corner braces inside a case).
    holes = None
    if closed_regions:
        wires = closed_wires if closed_wires is not None else sketch.Shape.Wires
        filled = [Part.Face(w) for w in wires if w.isClosed()]
        union = filled[0].multiFuse(filled[1:]) if len(filled) > 1 else filled[0]
        faces = [r['face'] for r in closed_regions]
        material = faces[0].multiFuse(faces[1:]) if len(faces) > 1 else faces[0]
        holes = union.cut(material)
    regions = []
    for face in split.Faces:
        if face.Area <= 1e-9 or face.common(border).Length > 1e-7:
            continue
        if holes and not holes.isNull():
            tolerance = max(1e-9, face.Area * 1e-8)
            if any(abs(face.Area - hole.Area) <= tolerance
                   and abs(face.common(hole).Area - hole.Area) <= tolerance
                   for hole in holes.Faces):
                continue
        loops = _boundary(face)
        if not loops:
            continue
        clean = face if len(_boundary_edges(face)) == len(face.Edges) else Part.makeFace(loops, 'Part::FaceMakerBullseye')
        if len(clean.Faces) != 1 or not clean.isValid():
            raise ValueError(tr('領域の境界を特定できません。線の重複や自己交差を確認してください。'))
        regions.append(dict(face=clean.Faces[0], edges=[], inputs=[], network=True,
                            key=('CurveRegion%d' % (len(regions) + 1),)))
    if not regions:
        raise ValueError(tr('閉じた輪郭がありません。線の端点をつないでください。'))
    return regions


def _reference_error():
    return ValueError(tr('スケッチ領域の境界を特定できません。削除・変更した線を戻すか、加工の領域を選び直してください。',
                         'Cannot identify the sketch profile boundary. Restore the removed or changed geometry, or reselect the feature profile.'))


def _geometry(sketch, identities=None):
    """Sketcher IDs survive insertion, deletion of other geometry and saving."""
    result={}
    for i,geometry in enumerate(sketch.Geometry):
        identity=sketch.getGeometryId(i)
        if identities is not None and identity not in identities:continue
        if sketch.getConstruction(i):continue
        shape=geometry.toShape()
        if not shape.Edges:continue
        if identity in result:raise _reference_error()
        result[identity]=shape.Edges[0]
    if identities is not None and set(result)!=set(identities):raise _reference_error()
    return result


def boundary_boxes_disjoint(edge, source_edge):
    threshold = max(1e-7, INTERSECTION_TOLERANCE * 10)
    if edge.Length <= threshold:
        return False
    a = edge.BoundBox
    b = source_edge.BoundBox
    return any(getattr(a, axis + 'Max') < getattr(b, axis + 'Min') - threshold or getattr(b, axis + 'Max') < getattr(a, axis + 'Min') - threshold for axis in 'XYZ')


def _covers_boundary(edge, source_edge):
    try:
        if boundary_boxes_disjoint(edge, source_edge):
            return False
        remainder = edge.cut(source_edge)
        if not remainder.isValid():
            return False
        length_threshold = max(1e-7, INTERSECTION_TOLERANCE * 10)
        return remainder.Length <= length_threshold
    except Part.OCCError:
        return False


def _signature(face, geometry):
    """Oriented boundary cycles distinguish adjacent cells with shared curves."""
    face=face.copy()
    if face.normalAt(0,0).z<0:face.reverse()
    loops=[]
    for wire in face.Wires:
        if not wire.isClosed():continue
        cycle=[]
        for edge in wire.OrderedEdges:
            # Ignore a dangling branch traversed once in each direction.
            if sum(edge.isSame(other) for other in wire.OrderedEdges)>1:continue
            matches=[]
            for identity,source_edge in geometry.items():
                if _covers_boundary(edge,source_edge):
                    matches.append((identity,source_edge))
            if not matches:raise _reference_error()
            # SplitAPI merges coincident fragments from overlapping sketch lines.
            # All matches cover this entire boundary fragment. Prefer the oldest
            # persistent geometry ID so adding another coincident line cannot
            # redirect an existing profile. A removed chosen ID still fails closed.
            identity,source_edge=min(matches,key=lambda item:item[0])
            parameter=(edge.FirstParameter+edge.LastParameter)/2
            point=edge.valueAt(parameter)
            tangent=source_edge.tangentAt(source_edge.Curve.parameter(point))
            direction=1 if edge.tangentAt(parameter).dot(tangent)>0 else -1
            if edge.Orientation=='Reversed':direction=-direction
            item=(identity,direction)
            if not cycle or cycle[-1]!=item:cycle.append(item)
        if len(cycle)>1 and cycle[0]==cycle[-1]:cycle.pop()
        if cycle:loops.append(min(tuple(cycle[i:]+cycle[:i]) for i in range(len(cycle))))
    if not loops:raise _reference_error()
    return tuple(sorted(loops))


def _cells(geometry):
    from BOPTools.SplitAPI import slice
    edges=list(geometry.values())
    if not edges:raise _reference_error()
    box=Part.makeCompound(edges).BoundBox
    extent=10+sum(abs(getattr(box,axis+end)) for axis in 'XY' for end in ('Min','Max'))
    frame=Part.makePlane(2*extent,2*extent,App.Vector(-extent,-extent,0))
    split=slice(frame,edges,'Standard',INTERSECTION_TOLERANCE)
    if not split.isValid():raise _reference_error()
    border=Part.makeCompound(frame.Edges);result=[]
    for face in split.Faces:
        if face.Area<=1e-9 or face.common(border).Length>1e-7:continue
        loops=_boundary(face)
        if not loops:continue
        clean=face if len(_boundary_edges(face))==len(face.Edges) else Part.makeFace(loops,'Part::FaceMakerBullseye')
        if len(clean.Faces)!=1 or not clean.isValid():raise _reference_error()
        result.append(clean.Faces[0])
    return result


class ProfileFeature:
    def execute(self,obj):
        try:
            sketch=obj.SourceSketch
            if not sketch or 'Invalid' in sketch.State:raise _reference_error()
            geometry=_geometry(sketch,obj.GeometryIds)
            wanted=json.loads(obj.BoundarySignature)
            matches=[f for f in _cells(geometry) if json.loads(json.dumps(_signature(f,geometry)))==wanted]
            if len(matches)!=1:raise _reference_error()
            import hashlib
            stable_name = 'FluxProfile_' + hashlib.sha256(json.dumps(wanted,sort_keys=True).encode('utf-8')).hexdigest()
            matches[0].ElementMap = {stable_name: 'Face1'}
            obj.Shape=matches[0];obj.Placement=sketch.getGlobalPlacement();obj.ProfileError=''
        except Exception as error:
            obj.Shape=Part.Shape();obj.ProfileError=str(error)
            raise
    def dumps(self):return None
    def loads(self,state):pass


def source(doc,sketch,region):
    """Capture the selected boundary, not the positions of Shape subelements."""
    import model
    local=region['face'].copy()
    local.Placement=sketch.Placement.inverse().multiply(local.Placement)
    geometry=_geometry(sketch);signature=_signature(local,geometry)
    identities=sorted({identity for loop in signature for identity,direction in loop})
    geometry={identity:geometry[identity] for identity in identities}
    matches=[f for f in _cells(geometry) if _signature(f,geometry)==signature]
    tolerance=max(1e-7,local.Area*1e-7)
    if (len(matches)!=1 or abs(matches[0].Area-local.Area)>tolerance or
            abs(matches[0].common(local).Area-local.Area)>tolerance):raise _reference_error()
    obj=model._internal(doc.addObject('Part::FeaturePython','ExtrusionProfile'))
    for name,kind in [('FluxSketchProfile','App::PropertyBool'),('SourceSketch','App::PropertyLinkGlobal'),
                      ('SourceContainers','App::PropertyLinkListGlobal'),('GeometryIds','App::PropertyIntegerList'),
                      ('BoundarySignature','App::PropertyString'),('ProfileError','App::PropertyString')]:
        obj.addProperty(kind,name,'Profile')
        obj.setEditorMode(name,1 if name=='ProfileError' else 2)
    obj.FluxSketchProfile=True;obj.SourceSketch=sketch;obj.GeometryIds=identities
    obj.BoundarySignature=json.dumps(signature);parents=[];parent=sketch.getParentGeoFeatureGroup()
    while parent:parents.append(parent);parent=parent.getParentGeoFeatureGroup()
    obj.SourceContainers=parents;obj.Proxy=ProfileFeature();obj.ViewObject.Proxy=0
    obj.Label=tr('押し出し領域 (%s)','Extrusion profile (%s)')%sketch.Label
    obj.Proxy.execute(obj);obj.Visibility=False
    return obj


def upgrade_profiles(sketch):
    """Upgrade intact legacy FluxCAD references before allowing a sketch edit.

    The old face must match the new boundary exactly and every dependent solid
    must remain unchanged. Damaged or ambiguous legacy data is never guessed.
    """
    import model
    doc=sketch.Document;uses={};single_profile=None
    for obj in doc.Objects:
        prop=('Base' if obj.TypeId=='Part::Extrusion' else 'Source' if obj.TypeId=='Part::Revolution'
              else 'Profiles' if hasattr(obj,'Profiles') and hasattr(obj,'SourceSketch') else None)
        if not prop:continue
        value=getattr(obj,prop);refs=list(value) if prop=='Profiles' else [value]
        for old in refs:
            if old==sketch and getattr(obj,'Solid',False):
                regions=model.profiles(sketch)
                if len(regions)==1:
                    single_profile=regions[0];uses.setdefault(old,[]).append((obj,prop))
                continue
            if (not old or old.TypeId!='PartDesign::SubShapeBinder' or not old.Name.startswith('ExtrusionProfile')
                    or sketch not in old.OutListRecursive):continue
            uses.setdefault(old,[]).append((obj,prop))
    if not uses:return 0
    preserved={};visibility={o.Name:bool(o.Visibility) for o in doc.Objects if hasattr(o,'Visibility')}
    for old in uses:
        if (old.Shape.isNull() or not old.Shape.isValid() or (old!=sketch and len(old.Shape.Faces)!=1) or
                any('Invalid' in o.State for o in [old]+old.OutListRecursive)):
            raise _reference_error()
        for dependent in old.InListRecursive:
            if 'Invalid' in dependent.State:raise _reference_error()
            if hasattr(dependent,'Shape') and dependent.Shape.Solids:
                preserved[dependent.Name]=model.world_shape(dependent)
    with model.transaction(doc,tr('スケッチ領域の参照を更新','Upgrade sketch profile references')):
        obsolete=set()
        delta=sketch.getGlobalPlacement().multiply(sketch.Placement.inverse())
        for old,consumers in uses.items():
            if old==sketch:new=source(doc,sketch,single_profile)
            else:
                face=model.world_shape(old);face.Placement=delta.inverse().multiply(face.Placement)
                new=source(doc,sketch,dict(face=face.Faces[0]))
            for obj,prop in consumers:
                setattr(obj,prop,[new if item==old else item for item in obj.Profiles] if prop=='Profiles' else new)
            if old!=sketch:
                obsolete.add(old)
                obsolete.update(o for o in old.OutListRecursive if getattr(o,'FluxCADInternal',False))
        doc.recompute()
        def verify():
            for name,expected in preserved.items():
                feature=doc.getObject(name);actual=model.world_shape(feature)
                tolerance=max(1e-6,abs(expected.Volume)*1e-7)
                if ('Invalid' in feature.State or 'Touched' in feature.State or actual.isNull() or not actual.isValid() or
                        abs(actual.Volume-expected.Volume)>tolerance or
                        abs(actual.common(expected).Volume-expected.Volume)>tolerance):raise _reference_error()
        verify()
        # Retire only generated helpers that nobody references anymore. Leaving
        # old mutable Slice networks orphaned can still break document recompute.
        while True:
            unused=[o for o in obsolete if not o.InList]
            if not unused:break
            for obj in unused:obsolete.remove(obj);doc.removeObject(obj.Name)
        doc.recompute();verify()
        for name,visible in visibility.items():
            obj=doc.getObject(name)
            if obj:obj.Visibility=visible
    return len(uses)



def nested_regions(sketch, regions):
    """Add intact nested cells without changing existing material profiles."""
    if regions and any('inputs' in region and not region.get('network') for region in regions):
        return crossing_nested_regions(sketch, regions)
    if not regions or any(region.get('network') or 'inputs' in region for region in regions):
        return regions
    wires = sketch.Shape.Wires
    if len(wires) < 2 or any(not wire.isClosed() for wire in wires):
        return regions
    filled = [Part.Face(wire) for wire in wires]
    if any(not face.isValid() or face.Area <= 1e-9 for face in filled):
        raise _reference_error()
    union = filled[0].multiFuse(filled[1:])
    material = regions[0]['face']
    if len(regions) > 1:
        material = material.multiFuse([region['face'] for region in regions[1:]])
    gaps = union.cut(material)
    if not gaps.isValid():
        raise _reference_error()
    result = list(regions)
    faces = sorted(gaps.Faces, key=lambda face: (face.CenterOfMass.x, face.CenterOfMass.y, face.CenterOfMass.z, face.Area))
    for face in faces:
        if face.Area <= 1e-9:
            continue
        if not face.isValid() or not all(wire.isClosed() for wire in face.Wires):
            raise _reference_error()
        result.append(dict(face=face, edges=[], inputs=[], network=True, nested_cell=True,
                           key=('NestedRegion%d' % (len(result) - len(regions) + 1),)))
    return result


def crossing_nested_regions(sketch, regions):
    if not regions:
        return regions
    material = regions[0]['face']
    if len(regions) > 1:
        material = material.multiFuse([r['face'] for r in regions[1:]])
    missing = []
    for cell in _cells(_geometry(sketch)):
        cell = cell.copy()
        cell.Placement = sketch.Placement.multiply(cell.Placement)
        tolerance = max(1e-9, cell.Area * 1e-8)
        overlap = cell.common(material).Area
        if overlap <= tolerance:
            missing.append(cell)
        elif abs(overlap - cell.Area) > tolerance:
            raise _reference_error()
    missing.sort(key=lambda c: (c.CenterOfMass.x, c.CenterOfMass.y, c.CenterOfMass.z, c.Area))
    result = list(regions)
    for index, face in enumerate(missing):
        result.append(dict(face=face, edges=[], inputs=[], network=True, nested_cell=True,
                           key=('CrossingNestedRegion%d' % (index + 1),)))
    return result
