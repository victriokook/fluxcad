"""Sketch palette backed by the active FreeCAD Sketcher view properties."""
from i18n import tr
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from grid import DENSITIES
from grid_input import GridSpacingBox


class SketchPanel(QtCore.QObject):
    def __init__(self, ws):
        super().__init__(ws.main)
        self.ws = ws
        self.key = None
        self.params = App.ParamGet('User parameter:BaseApp/Preferences/FluxCAD/SketchPalette')
        self.custom_position = self.params.GetBool('Positioned',False)
        self.offset = QtCore.QPoint(self.params.GetInt('X',0),self.params.GetInt('Y',0))
        self.legacy_position = self.custom_position and self.params.GetInt('PositionVersion',1)<2
        self.collapsed = self.params.GetBool('Collapsed',False)
        self.drag_start = None
        self.dragging = False
        self.watched_docks = []
        self.snap_params = App.ParamGet('User parameter:BaseApp/Preferences/Mod/Sketcher/Snap')
        settings = App.ParamGet('User parameter:BaseApp/Preferences/FluxCAD/Sketch')
        # Enable the newly added grid snap once; preserve subsequent user choices.
        if not settings.GetBool('GridSnapInitialized',False):
            self.snap_params.SetBool('Snap',True)
            self.snap_params.SetBool('SnapToGrid',True)
            settings.SetBool('GridSnapInitialized',True)
        # Overlay the viewport like Fusion. A dock changes its dimensions and
        # therefore moves every projected point when sketch editing is toggled.
        self.dock = W.QFrame(ws.main)
        self.dock.setObjectName('FluxSketchPalette')
        self.dock.setStyleSheet('QFrame#FluxSketchPalette {background:#f6f6f6;border:1px solid #c9cdd1;}')
        overlay = W.QVBoxLayout(self.dock)
        overlay.setContentsMargins(1,1,1,1)
        overlay.setSpacing(0)
        overlay.setSizeConstraint(W.QLayout.SetNoConstraint)
        self.dock.installEventFilter(self)
        self.header = W.QToolButton()
        self.header.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.header.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Fixed)
        self.header.setFixedHeight(26)
        self.header.setStyleSheet('text-align:left;background:#eeeeee;border:0;')
        self.header.setCursor(QtCore.Qt.OpenHandCursor)
        self.header.setMouseTracking(True)
        self.header.setToolTip(tr('ドラッグで移動／クリックで折りたたみ\n右クリックで自動配置に戻せます。'))
        self.header.clicked.connect(self.toggle)
        self.header.installEventFilter(self)
        self.header.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.header.customContextMenuRequested.connect(self.header_menu)
        overlay.addWidget(self.header)
        scroll = self.scroll = W.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(W.QFrame.NoFrame)
        overlay.addWidget(scroll)
        panel = W.QWidget()
        panel.setStyleSheet('background:#f6f6f6;color:#34383c;font:12px "Yu Gothic UI";')
        layout = W.QVBoxLayout(panel)
        layout.setContentsMargins(12,10,12,10)
        layout.setSpacing(9)
        layout.addWidget(W.QLabel(tr('オプション')))
        select = W.QPushButton(tr('選択（作図を終了）'))
        select.setToolTip(tr('線・長方形・トリムなどの操作を終了して、既存の線や頂点を選択します。'))
        select.clicked.connect(lambda: ws.safe(ws.select_sketch_geometry))
        layout.addWidget(select)
        selection_help = W.QLabel(tr('線・頂点をクリックで選択\n複数選択：Ctrl＋クリック\n削除：線を選択して Delete\n寸法変更：数値をダブルクリック',
                                    'Click edges/vertices to select\nMulti-select: Ctrl+click\nDelete: select edges, then Delete\nEdit dimension: double-click its value'))
        selection_help.setWordWrap(True)
        layout.addWidget(selection_help)
        validate = W.QPushButton(tr('スケッチを検証・修復…','Validate / Repair Sketch…'))
        validate.setObjectName('FluxValidateSketch')
        validate.setToolTip(tr('編集を終了して検証画面を開きます。検査だけでは形状を変更しません。',
                               'Finish sketch editing and open validation. Inspection alone does not change geometry.'))
        validate.clicked.connect(lambda: ws.safe(ws.validate_sketch))
        layout.addWidget(validate)
        self.plane_label=W.QLabel()
        self.plane_label.setObjectName('FluxSketchPlane')
        self.plane_label.setWordWrap(True);layout.addWidget(self.plane_label)
        normal = self.front_button = W.QPushButton(tr('ビュー正面'))
        normal.setObjectName('FluxSketchFront')
        normal.setToolTip(tr('編集中のスケッチ面を正面から表示します。ズームとグリッド間隔は維持します。',
                             'Look straight at the edited sketch plane, keeping zoom and grid spacing.'))
        normal.clicked.connect(lambda: ws.safe(lambda: ws.sketch_command('Sketcher_ViewSketch')))
        layout.addWidget(normal)
        self.view_hint=W.QLabel(tr('スケッチ面を真横から見ています。「ビュー正面」でこの面のグリッドを表示できます。別の面に描く場合は編集を終了し、その方向に表示して「スケッチを作成」を押してください。',
                                    'This sketch plane is viewed edge-on. Use Look At Sketch to see its grid. To draw on another plane, finish editing, switch to that view, then Create Sketch.'))
        self.view_hint.setObjectName('FluxSketchEdgeOnHint')
        self.view_hint.setWordWrap(True)
        self.view_hint.setStyleSheet('color:#936011;')
        self.view_hint.hide();layout.addWidget(self.view_hint)
        self.checks = {}
        for prop,title in [('ShowGrid',tr('スケッチ グリッド')),('GridAuto',tr('グリッド間隔を自動調整')),
                           ('Autoconstraints',tr('自動拘束')),('SectionView',tr('スライス表示'))]:
            checkbox = W.QCheckBox(title)
            checkbox.toggled.connect(lambda checked,p=prop: ws.safe(lambda: self.set_property(p,checked)))
            self.checks[prop] = checkbox
            layout.addWidget(checkbox)
            if prop == 'GridAuto':
                self.density = W.QComboBox()
                for label,value in DENSITIES:
                    self.density.addItem(label,value)
                self.density.setToolTip(tr('自動調整の細かさ。ズームに応じて間隔を変えます。'))
                self.density.currentIndexChanged.connect(lambda i: ws.safe(lambda: ws.grid.set_density(self.density.itemData(i))))
                layout.addWidget(self.density)
        self.spacing = GridSpacingBox()
        self.spacing.chosen.connect(lambda v: ws.safe(lambda: self.set_property('GridSize',v)))
        layout.addWidget(W.QLabel(tr('グリッド間隔')))
        layout.addWidget(self.spacing)
        presets = W.QHBoxLayout()
        for value in (0.1,0.5,1):
            # FreeCAD enforces wide minimums on dialog push buttons. Tool
            # buttons keep these three presets within the compact palette.
            button = W.QToolButton()
            button.setText('%g mm' % value)
            button.setObjectName('GridPreset_%g' % value)
            button.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Fixed)
            button.setMinimumWidth(45)
            button.setMinimumHeight(24)
            button.clicked.connect(lambda checked=False,v=value: self.spacing.choose(v))
            presets.addWidget(button)
        layout.addLayout(presets)
        self.grid_snap = W.QCheckBox(tr('グリッドにスナップ'))
        self.grid_snap.setToolTip(tr('作図点を近くのグリッド交点に吸着します。間隔は表示グリッドと共通です。既存の点・線へのスナップが優先されます。'))
        self.grid_snap.toggled.connect(lambda checked: ws.safe(lambda: self.set_grid_snap(checked)))
        layout.addWidget(self.grid_snap)
        self.strong_snap = W.QCheckBox(tr('スナップを強める', 'Stronger grid snapping'))
        self.strong_snap.setToolTip(tr('作図点を最寄りの格子点へ吸着します。拡大しても吸着し、既存の点・線への接続を優先します。',
                                      'Snap drawing points to the nearest grid intersection, even when zoomed in. Existing points and edges keep priority.'))
        self.strong_snap.setChecked(settings.GetBool('StrongGridSnap',True))
        self.strong_snap.toggled.connect(lambda checked: settings.SetBool('StrongGridSnap',checked))
        layout.addWidget(self.strong_snap)
        snap_hint = W.QLabel(tr('Shift＋クリック：格子点だけに固定', 'Shift + click: grid points only'))
        snap_hint.setWordWrap(True)
        snap_hint.setToolTip(tr('作図中はShiftでグリッドに強制吸着します。通常のスナップ設定がオフでも使えます。',
                               'Hold Shift while drawing to force grid snapping, even when normal snapping is off.'))
        layout.addWidget(snap_hint)
        self.info = W.QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        layout.addStretch()
        finish = W.QPushButton(tr('✓  スケッチを終了'))
        finish.setStyleSheet('background:#66b52a;color:white;padding:9px;border:0;border-radius:3px;')
        finish.clicked.connect(lambda: ws.safe(ws.finish_sketch))
        layout.addWidget(finish)
        scroll.setWidget(panel)
        ws.main.installEventFilter(self)
        self.dock.hide()

    def viewport_rect(self):
        doc = Gui.activeDocument()
        if not doc:return None
        view = doc.activeView()
        if not hasattr(view,'graphicsView'):return None
        viewport = view.graphicsView().viewport()
        return QtCore.QRect(viewport.mapTo(self.ws.main,QtCore.QPoint()),viewport.size())

    def movement_rect(self):
        viewport = self.viewport_rect()
        if viewport is None:return None
        # This palette is a main-window overlay: native side docks must not
        # restrict a deliberate drag to the narrower 3D viewport.
        area = self.ws.main.contentsRect()
        return QtCore.QRect(area.x(),viewport.y(),area.width(),viewport.height())

    def position_overlay(self):
        if not self.key:
            return
        viewport = self.viewport_rect()
        if viewport is not None:
            origin = viewport.topLeft()
            obstacles = self.obstacles()  # Observe native dock layout changes in both modes.
            if self.custom_position:
                area = self.movement_rect()
                if self.legacy_position:
                    self.offset += origin-area.topLeft()
                    self.save_position()
                if area.width()<1 or area.height()<28:
                    self.dock.hide();return
                compact = self.collapsed or area.height()<100
                width = min(250,area.width())
                height = 28 if compact else min(610,area.height())
                preferred = area.topLeft()+self.offset
                x = max(area.left(),min(preferred.x(),area.right()-width+1))
                y = max(area.top(),min(preferred.y(),area.bottom()-height+1))
                self.scroll.setVisible(not compact)
                self.header.setText(('▸' if compact else '▾')+tr('  スケッチ パレット'))
                self.dock.setGeometry(x,y,width,height)
                self.dock.show();self.dock.raise_()
                return
            area = viewport.adjusted(8,8,-8,-8)
            if area.width()<1 or area.height()<28:
                self.dock.hide()
                return
            width = min(250,area.width())
            height = 28 if self.collapsed else min(610,area.height())
            preferred = QtCore.QPoint(area.right()-width+1,origin.y()+min(120,max(8,viewport.height()//5)))
            spaces = [area]
            for obstacle in obstacles:
                remaining = []
                for space in spaces:
                    cut = space.intersected(obstacle.adjusted(-8,-8,8,8))
                    if cut.isEmpty():
                        remaining.append(space)
                        continue
                    # These four maximal strips may overlap one another, but
                    # none covers the obstacle. Keep full-height side spaces.
                    remaining.extend([
                        QtCore.QRect(space.left(),space.top(),cut.left()-space.left(),space.height()),
                        QtCore.QRect(cut.right()+1,space.top(),space.right()-cut.right(),space.height()),
                        QtCore.QRect(space.left(),space.top(),space.width(),cut.top()-space.top()),
                        QtCore.QRect(space.left(),cut.bottom()+1,space.width(),space.bottom()-cut.bottom())])
                spaces = [rect for rect in remaining if rect.width()>0 and rect.height()>=28]
            # Prefer a full-size palette next to Tasks over a tiny panel above
            # it. On narrow windows, use a shorter scrollable panel below the browser.
            candidates = []
            for space in spaces:
                w,h = min(width,space.width()),min(height,space.height())
                if w<min(180,width) or h<(28 if self.collapsed else min(100,height)):
                    continue
                x = max(space.left(),min(preferred.x(),space.right()-w+1))
                y = max(space.top(),min(preferred.y(),space.bottom()-h+1))
                score = (-min(w/width,h/height),-(w*h),abs(x-preferred.x())+abs(y-preferred.y()))
                candidates.append((score,QtCore.QRect(x,y,w,h)))
            compact = self.collapsed
            if not candidates:
                # Keep an accessible title strip even in very small windows.
                for space in spaces:
                    w = min(width,space.width())
                    if w>=min(120,width):
                        x=max(space.left(),min(preferred.x(),space.right()-w+1))
                        y=max(space.top(),min(preferred.y(),space.bottom()-27))
                        candidates.append(((0,-w,abs(x-preferred.x())+abs(y-preferred.y())),QtCore.QRect(x,y,w,28)))
                compact = True
            if not candidates:
                self.dock.hide()
                return
            self.scroll.setVisible(not compact)
            self.header.setText(('▸' if compact else '▾')+tr('  スケッチ パレット'))
            self.dock.setGeometry(min(candidates,key=lambda candidate:candidate[0])[1])
            self.dock.show()
            self.dock.raise_()

    def obstacles(self):
        result = []
        for dock in self.ws.main.findChildren(W.QDockWidget):
            if dock.objectName() not in ('Tasks','Task Panel','Combo View'):
                continue
            if dock not in self.watched_docks:
                dock.installEventFilter(self)
                self.watched_docks.append(dock)
            if dock.isVisible():
                point=self.ws.main.mapFromGlobal(dock.mapToGlobal(QtCore.QPoint()))
                result.append(QtCore.QRect(point,dock.size()))
        browser = getattr(self.ws,'browser',None)
        if browser and browser.panel.isVisible():
            result.append(browser.panel.geometry())
        return result

    def toggle(self):
        self.finish_drag()
        self.collapsed = not self.collapsed
        self.params.SetBool('Collapsed',self.collapsed)
        self.position_overlay()

    def reset_position(self):
        self.finish_drag()
        self.custom_position = False
        self.params.SetBool('Positioned',False)
        self.position_overlay()

    def header_menu(self,point):
        self.finish_drag()
        menu = W.QMenu(self.header)
        reset = menu.addAction(tr('自動配置に戻す'))
        if menu.exec_(self.header.mapToGlobal(point))==reset:
            self.reset_position()

    def finish_drag(self):
        dragged = self.dragging
        self.drag_start = None
        self.dragging = False
        self.header.setCursor(QtCore.Qt.OpenHandCursor)
        self.header.setDown(False)
        if W.QWidget.mouseGrabber()==self.header:self.header.releaseMouse()
        if dragged:
            area = self.movement_rect()
            if area is not None:self.offset = self.dock.pos()-area.topLeft()
            self.save_position()
        return dragged

    def save_position(self):
        self.legacy_position = False
        self.params.SetInt('PositionVersion',2)
        self.params.SetBool('Positioned',True)
        self.params.SetInt('X',self.offset.x())
        self.params.SetInt('Y',self.offset.y())

    def eventFilter(self,widget,event):
        kind = event.type()
        if widget==self.header:
            if kind==QtCore.QEvent.MouseButtonPress and event.button()==QtCore.Qt.LeftButton:
                self.drag_start = event.globalPosition().toPoint() if hasattr(event,'globalPosition') else event.globalPos()
                self.drag_panel_start = self.dock.pos()
                self.dragging = False
                self.header.setDown(True)
                self.header.grabMouse()
                return True
            elif kind==QtCore.QEvent.MouseMove and self.drag_start is not None:
                if not event.buttons() & QtCore.Qt.LeftButton:
                    self.finish_drag();return True
                point = event.globalPosition().toPoint() if hasattr(event,'globalPosition') else event.globalPos()
                delta = point-self.drag_start
                if self.dragging or delta.manhattanLength()>=W.QApplication.startDragDistance():
                    self.dragging = True
                    self.header.setDown(False)
                    self.header.setCursor(QtCore.Qt.ClosedHandCursor)
                    area=self.movement_rect()
                    if area is not None:
                        self.offset=self.drag_panel_start+delta-area.topLeft()
                        self.custom_position=True
                        self.legacy_position=False
                        self.position_overlay()
                    return True
            elif kind==QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.LeftButton:
                pressed=self.drag_start is not None
                dragged=self.finish_drag()
                if pressed and not dragged and self.header.rect().contains(event.position().toPoint()):self.toggle()
                return True
        if ((widget==self.ws.main and kind==QtCore.QEvent.WindowDeactivate) or
                (widget==self.dock and kind==QtCore.QEvent.Hide) or
                (widget==self.header and kind==QtCore.QEvent.UngrabMouse)):
            self.finish_drag()
        if widget not in (self.header,self.dock) and kind in (QtCore.QEvent.Resize,QtCore.QEvent.Move,QtCore.QEvent.Show,QtCore.QEvent.Hide) and self.key:
            QtCore.QTimer.singleShot(0,self.position_overlay)
        return False

    def set_property(self,prop,value):
        if prop == 'ShowGrid':
            self.ws.grid.enabled = bool(value)
            self.ws.grid.update()
            return
        if prop == 'GridAuto':
            self.ws.grid.set_auto(value)
            self.spacing.sync(self.ws.grid.spacing,force=True)
            self.refresh()
            return
        if prop == 'GridSize':
            self.ws.grid.set_spacing(value)
            self.refresh()
            return
        sketch = self.ws.current_sketch()
        if sketch and prop in sketch.ViewObject.PropertiesList:
            setattr(sketch.ViewObject,prop,value)

    def set_grid_snap(self,enabled):
        # Sketcher_Snap toggles the master switch only. Grid snapping has its own
        # native preference, observed immediately by Sketcher's SnapManager.
        self.snap_params.SetBool('SnapToGrid',enabled)
        if enabled:
            self.snap_params.SetBool('Snap',True)
            self.ws.grid.enabled = True
            self.ws.grid.update()

    def refresh(self):
        sketch = self.ws.current_sketch()
        for key in self.ws.sketch_action_keys:
            self.ws.ribbon_actions[key].setEnabled(sketch is not None)
        key = (sketch.Document.Name,sketch.Name) if sketch else None
        changed_sketch = key != self.key
        if key != self.key:
            self.key = key
            if sketch:
                if self.ws.ribbon_tabs.currentIndex()!=self.ws.tab_indices['sketch']:
                    self.return_tab=self.ws.ribbon_tabs.currentIndex()
                self.ws.ribbon_tabs.setTabVisible(self.ws.tab_indices['sketch'],True)
                self.ws.ribbon_tabs.setCurrentIndex(self.ws.tab_indices['sketch'])
                self.dock.show()
                self.ws.compact()
            else:
                self.dock.hide()
                self.ws.ribbon_tabs.setCurrentIndex(getattr(self,'return_tab',0))
                self.ws.ribbon_tabs.setTabVisible(self.ws.tab_indices['sketch'],False)
        if not sketch:
            return
        self.plane_label.setText(tr('作図面：%s','Sketch plane: %s')%self.ws.grid.plane_name(sketch.getGlobalPlacement()))
        edge_on=self.ws.grid.is_edge_on(Gui.activeDocument().activeView(),sketch.getGlobalPlacement())
        self.view_hint.setVisible(edge_on and self.ws.grid.enabled)
        self.position_overlay()
        self.grid_snap.blockSignals(True)
        self.grid_snap.setChecked(self.snap_params.GetBool('Snap',True) and self.snap_params.GetBool('SnapToGrid',False))
        self.grid_snap.blockSignals(False)
        self.strong_snap.blockSignals(True)
        self.strong_snap.setChecked(self.ws.sketch_snap.settings.GetBool('StrongGridSnap',True))
        self.strong_snap.setEnabled(self.grid_snap.isChecked())
        self.strong_snap.blockSignals(False)
        for prop,checkbox in self.checks.items():
            checkbox.blockSignals(True)
            value = (self.ws.grid.enabled if prop=='ShowGrid' else self.ws.grid.auto if prop=='GridAuto'
                     else getattr(sketch.ViewObject,prop))
            checkbox.setChecked(bool(value))
            checkbox.blockSignals(False)
        self.spacing.sync(self.ws.grid.spacing,force=changed_sketch)
        self.density.blockSignals(True)
        self.density.setCurrentIndex(self.density.findData(self.ws.grid.density))
        self.density.setEnabled(self.ws.grid.auto)
        self.density.blockSignals(False)
        info = tr('ジオメトリ  %d\n拘束  %d') % (sketch.GeometryCount,sketch.ConstraintCount)
        references = sum(max(1,len(elements)) for obj,elements in sketch.ExternalGeometry)
        if references:
            info += tr('\n外部参照  %d','\nExternal references  %d') % references
        self.info.setText(info)

    def close(self):
        self.key = None
        self.finish_drag()
        self.ws.main.removeEventFilter(self)
        self.header.removeEventFilter(self)
        self.dock.removeEventFilter(self)
        for dock in self.watched_docks:
            try:dock.removeEventFilter(self)
            except RuntimeError:pass
        self.dock.hide()
        self.dock.deleteLater()
