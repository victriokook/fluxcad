"""Parametric FreeCAD solids with persistent FluxCAD sketch profiles."""
from i18n import tr
import FreeCAD as App
import Part
import Sketcher
from contextlib import contextmanager


@contextmanager
def transaction(doc, label):
    doc.openTransaction(label)
    try:
        yield
        doc.recompute()
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        doc.recompute()
        raise


def check(obj):
    obj.Document.recompute()
    if obj.Shape.isNull() or not obj.Shape.isValid() or not obj.Shape.Solids:
        raise ValueError(tr('形状を作成できません。寸法や交差位置を確認してください。'))
    obj.ViewObject.ShapeColor = (0.72, 0.79, 0.85)
    obj.ViewObject.LineColor = (0.18, 0.23, 0.29)
    return obj


def box(doc, x, y, z):
    obj = doc.addObject('Part::Box', 'Box')
    obj.Label = tr('直方体')
    obj.Length, obj.Width, obj.Height = x, y, z
    return check(obj)


def cylinder(doc, radius, height):
    obj = doc.addObject('Part::Cylinder', 'Cylinder')
    obj.Label = tr('円柱')
    obj.Radius, obj.Height = radius, height
    return check(obj)


def rectangle(doc, width, height):
    obj = doc.addObject('Sketcher::SketchObject', 'Rectangle')
    obj.Label = tr('長方形スケッチ (XY)')
    pts = [App.Vector(0,0,0), App.Vector(width,0,0),
           App.Vector(width,height,0), App.Vector(0,height,0)]
    for i in range(4):
        idx = obj.addGeometry(Part.LineSegment(pts[i], pts[(i+1)%4]), False)
    for i in range(4):
        obj.addConstraint(Sketcher.Constraint('Coincident',i,2,(i+1)%4,1))
        obj.addConstraint(Sketcher.Constraint('Horizontal' if i%2 == 0 else 'Vertical',i))
    obj.addConstraint(Sketcher.Constraint('Coincident',0,1,-1,1))
    w = obj.addConstraint(Sketcher.Constraint('Distance',0,width))
    h = obj.addConstraint(Sketcher.Constraint('Distance',1,height))
    obj.renameConstraint(w,'Width')
    obj.renameConstraint(h,'Height')
    doc.recompute()
    return obj


def profiles(sketch):
    """Filled sketch cells, including regions divided by open curves."""
    if sketch.TypeId != 'Sketcher::SketchObject':
        raise ValueError(tr('閉じたスケッチを1つ選択してください。'))
    sketch.Document.recompute()
    wires = sketch.Shape.Wires
    simple = []
    for wire in wires:
        if wire.isClosed():
            face = Part.Face(wire)
            if face.isValid() and face.Area > 1e-9:
                simple.append(wire)
    # Closed polylines can cross themselves too. A single invalid face used to
    # suppress every region in the sketch, including a valid rectangle.
    if len(simple) != len(wires):
        import sketch_regions
        closed = _closed_profiles(sketch, simple) if simple else []
        return sketch_regions.profiles(sketch, closed, simple)
    import sketch_regions
    return sketch_regions.nested_regions(sketch, _closed_profiles(sketch))


