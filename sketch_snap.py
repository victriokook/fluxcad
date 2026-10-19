"""Nearest-grid snapping for native Sketcher drawing tools at any zoom."""
import math
import FreeCAD as App
import FreeCADGui as Gui
import Part
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
        self.geometry_cache = None
        self.last_target = None
        self.clicks = []
        self.creation = None
        App.addDocumentObserver(self)
        self.params = App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher/Snap')
        self.settings = App.ParamGet('User parameter:BaseApp/Preferences/FluxCAD/Sketch')

    def bind(self, widget):
        if widget not in self.widgets:
            widget.installEventFilter(self)
            self.widgets.append(widget)

    def started(self, command):
        self.command = command if command in DRAW_TOOLS else None
        self.geometry_cache = None
        self.last_target = None
        self.clicks = []

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
        App.removeDocumentObserver(self)
        for action, callback in self.actions.items():
            try: action.triggered.disconnect(callback)
            except RuntimeError: pass
        for widget in self.widgets:
            try: widget.removeEventFilter(self)
            except RuntimeError: pass
        self.actions.clear()
        self.widgets.clear()

    def slotChangedObject(self, sketch, prop):
        """Correct new geometry inside Sketcher's own creation transaction.

        Qt/Coin mouse events use integer pixels, and some native arc handlers
        bypass the grid when hovering an edge. Keep the intended model-space
        clicks, rather than round-tripping those pixels back into geometry.
        Existing geometry, constraints and native auto-constraint creation stay
        with Sketcher. Never run on editing, Undo, or recomputing old geometry.
        """
        if prop == 'Geometry': self.geometry_cache = None
        context = self.creation
        if not context or sketch != context[0] or prop != 'Geometry':
            return
        first, command, points, tolerance = context[1:]
        if sketch.GeometryCount <= first or not sketch.Document.HasPendingTransaction:
            return
        self.creation = None  # Reentrant property notifications / solver passes.
        if sketch.GeometryCount != first + 1:
            return
        geometry = list(sketch.Geometry)
        current = geometry[first]
        replacement = None
        def near(a, b):
            return (a - b).Length <= tolerance
        try:
            if command in ('Sketcher_CreateLine', 'Sketcher_CreatePolyline') and len(points) >= 2:
                if current.TypeId != 'Part::GeomLineSegment': return
                a, b = points[-2:]
                if near(current.StartPoint, a) and near(current.EndPoint, b) and (a-b).Length > 1e-7:
                    replacement = Part.LineSegment(a, b)
            elif command == 'Sketcher_Create3PointArc' and len(points) >= 3:
                if current.TypeId != 'Part::GeomArcOfCircle': return
                a, b, through = points[-3:]
                if near(current.StartPoint, b) and near(current.EndPoint, a): a, b = b, a
                if near(current.StartPoint, a) and near(current.EndPoint, b):
                    replacement = Part.ArcOfCircle(a, through, b)
            elif command == 'Sketcher_CreateCircle' and len(points) >= 2:
                if current.TypeId != 'Part::GeomCircle': return
                center, rim = points[-2:]
                radius = (rim-center).Length
                if near(current.Center, center) and abs(current.Radius-radius) <= tolerance and radius > 1e-7:
                    replacement = Part.Circle(center, App.Vector(0, 0, 1), radius)
            elif command == 'Sketcher_CreatePoint' and points:
                if current.TypeId != 'Part::GeomPoint': return
                if near(App.Vector(current.X, current.Y, current.Z), points[-1]):
                    replacement = Part.Point(points[-1])
            if replacement is not None:
                # Preserve native construction/internal geometry flags.
                for extension in current.getExtensions():
                    replacement.setExtension(extension)
                geometry[first] = replacement
                sketch.Geometry = geometry
        except (RuntimeError, ValueError, TypeError, Part.OCCError) as error:
            App.Console.PrintWarning('FluxCAD snap precision: %s\n' % error)

    @staticmethod
    def local_point(view, widget, position, sketch):
        origin, direction = RegionPicker.ray(view, widget, position)
        inverse = sketch.getGlobalPlacement().inverse()
        origin = inverse.multVec(origin)
        direction = inverse.Rotation.multVec(direction)
        if abs(direction.z) < 1e-8:
            return None
        return origin - direction * (origin.z / direction.z)

    def target(self, view, widget, position, sketch, grid_only=False):
        self.last_target = None
        point = self.local_point(view, widget, position, sketch)
        if point is None:
            return None
        step = self.ws.grid.spacing
        target = App.Vector(*(math.floor(v / step + 0.5) * step for v in (point.x, point.y)), 0)
        reference = None
        volume = view.getCameraNode().getViewVolume(widget.width() / max(1, widget.height()))
        def project(local):
            world = sketch.getGlobalPlacement().multVec(local)
            projected = volume.projectToScreen(coin.SbVec3f(*world))
            return QtCore.QPointF(projected[0] * widget.width(), (1 - projected[1]) * widget.height())
        if not grid_only and self.params.GetBool('SnapToObjects', True):
            # Native preselection may lag behind the mouse or disappear during
            # a multi-click tool. Pick from actual sketch geometry instead.
            key = (sketch.Document.Name, sketch.Name, sketch.GeometryCount,
                   sketch.ConstraintCount, sketch.Shape.hashCode())
            if not self.geometry_cache or self.geometry_cache[0] != key:
                points, edges = [], []
                for i, geometry in enumerate(sketch.Geometry):
                    for attr, pos in (('StartPoint', 1), ('EndPoint', 2), ('Center', 3)):
                        if hasattr(geometry, attr):
                            points.append((getattr(geometry, attr), (i, pos)))
                    if geometry.TypeId == 'Part::GeomPoint':
                        points.append((App.Vector(geometry.X, geometry.Y, geometry.Z), (i, 1)))
                    try: edges.append((geometry.toShape(), i))
                    except (RuntimeError, Part.OCCError): pass
                self.geometry_cache = key, points, edges
            def distance(local):
                delta = project(local) - position
                return math.hypot(delta.x(), delta.y())
            vertices = [(distance(p), p, ref) for p, ref in self.geometry_cache[1]]
            nearest = min(vertices, key=lambda item: item[0], default=None)
            if nearest and nearest[0] <= 10:
                _, target, reference = nearest
            else:
                candidates = []
                vertex = Part.Vertex(point)
                for edge, index in self.geometry_cache[2]:
                    if not edge.Edges: continue
                    try:
                        closest = vertex.distToShape(edge)[1][0][1]
                        pixels = distance(closest)
                        if pixels <= 10: candidates.append((pixels, edge, index, closest))
                    except (RuntimeError, Part.OCCError): continue
                if candidates:
                    _, edge, index, closest = min(candidates, key=lambda item: item[0])
                    # Keep the exact grid point when it lies on this edge. A
                    # raw native hover used to disable grid snapping here.
                    if Part.Vertex(target).distToShape(edge)[0] > 1e-7:
                        target = closest
                    reference = (index, 0)
        pixel = project(target)
        # A fixed pixel radius stops working as the user zooms in. Strong mode
        # quantizes the entire grid cell; never forward outside the viewport.
        if not widget.rect().contains(pixel.toPoint()):
            return None
        self.last_target = (App.Vector(target), reference)
        return pixel

    def eventFilter(self, widget, event):
        if not self.enabled or self.forwarding or not self.command:
            return False
        kind = event.type()
        if (kind == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape
                or kind == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.RightButton):
            self.clicks = []
        if kind not in (QtCore.QEvent.MouseMove, QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
            return False
        grid_only = event.modifiers() == QtCore.Qt.ShiftModifier
        if event.modifiers() != QtCore.Qt.NoModifier and not grid_only:
            if kind == QtCore.QEvent.MouseButtonPress: self.clicks = []
            return False  # Preserve native Ctrl angle snapping and navigation.
        if event.buttons() & (QtCore.Qt.MiddleButton | QtCore.Qt.RightButton):
            return False
        if kind != QtCore.QEvent.MouseMove and event.button() != QtCore.Qt.LeftButton:
            return False
        sketch = self.ws.current_sketch()
        if (not sketch or widget.cursor().shape() == QtCore.Qt.ArrowCursor
                or not grid_only and (not self.settings.GetBool('StrongGridSnap', True)
                or not self.params.GetBool('Snap', True)
                or not self.params.GetBool('SnapToGrid', False))):
            self.clicks = []
            return False
        native_state = None
        try:
            self.ws.grid.update()
            position = event.position() if hasattr(event, 'position') else event.pos()
            modifiers = QtCore.Qt.NoModifier if grid_only else event.modifiers()
            if grid_only:
                # Shift is an explicit grid-only override, even with the regular
                # snap checkboxes off. Native object magnets/auto constraints
                # must not pull this click back onto nearby off-grid geometry.
                native_state = (sketch.ViewObject.Autoconstraints,
                                self.params.GetBool('Snap', True),
                                self.params.GetBool('SnapToGrid', False),
                                self.params.GetBool('SnapToObjects', True))
                sketch.ViewObject.Autoconstraints = False
                self.params.SetBool('Snap', True)
                self.params.SetBool('SnapToGrid', True)
                self.params.SetBool('SnapToObjects', False)
            # Let Sketcher update its own preselection at the real cursor before
            # considering a grid magnet. Its edit-mode vertices are not exposed
            # consistently by getObjectInfo(), and stale hover state is unsafe.
            self.forwarding = True
            move = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, position, QtCore.Qt.NoButton,
                                    event.buttons(), modifiers)
            W.QApplication.sendEvent(widget, move)
            self.forwarding = False
            point = self.target(Gui.activeDocument().activeView(), widget,
                                position, sketch, grid_only=grid_only)
            if point is None:
                if kind == QtCore.QEvent.MouseButtonPress: self.clicks = []
                return grid_only  # Shift must never commit an unsnapped fallback.
            if kind == QtCore.QEvent.MouseButtonPress:
                self.clicks.append(self.last_target[0])
                self.clicks = self.clicks[-3:]
            view = Gui.activeDocument().activeView()
            adjacent = self.local_point(view, widget, position + QtCore.QPointF(2, 2), sketch)
            original = self.local_point(view, widget, position, sketch)
            tolerance = max(1e-7, (adjacent-original).Length) if adjacent is not None else 1e-7
            self.creation = (sketch, sketch.GeometryCount, self.command, list(self.clicks), tolerance)
            self.forwarding = True
            # Polyline commits its last move position, not the button event's
            # coordinates. The raw hover update above must not become that point.
            if kind != QtCore.QEvent.MouseMove:
                snapped_move = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, point, QtCore.Qt.NoButton,
                                                event.buttons(), modifiers)
                W.QApplication.sendEvent(widget, snapped_move)
            forwarded = QtGui.QMouseEvent(kind, point, event.button(), event.buttons(), modifiers)
            W.QApplication.sendEvent(widget, forwarded)
            return True
        except (RuntimeError, AttributeError, ValueError):
            return grid_only
        finally:
            self.forwarding = False
            self.creation = None
            if native_state is not None:
                sketch.ViewObject.Autoconstraints = native_state[0]
                for name, value in zip(('Snap', 'SnapToGrid', 'SnapToObjects'), native_state[1:]):
                    self.params.SetBool(name, value)
