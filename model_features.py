"""Parametric modeling operations using FreeCAD's bundled feature types."""
from i18n import tr
import math
import FreeCAD as App
import Part
import model
import model_axis
import model_mirror


def axis_vector(axis, reverse=False):
    if axis not in ('X','Y','Z'):
        raise ValueError(tr('X・Y・Zのいずれかの軸を選択してください。'))
    return App.Vector(*{'X':(1,0,0),'Y':(0,1,0),'Z':(0,0,1)}[axis])*(-1 if reverse else 1)


def solid(shape):
    if shape.isNull() or not shape.isValid() or not shape.Solids or shape.Volume<=1e-9:
        raise ValueError(tr('立体を作成できません。軸・輪郭・寸法を確認してください。'))
    return shape


def profile_face(sketch, region):
    face = region['face'].copy()
    face.Placement = sketch.getGlobalPlacement().multiply(sketch.Placement.inverse()).multiply(face.Placement)
    return face


def revolve_shape(face, axis='Y', center=(0,0,0), angle=360, reverse=False, reference=None, subelement=''):
    if not 0<angle<=360:
        raise ValueError(tr('回転角度は0より大きく360°以下にしてください。'))
    origin,direction=model_axis.values(axis,center,reverse,reference,subelement)
    return solid(face.revolve(origin,direction,angle))


def rectangular_intervals(count, axis, spacing, count2=1, axis2='Y', spacing2=10, distribution='spacing'):
    if (not all(math.isfinite(v) and int(v)==v for v in (count,count2))
            or not 2<=count<=200 or not 1<=count2<=200 or count*count2>200):
        raise ValueError(tr('個数は方向1が2以上、方向2が1以上、合計200個以内で指定してください。',
                            'Use at least 2 in direction 1 and 1 in direction 2, with at most 200 instances in total.'))
    if distribution not in ('spacing','extent'):
        raise ValueError(tr('距離の指定方法を選択してください。','Select a distance type.'))
    first,second=axis_vector(axis),axis_vector(axis2)
    if count2>1 and axis==axis2:
        raise ValueError(tr('方向1と方向2は異なる軸を選択してください。','Choose different axes for directions 1 and 2.'))
    if any(not math.isfinite(v) or abs(v)>100000 or abs(v)<1e-6 for v in (spacing,spacing2)[:2 if count2>1 else 1]):
        raise ValueError(tr('距離は0以外の−100000～100000 mmで指定してください。',
                            'Distances must be finite, nonzero and between -100000 and 100000 mm.'))
    step1=spacing/(count-1) if distribution=='extent' else spacing
    step2=spacing2/max(1,count2-1) if distribution=='extent' else spacing2
    return first*step1,second*step2