def _closed_profiles(sketch, wires=None):
    """Filled cells of closed contours; nested loops remain holes."""
    if wires is None:
        wires = [wire for wire in sketch.Shape.Wires if wire.isClosed()]
    if not wires:
        raise ValueError(tr('閉じた輪郭がありません。線の端点をつないでください。'))
    # Group nested loops before splitting crossings, so existing holes stay holes.
    filled = [Part.Face(wire) for wire in wires]
    if any(not face.isValid() or face.Area<=1e-9 for face in filled):
        raise ValueError(tr('不正な輪郭があります。線の重複や自己交差を確認してください。'))
    parents = [None]*len(wires)
    crossing = False
    for i,face in enumerate(filled):
        for j in range(i):
            other = filled[j]
            overlap = face.common(other).Area
            tolerance = max(1e-9,min(face.Area,other.Area)*1e-8)
            if overlap<=tolerance:
                continue
            inside_i = abs(overlap-face.Area)<=tolerance
            inside_j = abs(overlap-other.Area)<=tolerance
            if inside_i and inside_j:
                raise ValueError(tr('重複する閉じた輪郭があります。重複を取り除いてください。'))
            if inside_i:
                if parents[i] is None or other.Area<filled[parents[i]].Area:
                    parents[i] = j
            elif inside_j:
                if parents[j] is None or face.Area<filled[parents[j]].Area:
                    parents[j] = i
            else:
                crossing = True
    groups = {}
    for i,wire in enumerate(wires):
        root = i
        while parents[root] is not None:
            root = parents[root]
        groups.setdefault(root,[]).append(wire)
    faces = [face for group in groups.values()
             for face in Part.makeFace(group,'Part::FaceMakerBullseye').Faces]
    result = []
    for face in faces:
        if not face.isValid() or face.Area <= 1e-9:
            raise ValueError(tr('輪郭が不正です。線の重複や自己交差を確認してください。'))
        edges = ['Edge%d'%(i+1) for i,edge in enumerate(sketch.Shape.Edges)
                 if any(edge.isSame(boundary) for boundary in face.Edges)]
        if len(edges) != len(face.Edges):
            raise ValueError(tr('領域の境界を特定できません。線の重複や自己交差を確認してください。'))
        result.append({'face':face,'edges':edges})
    if not result:
        raise ValueError(tr('押し出せる領域がありません。'))
    if crossing:
        from BOPTools.SplitAPI import booleanFragments
        split = booleanFragments(faces,'Standard')
        if not split.isValid() or not split.Faces:
            raise ValueError(tr('輪郭の交点で領域を分割できません。'))
        # A cut boundary is a portion of an original edge, so edge IDs alone no
        # longer identify the cell. Use a cell key scoped to this sketch shape.
        return [{'face':face,'edges':[],'key':('Region%d'%(i+1),),'inputs':result}
                for i,face in enumerate(split.Faces) if face.Area>1e-9]
    return result


def profile_key(region):
    return tuple(region.get('key',region['edges']))


def profile_for_key(regions,key):
    matches = [i for i,region in enumerate(regions) if profile_key(region)==tuple(key)]
    if len(matches)!=1:
        raise ValueError(tr('スケッチが変更されています。領域を選び直してください。'))
    return matches[0]


def profile_for_edges(regions, selected_edges):
    selected = set(selected_edges)
    matches = [i for i,region in enumerate(regions) if selected and selected.issubset(region['edges'])]
    if len(matches) != 1:
        if any('inputs' in region for region in regions):
            raise ValueError(tr('交差する輪郭は、押し出す領域の内側をクリックして選択してください。'))
        raise ValueError(tr('1つの領域に属する辺を選択してください。複数領域は、内側をCtrl＋クリックして選びます。'))
    return matches[0]


def _profile_binder(doc,obj,elements,label):
    import PartDesign
    support, path = obj, ''
    parent = support.getParentGeoFeatureGroup()
    while parent:
        path = support.Name + '.' + path
        support = parent
        parent = support.getParentGeoFeatureGroup()
    binder = doc.addObject('PartDesign::SubShapeBinder','ExtrusionProfile')
    binder.Label = label
    binder.Support = [(support,[path+element for element in elements])]
    binder.MakeFace = True
    # Track the support's coordinate system (including its parent containers).
    # With Relative=False a single circular edge loses the sketch placement,
    # so it no longer intersects the other contour faces in world coordinates.
    binder.Relative = True
    binder.Visibility = False
    return binder


def _internal(obj):
    obj.addProperty('App::PropertyBool','FluxCADInternal','FluxCAD')
    obj.FluxCADInternal = True
    obj.setEditorMode('FluxCADInternal',2)
    obj.Visibility = False
    return obj


def _split_profile_source(doc,sketch,region):
    """Keep all sketch profiles attached to persistent geometry identities."""
    import sketch_regions
    return sketch_regions.source(doc,sketch,region)


