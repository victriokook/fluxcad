"""A wider screen-space grid magnet for native Sketcher drawing tools."""
import math
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets as W
from pivy import coin
from region_picker import RegionPicker


DRAW_TOOLS = {
    'Sketcher_CreatePoint', 'Sketcher_CreateLine', 'Sketcher_CreatePolyline',
    'Sketcher_CreateRectangle', 'Sketcher_CreateRectangle_Center',
    'Sketcher_CreateOblong', 'Sketcher_CreateRegularPolygon',
    'Sketcher_CreateCircle', 'Sketcher_Create3PointCircle',
    'Sketcher_CreateArc', 'Sketcher_Create3PointArc',
    'Sketcher_CreateEllipseByCenter', 'Sketcher_CreateSlot', 'Sketcher_CreateArcSlot',
    'Sketcher_CreateBSpline', 'Sketcher_CreateBSplineByInterpolation',
}


class SketchSnap(QtCore.QObject):
    def __init__(self, workspace):
        super().__init__(workspace.main)
        self.ws = workspace
        self.command = None
        self.forwarding = False
        self.enabled = True
        self.widgets = []
        self.actions = {}
        self.params = App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher/Snap')
        self.settings = App.ParamGet('User parameter:BaseApp/Preferences/FluxCAD/Sketch')

    def bind(self, widget):
        if widget not in self.widgets:
            widget.installEventFilter(self)
            self.widgets.append(widget)

    def started(self, command):
        self.command = command if command in DRAW_TOOLS else None

    def refresh(self):
        if not self.ws.current_sketch():
            self.command = None
        # Native menu/shortcut actions can start or stop tools too.
        for action in self.ws.main.findChildren(QtGui.QAction):
            name = action.objectName()
            if name.startswith('Sketcher_') and action not in self.actions:
                callback = lambda checked=False, n=name: self.started(n)
                action.triggered.connect(callback)
                self.actions[action] = callback

    def close(self):
        self.enabled = False
        for action, callback in self.actions.items():
            try: action.triggered.disconnect(callback)
            except RuntimeError: pass
        for widget in self.widgets:
            try: widget.removeEventFilter(self)
            except RuntimeError: pass
        self.actions.clear()
        self.widgets.clear()

    @staticmethod
    def local_point(view, widget, position, sketch):
        origin, direction = RegionPicker.ray(view, widget, position)
        inverse = sketch.getGlobalPlacement().inverse()
        origin = inverse.multVec(origin)
        direction = inverse.Rotation.multVec(direction)
        if abs(direction.z) < 1e-8:
            return None
        return origin - direction * (origin.z / direction.z)

    def target(self, view, widget, position, sketch):
        point = self.local_point(view, widget, position, sketch)
        if point is None:
            return None
        step = self.ws.grid.spacing
        target = App.Vector(*(math.floor(v / step + 0.5) * step for v in (point.x, point.y)), 0)
        world = sketch.getGlobalPlacement().multVec(target)
        volume = view.getCameraNode().getViewVolume(widget.width() / max(1, widget.height()))
        projected = volume.projectToScreen(coin.SbVec3f(*world))
        pixel = QtCore.QPointF(projected[0] * widget.width(), (1 - projected[1]) * widget.height())
        # In a dense grid this covers the whole cell. At high magnification it
        # remains a local magnet rather than pulling the cursor across the view.
        if max(abs(pixel.x() - position.x()), abs(pixel.y() - position.y())) > 12:
            return None
        if self.params.GetBool('SnapToObjects', True):
            preselection = Gui.Selection.getPreselection()
            if (preselection and preselection.DocumentName == sketch.Document.Name
                    and preselection.ObjectName == sketch.Name and preselection.SubElementNames):
                return None
        return pixel

    def eventFilter(self, widget, event):
        if not self.enabled or self.forwarding or not self.command:
            return False
        kind = event.type()
        if kind not in (QtCore.QEvent.MouseMove, QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
            return False
        if event.modifiers() != QtCore.Qt.NoModifier:
            return False  # Preserve native Ctrl angle snapping and navigation.
        if event.buttons() & (QtCore.Qt.MiddleButton | QtCore.Qt.RightButton):
            return False
        if kind != QtCore.QEvent.MouseMove and event.button() != QtCore.Qt.LeftButton:
            return False
        sketch = self.ws.current_sketch()
        if (not sketch or widget.cursor().shape() == QtCore.Qt.ArrowCursor
                or not self.settings.GetBool('StrongGridSnap', True)
                or not self.params.GetBool('Snap', True)
                or not self.params.GetBool('SnapToGrid', False)):
            return False
        try:
            self.ws.grid.update()
            position = event.position() if hasattr(event, 'position') else event.pos()
            # Let Sketcher update its own preselection at the real cursor before
            # considering a grid magnet. Its edit-mode vertices are not exposed
            # consistently by getObjectInfo(), and stale hover state is unsafe.
            self.forwarding = True
            move = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, position, QtCore.Qt.NoButton,
                                    event.buttons(), event.modifiers())
            W.QApplication.sendEvent(widget, move)
            self.forwarding = False
            point = self.target(Gui.activeDocument().activeView(), widget,
                                position, sketch)
            if point is None:
                return False
            self.forwarding = True
            forwarded = QtGui.QMouseEvent(kind, point, event.button(), event.buttons(), event.modifiers())
            W.QApplication.sendEvent(widget, forwarded)
            return True
        except (RuntimeError, AttributeError, ValueError):
            return False
        finally:
            self.forwarding = False
