"""Export visible document geometry, independently of the current selection."""
import model_mesh


def visible_objects(doc):
    if not doc:
        return []
    result = []
    for obj in doc.Objects:
        if (not getattr(obj, 'Visibility', False)
                or getattr(obj, 'FluxCADInternal', False)
                or getattr(obj, 'FluxPlane', False)
                or getattr(obj, 'FluxConstructionAxis', '')
                or obj.TypeId.endswith('ShapeBinder')
                or obj.TypeId in ('App::Part', 'App::DocumentObjectGroup', 'App::Origin',
                                  'App::Line', 'App::Plane', 'App::Point')
                or obj.isDerivedFrom('App::OriginFeature')):
            continue
        parent = obj.getParentGeoFeatureGroup()
        # A PartDesign Body already supplies its final solid. Exporting its
        # visible tip as well would duplicate the same material.
        if (parent and parent.isDerivedFrom('PartDesign::Body')
                and obj.isDerivedFrom('PartDesign::Feature')):
            continue
        while parent and getattr(parent, 'Visibility', True):
            parent = parent.getParentGeoFeatureGroup()
        if parent:
            continue  # A hidden container can still have visible child flags.
        if model_mesh.is_mesh(obj) and obj.Mesh.CountFacets:
            result.append(obj)
        elif hasattr(obj, 'Shape') and not obj.Shape.isNull():
            if obj.TypeId not in ('PartDesign::Plane', 'PartDesign::Line', 'PartDesign::Point'):
                result.append(obj)
    return result


def stl_objects(objects):
    """STL has facets only; visible sketch/curve/point objects have no facets."""
    return [obj for obj in objects if model_mesh.is_mesh(obj) or obj.Shape.Faces]


def export_step(objects, path):
    import FreeCAD as App
    import FreeCADGui as Gui
    import Import
    import model
    import Part
    active = App.ActiveDocument
    selection = Gui.Selection.getSelectionEx()
    temporary = App.newDocument('FluxCADExport', hidden=True)
    try:
        snapshots = []
        for obj in objects:
            snapshot = temporary.addObject('Part::Feature', obj.Name)
            snapshot.Label = obj.Label
            compound = Part.makeCompound([model.world_shape(obj)])
            snapshot.Shape = compound
            snapshots.append(snapshot)
        temporary.recompute()
        Import.export(snapshots, path)
    finally:
        App.closeDocument(temporary.Name)
        if active:
            App.setActiveDocument(active.Name)
        Gui.Selection.clearSelection()
        for entry in selection:
            for subelement in entry.SubElementNames or ['']:
                Gui.Selection.addSelection(entry.Object, subelement)


def context(doc):
    """Capture exact export membership, object identity, geometry and world pose."""
    import FreeCAD as App
    result = []
    for obj in visible_objects(doc):
        pose = tuple(obj.getGlobalPlacement().toMatrix().A)
        if model_mesh.is_mesh(obj):
            mesh = obj.Mesh.copy()
            mesh.Placement = App.Placement()
            vertices, triangles = mesh.Topology
            geometry = (tuple(tuple(v) for v in vertices), tuple(tuple(t) for t in triangles))
        else:
            geometry = obj.Shape.hashCode()
        result.append((obj.Name, id(obj), pose, geometry))
    return tuple(result)
