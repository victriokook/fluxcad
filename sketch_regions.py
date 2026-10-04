"""Exact planar cells for sketch networks containing open curves.

The temporary enclosing face is never selectable. Persistent profiles use only
FreeCAD's Plane, SubShapeBinder, expressions and bundled Slice feature, so they
also recompute when the document is opened without the FluxCAD workspace.
"""
import FreeCAD as App
import Part
from i18n import tr


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


def profiles(sketch, closed_regions):
    from BOPTools.SplitAPI import slice
    extent = _extent(sketch)
    frame = Part.makePlane(2 * extent, 2 * extent, App.Vector(-extent, -extent, 0))
    frame.Placement = sketch.Placement.multiply(frame.Placement)
    split = slice(frame, sketch.Shape.Edges, 'Standard')
    if not split.isValid():
        raise ValueError(tr('曲線の交点で領域を分割できません。重複する線や微小な隙間を確認してください。',
                            'Cannot split regions at curve intersections. Check for duplicate edges or small gaps.'))
    border = Part.makeCompound(frame.Edges)
    # Preserve the existing nested-contour (hole) behavior even when the sketch
    # also contains an open curve. Exterior caps formed by curves remain usable.
    holes = None
    if closed_regions:
        filled = [Part.Face(w) for w in sketch.Shape.Wires if w.isClosed()]
        union = filled[0].multiFuse(filled[1:]) if len(filled) > 1 else filled[0]
        faces = [r['face'] for r in closed_regions]
        material = faces[0].multiFuse(faces[1:]) if len(faces) > 1 else faces[0]
        holes = union.cut(material)
    regions = []
    for face in split.Faces:
        if face.Area <= 1e-9 or face.common(border).Length > 1e-7:
            continue
        if holes and not holes.isNull() and face.common(holes).Area > max(1e-9, face.Area * 1e-8):
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


def source(doc, sketch, region):
    import model
    from BOPTools import SplitFeatures
    internal = model._internal
    frame = internal(doc.addObject('Part::Plane', 'RegionPlane'))
    frame.Label = tr('領域判定の基準面', 'Region support plane')
    frame.addProperty('App::PropertyLength', 'Extent', 'FluxCAD')
    frame.addProperty('App::PropertyPlacement', 'FrameOffset', 'FluxCAD')
    box, origin = sketch.Name + '.Shape.BoundBox.', sketch.Name + '.Placement.Base.'
    frame.setExpression('Extent', '10 mm + ' + ' + '.join(
        'abs(%s%s%s * 1 mm - %s%s)' % (box, axis, end, origin, axis.lower())
        for axis in 'XYZ' for end in ('Min', 'Max')))
    frame.setExpression('Length', '2 * Extent')
    frame.setExpression('Width', '2 * Extent')
    frame.setExpression('FrameOffset.Base.x', '-Extent')
    frame.setExpression('FrameOffset.Base.y', '-Extent')
    chain, parent = [sketch.Name + '.Placement'], sketch.getParentGeoFeatureGroup()
    while parent:
        chain.insert(0, parent.Name + '.Placement')
        parent = parent.getParentGeoFeatureGroup()
    frame.setExpression('Placement', ' * '.join(chain + ['FrameOffset']))
    # Separate inputs are essential: OCC does not intersect the edges inside
    # one unsplit compound with each other.
    tools = []
    for i in range(len(sketch.Shape.Edges)):
        binder = internal(model._profile_binder(doc, sketch, ['Edge%d' % (i + 1)], sketch.Label))
        binder.MakeFace = False
        tools.append(binder)
    fragments = internal(doc.addObject('Part::FeaturePython', 'SketchRegions'))
    SplitFeatures.FeatureSlice(fragments)
    if App.GuiUp:
        SplitFeatures.ViewProviderSlice(fragments.ViewObject)
    fragments.Base, fragments.Tools, fragments.Mode = frame, tools, 'Standard'
    fragments.Label = tr('スケッチの交差領域')
    doc.recompute()
    target = region['face'].copy()
    delta = sketch.getGlobalPlacement().multiply(sketch.Placement.inverse())
    target.Placement = delta.multiply(target.Placement)
    tolerance = max(1e-8, target.Area * 1e-7)
    matches = [face for face in fragments.Shape.Faces
               if abs(face.Area - target.Area) <= tolerance
               and abs(face.common(target).Area - target.Area) <= tolerance]
    if len(matches) != 1:
        raise ValueError(tr('選択した交差領域を特定できません。領域を選び直してください。'))
    # Keep original OCC identities here: constructing a wire can copy and
    # reparameterize trimmed arcs/splines, breaking the native subelement link.
    boundary = _boundary_edges(matches[0])
    if len(boundary) == len(matches[0].Edges):
        names = ['Face%d' % (i + 1) for i, face in enumerate(fragments.Shape.Faces) if face.isSame(matches[0])]
    else:
        names = ['Edge%d' % (i + 1) for i, edge in enumerate(fragments.Shape.Edges)
                 if any(edge.isSame(other) for other in boundary)]
    return internal(model._profile_binder(doc, fragments, names, tr('押し出し領域 (%s)') % sketch.Label))