def extrude(doc, sketch, length, profile_edges=None, profile_index=None):
    regions = profiles(sketch)
    if profile_edges is None and profile_index is None:
        material = [i for i, region in enumerate(regions) if not region.get('nested_cell')]
        if len(material) == 1:
            profile_index = material[0]
    if len(regions)>1 and profile_edges is None and profile_index is None:
        raise ValueError(tr('複数の領域があります。押し出す輪郭の辺を選択してください。'))
    source = sketch
    if profile_edges is not None or profile_index is not None or len(regions)==1:
        index = profile_index if profile_index is not None else (profile_for_edges(regions,profile_edges) if profile_edges is not None else 0)
        if not isinstance(index,int) or not 0<=index<len(regions):
            raise ValueError(tr('領域を選び直してください。'))
        region = regions[index]
        source = _split_profile_source(doc,sketch,region)
        if source!=sketch:
            doc.recompute()
            if source.Shape.isNull() or len(source.Shape.Faces)!=1:
                raise ValueError(tr('選択した領域から面を作成できません。'))
    obj = doc.addObject('Part::Extrusion', 'Extrude')
    obj.Label = tr('押し出し')
    obj.Base = source
    obj.DirMode = 'Normal'
    obj.LengthFwd = length
    obj.Solid = True
    check(obj)
    source.Visibility = False
    # Keep the other regions available for the next extrusion.
    sketch.Visibility = len(regions)>1
    return obj


def world_shape(obj):
    shape = obj.Shape.copy()
    parent = obj.getGlobalPlacement().multiply(obj.Placement.inverse())
    shape.Placement = parent.multiply(shape.Placement)
    return shape


def extrusion_lengths(distance, direction, second=0):
    if distance<=0 or direction not in ('forward','reverse','symmetric','two'):
        raise ValueError(tr('押し出し距離を0より大きくしてください。'))
    if direction=='two' and second<=0:
        raise ValueError(tr('反対側の距離を0より大きくしてください。'))
    return {'forward':(distance,0),'reverse':(0,distance),
            'symmetric':(distance/2,distance/2),'two':(distance,second)}[direction]


def extrusion_shape(sketch, region, distance, direction='forward', second=0):
    forward,backward = extrusion_lengths(distance,direction,second)
    face = region['face'].copy()
    parent = sketch.getGlobalPlacement().multiply(sketch.Placement.inverse())
    face.Placement = parent.multiply(face.Placement)
    normal = sketch.getGlobalPlacement().Rotation.multVec(App.Vector(0,0,1))
    face.translate(normal*(-backward))
    shape = face.extrude(normal*(forward+backward))
    if shape.isNull() or not shape.isValid() or not shape.Solids:
        raise ValueError(tr('この領域は押し出せません。閉じた輪郭を確認してください。'))
    return shape


def extrusion_result(tool, target=None, operation='new'):
    if operation=='new':
        return tool
    if operation not in ('join','cut','intersect') or not target or not target.Shape.Solids:
        raise ValueError(tr('対象のボディを選択してください。'))
    base = world_shape(target)
    shape = {'join':base.fuse,'cut':base.cut,'intersect':base.common}[operation](tool).removeSplitter()
    tolerance = max(1e-8,base.Volume*1e-9)
    if shape.isNull() or not shape.isValid() or not shape.Solids or shape.Volume<tolerance:
        raise ValueError(tr('結果の立体が残りません。方向・距離・対象ボディを確認してください。'))
    if operation=='join' and len(shape.Solids)>len(base.Solids):
        raise ValueError(tr('対象ボディにつながりません。距離を変えるか「新規ボディ」を選んでください。'))
    if operation in ('join','cut') and abs(shape.Volume-base.Volume)<tolerance:
        raise ValueError(tr('対象ボディの形状が変わりません。方向・距離・対象ボディを確認してください。'))
    return shape


def profile_indices(regions, indices):
    indices = list(indices)
    if not indices or any(not isinstance(i,int) or not 0<=i<len(regions) for i in indices):
        raise ValueError(tr('押し出す領域を1つ以上選択してください。'))
    return list(dict.fromkeys(indices))


def extrusion_shapes(sketch, regions, indices, distance, direction='forward', second=0):
    """Union selected cells, keeping disconnected solids and excluding other cells."""
    indices = profile_indices(regions,indices)
    shapes = [extrusion_shape(sketch,regions[i],distance,direction,second) for i in indices]
    result = shapes[0].multiFuse(shapes[1:]).removeSplitter() if len(shapes)>1 else shapes[0]
    if result.isNull() or not result.isValid() or not result.Solids:
        raise ValueError(tr('選択領域をまとめて押し出せません。輪郭を確認してください。'))
    return result


