"""FluxCAD: a compact FreeCAD desktop workspace inspired by Fusion workflows."""
from i18n import tr
import os
from contextlib import contextmanager
import FreeCAD as App
import FreeCADGui as Gui
from pivy import coin
from PySide import QtCore, QtGui
try:
    from PySide import QtWidgets as W
except ImportError:
    W = QtGui
import model
import model_features
from grid import Grid

ROOT = os.path.dirname(__file__)


from navigation import FusionMouse


class Workspace:
    def __init__(self):
        self.main = Gui.getMainWindow()
        self.mouse = FusionMouse(self.main,self)
        self.grid = Grid()
        from drag_move import DragMove
        self.drag_move = DragMove(self)
        from region_picker import RegionPicker
        self.region_picker = RegionPicker(self)
        from sketch_snap import SketchSnap
        self.sketch_snap = SketchSnap(self)
        self.previous_style = self.main.styleSheet()
        self.previous_bars = []
        self.layout_params = App.ParamGet('User parameter:BaseApp/Preferences/FluxCAD/Layout')
        self.bottom_tabs_visible = self.layout_params.GetBool('BottomTabsVisible',True)
        self.previous_document_tabs = {}
        Gui.activateWorkbench('PartWorkbench')
        self.toolbar = W.QToolBar('FluxCAD', self.main)
        self.toolbar.setObjectName('FluxCADToolbar')
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.toolbar.setIconSize(QtCore.QSize(25,25))
        self.main.addToolBar(QtCore.Qt.TopToolBarArea, self.toolbar)
        self.actions = []
        self.previous_menu_visible = self.main.menuBar().isVisible()
        self.main.menuBar().hide()
        import ribbon
        ribbon.build(self)
        self.build_history()
        from sketch_panel import SketchPanel
        self.sketch_panel = SketchPanel(self)
        from browser import Browser
        self.browser = Browser(self)
        from extent_panel import ExtentPanel
        self.extrusion = ExtentPanel(self)
        from feature_panel import FeaturePanel
        self.features = FeaturePanel(self)
        from transform_panel import TransformPanel
        self.transform = TransformPanel(self)
        from align_panel import AlignPanel
        self.alignment = AlignPanel(self)
        from mesh_panel import MeshPanel
        self.mesh_edit = MeshPanel(self)
        from mesh_operations_panel import MeshOperationsPanel
        self.mesh_ops = MeshOperationsPanel(self)
        from hole_panel import HolePanel
        self.hole_panel = HolePanel(self)
        from edge_panel import EdgePanel
        self.edge_panel = EdgePanel(self)
        from split_panel import SplitPanel
        self.split_panel = SplitPanel(self)
        from combine_panel import CombinePanel
        self.combine_panel = CombinePanel(self)
        from assembly_panel import ComponentPanel,JointPanel
        self.component_panel = ComponentPanel(self)
        self.joint_panel = JointPanel(self)
        from primitive_panel import PrimitivePanel
        self.primitive_panel = PrimitivePanel(self)
        from path_pattern_panel import PathPatternPanel
        self.path_pattern_panel = PathPatternPanel(self)
        from construction_panel import ConstructionPanel
        self.construction_panel = ConstructionPanel(self)
        from construction_axis_panel import ConstructionAxisPanel
        self.construction_axis_panel = ConstructionAxisPanel(self)
        from navigation_cube import CubeNavigation
        self.cube = CubeNavigation(self)
        from drawing import SceneRepair
        self.drawing_scene = SceneRepair(self)
        self.editing_sketch_name = None
        self.main.setStyleSheet(self.previous_style + '''
QDockWidget#FluxCADHistory {font:12px "Yu Gothic UI";}
QListWidget#FluxHistoryList {background:#f4f7fa;border:0;color:#304152;outline:0;}
QListWidget#FluxHistoryList::item {padding:2px 6px;margin:1px;border:1px solid #d5dee7;border-radius:2px;font-size:11px;}
QListWidget#FluxHistoryList::item:selected {background:#d1eee8;color:#12584d;border:1px solid #34aa97;}
''')
        self.timer = QtCore.QTimer(self.main)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(600)
        self.signature = None
        self.main.workbenchActivated.connect(self.workbench_changed)
        self.compact()
        if not App.ActiveDocument:
            App.newDocument('Untitled')
        self.fit()
        self.refresh()
        self.main.statusBar().showMessage(tr('FluxCAD  |  スケッチ → 押し出し → 編集  |  単位 mm'), 12000)

    def add(self, text, icon, callback, shortcut=None):
        local = os.path.join(ROOT,'icons',icon+'.svg')
        action = self.toolbar.addAction(QtGui.QIcon(local if os.path.exists(local) else ':/icons/'+icon+'.svg'), text)
        action.triggered.connect(lambda checked=False: self.safe(callback))
        # View-only shortcut context prevents stealing text input in property editors.
        if shortcut:
            action.setToolTip(text + tr(' — 3Dビューで ') + shortcut)
        self.actions.append((action, shortcut, callback))

    def safe(self, callback):
        try:
            if getattr(self,'native_task_opened',False) and Gui.Control.activeDialog() and not self.current_sketch() and callback!=self.restore:
                raise ValueError(tr('開いているタスクを確定または閉じてから実行してください。',
                                    'Finish or close the current task before starting another tool.'))
            self.native_task_opened=False
            for panel in (self.component_panel,self.joint_panel,self.primitive_panel,self.path_pattern_panel,self.construction_panel,self.construction_axis_panel):
                if panel.active:panel.cancel()
            if self.extrusion.active:
                self.extrusion.cancel()
            if self.features.active:
                self.features.cancel()
            if self.transform.active:
                self.transform.cancel()
            if self.alignment.active:
                self.alignment.cancel()
            if self.mesh_edit.active:
                self.mesh_edit.cancel()
            if self.mesh_ops.active:
                self.mesh_ops.cancel()
            if self.hole_panel.active:
                self.hole_panel.cancel()
            if self.split_panel.active:
                self.split_panel.cancel()
            if self.combine_panel.active:
                self.combine_panel.cancel()
            if self.edge_panel.active:
                self.edge_panel.cancel()
            if self.drag_move.active and callback!=self.start_move:
                self.drag_move.stop()
            callback()
            self.refresh()
        except Exception as error:
            W.QMessageBox.warning(self.main, 'FluxCAD', str(error))

    def change_language(self,code):
        import i18n
        i18n.save_language(code)
        for key,action in self.language_actions.items():action.setChecked(key==code)
        W.QMessageBox.information(self.main,tr('表示言語の変更','Display Language'),
            tr('言語設定を保存しました。作業を保存してFluxCADを再起動すると、FreeCADの標準画面も含めて反映されます。',
               'Language saved. Save your work and restart FluxCAD to apply it to FluxCAD and the native FreeCAD interface.'))

    def workbench_changed(self, name):
        QtCore.QTimer.singleShot(0, self.compact)

    def compact(self):
        if hasattr(self,'browser'):
            self.browser.compact()
        for bar in self.main.findChildren(W.QToolBar):
            if bar != self.toolbar and bar.isVisible():
                if bar not in self.previous_bars:
                    self.previous_bars.append(bar)
                bar.hide()
        self.toolbar.show()

    def restore(self):
        if getattr(self,'restored',False):
            return
        self.restored = True
        self.drawing_scene.close()
        if getattr(self,'search_dialog',None):self.search_dialog.close()
        self.mouse.enabled = False
        self.mouse.cancel()
        self.cube.close()
        self.extrusion.close()
        self.features.close()
        self.transform.close()
        self.alignment.close()
        self.mesh_edit.close()
        self.mesh_ops.close()
        self.hole_panel.close()
        self.edge_panel.close()
        self.split_panel.close()
        self.combine_panel.close()
        self.component_panel.close()
        self.joint_panel.close()
        self.primitive_panel.close()
        self.path_pattern_panel.close()
        self.construction_panel.close()
        self.construction_axis_panel.close()
        self.drag_move.close()
        self.grid.clear()
        self.sketch_snap.close()
        self.region_picker.close()
        self.sketch_panel.close()
        self.browser.close()
        self.timer.stop()
        self.main.workbenchActivated.disconnect(self.workbench_changed)
        self.toolbar.hide()
        self.history.hide()
        for bar,(visible,margins,style) in self.previous_document_tabs.items():
            try:
                bar.setStyleSheet(style)
                bar.setVisible(visible)
                bar.parentWidget().setViewportMargins(margins)
            except RuntimeError:pass
        self.main.setStyleSheet(self.previous_style)
        self.main.menuBar().setVisible(self.previous_menu_visible)
        for bar in self.previous_bars:
            try:
                bar.show()
            except RuntimeError:
                pass  # A reloaded workspace or native workbench removed it.
        for shortcut in getattr(self, 'shortcuts', []):
            try:
                shortcut.setEnabled(False)
            except RuntimeError:
                pass  # A closed document has already destroyed its Qt shortcuts.

    def build_history(self):
        self.history = W.QDockWidget(tr('デザイン履歴  •  選択してプロパティを編集'), self.main)
        self.history.setObjectName('FluxCADHistory')
        self.history.setFeatures(W.QDockWidget.DockWidgetMovable)
        title = W.QWidget(self.history)
        title.setFixedHeight(0)
        self.history.setTitleBarWidget(title)
        self.history.setFixedHeight(42)
        self.list = W.QListWidget()
        self.list.setObjectName('FluxHistoryList')
        self.list.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.list.setFlow(W.QListView.LeftToRight)
        self.list.setFixedHeight(42)
        self.list.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.list.setStyleSheet('QScrollBar:horizontal {height:10px;}')
        self.list.itemSelectionChanged.connect(self.select_history)
        self.list.itemDoubleClicked.connect(self.edit_history)
        self.list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.history_menu)
        self.history.setWidget(self.list)
        self.main.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.history)
        self.apply_bottom_tabs()

    def apply_bottom_tabs(self):
        self.history.setVisible(self.bottom_tabs_visible)
        # Only the native document tabs; leave ribbon and task tabs alone.
        for bar in self.main.findChildren(W.QTabBar,'mdiAreaTabBar'):
            area = bar.parentWidget()
            if bar not in self.previous_document_tabs:
                self.previous_document_tabs[bar] = (not bar.isHidden(),area.viewportMargins(),bar.styleSheet())
            was_hidden = bar.isHidden()
            style = self.previous_document_tabs[bar][2]
            if not self.bottom_tabs_visible:
                style += '\nQTabBar {min-height:0px;max-height:0px;} QTabBar::tab {height:0px;min-height:0px;max-height:0px;padding:0px;margin:0px;border:0px;}'
            if bar.styleSheet()!=style:
                bar.setStyleSheet(style)
            bar.setVisible(self.bottom_tabs_visible)
            # QMdiArea keeps reserving the tab strip even when QTabBar is hidden.
            if not self.bottom_tabs_visible:
                if area.viewportMargins()!=QtCore.QMargins():
                    area.setViewportMargins(0,0,0,0)
            elif was_hidden:
                area.setViewportMargins(self.previous_document_tabs[bar][1])
        self.ribbon_actions['bottom_tabs'].setChecked(self.bottom_tabs_visible)

    def toggle_bottom_tabs(self):
        self.bottom_tabs_visible = not self.bottom_tabs_visible
        self.layout_params.SetBool('BottomTabsVisible',self.bottom_tabs_visible)
        self.apply_bottom_tabs()
        self.main.layout().activate()

    def history_menu(self,point):
        menu = W.QMenu(self.list)
        hide = menu.addAction(tr('下段タブを隠す'))
        if menu.exec_(self.list.viewport().mapToGlobal(point))==hide:
            self.safe(self.toggle_bottom_tabs)

    def select_history(self):
        for panel in (self.component_panel,self.joint_panel,self.primitive_panel,self.path_pattern_panel,self.construction_panel,self.construction_axis_panel):
            if panel.active:panel.cancel()
        if self.split_panel.active:
            self.split_panel.cancel()
        if self.combine_panel.active:
            self.combine_panel.cancel()
        if self.edge_panel.active:
            self.edge_panel.cancel()
        if self.hole_panel.active:
            self.hole_panel.cancel()
        if self.mesh_ops.active:
            self.mesh_ops.cancel()
        if self.mesh_edit.active:
            self.mesh_edit.cancel()
        if self.alignment.active:
            self.alignment.cancel()
        if self.transform.active:
            self.transform.cancel()
        if self.features.active:
            self.features.cancel()
        if self.extrusion.active:
            self.extrusion.cancel()
        if self.drag_move.active:
            self.drag_move.stop()
        doc = App.ActiveDocument
        if not doc:
            return
        names = [item.data(QtCore.Qt.UserRole) for item in self.list.selectedItems()]
        # Keep click order: for a cut, the first shape is the base and the second
        # is the tool. QListWidget.selectedItems() itself returns row order.
        previous = [obj for obj in Gui.Selection.getSelection()
                    if obj.Document==doc and obj.Name in names]
        added = [doc.getObject(name) for name in names if name not in {obj.Name for obj in previous}]
        self.region_picker.clear()
        Gui.Selection.clearSelection()
        for obj in previous+added:
            if obj:
                Gui.Selection.addSelection(obj)

    def edit_history(self,item):
        def edit():
            import native_tools
            doc = App.ActiveDocument
            obj = doc.getObject(item.data(QtCore.Qt.UserRole)) if doc else None
            if not obj:
                return
            if obj.TypeId=='Part::Scale' and not self.current_sketch():
                import native_tools
                native_tools.edit_scale(self,obj);return
            if native_tools.can_edit_surface(obj) and not self.current_sketch():
                native_tools.edit_surface(self,obj);return
            if getattr(obj,'FluxConstructionAxis','') and not self.current_sketch():
                self.construction_axis_panel.start(existing=obj);return
            if getattr(obj,'FluxConstructionPlane','') and not self.current_sketch():
                self.construction_panel.start(existing=obj);return
            if getattr(obj,'FluxPrimitive','') and not self.current_sketch():
                self.primitive_panel.start(existing=obj);return
            if getattr(obj,'FluxPathPattern',False) and not self.current_sketch():
                self.path_pattern_panel.start(existing=obj);return
            if getattr(obj,'FluxComponent',False) and not self.current_sketch():
                self.component_panel.start(existing=obj);return
            if getattr(obj,'FluxJoint',False) and not self.current_sketch():
                self.joint_panel.start(existing=obj);return
            if getattr(obj,'FluxCombine',False) and not self.current_sketch():
                self.combine_panel.start(existing=obj)
                return
            if getattr(obj,'FluxSplit',False) and not self.current_sketch():
                self.split_panel.start(existing=obj)
                return
            if obj.TypeId in ('Part::Fillet','Part::Chamfer') and not self.current_sketch():
                self.edge_panel.start(existing=obj)
                return
            if getattr(obj,'FluxExtent',False) and not self.current_sketch():
                self.extrusion.start(existing=obj)
                return
            kind = model_features.feature_kind(obj)
            if kind and not self.current_sketch():
                self.features.start(kind,model_features.feature_source(obj),existing=obj)
                return
            if obj.TypeId=='Sketcher::SketchObject':
                browser_item = self.browser.items.get(obj.Name)
                if browser_item:
                    self.browser.activate(browser_item)
            else:
                extrusion = getattr(obj,'FluxExtrusion',None) or (obj if obj.TypeId=='Part::Extrusion' else None)
                if not extrusion or self.current_sketch():
                    return
                fields = [(tr('全長') if extrusion.Symmetric else tr('距離'),extrusion.LengthFwd.Value,0.001)]
                if not extrusion.Symmetric and extrusion.LengthRev.Value>0:
                    fields.append((tr('反対側の距離'),extrusion.LengthRev.Value,0.001))
                values = self.values(tr('押し出しを編集'),fields,
                                     obj.Label+tr(' の長さを変更します。後の切り取り・フィレットも更新します。'))
                if values:
                    with model.transaction(doc,tr('押し出し長さを変更')):
                        extrusion.LengthFwd = values[0]
                        if len(values)>1:
                            extrusion.LengthRev = values[1]
                        doc.recompute()
                        for feature in [extrusion]+extrusion.InListRecursive:
                            if hasattr(feature,'Shape') and (feature.Shape.isNull() or not feature.Shape.isValid()):
                                raise ValueError(tr('後の加工を更新できません。この寸法変更は取り消しました。'))
        self.safe(edit)

    def refresh(self):
        doc = App.ActiveDocument
        self.drawing_scene.refresh()
        if Gui.activeDocument() and hasattr(Gui.activeDocument().activeView(),'getPage'):
            import drawing
            drawing.set_mode(self,True)
        self.apply_bottom_tabs()
        self.region_picker.refresh()
        self.grid.update()
        self.sketch_snap.refresh()
        self.drag_move.refresh()
        self.extrusion.refresh()
        self.features.refresh()
        self.transform.refresh()
        self.alignment.refresh()
        self.mesh_edit.refresh()
        self.mesh_ops.refresh()
        self.browser.refresh()
        self.sketch_panel.refresh()
        self.hole_panel.refresh()
        self.edge_panel.refresh()
        self.split_panel.refresh()
        self.combine_panel.refresh()
        self.component_panel.refresh()
        self.joint_panel.refresh()
        self.primitive_panel.refresh()
        self.path_pattern_panel.refresh()
        self.construction_panel.refresh()
        self.construction_axis_panel.refresh()
        sketch = self.current_sketch()
        self.ribbon_actions['move'].setEnabled(sketch is None)
        self.ribbon_actions['move'].setChecked(self.drag_move.active)
        self.ribbon_actions['move_numeric'].setEnabled(sketch is None)
        for key in self.solid_action_keys:
            self.ribbon_actions[key].setEnabled(sketch is None)
        self.ribbon_actions['grid'].setChecked(self.grid.enabled)
        for shortcut in getattr(self,'shortcuts',[]):
            try:
                shortcut.setEnabled(sketch is None or bool(shortcut.property('FluxInSketch')))
            except RuntimeError:
                pass
        self.doc_title.setText(doc.Label if doc else tr('無題のデザイン'))
        objects = [o for o in doc.Objects if (hasattr(o, 'Shape') or getattr(o,'FluxJoint',False)) and not getattr(o,'FluxCADInternal',False) and not getattr(o,'FluxSplitPart',False)] if doc else []
        signature = (doc.Name if doc else '', tuple((o.Name,o.Label) for o in objects))
        signals = self.list.blockSignals(True)
        try:
            if signature != self.signature:
                self.signature = signature
                self.list.clear()
                for i,obj in enumerate(objects):
                    item = W.QListWidgetItem('%02d  %s' % (i+1,obj.Label))
                    item.setData(QtCore.Qt.UserRole, obj.Name)
                    item.setToolTip(tr('クリックで選択。Ctrl＋クリックで追加・解除。切り取りは本体→工具の順に選択します。'))
                    self.list.addItem(item)
            selected = {obj.Name for obj in Gui.Selection.getSelection() if obj.Document==doc}
            for i in range(self.list.count()):
                item = self.list.item(i)
                item.setSelected(item.data(QtCore.Qt.UserRole) in selected)
                obj = doc.getObject(item.data(QtCore.Qt.UserRole))
                later = [title for target,title in self.browser.downstream.get(obj.Name,[]) if target!=obj]
                item.setForeground(QtGui.QBrush(QtGui.QColor('#92989e' if later else '#304152')))
                help_text = tr('加工前の履歴。現在の形状：')+ '、'.join(later) if later else tr('クリックで選択。Ctrl＋クリックで追加・解除。')
                if getattr(obj,'FluxPrimitive',''):
                    help_text += tr('\nダブルクリックで寸法と位置を編集。','\nDouble-click to edit dimensions and position.')
                if getattr(obj,'FluxPathPattern',False):
                    help_text += tr('\nダブルクリックで経路・個数・間隔・向きを編集。','\nDouble-click to edit path, quantity, distance and orientation.')
                if obj.TypeId=='Sketcher::SketchObject':
                    help_text += tr('\nダブルクリックでスケッチを編集。')
                elif obj.TypeId=='Part::Extrusion' or getattr(obj,'FluxExtrusion',None) or getattr(obj,'FluxExtent',False):
                    help_text += tr('\nダブルクリックで押し出し長さを変更。')
                elif model_features.feature_kind(obj):
                    help_text += tr('\nダブルクリックで寸法・配置などを編集。')
                elif getattr(obj,'FluxSplit',False):
                    help_text += tr('\nダブルクリックで切断平面と位置を編集。','\nDouble-click to edit the splitting plane and offset.')
                elif getattr(obj,'FluxCombine',False):
                    help_text += tr('\nダブルクリックで操作と工具を編集。','\nDouble-click to edit the operation and tools.')
                elif obj.TypeId in ('Part::Fillet','Part::Chamfer'):
                    help_text += tr('\nダブルクリックで辺と寸法を編集。','\nDouble-click to edit edges and dimensions.')
                item.setToolTip(help_text)
        finally:
            self.list.blockSignals(signals)
        # Bind shortcuts to 3D widgets only, never globally to text fields.
        if not hasattr(self, 'bound_views'):
            self.bound_views, self.shortcuts = set(), []
        for widget in self.main.findChildren(W.QWidget):
            if widget.metaObject().className() == 'Gui::View3DInventorViewer' and widget not in self.bound_views:
                self.bound_views.add(widget)
                widget.installEventFilter(self.mouse)
                if hasattr(widget,'viewport'):
                    widget.viewport().installEventFilter(self.mouse)
                    widget.viewport().installEventFilter(self.region_picker)
                    self.sketch_snap.bind(widget.viewport())
                for child in widget.findChildren(W.QWidget):
                    if child.metaObject().className() == 'QOpenGLWidget':
                        child.installEventFilter(self.mouse)
                self.drag_move.bind(widget)
                if hasattr(widget,'viewport'):
                    self.drag_move.bind(widget.viewport())
                self.extrusion.bind(widget)
                self.features.bind(widget)
                self.transform.bind(widget)
                self.alignment.bind(widget)
                self.mesh_edit.bind(widget)
                self.mesh_ops.bind(widget)
                self.hole_panel.bind(widget)
                self.edge_panel.bind(widget)
                self.split_panel.bind(widget)
                self.combine_panel.bind(widget)
                self.component_panel.bind(widget)
                self.joint_panel.bind(widget)
                self.primitive_panel.bind(widget)
                self.path_pattern_panel.bind(widget)
                self.construction_panel.bind(widget)
                self.construction_axis_panel.bind(widget)
                if hasattr(widget,'viewport'):
                    self.extrusion.bind(widget.viewport())
                    self.features.bind(widget.viewport())
                    self.transform.bind(widget.viewport())
                    self.alignment.bind(widget.viewport())
                    self.mesh_edit.bind(widget.viewport())
                    self.mesh_ops.bind(widget.viewport())
                    self.hole_panel.bind(widget.viewport())
                    self.edge_panel.bind(widget.viewport())
                    self.split_panel.bind(widget.viewport())
                    self.combine_panel.bind(widget.viewport())
                    self.component_panel.bind(widget.viewport())
                    self.joint_panel.bind(widget.viewport())
                    self.primitive_panel.bind(widget.viewport())
                    self.path_pattern_panel.bind(widget.viewport())
                    self.construction_panel.bind(widget.viewport())
                    self.construction_axis_panel.bind(widget.viewport())
                    self.cube.bind(widget.viewport())
                for action,key,callback in self.actions:
                    if key:
                        shortcut_class = getattr(W,'QShortcut',None) or QtGui.QShortcut
                        s = shortcut_class(QtGui.QKeySequence(key), widget)
                        s.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
                        s.setProperty('FluxInSketch',key=='S')
                        s.activated.connect(lambda cb=callback: self.safe(cb))
                        self.shortcuts.append(s)

    def doc(self):
        return App.ActiveDocument or App.newDocument('Untitled')

    def selection(self, count=1):
        selected = Gui.Selection.getSelection()
        if len(selected) != count or any(not hasattr(o,'Shape') for o in selected):
            raise ValueError(tr('形状を%d個選択してください。複数選択はCtrlキーです。') % count)
        if any(o.Document != App.ActiveDocument for o in selected):
            raise ValueError(tr('同じアクティブ文書内の形状を選択してください。'))
        return selected

    def values(self, title, fields, note=tr('寸法の単位：mm')):
        dialog = W.QDialog(self.main)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(330)
        layout = W.QFormLayout(dialog)
        layout.addRow(W.QLabel(note))
        inputs = []
        for label, value, minimum in fields:
            spin = W.QDoubleSpinBox()
            spin.setRange(minimum, 100000)
            spin.setDecimals(3)
            spin.setSuffix(' mm')
            spin.setValue(value)
            layout.addRow(label,spin)
            inputs.append(spin)
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        return [s.value() for s in inputs] if dialog.exec_() else None

    def make(self, label, function, *args):
        doc = self.doc()
        if Gui.activeDocument().getInEdit():
            raise ValueError(tr('先にスケッチ編集を閉じてください。'))
        with model.transaction(doc,label):
            obj = function(doc,*args)
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)
        self.fit()
        return obj

    def fit(self):
        if Gui.activeDocument():
            view = Gui.activeDocument().activeView()
            if not hasattr(view,'getCameraOrientation'):
                view.fitAll()
                return
            orientation = view.getCameraOrientation()
            with self.grid.excluded():
                view.fitAll()
            view.setCameraOrientation(orientation.Q)
            self.grid.update()

    def toggle_grid(self):
        self.grid.enabled = not self.grid.enabled
        self.ribbon_actions['grid'].setChecked(self.grid.enabled)
        self.grid.update()

    def grid_settings(self):
        from grid import show_settings
        show_settings(self)

    @contextmanager
    def preserve_view(self):
        """Keep the current camera through native sketch entry/exit and dialogs."""
        gd = Gui.activeDocument()
        view = gd.activeView() if gd else None
        if not view or not hasattr(view,'getCamera'):
            yield
            return
        camera = view.getCamera()
        animation = view.isAnimationEnabled()
        viewers = [(widget,widget.updatesEnabled()) for widget in self.main.findChildren(W.QWidget)
                   if widget.metaObject().className()=='Gui::View3DInventorViewer' and widget.isVisible()]
        # Native Sketcher starts an asynchronous rotate animation. Stop it before
        # switching, otherwise it can overwrite a restored camera on a later frame.
        view.setAnimationEnabled(False)
        for widget,updates in viewers:
            widget.setUpdatesEnabled(False)
        try:
            with self.grid.excluded():
                yield
        finally:
            try:
                self.compact()
                self.sketch_panel.refresh()
                self.main.layout().activate()
                view.setCamera(camera)
                self.grid.update()
                view.setAnimationEnabled(animation)
            finally:
                for widget,updates in viewers:
                    widget.setUpdatesEnabled(updates)

    def sketch(self):
        doc=self.doc()
        selected=Gui.Selection.getSelection()
        plane=selected[0] if len(selected)==1 and getattr(selected[0],'FluxPlane',False) else None
        with self.preserve_view():
            Gui.activateWorkbench('SketcherWorkbench')
            if plane:
                import model_planes
                sketch=model_planes.sketch_on_plane(doc,plane)
                Gui.Selection.clearSelection();Gui.activeDocument().setEdit(sketch.Name)
            else:
                Gui.runCommand('Sketcher_NewSketch')
            self.compact()
        self.refresh()

    def current_sketch(self):
        gd = Gui.activeDocument()
        edit = gd.getInEdit() if gd else None
        obj = getattr(edit,'Object',None)
        return obj if obj and obj.TypeId == 'Sketcher::SketchObject' else None

    def offset_plane(self):
        if self.current_sketch():raise ValueError(tr('先にスケッチ編集を終了してください。'))
        self.construction_panel.start('offset')

    def command_search(self):
        import command_search
        command_search.show(self)

    def select_mode(self):
        if self.current_sketch():self.select_sketch_geometry()
        else:
            self.region_picker.clear();Gui.Selection.clearSelection()

    def edit_sketch(self):
        if self.current_sketch():
            self.select_sketch_geometry()
            return
        selected = self.selection()[0]
        if selected.TypeId != 'Sketcher::SketchObject':
            raise ValueError(tr('編集するスケッチを選択してください。'))
        self.region_picker.clear()
        Gui.Selection.clearSelection()
        with self.preserve_view():
            Gui.activateWorkbench('SketcherWorkbench')
            Gui.activeDocument().setEdit(selected.Name)
            self.compact()
        self.refresh()
        self.select_sketch_geometry()

    def select_sketch_geometry(self):
        if not self.current_sketch():
            raise ValueError(tr('先にスケッチの編集を開始してください。'))
        # Stop the native draw/trim handler without closing the sketch edit session.
        Gui.runCommand('Sketcher_StopOperation')
        self.sketch_snap.started(None)
        self.region_picker.clear()
        self.mouse.cancel()
        Gui.Selection.clearSelection()
        view = Gui.activeDocument().activeView()
        if hasattr(view,'setFocus'):
            view.setFocus()
        self.main.statusBar().showMessage(tr('選択：線・頂点をクリック。複数選択は Ctrl＋クリック。寸法は数値をダブルクリック。'),12000)

    def sketch_command(self, command):
        if not self.current_sketch():
            raise ValueError(tr('先にスケッチを作成するか、選択して編集を開始してください。'))
        if command not in Gui.listCommands():
            raise ValueError(tr('このFreeCADではこのコマンドを使用できません。'))
        self.grid.update()
        Gui.runCommand(command)
        self.sketch_snap.started(command)

    def finish_sketch(self):
        if self.current_sketch():
            with self.preserve_view():
                Gui.activeDocument().resetEdit()
                App.ActiveDocument.recompute()
                Gui.activateWorkbench('PartWorkbench')
                self.ribbon_tabs.setCurrentIndex(0)
                self.compact()
            self.refresh()

    def rectangle(self):
        v = self.values(tr('長方形スケッチ'), [(tr('幅'),60,0.01),(tr('奥行'),40,0.01)], tr('XY平面に作成。Width / Height 拘束で寸法を編集できます。'))
        if v: self.make(tr('長方形'),model.rectangle,*v)

    def selected_profile(self,multiple=False):
        if self.current_sketch():
            raise ValueError(tr('先にスケッチ編集を終了してください。'))
        obj = self.selection()[0]
        regions = model.profiles(obj)
        selected_edges = [name for sel in Gui.Selection.getSelectionEx() for name in sel.SubElementNames if name.startswith('Edge')]
        if multiple:
            indices = self.region_picker.chosen_many(obj,regions)
            if indices:
                return obj,regions,indices
        region_index = self.region_picker.chosen(obj,regions)
        if region_index is not None:
            index = region_index
        elif selected_edges:
            index = model.profile_for_edges(regions,selected_edges)
        elif len(regions)>1:
            index = 0
        else:
            index = 0
        return obj,regions,index

    def extrude(self):
        self.extrusion.start(*self.selected_profile(multiple=True))

    def revolve(self):
        obj,regions,index = self.selected_profile()
        self.features.start('revolve',obj,regions,index)

    def section_feature(self,kind):
        if self.current_sketch():
            raise ValueError(tr('先にスケッチ編集を終了してください。'))
        doc=App.ActiveDocument
        sketches=[obj for obj in doc.Objects if obj.TypeId=='Sketcher::SketchObject'
                  and not getattr(obj,'FluxCADInternal',False)] if doc else []
        if len(sketches)<2:
            raise ValueError(tr('先にスケッチを2つ以上作成してください。ロフトは断面同士、スイープは断面と経路を使います。'))
        selected=[obj for obj in Gui.Selection.getSelection() if obj in sketches]
        if kind=='sweep' and len(selected)>2:
            raise ValueError(tr('断面、経路の順でスケッチを2つまで選択してください。'))
        self.features.start(kind,selected[0] if selected else sketches[0],sections=selected)

    def pattern(self,kind):
        if self.current_sketch():
            raise ValueError(tr('先にスケッチ編集を終了してください。'))
        from browser import body_owner
        obj = body_owner(self.selection()[0])
        if obj.Shape.isNull() or not obj.Shape.Solids:
            raise ValueError(tr('パターンにするボディを1つ選択してください。'))
        self.features.start(kind,obj)

    def mirror(self):
        if self.current_sketch():
            raise ValueError(tr('先にスケッチ編集を終了してください。'))
        from browser import body_owner
        selected=Gui.Selection.getSelection()
        if not 1<=len(selected)<=2 or any(o.Document!=App.ActiveDocument or not hasattr(o,'Shape') for o in selected):
            raise ValueError(tr('ボディを1つ選択してください。続けて基準面を選択することもできます。',
                                'Select one body, optionally followed by a reference plane.'))
        obj = body_owner(selected[0])
        if obj.Shape.isNull() or not obj.Shape.Solids:
            raise ValueError(tr('ミラーにするボディを1つ選択してください。'))
        if len(selected)==2:
            import model_mirror
            extra=Gui.Selection.getSelectionEx()[1]
            if len(extra.SubElementNames)>1:raise ValueError(tr('基準面は1つ選択してください。','Select one reference plane.'))
            model_mirror.resolve(App.ActiveDocument,extra.ObjectName,next(iter(extra.SubElementNames),''))
        self.features.start('mirror',obj)

    def shell(self):
        if self.current_sketch():
            raise ValueError(tr('先にスケッチ編集を終了してください。'))
        from browser import body_owner
        obj = body_owner(self.selection()[0])
        if obj.Shape.isNull() or len(obj.Shape.Solids)!=1:
            raise ValueError(tr('シェルにする、1つにつながった立体を選択してください。'))
        faces = [name for selected in Gui.Selection.getSelectionEx() for name in selected.SubElementNames if name.startswith('Face')]
        self.features.start('shell',obj,faces=faces)

    def box(self):
        v = self.values(tr('直方体'), [(tr('幅 X'),60,0.01),(tr('奥行 Y'),40,0.01),(tr('高さ Z'),12,0.01)])
        if v: self.make(tr('直方体'),model.box,*v)

    def cylinder(self):
        v = self.values(tr('円柱'), [(tr('半径'),10,0.01),(tr('高さ'),25,0.01)])
        if v: self.make(tr('円柱'),model.cylinder,*v)

    def hole(self):
        self.hole_panel.start()

    def fillet(self):
        self.edge_panel.start('fillet')

    def boolean(self, cut):
        self.combine_panel.start(cut if isinstance(cut,str) else 'cut' if cut else 'join')

    def split_body(self):
        self.split_panel.start()

    def create_component(self):
        self.component_panel.start()

    def duplicate_component(self):
        import model_assembly as assembly
        result=assembly.create_components(self.doc(),Gui.Selection.getSelection(),duplicate=True)
        Gui.Selection.clearSelection()
        for obj in result:Gui.Selection.addSelection(obj)

    def ground_component(self):
        import model_assembly as assembly
        obj=assembly.valid_component(self.selection()[0]);assembly.edit_component(obj,obj.Label,not obj.Grounded)

    def start_joint(self,kind='rigid'):
        selected=Gui.Selection.getSelection()
        existing=selected[0] if len(selected)==1 and getattr(selected[0],'FluxJoint',False) else None
        self.joint_panel.start(kind,existing)

    def release_joint(self):
        import model_assembly as assembly
        selected=Gui.Selection.getSelection()
        if len(selected)!=1:raise ValueError(tr('ジョイントまたは接続された部品を1つ選択してください。','Select one joint or connected component.'))
        obj=selected[0];joint=obj if getattr(obj,'FluxJoint',False) else getattr(obj,'Driver',None)
        if not joint:raise ValueError(tr('接続されたジョイントがありません。','No connected joint was found.'))
        result=assembly.release_joint(joint);Gui.Selection.clearSelection();Gui.Selection.addSelection(result)

    def chamfer(self):
        self.edge_panel.start('chamfer')

    def start_move(self):
        self.drag_move.start()

    def move_copy(self):
        if self.current_sketch():
            raise ValueError(tr('先にスケッチ編集を閉じてください。'))
        import model_mesh
        if any(model_mesh.is_mesh(obj) for obj in Gui.Selection.getSelection()):
            self.edit_mesh('rotate')
        else:
            self.transform.start(Gui.Selection.getSelection())

    def edit_mesh(self,mode='scale'):
        if self.current_sketch():
            raise ValueError(tr('先にスケッチ編集を閉じてください。'))
        panel=self.mesh_ops if mode in ('cut','separate') else self.mesh_edit
        panel.start(Gui.Selection.getSelection(),mode)

    def align(self):
        if self.current_sketch():
            raise ValueError(tr('先にスケッチ編集を閉じてください。'))
        self.alignment.start()

    def move(self):
        if self.drag_move.active:
            self.drag_move.stop()
        if Gui.activeDocument() and Gui.activeDocument().getInEdit():
            raise ValueError(tr('先にスケッチ編集を閉じてください。'))
        doc = App.ActiveDocument
        targets = model.movable_solids(doc,Gui.Selection.getSelection(),allow_mesh=True)
        values = self.values(tr('立体を移動'), [(tr('X方向'),0,-100000),(tr('Y方向'),0,-100000),(tr('Z方向'),0,-100000)],
                             tr('対象：%d個の立体\n原点のX・Y・Z軸に沿った移動量（mm）。逆方向は負の値。') % len(targets))
        if values is None:
            return
        moved = model.move_solids(doc,targets,*values,allow_mesh=True)
        self.region_picker.clear()
        Gui.Selection.clearSelection()
        for obj in moved:
            Gui.Selection.addSelection(obj)
        self.main.statusBar().showMessage(tr('%d個の立体を移動：X %g / Y %g / Z %g mm — Ctrl＋Zで元に戻す') %
                                          (len(moved),*values),10000)
        self.refresh()

    def export(self):
        import model_mesh
        selected = Gui.Selection.getSelection()
        if not selected or any(o.Document!=App.ActiveDocument or
                               not (model_mesh.is_mesh(o) and o.Mesh.CountFacets or hasattr(o,'Shape') and not o.Shape.isNull()) for o in selected):
            raise ValueError(tr('ソリッド・サーフェス・曲線またはメッシュを選択してください。','Select solids, surfaces, curves or meshes.'))
        has_mesh=any(model_mesh.is_mesh(o) for o in selected)
        path, kind = W.QFileDialog.getSaveFileName(self.main,tr('形状を書き出し'),'','STL (*.stl)' if has_mesh else 'STEP (*.step);;STL (*.stl)')
        if not path: return
        ext = '.stl' if kind.startswith('STL') else '.step'
        if not path.lower().endswith(ext): path += ext
        if ext == '.stl':
            if any(not model_mesh.is_mesh(o) and not o.Shape.Faces for o in selected):
                raise ValueError(tr('曲線や点はSTLに含められません。STEPで別に書き出してください。',
                                    'STL cannot contain curves or points. Export them separately as STEP.'))
            model_mesh.export(selected,path)
        else:
            import Import
            Import.export(selected,path)
        self.main.statusBar().showMessage(tr('出力しました：')+path,8000)


def start():
    if hasattr(Gui,'fluxcad_workspace'):
        old = Gui.fluxcad_workspace
        old.restore()
        old.toolbar.deleteLater()
        old.history.deleteLater()
    Gui.fluxcad_workspace = Workspace()
