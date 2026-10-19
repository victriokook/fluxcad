"""Delete current bodies and their exclusive history in one native transaction."""
from i18n import tr
import model


def _container_reference(parent, child):
    # Group membership is removed by FreeCAD; geometric references must survive.
    if parent.TypeId not in ('App::Part', 'App::DocumentObjectGroup'):
        return False
    if getattr(parent, 'ExpressionEngine', []):
        return False
    import browser
    references = [prop for prop in parent.PropertiesList
                  if child in list(browser.linked_objects(getattr(parent, prop)))]
    return references == ['Group']


def plan(doc, names):
    """Keep shared upstream history; reject live downstream dependencies."""
    import browser
    names = set(names)
    bodies, _, downstream = browser.collect(doc)
    tips = {obj.Name for obj, _ in bodies if not getattr(obj, 'FluxComponent', False)}
    if not names or not names <= tips:
        raise ValueError(tr('ブラウザーの「ボディ」から削除するボディを選択してください。',
                            'Select the bodies to delete in the browser Bodies group.'))
    required = {name for name, results in downstream.items()
                if {obj.Name for obj, _ in results} <= names}
    # A native PartDesign Body owns its entire group, including its sketches.
    # Sketches outside a Body, as used by FluxCAD, are never included here.
    for name in list(required):
        obj = doc.getObject(name)
        if obj.isDerivedFrom('PartDesign::Body'):
            stack = list(obj.Group) + [obj.Origin]
            while stack:
                child = stack.pop()
                if child is None or child.Name in required:
                    continue
                required.add(child.Name)
                stack.extend(getattr(child, 'Group', []))
                stack.extend(getattr(child, 'OriginFeatures', []))
    candidates = set(required)
    stack = list(required)
    while stack:
        for source in doc.getObject(stack.pop()).OutList:
            if (source.Document == doc and getattr(source, 'FluxCADInternal', False)
                    and source.Name not in candidates):
                candidates.add(source.Name)
                stack.append(source.Name)

    def external_users(name):
        obj = doc.getObject(name)
        return [parent for parent in obj.InList
                if not (parent.Document == doc and parent.Name in candidates)
                and not _container_reference(parent, obj)]

    # Helpers may be shared by another extrusion or drawing. Preserve them and
    # all of their own inputs; never leave surviving objects with broken links.
    while True:
        shared = {name for name in candidates-required if external_users(name)}
        if not shared:
            break
        candidates -= shared
    blockers = {parent.Label for name in required for parent in external_users(name)}
    if blockers:
        raise ValueError(tr('次のオブジェクトがこのボディを参照しているため削除できません：\n',
                            'These objects reference this body, so it cannot be deleted:\n') +
                         '\n'.join(sorted(blockers)) + tr(
                             '\n参照するボディも一緒に選択するか、先に参照を解除してください。',
                             '\nSelect the dependent bodies too, or remove their references first.'))
    # Dependents first, so native onDelete handlers see an intact source.
    ordered, visited = [], set()
    def visit(name):
        if name in visited:
            return
        visited.add(name)
        for parent in doc.getObject(name).InList:
            if parent.Document == doc and parent.Name in candidates:
                visit(parent.Name)
        ordered.append(name)
    for obj in doc.Objects:
        if obj.Name in candidates:
            visit(obj.Name)
    return ordered


def remove(doc, names):
    ordered = plan(doc, names)
    with model.transaction(doc, tr('ボディを削除', 'Delete Bodies')):
        for name in ordered:
            if doc.getObject(name):
                doc.removeObject(name)
    return ordered


def check_context(doc,names,expected):
    current=plan(doc,names)
    if current!=[name for name,obj in expected] or any(doc.getObject(name) is not obj for name,obj in expected):
        raise ValueError(tr('削除対象が変更されました。キャンセルして選び直してください。','The deletion targets changed. Cancel and select them again.'))
