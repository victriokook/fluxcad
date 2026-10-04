"""Viewport dragging of selected solids, one native undo transaction per drag."""
from i18n import tr
import math
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets as W
import model


class DragMove(QtCore.QObject):
    def __init__(self, ws):
        super().__init__(ws.main)
        self.ws = ws
        self.active = False
        self.dragging = False
        self.transaction = False
        self.owner = None
        self.widgets = []
        self.targets = []
        self.doc = None
        self.axis = None
        self.params = App.ParamGet('User parameter:BaseApp/Preferences/FluxCAD/Move')
        self.panel = W.QFrame(ws.main)
        self.panel.setObjectName('FluxDragMove')
        self.panel.setStyleSheet('QFrame#FluxDragMove {background:#f3f7fa;border:1px solid #94b9cc;border-radius:4px;}')
        layout = W.QVBoxLayout(self.panel)
        layout.setContentsMargins(12,8,12,8)
        layout.setSpacing(5)
        self.title = W.QLabel()
        layout.addWidget(self.title)
        row = W.QHBoxLayout()
        self.axes = W.QButtonGroup(self.panel)
        self.axes.setExclusive(True)
        for text,axis in [(tr('画面に沿う'),None),('X','X'),('Y','Y'),('Z','Z')]:
            button = W.QPushButton(text)
            button.setCheckable(True)
            button.setChecked(axis is None)
            button.clicked.connect(lambda checked=False,a=axis:self.set_axis(a))
            self.axes.addButton(button)
            row.addWidget(button)
        finish = W.QPushButton(tr('終了 (Esc)'))
        finish.clicked.connect(lambda:self.stop())
        row.addWidget(finish)
        layout.addLayout(row)
        row = W.QHBoxLayout()
        self.coordinate_mode = W.QComboBox()
        self.coordinate_mode.addItems([tr('配置先の座標'), tr('現在位置からの移動量')])
        self.coordinate_mode.currentIndexChanged.connect(self.sync_fields)
        row.addWidget(self.coordinate_mode)
        self.coordinates = []
        for axis in 'XYZ':
            row.addWidget(W.QLabel(axis))
            field = W.QDoubleSpinBox()
            field.setObjectName('FluxMove'+axis)
            field.setDecimals(6)
            field.setRange(-1e9,1e9)
            field.setSuffix(' mm')
            field.setKeyboardTracking(False)
            field.setMinimumWidth(115)
            field.installEventFilter(self)
            field.lineEdit().installEventFilter(self)
            self.coordinates.append(field)
            row.addWidget(field)
        self.apply_button = W.QPushButton(tr('数値を適用'))
        self.apply_button.clicked.connect(self.apply_numbers)
        row.addWidget(self.apply_button)
        layout.addLayout(row)
        row = W.QHBoxLayout()
        self.snap = W.QCheckBox(tr('グリッドにスナップ'))
        self.snap.setChecked(self.params.GetBool('Snap',True))
        self.snap_step = W.QDoubleSpinBox()
        self.snap_step.setDecimals(3)
        self.snap_step.setRange(0.001,1000)
        self.snap_step.setSuffix(' mm')
        self.snap_step.setValue(self.params.GetFloat('Step',1.0))
        self.snap.toggled.connect(self.snap_changed)
        self.snap_step.valueChanged.connect(self.snap_changed)
        row.addWidget(self.snap)
        row.addWidget(self.snap_step)
        row.addWidget(W.QLabel(tr('数値入力はスナップせず、入力どおりに配置')))
        row.addStretch()
        layout.addLayout(row)
        self.reference = W.QLabel()
        layout.addWidget(self.reference)
        self.readout = W.QLabel(tr('左ドラッグで移動 → ボタンを離すと確定'))
        layout.addWidget(self.readout)
        self.panel.hide()
        ws.main.installEventFilter(self)

    def bind(self, widget):
        if widget not in self.widgets:
            widget.installEventFilter(self)
            self.widgets.append(widget)

    def sync_fields(self, *args):
        if not self.active:
            return
        origin = self.targets[0].getGlobalPlacement().Base
        values = origin if self.coordinate_mode.currentIndex()==0 else App.Vector()
        for field,value in zip(self.coordinates,values):
            field.setValue(value)
        self.reference.setText(tr('基準：%s の配置原点  |  全体のX・Y・Z軸') % self.targets[0].Label)
        self.last_positions = tuple(str(obj.getGlobalPlacement()) for obj in self.targets)

    def apply_numbers(self):
        if not self.active or self.dragging:
            return
        try:
            self.refresh()
            if not self.active:
                return
            for field in self.coordinates:
                field.interpretText()
            delta = App.Vector(*(field.value() for field in self.coordinates))
            if self.coordinate_mode.currentIndex()==0:
                delta -= self.targets[0].getGlobalPlacement().Base
            model.move_solids(self.doc,self.targets,*delta,allow_mesh=True)
            self.sync_fields()
            self.readout.setText(tr('数値を適用しました  |  Ctrl＋Zで元に戻す'))
        except Exception as error:
            W.QMessageBox.warning(self.ws.main,tr('移動'),str(error))

    def snap_changed(self, *args):
        self.params.SetBool('Snap',self.snap.isChecked())
        self.params.SetFloat('Step',self.snap_step.value())
        for field in self.coordinates:
            field.setSingleStep(self.snap_step.value())
        self.ws.grid.move_step = self.snap_step.value() if self.active and self.snap.isChecked() else None
        self.ws.grid.update()

    def snapped_delta(self, delta):
        if not self.snap.isChecked():
            return delta
        step = self.snap_step.value()
        result = []
        for index,(start,amount) in enumerate(zip(self.anchor,delta)):
            moving = ('XYZ'[index]==self.axis if self.axis else
                      abs(tuple(self.right)[index])+abs(tuple(self.up)[index])>1e-9)
            if moving:
                coordinate = (start+amount)/step
                # Symmetric rounding also gives predictable negative half steps.
                snapped = math.copysign(math.floor(abs(coordinate)+0.5),coordinate)*step
                amount = snapped-start
            result.append(amount)
        return App.Vector(*result)

    def set_axis(self, axis):
        if self.dragging:
            return
        self.axis = axis
        for button in self.axes.buttons():
            button.setChecked(button.text()==(axis or tr('画面に沿う')))
        from i18n import language
        direction=tr('画面に沿って') if axis is None else axis+tr('方向に')
        self.readout.setText(tr('左ドラッグで移動')+' — '+direction.strip() if language()=='en' else direction+tr('左ドラッグで移動'))

    def start(self):
        if self.active:
            self.stop()
            return
        gd = Gui.activeDocument()
        if gd and gd.getInEdit():
            raise ValueError(tr('先にスケッチ編集を閉じてください。'))
        self.doc = App.ActiveDocument
        self.targets = model.movable_solids(self.doc,Gui.Selection.getSelection(),allow_mesh=True)
        self.ws.region_picker.ticket += 1
        self.ws.region_picker.press = None
        self.ws.region_picker.clear()
        self.ws.mouse.cancel()
        Gui.Selection.clearSelection()
        for obj in self.targets:
            Gui.Selection.addSelection(obj)
        self.active = True
        self.sync_fields()
        self.snap_changed()
        self.ws.ribbon_actions['move'].setChecked(True)
        self.set_axis(None)
        self.title.setText(tr('移動 — %d個の形状  |  ドラッグ中はEscで取り消し','Move — %d objects | Esc to cancel dragging') % len(self.targets))
        self.panel.show()
        self.position_panel()
        live = []
        for widget in self.widgets:
            try:
                if widget.isVisible():
                    widget.setCursor(QtCore.Qt.OpenHandCursor)
                live.append(widget)
            except RuntimeError:
                pass  # A document/view may have been closed since binding.
        self.widgets = live
        self.ws.main.statusBar().showMessage(tr('移動：左ドラッグ。X / Y / Zで方向固定、Vで画面に沿う。離すと確定、Escで終了。'),15000)

    def position_panel(self):
        viewer = next((w for w in self.ws.main.findChildren(W.QWidget)
                       if w.metaObject().className()=='Gui::View3DInventorViewer' and w.isVisible()),None)
        if viewer and self.active:
            viewport = viewer.viewport()
            origin = viewport.mapTo(self.ws.main,QtCore.QPoint(0,0))
            self.panel.adjustSize()
            self.panel.move(origin.x()+max(8,(viewport.width()-self.panel.width())//2),origin.y()+12)
            self.panel.raise_()

    def refresh(self):
        if not self.active:
            return
        try:
            gd = Gui.activeDocument()
            if (App.ActiveDocument!=self.doc or not gd or gd.getInEdit() or
                    any(not obj.Document or not obj.Visibility for obj in self.targets)):
                self.stop()
                return
            selected = Gui.Selection.getSelection()
            if not self.dragging and selected != self.targets:
                self.stop()
                return
            if not self.dragging and tuple(str(obj.getGlobalPlacement()) for obj in self.targets)!=self.last_positions:
                self.sync_fields()
            self.position_panel()
        except (RuntimeError,ReferenceError):
            self.stop()

    def begin_drag(self, widget, point):
        self.owner = widget
        self.press = QtCore.QPointF(point)
        self.delta = App.Vector()
        self.originals = [(obj,App.Placement(obj.Placement)) for obj in self.targets]
        self.anchor = App.Vector(self.targets[0].getGlobalPlacement().Base)
        self.parents = [obj.getGlobalPlacement().multiply(placement.inverse()).Rotation.inverted()
                        for obj,placement in self.originals]
        view = Gui.activeDocument().activeView()
        node = view.getCameraNode()
        rotation = view.getCameraOrientation()
        self.right = rotation.multVec(App.Vector(1,0,0))
        self.up = rotation.multVec(App.Vector(0,1,0))
        position = App.Vector(*node.position.getValue().getValue())
        centers = []
        for obj,placement in self.originals:
            parent = obj.getGlobalPlacement().multiply(placement.inverse())
            geometry=obj.Mesh if hasattr(obj,'Mesh') else obj.Shape
            centers.append(parent.multVec(geometry.BoundBox.Center))
        center = sum(centers,App.Vector())/len(centers)
        if hasattr(node,'height'):
            height = node.height.getValue()
        else:
            depth = max(1e-6,(center-position).dot(rotation.multVec(App.Vector(0,0,-1))))
            height = 2*depth*math.tan(node.heightAngle.getValue()/2)
        self.scale = height/max(1,widget.height())
        self.dragging = True
        widget.setFocus(QtCore.Qt.MouseFocusReason)
        widget.setCursor(QtCore.Qt.ClosedHandCursor)
        widget.grabMouse()

    def update_drag(self, point):
        dx,dy = point.x()-self.press.x(),point.y()-self.press.y()
        if not self.transaction and abs(dx)+abs(dy)<W.QApplication.startDragDistance():
            return
        if self.axis:
            axis = {'X':App.Vector(1,0,0),'Y':App.Vector(0,1,0),'Z':App.Vector(0,0,1)}[self.axis]
            sx,sy = axis.dot(self.right),-axis.dot(self.up)
            length2 = sx*sx+sy*sy
            # An axis viewed end-on has no screen direction; vertical movement
            # provides a usable depth control without an unstable huge factor.
            distance = ((dx*sx+dy*sy)/length2 if length2>=0.02 else -dy)*self.scale
            self.delta = axis*distance
        else:
            self.delta = (self.right*dx-self.up*dy)*self.scale
        self.delta = self.snapped_delta(self.delta)
        if not self.transaction and self.delta.Length<1e-12:
            return
        if not self.transaction:
            self.doc.openTransaction(tr('立体をドラッグ移動'))
            self.transaction = True
        for (obj,original),parent in zip(self.originals,self.parents):
            placement = App.Placement(original)
            placement.Base += parent.multVec(self.delta)
            obj.Placement = placement
        self.doc.recompute()
        self.sync_fields()
        self.readout.setText(tr('X %.3f   Y %.3f   Z %.3f mm  |  離すと確定') % tuple(self.delta))

    def end_drag(self, cancel=False):
        if not self.dragging:
            return
        owner = self.owner
        self.dragging = False
        self.owner = None
        try:
            if self.transaction and self.doc in App.listDocuments().values():
                try:
                    if cancel or self.delta.Length<1e-12:
                        self.doc.abortTransaction()
                    else:
                        self.doc.recompute()
                        self.doc.commitTransaction()
                    self.doc.recompute()
                except Exception:
                    self.doc.abortTransaction()
                    raise
        finally:
            self.transaction = False
            if owner:
                try:
                    owner.releaseMouse()
                    owner.setCursor(QtCore.Qt.OpenHandCursor)
                except RuntimeError:
                    pass  # Closing a document also destroys its viewport.
        self.readout.setText(tr('取り消しました') if cancel else tr('X %.3f   Y %.3f   Z %.3f mm  |  確定済み') % tuple(self.delta))
        if self.active:
            self.sync_fields()

    def stop(self):
        self.active = False
        self.end_drag(cancel=True)
        self.ws.grid.move_step = None
        self.ws.grid.update()
        self.panel.hide()
        self.targets = []
        self.doc = None
        if 'move' in self.ws.ribbon_actions:
            self.ws.ribbon_actions['move'].setChecked(False)
        for widget in self.widgets:
            try: widget.unsetCursor()
            except RuntimeError: pass

    def close(self):
        self.stop()
        self.ws.main.removeEventFilter(self)
        for widget in self.widgets:
            try: widget.removeEventFilter(self)
            except RuntimeError: pass
        self.widgets.clear()
        self.panel.deleteLater()

    def eventFilter(self, widget, event):
        if getattr(getattr(self.ws,'cube',None),'forwarding',False):
            return False
        if not self.active:
            return False
        kind = event.type()
        try:
            if kind in (QtCore.QEvent.Close,QtCore.QEvent.Hide,QtCore.QEvent.WindowDeactivate):
                if widget==self.ws.main or widget==self.owner:
                    self.stop()
                return False
            if kind==QtCore.QEvent.Resize:
                QtCore.QTimer.singleShot(0,self.position_panel)
            if kind==QtCore.QEvent.ShortcutOverride:
                if self.dragging or event.key() in (QtCore.Qt.Key_Escape,QtCore.Qt.Key_X,QtCore.Qt.Key_Y,QtCore.Qt.Key_Z,QtCore.Qt.Key_V):
                    if self.dragging or event.modifiers()==QtCore.Qt.NoModifier:
                        event.accept()
                        return True
            if kind==QtCore.QEvent.KeyPress:
                if widget in self.coordinates or any(widget==field.lineEdit() for field in self.coordinates):
                    if event.key() in (QtCore.Qt.Key_Return,QtCore.Qt.Key_Enter):
                        self.apply_numbers()
                        return True
                    if event.key()!=QtCore.Qt.Key_Escape:
                        return False
                if event.key()==QtCore.Qt.Key_Escape:
                    self.stop()
                    return True
                if not self.dragging and event.modifiers()==QtCore.Qt.NoModifier:
                    keys = {QtCore.Qt.Key_X:'X',QtCore.Qt.Key_Y:'Y',QtCore.Qt.Key_Z:'Z',QtCore.Qt.Key_V:None}
                    if event.key() in keys:
                        self.set_axis(keys[event.key()])
                        return True
                if self.dragging:
                    return True
            if widget not in self.widgets:
                return False
            point = event.position() if hasattr(event,'position') else None
            if kind==QtCore.QEvent.MouseButtonPress and event.button()==QtCore.Qt.LeftButton:
                if event.modifiers()==QtCore.Qt.NoModifier:
                    self.refresh()
                    if not self.active:
                        return False
                    self.begin_drag(widget,point)
                    return True
            if kind==QtCore.QEvent.MouseMove and self.dragging and widget==self.owner:
                if event.buttons() & QtCore.Qt.LeftButton:
                    self.update_drag(point)
                else:
                    self.end_drag(cancel=True)
                return True
            if kind==QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.LeftButton and self.dragging:
                self.update_drag(point)
                self.end_drag()
                return True
            if self.dragging and kind in (QtCore.QEvent.Wheel,QtCore.QEvent.MouseButtonPress,QtCore.QEvent.MouseButtonDblClick):
                return True
        except Exception as error:
            self.stop()
            W.QMessageBox.warning(self.ws.main,tr('移動'),str(error))
            return True
        return False