def pattern_shape(base, kind, count=3, axis='X', spacing=10, angle=360, center=(0,0,0), reverse=False,
                  count2=1, axis2='Y', spacing2=10, distribution='spacing', reference=None, subelement=''):
    if int(count)!=count or not 2<=count<=200:
        raise ValueError(tr('個数は元のボディを含めて2～200個で指定してください。'))
    origin,direction=model_axis.values(axis,center,reverse,reference,subelement) if kind=='circular' else (None,axis_vector(axis))
    if kind not in ('linear','circular'):
        raise ValueError(tr('パターンの種類を選択してください。'))
    if kind=='linear':
        first,second=rectangular_intervals(count,axis,spacing,count2,axis2,spacing2,distribution)
    if kind=='circular' and not 0<angle<=360:
        raise ValueError(tr('配置角度は0より大きく360°以下にしてください。'))
    source = solid(model.world_shape(base))
    shapes = []
    step = angle/(count if angle==360 else count-1)
    for i in range(count*(count2 if kind=='linear' else 1)):
        shape = source.copy()
        if kind=='linear':
            shape.translate(first*(i%count)+second*(i//count))
        elif i:
            shape.rotate(origin,direction,step*i)
        shapes.append(shape)
    return solid(Part.makeCompound(shapes))


def placed_preview(shape, existing=None):
    if existing:
        shape.Placement = existing.Placement.multiply(shape.Placement)
    return shape


def verify_result(obj, expected):
    model.check(obj)
    if 'Invalid' in obj.State or any('Invalid' in source.State for source in obj.OutListRecursive):
        raise ValueError(tr('参照元または形状にエラーがあるため、変更を取り消しました。',
                            'The source or result has an error. The change was cancelled.'))
    tolerance = max(1e-7,expected.Volume*1e-7)
    def center(shape):
        return sum((s.CenterOfMass*s.Volume for s in shape.Solids),App.Vector())/shape.Volume
    if (abs(obj.Shape.Volume-expected.Volume)>tolerance or
            (center(obj.Shape)-center(expected)).Length>1e-5):
        raise ValueError(tr('プレビューと作成結果が一致しないため、操作を取り消しました。'))
    for feature in obj.InListRecursive:
        if hasattr(feature,'Shape') and (feature.Shape.isNull() or not feature.Shape.isValid() or 'Invalid' in feature.State):
            raise ValueError(tr('後の加工を更新できないため、変更を取り消しました。'))


def create_revolution(doc, sketch, index=0, axis='Y', center=(0,0,0), angle=360, reverse=False, existing=None,
                      reference=None, subelement=''):
    if reference:model_axis.validate(doc,reference,subelement,existing)
    if existing:
        source = existing.Source
        face = model.world_shape(source).Faces[0]
    else:
        if sketch.Document!=doc:
            raise ValueError(tr('同じ文書内のスケッチを選択してください。'))
        regions = model.profiles(sketch)
        if not 0<=index<len(regions):
            raise ValueError(tr('領域を選び直してください。'))
        region = regions[index]
        face = profile_face(sketch,region)
    expected = placed_preview(revolve_shape(face,axis,center,angle,reverse,reference,subelement),existing)
    with model.transaction(doc,tr('回転を編集') if existing else tr('回転')):
        if existing:
            obj = existing
        else:
            source = model._split_profile_source(doc,sketch,region)
            doc.recompute()
            obj = doc.addObject('Part::Revolution','Revolution')
            obj.Label = tr('回転')
            obj.Source = source
            obj.Solid = True
            obj.addProperty('App::PropertyBool','FluxRevolution','FluxCAD')
            obj.FluxRevolution = True
            obj.setEditorMode('FluxRevolution',2)
        model_axis.bind(obj,axis,center,reverse,reference,subelement)
        obj.Angle = angle
        verify_result(obj,expected)
        if not existing:
            source.Visibility = False
            sketch.Visibility = len(regions)>1
            obj.Visibility = True
    return obj


def create_pattern(doc, base, kind, count=3, axis='X', spacing=10, angle=360, center=(0,0,0), reverse=False, existing=None,
                   count2=1, axis2='Y', spacing2=10, distribution='spacing', reference=None, subelement=''):
    if base.Document!=doc or (existing and existing.Document!=doc):
        raise ValueError(tr('同じ文書内のボディを選択してください。'))
    if existing and (existing.FluxPattern!=kind or base==existing or base in existing.InListRecursive):
        raise ValueError(tr('パターンの種類や参照元を確認してください。','Check the pattern type and source.'))
    if reference:
        if kind!='circular':raise ValueError(tr('形状の軸は円形パターンで選択してください。','Geometry axes are supported for circular patterns.'))
        model_axis.validate(doc,reference,subelement,existing)
    expected = placed_preview(pattern_shape(base,kind,count,axis,spacing,angle,center,reverse,
                                            count2,axis2,spacing2,distribution,reference,subelement),existing)
    with model.transaction(doc,tr('パターンを編集') if existing else tr('パターン')):
        if existing:
            obj = existing
        else:
            from draftobjects.array import Array
            from draftviewproviders.view_array import ViewProviderDraftArray
            obj = doc.addObject('Part::FeaturePython','Pattern')
            Array(obj)
            ViewProviderDraftArray(obj.ViewObject)
            obj.Base = model._world_source(doc,base)
            obj.addProperty('App::PropertyString','FluxPattern','FluxCAD')
            obj.FluxPattern = kind
            obj.setEditorMode('FluxPattern',2)
            obj.addProperty('App::PropertyLinkGlobal','FluxBodySource','FluxCAD')
            obj.FluxBodySource = base
            obj.setEditorMode('FluxBodySource',2)
            obj.Label = tr('矩形状パターン','Rectangular Pattern') if kind=='linear' else tr('円形パターン')
        obj.Fuse = False
        if kind=='linear':
            obj.ArrayType = 'ortho'
            obj.NumberX = count
            obj.NumberY = count2;obj.NumberZ = 1
            if 'FluxDistribution' not in obj.PropertiesList:
                obj.addProperty('App::PropertyEnumeration','FluxDistribution','Pattern')
                obj.FluxDistribution=['spacing','extent']
                for name in ('FluxDistance1','FluxDistance2'):
                    obj.addProperty('App::PropertyDistance',name,'Pattern')
            obj.FluxDistribution=distribution
            obj.FluxDistance1=spacing;obj.FluxDistance2=spacing2
            first,second=rectangular_intervals(count,axis,spacing,count2,axis2,spacing2,distribution)
            # Native expressions keep total extents when a quantity is changed,
            # and remain editable/recomputable without a FluxCAD proxy.
            for interval,vector,axis_name,distance_name,number in (
                    ('IntervalX',first,axis,'FluxDistance1','NumberX'),
                    ('IntervalY',second,axis2,'FluxDistance2','NumberY')):
                for component in 'xyz':obj.setExpression(interval+'.'+component,None)
                setattr(obj,interval,vector)
                divisor=' / ('+number+' > 1 ? '+number+' - 1 : 1)' if distribution=='extent' else ''
                obj.setExpression(interval+'.'+axis_name.lower(),distance_name+divisor)
        else:
            obj.ArrayType = 'polar'
            obj.NumberPolar = count
            obj.Angle = angle
            model_axis.bind(obj,axis,center,reverse,reference,subelement)
        verify_result(obj,expected)
        if not existing:
            base.Visibility = False
            obj.Base.Visibility = False
            obj.Visibility = True
    return obj


def mirror_shape(base, plane='YZ', offset=0, reference=None, subelement=''):
    origin,normal=model_mirror.frame(plane,offset,reference,subelement)
    return solid(solid(model.world_shape(base)).mirror(origin,normal))


def shell_shape(base, faces, thickness=1, inward=True):
    source = solid(model.world_shape(base))
    if len(source.Solids)!=1:
        raise ValueError(tr('シェルにする、1つにつながった立体を選択してください。'))
    if not thickness>0:
        raise ValueError(tr('厚さを0より大きくしてください。'))
    faces = list(dict.fromkeys(faces))
    if not faces or len(faces)>=len(source.Faces):
        raise ValueError(tr('開ける面を1つ以上選択してください。すべての面は選択できません。'))
    indices = []
    for name in faces:
        if not name.startswith('Face') or not name[4:].isdigit() or not 1<=int(name[4:])<=len(source.Faces):
            raise ValueError(tr('開ける面を選び直してください。'))
        indices.append(int(name[4:])-1)
    try:
        # Skin mode, sharp intersections, no self-intersection correction.
        result = source.makeThickness([source.Faces[i] for i in indices],
                                      -thickness if inward else thickness,1e-4,False,False,0,2)
        solid(result)
        if len(result.Solids)!=1:
            raise ValueError('separated walls')
        if inward:
            # OCC can return the unchanged, valid source when the cavity collapses.
            tolerance = max(1e-7,source.Volume*1e-8)
            if (source.Volume-result.Volume<=tolerance or
                    abs(source.common(result).Volume-result.Volume)>tolerance):
                raise ValueError('collapsed or protruding cavity')
    except (RuntimeError,ValueError):
        raise ValueError(tr('この面と厚さではシェルを作成できません。厚さを小さくするか、開ける面を変更してください。')) from None
    return result


def create_mirror(doc, base, plane='YZ', offset=0, existing=None, reference=None, subelement=''):
    if base.Document!=doc or (existing and existing.Document!=doc):
        raise ValueError(tr('同じ文書内のボディを選択してください。'))
    if existing and (existing.TypeId!='Part::Mirroring' or base==existing or existing in base.OutListRecursive):
        raise ValueError(tr('ミラーの参照元を確認してください。','Check the mirror source.'))
    if reference is not None:model_mirror.validate(doc,reference,subelement,existing)
    expected = placed_preview(mirror_shape(base,plane,offset,reference,subelement),existing)
    downstream_solids=[o for o in existing.InListRecursive if hasattr(o,'Shape') and o.Shape.Solids] if existing else []
    with model.transaction(doc,tr('ミラーを編集') if existing else tr('ミラー')):
        obj = existing
        if obj is None:
            obj = doc.addObject('Part::Mirroring','Mirror')
            obj.Label = tr('ミラー')
            obj.Source = model._world_source(doc,base)
            obj.addProperty('App::PropertyBool','FluxMirror','FluxCAD')
            obj.FluxMirror = True
            obj.setEditorMode('FluxMirror',2)
        model_mirror.bind(obj,plane,offset,reference,subelement)
        verify_result(obj,expected)
        if any(not feature.Shape.Solids or feature.Shape.Volume<=1e-9 for feature in downstream_solids):
            raise ValueError(tr('後の加工の立体が失われるため、変更を取り消しました。','The edit would remove a downstream solid and was cancelled.'))
        if not existing:obj.Visibility=True
    return obj


def create_shell(doc, base, faces, thickness=1, inward=True, existing=None):
    if base.Document!=doc or (existing and existing.Document!=doc):
        raise ValueError(tr('同じ文書内のボディを選択してください。'))
    expected = placed_preview(shell_shape(base,faces,thickness,inward),existing)
    with model.transaction(doc,tr('シェルを編集') if existing else tr('シェル')):
        obj = existing
        if obj is None:
            obj = doc.addObject('Part::Thickness','Shell')
            obj.Label = tr('シェル')
            obj.addProperty('App::PropertyBool','FluxShell','FluxCAD')
            obj.FluxShell = True
            obj.setEditorMode('FluxShell',2)
            obj.addProperty('App::PropertyLinkGlobal','FluxBodySource','FluxCAD')
            obj.FluxBodySource = base
            obj.setEditorMode('FluxBodySource',2)
            source = model._world_source(doc,base)
        else:
            source = base
        obj.Faces = (source,list(dict.fromkeys(faces)))
        obj.Value = -thickness if inward else thickness
        obj.Mode = 'Skin'
        obj.Join = 'Intersection'
        obj.Intersection = obj.SelfIntersection = False
        verify_result(obj,expected)
        if not existing:
            base.Visibility = False
            source.Visibility = False
            obj.Visibility = True
    return obj


def feature_kind(obj):
    if getattr(obj,'FluxHole',False):return 'hole'
    if getattr(obj,'FluxPlane',False):return 'plane'
    if getattr(obj,'FluxLoft',False):return 'loft'
    if getattr(obj,'FluxSweep',False):return 'sweep'
    if getattr(obj,'FluxRevolution',False):return 'revolve'
    if getattr(obj,'FluxMirror',False):return 'mirror'
    if getattr(obj,'FluxShell',False):return 'shell'
    return getattr(obj,'FluxPattern','')


def feature_source(obj):
    kind = feature_kind(obj)
    if kind=='hole':return obj.Tool.Support[0]
    if kind=='plane':return obj
    if kind in ('loft','sweep'):return obj.Sections[0]
    if kind in ('revolve','mirror'):return obj.Source
    if kind=='shell':return obj.Faces[0]
    return obj.Base


def settings(obj):
    if getattr(obj,'FluxMirror',False):
        linked=model_mirror.settings(obj)
        if linked:return dict(linked,kind='mirror')
        axis = max(range(3),key=lambda i:abs(tuple(obj.Normal)[i]))
        return {'kind':'mirror','plane':('YZ','XZ','XY')[axis],'offset':tuple(obj.Base)[axis]}
    if getattr(obj,'FluxShell',False):
        return {'kind':'shell','faces':list(obj.Faces[1]),'thickness':abs(obj.Value.Value),'inward':obj.Value.Value<0}
    if obj.TypeId=='Part::Revolution':
        direction = obj.Axis
        values = {'kind':'revolve','angle':float(obj.Angle),'center':tuple(obj.Base)}
    elif obj.FluxPattern=='linear':
        direction = obj.IntervalX
        values = {'kind':'linear','count':obj.NumberX,'spacing':0}
    else:
        direction = obj.Axis
        values = {'kind':'circular','count':obj.NumberPolar,'angle':obj.Angle.Value,'center':tuple(obj.Center)}
    index = max(range(3),key=lambda i:abs(tuple(direction)[i]))
    values['axis'] = 'XYZ'[index]
    values['reverse'] = tuple(direction)[index]<0
    if values['kind']!='linear':
        linked=model_axis.settings(obj)
        if linked:values.update(linked)
        elif sum(abs(v)>1e-9 for v in tuple(direction))>1:
            # Preserve native/imported oblique axes during history edits too.
            values.update(axis_mode='vector',axis=tuple(direction),reverse=False)
    if values['kind']=='linear':
        values['spacing'] = tuple(direction)[index]
        second=obj.IntervalY
        index2=max(range(3),key=lambda i:abs(tuple(second)[i])) if second.Length>1e-9 else (index+1)%3
        values.update(count2=obj.NumberY,axis2='XYZ'[index2],spacing2=tuple(second)[index2] if second.Length>1e-9 else 10,
                      distribution=str(getattr(obj,'FluxDistribution','spacing')))
        if values['distribution']=='extent':
            values['spacing']*=obj.NumberX-1
            values['spacing2']*=max(1,obj.NumberY-1)
    return values
