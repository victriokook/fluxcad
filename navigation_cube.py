"""Drag the native view cube to orbit; short clicks retain FreeCAD's controls."""
import itertools
import math
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui
try:
    from PySide import QtWidgets as W
except ImportError:
    W = QtGui


class CubeNavigation(QtCore.QObject):
    def __init__(self, ws):
        super().__init__(ws.main)
        self.ws = ws
        self.params = App.ParamGet('User parameter:BaseApp/Preferences/NaviCube')
        self.widgets = set()
        self.forwarding = False
        self.enabled = True
        self.owner = None
        self.dragging = False
        self.suppress_release = False
        ws.main.installEventFilter(self)

    def bind(self, widget):
        # Last installed: navigation must precede profile selection and move tools.
        self.widgets.add(widget)
        widget.installEventFilter(self)

    def layout(self, widget):
        """Native 1.1 cube coordinates, expressed in Qt logical pixels."""
        ratio = widget.devicePixelRatioF()
        size = max(1, self.params.GetInt('CubeSize', 132))
        x = min(int(self.params.GetInt('OffsetX', 0) + size * ratio * .55) / ratio,
                widget.width() / 2)
        y = min(int(self.params.GetInt('OffsetY', 0) + size * ratio * .55) / ratio,
                widget.height() / 2)
        corner = self.params.GetInt('CornerNaviCube', 1)
        return QtCore.QPointF(x if corner in (0, 2) else widget.width() - x,
                             y if corner in (0, 1) else widget.height() - y), size

    def hit(self, view, widget, point):
        if not view.getViewer().isEnabledNaviCube():
            return None
        center, size = self.layout(widget)
        if not QtCore.QRectF(center.x()-size/2, center.y()-size/2, size, size).contains(point):
            return None
        # Project a beveled cube and use its convex silhouette. The surrounding
        # arrow buttons keep their native click/drag behavior.
        rotation = view.getCameraOrientation().inverted()
        chamfer = max(.05, min(.18, self.params.GetFloat('ChamferSize', .12)))
        points = []
        perspective = not hasattr(view.getCameraNode(), 'height')
        for axis in range(3):
            for signs in itertools.product((-1, 1), repeat=3):
                v = rotation.multVec(App.Vector(*[s*(1 if i == axis else 1-chamfer)
                                                  for i, s in enumerate(signs)]))
                half = (5.1-v.z)*math.tan(math.pi/8)*1.1 if perspective else 2.1
                points.append((center.x()+v.x*size/(2*half), center.y()-v.y*size/(2*half)))
        points = sorted(set(points))
        def cross(a, b, c):
            return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        halves = []
        for sequence in (points, reversed(points)):
            half = []
            for p in sequence:
                while len(half) > 1 and cross(half[-2], half[-1], p) <= 0:
                    half.pop()
                half.append(p)
            halves.extend(half[:-1])
        polygon = QtGui.QPolygonF([QtCore.QPointF(*p) for p in halves])
        return 'cube' if polygon.containsPoint(point, QtCore.Qt.OddEvenFill) else 'controls'

    def forward(self, widget, kind, point, button, buttons, modifiers):
        # Forward native controls, never the release of an orbit (which would
        # snap to a face). Modeling filters bypass this guarded dispatch.
        event = QtGui.QMouseEvent(kind, point, QtCore.QPointF(widget.mapToGlobal(point.toPoint())),
                                 button, buttons, modifiers)
        self.forwarding = True
        try:
            W.QApplication.sendEvent(widget, event)
        finally:
            self.forwarding = False

    def cancel(self):
        owner, dragging = self.owner, self.dragging
        self.owner = None
        self.dragging = False
        if owner is not None:
            self.suppress_release = True
            try:
                if dragging:
                    owner.setCursor(self.cursor)
                    if W.QWidget.mouseGrabber() == owner:
                        owner.releaseMouse()
            except RuntimeError:
                pass  # The document's viewport was destroyed.

    def close(self):
        self.enabled = False
        self.cancel()
        for widget in list(self.widgets) + [self.ws.main]:
            try:
                widget.removeEventFilter(self)
            except RuntimeError:
                pass
        self.widgets.clear()

    def eventFilter(self, widget, event):
        if not self.enabled or self.forwarding:
            return False
        kind = event.type()
        if kind in (QtCore.QEvent.Hide, QtCore.QEvent.WindowDeactivate, QtCore.QEvent.UngrabMouse):
            if widget == self.owner or widget == self.ws.main:
                self.cancel()
            return False
        if self.owner is not None and kind in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
            if event.key() == QtCore.Qt.Key_Escape:
                if kind == QtCore.QEvent.KeyPress:
                    self.cancel()
                event.accept()
                return True
        if widget not in self.widgets:
            return False
        mouse_events = (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease,
                        QtCore.QEvent.MouseButtonDblClick, QtCore.QEvent.MouseMove)
        if kind not in mouse_events:
            return False
        if not Gui.activeDocument():
            self.cancel()
            return False
        view = Gui.activeDocument().activeView()
        if not hasattr(view, 'getCameraNode'):
            self.cancel()
            return False
        if self.owner is not None and view.graphicsView() != self.graphics:
            self.cancel()
        if kind == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton and self.suppress_release:
            self.suppress_release = False
            return True
        point = QtCore.QPointF(self.ws.mouse.position(event))
        if kind in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonDblClick):
            if event.button() != QtCore.Qt.LeftButton:
                return self.owner is not None
            self.suppress_release = False
            hit = self.hit(view, widget, point)
            if hit is None:
                return False
            self.ws.region_picker.ticket += 1
            self.ws.region_picker.press = None
            if hit == 'controls':
                self.forward(widget, kind, point, event.button(), event.buttons(), event.modifiers())
                return True
            self.owner = widget
            self.graphics = view.graphicsView()
            self.start = self.last = point
            self.modifiers = event.modifiers()
            self.pivot = self.ws.mouse.center(view)
            return True
        if self.owner == widget:
            if kind == QtCore.QEvent.MouseMove:
                if not event.buttons() & QtCore.Qt.LeftButton:
                    self.cancel()
                    return True
                if not self.dragging:
                    if (point-self.start).manhattanLength() < W.QApplication.startDragDistance():
                        return True
                    self.dragging = True
                    self.cursor = widget.cursor()
                    widget.setCursor(QtCore.Qt.ClosedHandCursor)
                    widget.grabMouse()
                self.ws.mouse.orbit(view, self.pivot, point.x()-self.last.x(), point.y()-self.last.y())
                self.last = point
                self.ws.grid.update()
                return True
            if kind == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                if not self.dragging:
                    self.forward(widget, QtCore.QEvent.MouseButtonPress, self.start, QtCore.Qt.LeftButton,
                                 QtCore.Qt.LeftButton, self.modifiers)
                    self.forward(widget, kind, point, event.button(), event.buttons(), event.modifiers())
                self.cancel()
                self.suppress_release = False
                return True
        if self.hit(view, widget, point) is not None:
            if kind == QtCore.QEvent.MouseMove or event.button() == QtCore.Qt.LeftButton:
                self.forward(widget, kind, point, event.button(), event.buttons(), event.modifiers())
                return True
        return False