def _connected_profiles(regions,indices):
    # An edge connects two extruded cells. Contact at a vertex alone does not
    # make a single solid and must keep the bodies separate.
    pending = list(indices)
    boundaries = {i:Part.makeCompound(regions[i]['face'].Edges) for i in indices}
    groups = []
    while pending:
        group = [pending.pop(0)]
        for i in group:
            for j in list(pending):
                if boundaries[i].common(boundaries[j]).Length>1e-7:
                    group.append(j)
                    pending.remove(j)
        groups.append(group)
    return groups


def _extrude_profiles(doc,sketch,regions,indices,distance,direction,second):
    if len(indices)>1:
        # Split cells may have opposite face normals. Normalize each extrusion
        # first, then fuse solids; fusing those faces can retain an internal seam.
        tools = [_extrude_profiles(doc,sketch,regions,[i],distance,direction,second) for i in indices]
        first = tools[0]
        for other in tools[1:]:
            for prop in ('LengthFwd','LengthRev','Symmetric'):
                other.setExpression(prop,first.Name+'.'+prop)
            reverse = first.Name+'.Reversed'
            other.setExpression('Reversed',reverse if other.Reversed==first.Reversed else '('+reverse+' ? 0 : 1)')
        combined = doc.addObject('Part::MultiFuse','MultiExtrude')
        combined.Label = tr('押し出し（%d 領域）')%len(indices)
        combined.Shapes = tools
        combined.Refine = True
        combined.addProperty('App::PropertyLink','FluxExtrusion','FluxCAD')
        combined.FluxExtrusion = first
        combined.setEditorMode('FluxExtrusion',2)
        for tool in tools:_internal(tool)
        return check(combined)
    tool = extrude(doc,sketch,distance,profile_index=indices[0])
    if tool.Base!=sketch and not getattr(tool.Base,'FluxCADInternal',False):
        _internal(tool.Base)
    normal = sketch.getGlobalPlacement().Rotation.multVec(App.Vector(0,0,1))
    opposite = tool.Dir.dot(normal)<0
    tool.LengthFwd = distance
    tool.LengthRev = second if direction=='two' else 0
    tool.Reversed = (direction=='reverse') != opposite
    tool.Symmetric = direction=='symmetric'
    check(tool)
    return tool


def create_extrusions(doc,sketch,indices,distance,direction='forward',second=0,
                      operation='new',target=None):
    """One Undo step; each disconnected new body remains independently editable."""
    if sketch.Document!=doc or (target and target.Document!=doc):
        raise ValueError(tr('同じ文書内のスケッチとボディを選択してください。'))
    regions = profiles(sketch)
    indices = profile_indices(regions,indices)
    if len(indices)==1:
        return [create_extrusion(doc,sketch,indices[0],distance,direction,second,operation,target)]
    expected = extrusion_result(extrusion_shapes(sketch,regions,indices,distance,direction,second),target,operation)
    groups = _connected_profiles(regions,indices) if operation=='new' else [indices]
    visibility = [(obj,bool(obj.Visibility)) for obj in doc.Objects if hasattr(obj,'Visibility')]
    try:
        with transaction(doc,tr('複数領域を押し出し')):
            tools = [_extrude_profiles(doc,sketch,regions,group,distance,direction,second) for group in groups]
            results = tools
            if operation!='new':
                tool = tools[0]
                result = doc.addObject({'join':'Part::Fuse','cut':'Part::Cut','intersect':'Part::Common'}[operation],'ExtrudeOperation')
                result.Label = tr('押し出し（%s）')%{'join':tr('結合'),'cut':tr('切り取り'),'intersect':tr('交差')}[operation]
                result.Base = _world_source(doc,target)
                result.Tool = tool
                result.Refine = True
                result.addProperty('App::PropertyLink','FluxExtrusion','FluxCAD')
                result.FluxExtrusion = getattr(tool,'FluxExtrusion',None) or tool
                result.addProperty('App::PropertyLinkGlobal','FluxBodySource','FluxCAD')
                result.FluxBodySource = target
                result.setEditorMode('FluxExtrusion',2)
                result.setEditorMode('FluxBodySource',2)
                _internal(tool)
                check(result)
                target.Visibility = False
                result.Base.Visibility = False
                results = [result]
            actual = Part.makeCompound([obj.Shape for obj in results])
            tolerance = max(1e-7,expected.Volume*1e-7)
            if (abs(actual.Volume-expected.Volume)>tolerance or
                    abs(actual.common(expected).Volume-expected.Volume)>tolerance):
                raise ValueError(tr('プレビューと作成結果が一致しないため、操作を取り消しました。'))
            sketch.Visibility = len(indices)<len(regions)
            for result in results:
                result.Visibility = True
        return results
    except Exception:
        for obj,visible in visibility:
            if obj.Document:
                obj.Visibility = visible
        raise


