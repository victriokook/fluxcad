"""One unpickable construction grid for viewing, sketching and native snapping."""
from i18n import tr
import math
from contextlib import contextmanager
import FreeCAD as App
import FreeCADGui as Gui
from pivy import coin

DENSITIES = [(tr('標準（従来）'),20),(tr('細かい'),80),(tr('さらに細かい'),160)]


class Grid:
    def __init__(self):
        self.enabled = True
        self.scenes = {}
        self.spacing = 10.0
        self.params = App.ParamGet('User parameter:BaseApp/Preferences/FluxCAD/Grid')
        self.auto = self.params.GetBool('Auto',True)
        density = self.params.GetInt('Density',80)
        self.density = density if density in [value for _,value in DENSITIES] else 80
        self.manual_spacing = max(0.001,self.params.GetFloat('Spacing',1.0))
        self.plane = App.Placement()
        self.document = None
        self.native_grids = {}
        self.active_sketch = None
        self.move_step = None

    def set_auto(self,value):
        self.auto = bool(value)
        self.params.SetBool('Auto',self.auto)
        self.update()

    def set_spacing(self,value):
        self.manual_spacing = max(0.001,float(value))
        self.params.SetFloat('Spacing',self.manual_spacing)
        self.set_auto(False)

    def set_density(self,value):
        self.density = int(value) if value in [n for _,n in DENSITIES] else 80
        self.params.SetInt('Density',self.density)
        self.update()

    @staticmethod
    def for_view(view,current):
        """Use an origin plane for principal views; retain the plane in orbit.

        A parallel last sketch plane keeps its offset and local grid origin.
        This method is deliberately never used to reorient an edited sketch.
        """
        direction=view.getCameraOrientation().multVec(App.Vector(0,0,1))
        normal=current.Rotation.multVec(App.Vector(0,0,1))
        if abs(normal.dot(direction))>0.9999:
            return App.Placement(current)
        components=tuple(direction);axis=max(range(3),key=lambda i:abs(components[i]))
        if abs(components[axis])<0.9999:
            return App.Placement(current)
        sign=1 if components[axis]>0 else -1
        if axis==0:
            x=App.Vector(0,sign,0);y=App.Vector(0,0,1)
        elif axis==1:
            x=App.Vector(-sign,0,0);y=App.Vector(0,0,1)
        else:
            x=App.Vector(1,0,0);y=App.Vector(0,sign,0)
        return App.Placement(App.Vector(),App.Rotation(x,y,x.cross(y),'ZXY'))

    @staticmethod
    def plane_name(plane):
        normal=plane.Rotation.multVec(App.Vector(0,0,1))
        if abs(normal.z)>0.9999:return tr('XY（上／下面）','XY (Top / Bottom)')
        if abs(normal.y)>0.9999:return tr('XZ（前／後面）','XZ (Front / Rear)')
        if abs(normal.x)>0.9999:return tr('YZ（右／左側面）','YZ (Right / Left)')
        return tr('傾斜したスケッチ面','Inclined sketch plane')

    @staticmethod
    def is_edge_on(view,plane):
        """A grid seen within about six degrees of its plane collapses to lines."""
        normal=plane.Rotation.multVec(App.Vector(0,0,1))
        direction=view.getCameraOrientation().multVec(App.Vector(0,0,1))
        return abs(normal.dot(direction))<0.1

    def hide(self):
        for graph, switch, signature in self.scenes.values():
            switch.whichChild = coin.SO_SWITCH_NONE

    def clear(self):
        for sketch,show,auto,size in self.native_grids.values():
            try:
                sketch.ViewObject.GridSize = size
                sketch.ViewObject.GridAuto = auto
                sketch.ViewObject.ShowGrid = show
            except (ReferenceError,RuntimeError,AttributeError):
                pass  # The document may already have been closed.
        self.native_grids.clear()
        self.active_sketch = None
        for graph, switch, signature in self.scenes.values():
            if graph.findChild(switch) >= 0:
                graph.removeChild(switch)
        self.scenes.clear()

    @contextmanager
    def excluded(self):
        # Remove from the scene during fit, including FreeCAD bounding-box caches.
        detached = []
        for graph, switch, signature in self.scenes.values():
            index = graph.findChild(switch)
            if index >= 0:
                graph.removeChild(switch)
                detached.append((graph,switch,index))
        try:
            yield
        finally:
            for graph,switch,index in detached:
                graph.insertChild(switch,min(index,graph.getNumChildren()))

    @staticmethod
    def lines(points, color, width=1):
        group = coin.SoSeparator()
        material = coin.SoBaseColor()
        material.rgb = color
        group.addChild(material)
        style = coin.SoDrawStyle()
        style.lineWidth = width
        group.addChild(style)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0,len(points),points)
        group.addChild(coords)
        lines = coin.SoLineSet()
        lines.numVertices.setValues(0,len(points)//2,[2]*(len(points)//2))
        group.addChild(lines)
        return group

    def update(self):
        doc = Gui.activeDocument()
        if not doc:
            self.active_sketch = None
            return
        if self.document != doc.Document.Name:
            self.document = doc.Document.Name
            self.plane = App.Placement()
        edit = doc.getInEdit()
        sketch = getattr(edit,'Object',None)
        if sketch and sketch.TypeId == 'Sketcher::SketchObject':
            self.plane = sketch.getGlobalPlacement()
        else:
            sketch = None
        view = doc.activeView()
        if not hasattr(view,'getSceneGraph'):
            return
        if sketch is None:
            self.plane = self.for_view(view,self.plane)
        graph = view.getSceneGraph()
        key = int(graph.this)
        if key not in self.scenes:
            switch = coin.SoSwitch()
            switch.setName('FluxCAD_Grid')
            # The camera and view state must be traversed before the grid.
            graph.addChild(switch)
            self.scenes[key] = (graph,switch,None)
        graph,switch,previous = self.scenes[key]
        camera = view.getCameraNode()
        height = (camera.height.getValue() if hasattr(camera,'height') else
                  2*camera.focalDistance.getValue()*math.tan(camera.heightAngle.getValue()/2))
        desired = max(0.001,abs(height)/self.density)
        power = 10 ** math.floor(math.log10(desired))
        step = next(n*power for n in (1,2,5,10) if n*power >= desired) if self.auto else self.manual_spacing
        # Solid placement uses world XYZ. Show that grid at the chosen snap
        # interval only during Move, retaining the saved sketch grid settings.
        moving = self.move_step is not None and sketch is None
        if moving:
            step = self.move_step
        plane = self.for_view(view,App.Placement()) if moving else self.plane
        self.spacing = step
        if sketch:
            native = sketch.ViewObject
            native_key = (sketch.Document.Name,sketch.Name)
            refresh_snap = (self.active_sketch != native_key or native.GridAuto
                            or abs(native.GridSize.Value-step)>1e-9)
            self.active_sketch = native_key
            if native_key not in self.native_grids:
                self.native_grids[native_key] = (sketch,native.ShowGrid,native.GridAuto,native.GridSize.Value)
            # Keep FreeCAD's snapping engine, but give it exactly the interval
            # drawn by our shared renderer. Never draw two grids over each other.
            if native.ShowGrid:
                native.ShowGrid = False
            if native.GridAuto:
                native.GridAuto = False
            if refresh_snap:
                native.GridSize = step
                # Sketcher's internal snap grid is refreshed when shown. Prime
                # it synchronously, then hide it before the next rendered frame.
                native.ShowGrid = True
                native.ShowGrid = False
        else:
            self.active_sketch = None
        if not self.enabled:
            self.hide()
            return
        position = App.Vector(*camera.position.getValue().getValue())
        target = position + view.getCameraOrientation().multVec(App.Vector(0,0,-camera.focalDistance.getValue()))
        target = plane.inverse().multVec(target)
        cx,cy = round(target.x/step),round(target.y/step)
        extent = min(1000,max(40,math.ceil(abs(height)/step)*2))
        # An attached sketch needs a visible grid on the solid face itself.
        # Offset toward the camera during edit; ordinary grids stay behind.
        facing=plane.Rotation.multVec(App.Vector(0,0,1)).dot(view.getCameraOrientation().multVec(App.Vector(0,0,1)))
        z=(0.002 if facing>=0 else -0.002) if sketch else -0.002
        signature = (step,cx,cy,extent,tuple(plane.Base),tuple(plane.Rotation.Q),z)
        if signature != previous:
            group = coin.SoSeparator()
            pick = coin.SoPickStyle()
            pick.style = coin.SoPickStyle.UNPICKABLE
            group.addChild(pick)
            light = coin.SoLightModel()
            light.model = coin.SoLightModel.BASE_COLOR
            group.addChild(light)
            transform = coin.SoTransform()
            transform.translation.setValue(*plane.Base)
            transform.rotation.setValue(*plane.Rotation.Q)
            group.addChild(transform)
            minor,major = [],[]
            x0,x1 = (cx-extent)*step,(cx+extent)*step
            y0,y1 = (cy-extent)*step,(cy+extent)*step
            for i in range(-extent,extent+1):
                x,y = (cx+i)*step,(cy+i)*step
                (major if (cx+i)%5 == 0 else minor).extend([(x,y0,z),(x,y1,z)])
                (major if (cy+i)%5 == 0 else minor).extend([(x0,y,z),(x1,y,z)])
            group.addChild(self.lines(minor,(0.76,0.78,0.80)))
            group.addChild(self.lines(major,(0.59,0.63,0.67)))
            if y0 <= 0 <= y1:
                group.addChild(self.lines([(x0,0,z),(x1,0,z)],(0.78,0.29,0.26),1.5))
            if x0 <= 0 <= x1:
                group.addChild(self.lines([(0,y0,z),(0,y1,z)],(0.25,0.58,0.36),1.5))
            switch.removeAllChildren()
            switch.addChild(group)
            self.scenes[key] = (graph,switch,signature)
        switch.whichChild = coin.SO_SWITCH_ALL


def show_settings(ws):
    """Apply grid preferences together; Cancel leaves the grid untouched."""
    from PySide import QtWidgets as W
    from grid_input import GridSpacingBox
    dialog = W.QDialog(ws.main)
    dialog.setObjectName('FluxGridSettings')
    dialog.setWindowTitle(tr('グリッド設定'))
    layout = W.QVBoxLayout(dialog)
    auto = W.QCheckBox(tr('グリッド間隔を自動調整'))
    auto.setObjectName('GridAuto')
    auto.setChecked(ws.grid.auto)
    layout.addWidget(auto)
    form = W.QFormLayout()
    density = W.QComboBox()
    density.setObjectName('GridDensity')
    for label,value in DENSITIES:
        density.addItem(label,value)
    density.setCurrentIndex(density.findData(ws.grid.density))
    form.addRow(tr('自動調整の細かさ'),density)
    spacing = GridSpacingBox()
    spacing.setObjectName('GridSpacing')
    spacing.sync(ws.grid.spacing if ws.grid.auto else ws.grid.manual_spacing)
    spacing.chosen.connect(lambda value: auto.setChecked(False))
    form.addRow(tr('固定間隔'),spacing)
    layout.addLayout(form)
    presets = W.QHBoxLayout()
    presets.addWidget(W.QLabel(tr('間隔を固定：')))
    for value in (0.1,0.5,1):
        button = W.QPushButton('%g mm' % value)
        button.setObjectName('GridPreset_%g' % value)
        button.clicked.connect(lambda checked=False,v=value: spacing.choose(v))
        presets.addWidget(button)
    layout.addLayout(presets)
    hint = W.QLabel(tr('通常表示とスケッチ編集で共通です。\nスケッチのスナップも、この間隔に合わせます。'))
    layout.addWidget(hint)
    planes = W.QLabel(tr('通常表示は上／下：XY、前／後：XZ、右／左：YZへ切り替わります。\nスケッチ編集中は、そのスケッチの面に固定します。',
                        'Outside sketch edit: Top/Bottom uses XY, Front/Rear XZ, Right/Left YZ.\nWhile editing, the grid stays on that sketch plane.'))
    planes.setWordWrap(True);layout.addWidget(planes)
    def update_enabled():
        density.setEnabled(auto.isChecked())
    auto.toggled.connect(update_enabled)
    update_enabled()
    buttons = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec_() == W.QDialog.Accepted:
        ws.grid.set_density(density.currentData())
        ws.grid.set_spacing(spacing.value())
        ws.grid.set_auto(auto.isChecked())
        ws.refresh()
    dialog.deleteLater()
