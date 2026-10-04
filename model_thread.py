"""Metric internal threads using the installed FreeCAD PartDesign Hole engine."""
from contextlib import contextmanager
from functools import lru_cache
import math
import FreeCAD as App
import Part
import Sketcher  # Register native sketch types in a fresh session.
from i18n import tr

TYPES = ('ISOMetricProfile', 'ISOMetricFineProfile')
DEFAULTS = dict(thread_type=TYPES[0], thread_size='M6x1.0',
                thread_direction='Right', model_thread=False,
                thread_full=True, thread_depth=6)
PROPERTIES = dict(thread_type=('ThreadType','App::PropertyString'),
                  thread_size=('ThreadSize','App::PropertyString'),
                  thread_direction=('ThreadDirection','App::PropertyString'),
                  model_thread=('ModelThread','App::PropertyBool'),
                  thread_full=('ThreadFull','App::PropertyBool'),
                  thread_depth=('ThreadDepth','App::PropertyLength'))


@contextmanager
def native_hole():
    # Hidden, temporary documents have no GUI view, no saved user configuration,
    # and no undo entries in the user's document. Always dispose them on failure.
    active = App.ActiveDocument
    doc = App.newDocument('FluxThreadGenerator', '', True, True)
    try:
        body = doc.addObject('PartDesign::Body','Body')
        yield doc, body, doc.addObject('PartDesign::Hole','Hole')
    finally:
        App.closeDocument(doc.Name)
        if active and App.ActiveDocument != active:App.setActiveDocument(active.Name)


@lru_cache(maxsize=2)
def catalog(thread_type):
    if thread_type not in TYPES:raise ValueError(tr('メートルねじの規格を選択してください。','Select a metric thread standard.'))
    with native_hole() as (doc,body,hole):
        hole.ThreadType=thread_type;hole.Threaded=True;hole.ThreadClass='6H'
        result=[]
        for size in hole.getEnumerationsOfProperty('ThreadSize'):
            hole.ThreadSize=size
            # Names and tap-drill sizes come from this FreeCAD installation.
            result.append((size,float(hole.ThreadDiameter.Value),
                           float(size.split('x')[1]),float(hole.Diameter.Value)))
        return tuple(result)


def specification(thread_type,thread_size):
    for row in catalog(thread_type):
        if row[0]==thread_size:return row
    raise ValueError(tr('規格に含まれる呼び径とピッチを選択してください。','Select a designation offered by the thread standard.'))


def validate(depth,thread_type,thread_size,thread_direction,model_thread,thread_full,thread_depth):
    info=specification(thread_type,thread_size)
    if thread_direction not in ('Right','Left'):
        raise ValueError(tr('ねじ方向を選択してください。','Select a thread direction.'))
    length=depth if thread_full else thread_depth
    if not all(math.isfinite(x) and x>0 for x in (depth,length)) or length>depth+1e-7:
        raise ValueError(tr('ねじ深さは0より大きく、穴の深さ以下にしてください。','Thread depth must be positive and no greater than the hole depth.'))
    if model_thread and (length<info[2] or length/info[2]>50):
        raise ValueError(tr('ねじ山の実体化は1〜50ピッチの深さに対応します。ねじ深さを変更するか実体化を解除してください。',
                            'Modeled threads support depths of 1–50 pitches. Change the thread depth or turn off modeling.'))
    return info,length


@lru_cache(maxsize=8)
def _cutter(depth,thread_type,thread_size,thread_direction,thread_full,thread_depth):
    info,length=validate(depth,thread_type,thread_size,thread_direction,True,thread_full,thread_depth)
    with native_hole() as (doc,body,hole):
        # Native Hole needs a base even when only AddSubShape is requested.
        base=body.newObject('PartDesign::Feature','Base')
        base.Shape=Part.makeCylinder(info[1]/2+2,depth+2,App.Vector(0,0,-depth-1))
        sketch=body.newObject('Sketcher::SketchObject','Profile')
        sketch.addGeometry(Part.Circle(App.Vector(),App.Vector(0,0,1),info[1]/2),False)
        body.addObject(hole)
        hole.BaseFeature=base;hole.Profile=sketch
        hole.ThreadType=thread_type;hole.Threaded=True;hole.ThreadSize=thread_size
        hole.ThreadClass='6H';hole.ThreadDirection=thread_direction
        hole.DepthType='Dimension';hole.Depth=depth;hole.DrillPoint='Flat'
        hole.ThreadDepthType='Hole Depth' if thread_full else 'Dimension'
        if not thread_full:hole.ThreadDepth=length
        hole.ModelThread=True
        doc.recompute()
        tool=hole.AddSubShape.copy()
        if tool.isNull() or not tool.isValid() or len(tool.Solids)!=1 or 'Invalid' in hole.State:
            raise ValueError(tr('ねじ山を生成できません。呼び径・深さを変更してください。','Thread generation failed. Change the size or depth.'))
        # Native helical runout can extend beyond ThreadDepth and even Depth.
        # This panel promises distances from the entry face: trim at the chosen
        # thread depth, then continue only the drill cylinder for a partial thread.
        bounds=tool.BoundBox
        limit=Part.makeBox(bounds.XLength+2,bounds.YLength+2,bounds.ZMax+length+1,
                           App.Vector(bounds.XMin-1,bounds.YMin-1,-length))
        tool=tool.common(limit)
        if length<depth:
            stem=Part.makeCylinder(hole.Diameter.Value/2,depth,App.Vector(0,0,-depth))
            tool=tool.fuse(stem)
        tool=tool.removeSplitter()
        if tool.isNull() or not tool.isValid() or len(tool.Solids)!=1:
            raise ValueError(tr('指定した深さでねじ山を生成できません。','Unable to generate a thread at the specified depth.'))
        return tool


def cutter(depth,**values):
    values=dict(DEFAULTS,**values)
    validate(depth,**values)
    values.pop('model_thread')
    return _cutter(depth,**values).copy()


def settings(tool):
    return {key:(getattr(tool,name).Value if kind=='App::PropertyLength' else getattr(tool,name))
            if name in tool.PropertiesList else DEFAULTS[key]
            for key,(name,kind) in PROPERTIES.items()}


def assign(tool,values):
    for key,(name,kind) in PROPERTIES.items():
        if name not in tool.PropertiesList:tool.addProperty(kind,name,'Thread')
        setattr(tool,name,values.get(key,DEFAULTS[key]))
    if 'ThreadClass' not in tool.PropertiesList:tool.addProperty('App::PropertyString','ThreadClass','Thread')
    tool.ThreadClass='6H';tool.setEditorMode('ThreadClass',1)