def _world_source(doc, obj):
    if not obj.getParentGeoFeatureGroup():
        return obj
    binder = _profile_binder(doc,obj,[''],tr('ボディ参照 (%s)')%obj.Label)
    binder.MakeFace = False
    _internal(binder)
    doc.recompute()
    return binder


def create_extrusion(doc, sketch, index, distance, direction='forward', second=0,
                     operation='new', target=None):
    if sketch.Document!=doc or (target and target.Document!=doc):
        raise ValueError(tr('同じ文書内のスケッチとボディを選択してください。'))
    regions = profiles(sketch)
    if not 0<=index<len(regions):
        raise ValueError(tr('領域を選び直してください。'))
    expected = extrusion_result(extrusion_shape(sketch,regions[index],distance,direction,second),target,operation)
    visibility = [(obj,bool(obj.Visibility)) for obj in doc.Objects if hasattr(obj,'Visibility')]
    try:
        with transaction(doc,tr('押し出し')):
            tool = extrude(doc,sketch,distance,profile_index=index)
            # Native normal mode follows subsequent sketch/container rotations.
            tool.DirMode = 'Normal'
            normal = sketch.getGlobalPlacement().Rotation.multVec(App.Vector(0,0,1))
            # A split face may have the opposite orientation to its sketch.
            opposite = tool.Dir.dot(normal)<0
            tool.LengthFwd = distance
            tool.LengthRev = second if direction=='two' else 0
            tool.Reversed = (direction=='reverse') != opposite
            tool.Symmetric = direction=='symmetric'
            check(tool)
            result = tool
            if operation!='new':
                result = doc.addObject({'join':'Part::Fuse','cut':'Part::Cut','intersect':'Part::Common'}[operation],'ExtrudeOperation')
                result.Label = tr('押し出し（%s）')%{'join':tr('結合'),'cut':tr('切り取り'),'intersect':tr('交差')}[operation]
                result.Base = _world_source(doc,target)
                result.Tool = tool
                result.Refine = True
                result.addProperty('App::PropertyLink','FluxExtrusion','FluxCAD')
                result.FluxExtrusion = tool
                result.addProperty('App::PropertyLinkGlobal','FluxBodySource','FluxCAD')
                result.FluxBodySource = target
                result.setEditorMode('FluxExtrusion',2)
                result.setEditorMode('FluxBodySource',2)
                _internal(tool)
                check(result)
                target.Visibility = False
                result.Base.Visibility = False
            actual = result.Shape
            tolerance = max(1e-7,expected.Volume*1e-7)
            # Display tessellation can shift a curved shape's cached bounding
            # box. Compare the solids themselves, not those approximate bounds.
            if (abs(actual.Volume-expected.Volume)>tolerance or
                    abs(actual.common(expected).Volume-expected.Volume)>tolerance):
                raise ValueError(tr('プレビューと作成結果が一致しないため、操作を取り消しました。'))
            result.Visibility = True
        return result
    except Exception:
        for obj,visible in visibility:
            if obj.Document:
                obj.Visibility = visible
        raise


def hole(doc, base, x, y, diameter):
    bounds = base.Shape.BoundBox
    tool = cylinder(doc, diameter / 2, bounds.ZLength + 2)
    tool.Label = tr('穴の工具 (直径・位置)')
    tool.Placement.Base = App.Vector(x,y,bounds.ZMin-1)
    doc.recompute()
    obj = doc.addObject('Part::Cut', 'Hole')
    obj.Label = tr('貫通穴 (Z方向)')
    obj.Base, obj.Tool = base, tool
    check(obj)
    if obj.Shape.Volume >= base.Shape.Volume - 1e-7:
        raise ValueError(tr('穴がボディと交差していません。中心座標を変更してください。'))
    base.Visibility = False
    tool.Visibility = False
    return obj


