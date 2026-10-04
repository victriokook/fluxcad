"""Movable, collapsible modeling panel with viewport-relative placement."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from i18n import tr
from extrude_panel import ExtrudePanel


class FloatingPanel(ExtrudePanel):
    layout_key = 'FloatingPanel'

    def __init__(self, ws):
        super().__init__(ws)
        self.status.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Minimum)
        self.layout_params = App.ParamGet('User parameter:BaseApp/Preferences/FluxCAD/'+self.layout_key)
        self.custom_position = self.layout_params.GetBool('Positioned',False)
        self.offset = QtCore.QPoint(self.layout_params.GetInt('X',0),self.layout_params.GetInt('Y',0))
        self.collapsed = self.layout_params.GetBool('Collapsed',False)
        self.drag_start = None
        self.dragging = False
        self.drag_owner = None
        self.scroll = self.panel.findChild(W.QScrollArea)
        layout = self.panel.layout()
        self.expanded_margins = layout.contentsMargins()
        self.expanded_spacing = layout.spacing()
        layout.setSizeConstraint(W.QLayout.SetNoConstraint)
        layout.removeWidget(self.heading)
        self.header = W.QFrame(self.panel)
        self.header.setFixedHeight(28)
        self.header.setStyleSheet('background:#eeeeee;border:0;')
        row = W.QHBoxLayout(self.header); row.setContentsMargins(2,0,4,0); row.setSpacing(4)
        self.fold_button = W.QToolButton(self.header)
        self.fold_button.setFixedSize(22,24)
        self.fold_button.clicked.connect(self.toggle_panel)
        row.addWidget(self.fold_button); row.addWidget(self.heading,1)
        layout.insertWidget(0,self.header)
        for widget in (self.header,self.heading):
            widget.setCursor(QtCore.Qt.OpenHandCursor)
            widget.setMouseTracking(True)
            widget.setToolTip(tr('ドラッグで移動／クリックで折りたたみ\n右クリックで右側の初期位置に戻せます。',
                                 'Drag to move / click to collapse\nRight-click to restore the default position on the right.'))
            widget.installEventFilter(self)
            widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            widget.customContextMenuRequested.connect(lambda point,w=widget:self.header_menu(w,point))
        self.fold_button.installEventFilter(self)
        self.panel.installEventFilter(self)

    def viewport_rect(self):
        gd = Gui.activeDocument()
        if not gd:return None
        view = gd.activeView()
        if not hasattr(view,'graphicsView'):return None
        viewport = view.graphicsView().viewport()
        return QtCore.QRect(viewport.mapTo(self.ws.main,QtCore.QPoint()),viewport.size())

    def movement_rect(self):
        viewport = self.viewport_rect()
        if viewport is None:return None
        # Main-window overlays can reach the left edge even with a native dock.
        area = self.ws.main.contentsRect()
        return QtCore.QRect(area.x(),viewport.y(),area.width(),viewport.height())

    def position(self):
        if not self.active or self.closed or not hasattr(self,'header'):return
        area = self.movement_rect()
        if area is None or area.width()<1 or area.height()<32:return
        compact = self.collapsed or area.height()<150
        self.scroll.setVisible(not compact)
        self.accept_button.setVisible(not compact); self.cancel_button.setVisible(not compact)
        self.fold_button.setArrowType(QtCore.Qt.RightArrow if compact else QtCore.Qt.DownArrow)
        self.fold_button.setToolTip(tr('展開する','Expand') if compact else tr('折りたたむ','Collapse'))
        layout = self.panel.layout()
        layout.setContentsMargins(QtCore.QMargins(6,2,6,2) if compact else self.expanded_margins)
        layout.setSpacing(0 if compact else self.expanded_spacing)
        width = min(310,area.width())
        height = 32 if compact else min(self.preferred_height,area.height())
        if self.custom_position:
            preferred = area.topLeft()+self.offset
        else:
            viewport = self.viewport_rect()
            preferred = QtCore.QPoint(viewport.right()-width-11,
                                      viewport.top()+min(110,max(8,viewport.height()//6)))
        x = max(area.left(),min(preferred.x(),area.right()-width+1))
        y = max(area.top(),min(preferred.y(),area.bottom()-height+1))
        self.panel.setGeometry(x,y,width,height)
        self.panel.raise_()

    def toggle_panel(self):
        self.finish_drag()
        self.collapsed = not self.collapsed
        self.layout_params.SetBool('Collapsed',self.collapsed)
        self.position()

    def finish_drag(self):
        dragged,owner = self.dragging,self.drag_owner
        self.drag_start = self.drag_owner = None
        self.dragging = False
        if owner is not None:
            try:
                owner.setCursor(QtCore.Qt.OpenHandCursor)
                if W.QWidget.mouseGrabber()==owner:owner.releaseMouse()
            except RuntimeError:pass
        if dragged:
            area = self.movement_rect()
            if area is not None:
                self.offset = self.panel.pos()-area.topLeft()
                self.layout_params.SetBool('Positioned',True)
                self.layout_params.SetInt('X',self.offset.x())
                self.layout_params.SetInt('Y',self.offset.y())
        return dragged

    def reset_position(self):
        self.finish_drag()
        self.custom_position = False
        self.offset = QtCore.QPoint()
        self.layout_params.SetBool('Positioned',False)
        self.position()

    def header_menu(self,widget,point):
        self.finish_drag()
        menu = W.QMenu(widget)
        reset = menu.addAction(tr('右側の初期位置に戻す','Restore Default Position on Right'))
        if menu.exec_(widget.mapToGlobal(point))==reset:self.reset_position()

    def cancel(self):
        if hasattr(self,'header'):self.finish_drag()
        super().cancel()

    def ray(self, widget, point):
        view = Gui.activeDocument().activeView(); node = view.getCameraNode()
        rotation = view.getCameraOrientation(); height = self.ws.mouse.camera_height(node)
        offset = rotation.multVec(App.Vector((point.x()-widget.width()/2)*height/widget.height(),
                                             (widget.height()/2-point.y())*height/widget.height(),0))
        origin = App.Vector(*node.position.getValue().getValue())
        direction = rotation.multVec(App.Vector(0,0,-1))
        if hasattr(node,'height'):origin += offset
        else:direction = direction*node.focalDistance.getValue()+offset;direction.normalize()
        return origin,direction

    def eventFilter(self,widget,event):
        if getattr(getattr(self.ws,'cube',None),'forwarding',False):return False
        if hasattr(self,'header'):
            kind=event.type()
            if kind in (QtCore.QEvent.Hide,QtCore.QEvent.WindowDeactivate,QtCore.QEvent.UngrabMouse):
                if widget in (self.panel,self.ws.main,self.drag_owner):self.finish_drag()
            if self.active and widget in (self.header,self.heading):
                if kind==QtCore.QEvent.MouseButtonPress and event.button()==QtCore.Qt.LeftButton:
                    self.drag_start=event.globalPosition().toPoint()
                    self.drag_panel_start=self.panel.pos()
                    self.drag_owner=widget;self.dragging=False
                    widget.grabMouse()
                    return True
                if kind==QtCore.QEvent.MouseMove and self.drag_start is not None:
                    if not event.buttons() & QtCore.Qt.LeftButton:
                        self.finish_drag();return True
                    delta=event.globalPosition().toPoint()-self.drag_start
                    if self.dragging or delta.manhattanLength()>=W.QApplication.startDragDistance():
                        area=self.movement_rect()
                        if area is not None:
                            self.dragging=True;self.custom_position=True
                            widget.setCursor(QtCore.Qt.ClosedHandCursor)
                            self.offset=self.drag_panel_start+delta-area.topLeft()
                            self.position()
                    return True
                if kind==QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.LeftButton:
                    pressed=self.drag_start is not None
                    if not self.finish_drag() and pressed:self.toggle_panel()
                    return True
        return super().eventFilter(widget,event)
