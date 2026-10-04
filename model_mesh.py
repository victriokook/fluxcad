"""Native mesh transforms, retaining topology and serializable Mesh::Features."""
import math
import FreeCAD as App
from i18n import tr
import model


def is_mesh(obj):
    return bool(obj and obj.isDerivedFrom('Mesh::Feature') and not getattr(obj,'FluxCADInternal',False))


def targets(doc,objects):
    if not objects:
        raise ValueError(tr('メッシュを選択してください。複数選択はCtrl＋クリックです。',
                            'Select a mesh. Ctrl-click to select multiple meshes.'))
    result=[]
    for obj in objects:
        if obj.Document!=doc or not is_mesh(obj) or not obj.Mesh.CountFacets:
            raise ValueError(tr('同じ文書のメッシュだけを選択してください。','Select only meshes from the same document.'))
        # Generated meshes must retain their source relationship; edit a plain
        # imported Mesh::Feature rather than silently overriding a generator.
        if obj.TypeId!='Mesh::Feature':
            raise ValueError(tr('生成されたメッシュは対象外です。STLとして読み込んだメッシュを選択してください。',
                                'Select an imported mesh; generated meshes are not supported.'))
        if any(path=='Placement' or path.startswith('Placement.') or path=='Mesh' for path,value in obj.ExpressionEngine):
            raise ValueError(tr('配置や形状が式で制御されているメッシュは変更できません。',
                                'This mesh has an expression-controlled placement or geometry.'))
        if obj not in result:result.append(obj)
    return result


def world_mesh(obj):
    mesh=obj.Mesh.copy()
    # Bake the placement: Mesh.BoundBox otherwise rotates the local bounding
    # box, overestimating dimensions for a rotated, irregular mesh.
    mesh.Placement=App.Placement()
    mesh.transformGeometry(obj.getGlobalPlacement().toMatrix())
    return mesh


def bounds(objects):
    result=App.BoundBox()
    for obj in objects:result.add(world_mesh(obj).BoundBox)
    return result


def scaling(factors,center):
    if len(factors)!=3 or any(not math.isfinite(f) or f<=0 for f in factors):
        raise ValueError(tr('倍率は0より大きい値を指定してください。','Scale factors must be greater than zero.'))
    matrix=App.Matrix()
    matrix.A11,matrix.A22,matrix.A33=factors
    matrix.A14,matrix.A24,matrix.A34=((1-f)*v for f,v in zip(factors,center))
    return matrix


def apply(doc,objects,*,factors=None,rotation=None,center=(0,0,0)):
    objects=targets(doc,objects)
    if (factors is None)==(rotation is None):raise ValueError('Specify one mesh transform.')
    results=[]
    matrix=scaling(factors,center) if factors is not None else rotation.toMatrix()
    for obj in objects:
        pose=App.Placement(obj.getGlobalPlacement())
        if factors is not None:
            mesh=obj.Mesh.copy();mesh.Placement=App.Placement()
            mesh.transformGeometry(pose.inverse().toMatrix().multiply(matrix).multiply(pose.toMatrix()))
            mesh.Placement=App.Placement(obj.Placement)
            results.append((obj,mesh))
        else:
            parent=pose.multiply(obj.Placement.inverse())
            results.append((obj,parent.inverse().multiply(rotation).multiply(pose)))
    with model.transaction(doc,tr('メッシュを変更','Transform meshes')):
        for obj,value in results:
            if factors is not None:obj.Mesh=value
            else:obj.Placement=value
    return objects


def export(objects,path):
    """Bake global placements, including parent containers, into the STL."""
    import Mesh
    result=Mesh.Mesh()
    for obj in objects:
        if is_mesh(obj):
            # addMesh merges raw coordinates and ignores the source Placement.
            result.addMesh(world_mesh(obj))
        else:
            vertices,triangles=model.world_shape(obj).tessellate(.1)
            result.addMesh(Mesh.Mesh((vertices,triangles)))
    if not result.CountFacets:raise ValueError(tr('書き出すメッシュがありません。','There is no mesh to export.'))
    result.write(path)