def fillet(doc, base, edges, radius):
    if not edges:
        raise ValueError(tr('Ctrlキーでエッジを選択してください。'))
    obj = doc.addObject('Part::Fillet', 'Fillet')
    obj.Label = tr('フィレット')
    obj.Base = base
    obj.Edges = [(int(e[4:]), radius, radius) for e in edges]
    check(obj)
    base.Visibility = False
    return obj


def chamfer(doc, base, edges, distance):
    if not edges or distance<=0:
        raise ValueError(tr('面取りするエッジを選択し、0より大きい距離を指定してください。'))
    obj = doc.addObject('Part::Chamfer','Chamfer')
    obj.Label = tr('面取り')
    obj.Base = _world_source(doc,base)
    obj.Edges = [(int(edge[4:]),distance,distance) for edge in edges]
    if obj.Base!=base:
        obj.addProperty('App::PropertyLinkGlobal','FluxBodySource','FluxCAD')
        obj.FluxBodySource=base
        obj.setEditorMode('FluxBodySource',2)
    check(obj)
    base.Visibility=False
    obj.Base.Visibility=False
    return obj


def combine(doc, first, second, cut=False):
    obj = doc.addObject('Part::Cut' if cut else 'Part::Fuse', 'Boolean')
    obj.Label = tr('切り取り') if cut else tr('結合')
    obj.Base, obj.Tool = first, second
    check(obj)
    first.Visibility = second.Visibility = False
    return obj


def movable_solids(doc, objects, allow_mesh=False):
    """Resolve picked faces/features to the solids whose placements can move."""
    if not objects:
        raise ValueError(tr('移動する立体を選択してください。複数選択はCtrl＋クリックです。'))
    result = []
    for obj in objects:
        if allow_mesh:
            import model_mesh
            if model_mesh.is_mesh(obj):
                for mesh in model_mesh.targets(doc, [obj]):
                    if mesh not in result:
                        result.append(mesh)
                continue
        if obj.Document != doc or not hasattr(obj, 'Shape') or obj.Shape.isNull() or (not obj.Shape.Solids):
            raise ValueError(tr('同じ文書内の立体を選択してください。スケッチは移動対象に含められません。'))
        if obj.isDerivedFrom('PartDesign::Feature'):
            body = obj.getParentGeoFeatureGroup()
            if body and body.isDerivedFrom('PartDesign::Body'):
                obj = body
        if getattr(obj, 'FluxSplit', False):
            raise ValueError(tr('ブラウザーで分割後のボディを選択して移動してください。', 'Select the resulting bodies in the browser to move them.'))
        if not hasattr(obj, 'Placement'):
            raise ValueError(tr('%s の位置は変更できません。') % obj.Label)
        if getattr(obj, 'FluxComponent', False) and (obj.Grounded or obj.Driver):
            raise ValueError(tr('接地された部品は接地を解除してください。接続された部品はジョイントの角度・距離を編集するか、ジョイントを解除してください。', 'Unground fixed components. For connected components, edit the joint angle/distance or release the joint.'))
        if any((path.lstrip('.') == 'Placement' or path.lstrip('.').startswith('Placement.') for path, value in obj.ExpressionEngine)):
            raise ValueError(tr('%s の配置は式で制御されています。配置の式を解除してから移動してください。') % obj.Label)
        if obj not in result:
            result.append(obj)
    return result


def move_solids(doc, objects, dx, dy, dz, allow_mesh=False):
    targets = movable_solids(doc,objects,allow_mesh=allow_mesh)
    delta = App.Vector(dx,dy,dz)
    if delta.Length < 1e-12:
        return targets
    placements = []
    for obj in targets:
        # FreeCAD exposes a live Placement wrapper. Copy it before computing
        # changes so every write happens inside the single undo transaction.
        placement = App.Placement(obj.Placement)
        parent = obj.getGlobalPlacement().multiply(placement.inverse())
        placement.Base += parent.Rotation.inverted().multVec(delta)
        placements.append((obj,placement))
    with transaction(doc,tr('立体を移動')):
        for obj,placement in placements:
            obj.Placement = placement
    return targets
