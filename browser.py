"""Current bodies and sketches, separate from the native feature history."""
from i18n import tr
import os
import FreeCAD as App
import FreeCADGui as Gui
import model_mesh
from PySide import QtCore, QtGui, QtWidgets as W


def body_owner(obj):
    if obj.isDerivedFrom('PartDesign::Feature'):
        parent = obj.getParentGeoFeatureGroup()
        if parent and parent.isDerivedFrom('PartDesign::Body'):
            return parent
    return obj


def solid_candidate(obj):
    if getattr(obj,'FluxCADInternal',False) or not hasattr(obj,'Shape'):
        return False
    if obj.TypeId=='Sketcher::SketchObject' or obj.TypeId.endswith('ShapeBinder'):
        return False
    if obj.Shape.Solids:
        return True
    if obj.Shape.Faces or obj.Shape.Edges or obj.Shape.Vertexes:
        return False  # Valid open faces/wires belong to Surface/Curve groups.
    if obj.TypeId in ('Part::Extrusion','Part::Revolution','Part::Loft','Part::Sweep') and not obj.Solid:
        return False
    if obj.TypeId=='Part::Offset' and getattr(obj,'FluxSurfaceOffset',False):return bool(obj.Fill)
    if obj.TypeId=='Part::Refine':return bool(obj.Source and obj.Source.Shape.Solids)
    if getattr(obj,'FluxPrimitive',''):return True
    if getattr(obj,'FluxPathPattern',False):return True
    # Keep broken/empty final operations accessible instead of replacing them
    # with earlier solids when a dimension edit causes a recompute error.
    return (getattr(obj,'FluxCombine',False) or getattr(obj,'FluxSplitPart',False) or getattr(obj,'FluxSplit',False) or getattr(obj,'FluxPattern','') or getattr(obj,'FluxExtent',False) or obj.TypeId in ('Part::Box','Part::Cylinder','Part::Cut','Part::Fuse','Part::Revolution',
                          'Part::MultiFuse','Part::Common','Part::Fillet','Part::Chamfer','Part::Mirroring','Part::Thickness',
                          'Part::Loft','Part::Sweep','Part::Scale','PartDesign::Body') or
            (obj.TypeId=='Part::Extrusion' and obj.Solid))


def linked_objects(value):
    if hasattr(value,'Name') and hasattr(value,'Document'):
        yield value
    elif isinstance(value,(list,tuple)):
        for entry in value:
            yield from linked_objects(entry)


def geometry_kind(obj):
    """Non-solid native geometry, excluding sketch and construction helpers."""
    if (getattr(obj,'FluxCADInternal',False) or getattr(obj,'FluxPlane',False) or
        getattr(obj,'FluxConstructionAxis','') or not hasattr(obj,'Shape') or
        obj.TypeId=='Sketcher::SketchObject' or obj.TypeId.endswith('ShapeBinder') or solid_candidate(obj)):
        return None
    import native_tools
    if obj.Shape.Faces or native_tools.can_edit_surface(obj) or (obj.TypeId=='Part::Refine' and obj.Source and obj.Source.Shape.Faces):
        return 'surface'
    if obj.Shape.Edges or obj.Shape.Vertexes:return 'curve'
    return None


def collect(doc):
    """Follow solid-producing inputs, not visibility or arbitrary references."""
    if not doc:
        return [],[],{}
    sketches = [obj for obj in doc.Objects if obj.TypeId=='Sketcher::SketchObject'
                and not getattr(obj,'FluxCADInternal',False)]
    solids = [obj for obj in doc.Objects if solid_candidate(obj) and body_owner(obj)==obj]
    by_name = {obj.Name:obj for obj in solids}
    sources = {}
    for obj in solids:
        names = []
        # Container groups, attachment Support and sketch-on-face references do
        # not consume bodies. Only modeling operands are considered here.
        properties = ['FluxBodySource','Base','Tool','Shapes','Originals','Source','Faces']
        if getattr(obj,'FluxCombine',False):
            properties=['FluxBodySource']+([] if obj.KeepTools else ['Tools'])
        if getattr(obj,'FluxMirror',False):
            properties = []  # A mirror creates a second body; its source remains independent.
        if getattr(obj,'FluxComponent',False):properties=[]  # Instances do not consume their source body.
        if obj.TypeId=='Part::Compound':
            properties.append('Links')
        for prop in properties:
            if prop not in obj.PropertiesList:
                continue
            for source in linked_objects(getattr(obj,prop)):
                source = body_owner(source)
                if source.Document==doc and source.Name in by_name and source!=obj and source.Name not in names:
                    names.append(source.Name)
        sources[obj.Name] = names
    consumed = {name for names in sources.values() for name in names}
    tips = [obj for obj in solids if obj.Name not in consumed and not getattr(obj,'FluxSplit',False)]
    def root(name):
        seen = set()
        while sources[name] and name not in seen:
            seen.add(name)
            name = sources[name][0]
        return name
    order = {obj.Name:index for index,obj in enumerate(solids)}
    roots = sorted({root(obj.Name) for obj in solids},key=order.get)
    numbers = {name:index+1 for index,name in enumerate(roots)}
    tips.sort(key=lambda obj:(order[root(obj.Name)],order[obj.Name]))
    bodies = []
    downstream = {}
    for obj in tips:
        number = numbers[root(obj.Name)]
        title = tr('ボディ %d') % number
        # Branching a feature can legitimately create more than one result.
        if sum(root(other.Name)==root(obj.Name) for other in tips)>1:
            title += '（%s）' % obj.Label
        bodies.append((obj,title))
        stack,seen = [obj.Name],set()
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            downstream.setdefault(name,[]).append((obj,title))
            stack.extend(sources[name])
    return bodies,sketches,downstream


class BrowserTree(W.QTreeWidget):
    visibilityClicked = QtCore.Signal(object)

    def mousePressEvent(self,event):
        item = self.itemAt(event.pos())
        if (event.button()==QtCore.Qt.LeftButton and self.columnAt(event.pos().x())==1
                and item and item.data(0,QtCore.Qt.UserRole)):
            self.visibilityClicked.emit(item)
            event.accept()
            return
        super().mousePressEvent(event)


class Browser(QtCore.QObject):
    def __init__(self,ws):
        super().__init__(ws.main)
        self.ws = ws
        self.items = {}
        self.signature = None
        self.downstream = {}
        self.collapsed = False
        self.closed = False
        self.native_docks = []
        self.params = App.ParamGet('User parameter:BaseApp/Preferences/FluxCAD/Browser')
        self.offset = QtCore.QPoint(self.params.GetInt('X',0),self.params.GetInt('Y',8))
        self.legacy_position = self.params.GetInt('PositionVersion',0)<2 and self.params.GetInt('X',-1)>=0
        self.drag_start = None
        self.dragging = False
        self.panel = W.QFrame(ws.main)
        self.panel.setObjectName('FluxBrowser')
        self.panel.setStyleSheet('''
QFrame#FluxBrowser {background:#f6f6f6;border:1px solid #c9cdd1;}
QTreeWidget {background:#f6f6f6;border:0;font:12px "Yu Gothic UI";outline:0;}
QTreeWidget::item {height:25px;}
QTreeWidget::item:selected {background:#d1eee8;color:#12584d;}
''')
        layout = W.QVBoxLayout(self.panel)
        layout.setContentsMargins(1,1,1,1)
        layout.setSpacing(0)
        self.header = W.QToolButton()
        self.header.setText(tr('▾  ブラウザー'))
        self.header.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.header.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Fixed)
        self.header.setFixedHeight(26)
        self.header.setStyleSheet('text-align:left;background:#eeeeee;border:0;')
        self.header.setCursor(QtCore.Qt.OpenHandCursor)
        self.header.setToolTip(tr('ドラッグで移動／クリックで折りたたみ\n右クリックで左上に戻せます。'))
        self.header.clicked.connect(self.toggle)
        self.header.installEventFilter(self)
        self.header.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.header.customContextMenuRequested.connect(self.header_menu)
        layout.addWidget(self.header)
        self.tree = BrowserTree()
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0,W.QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1,W.QHeaderView.Fixed)
        self.tree.setColumnWidth(1,28)
        self.tree.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setIndentation(16)
        self.tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.tree.itemSelectionChanged.connect(self.select)
        self.tree.itemDoubleClicked.connect(self.activate)
        self.tree.visibilityClicked.connect(self.toggle_visibility)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.context_menu)
        shortcut_class = getattr(W,'QShortcut',None) or QtGui.QShortcut
        self.shortcuts = []
        for key,callback in [('M',ws.start_move),('E',ws.extrude)]:
            shortcut = shortcut_class(QtGui.QKeySequence(key),self.tree)
            shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda cb=callback: ws.safe(cb))
            self.shortcuts.append(shortcut)
        layout.addWidget(self.tree)
        root = os.path.join(os.path.dirname(__file__),'icons')
        self.icons = {name:QtGui.QIcon(os.path.join(root,file+'.svg')) for name,file in
                      [('body','Part_Box'),('sketch','Sketcher_NewSketch'),('mesh','mesh'),('plane','offset-plane'),('axis','construction-axis'),
                       ('component','component'),('joint','revolute-joint'),('slider','slider-joint'),('rigid','rigid-joint'),('measure','measure'),
                       ('surface','surface-patch'),('curve','cross-sections'),('drawing','drawing-page'),('visible','eye'),('hidden','eye-off')]}
        ws.main.installEventFilter(self)
        self.panel.show()

    def compact(self):
        for dock in self.ws.main.findChildren(W.QDockWidget):
            if dock.objectName() in ('Model','Combo View','Tree view') and dock.isVisible():
                if dock not in self.native_docks:
                    self.native_docks.append(dock)
                dock.hide()

    def toggle(self):
        self.collapsed = not self.collapsed
        self.header.setText(('▸' if self.collapsed else '▾')+tr('  ブラウザー'))
        self.tree.setVisible(not self.collapsed)
        self.position()

    def viewport_rect(self):
        viewer = next((widget for widget in self.ws.main.findChildren(W.QWidget)
                       if widget.metaObject().className() in ('Gui::View3DInventorViewer','TechDrawGui::QGVPage') and widget.isVisible()),None)
        if viewer:
            viewport = viewer.viewport()
            return QtCore.QRect(viewport.mapTo(self.ws.main,QtCore.QPoint()),viewport.size())

    def movement_rect(self):
        viewport = self.viewport_rect()
        if viewport is not None:
            # The 3D view may begin to the right of a native dock. The browser
            # is a main-window overlay and can move across that dock as well.
            area = self.ws.main.contentsRect()
            return QtCore.QRect(area.x(),viewport.y(),area.width(),viewport.height())

    def position(self):
        if self.closed:
            return
        area = self.movement_rect()
        if area is None:
            self.panel.hide()
            return
        if self.legacy_position:
            self.offset.setX(self.offset.x()+self.viewport_rect().x()-area.x())
            self.save_position()
        height = 28 if self.collapsed else max(135,28+25*(len(self.items)+self.tree.topLevelItemCount())+8)
        height = min(height,max(28,area.height()-16))
        width = min(270,max(1,area.width()))
        x = max(0,min(self.offset.x(),area.width()-width))
        y = max(8,min(self.offset.y(),area.height()-height-8))
        self.panel.setGeometry(area.x()+x,area.y()+y,width,height)
        if self.ws.drag_move.active and self.panel.geometry().intersects(self.ws.drag_move.panel.geometry()):
            self.panel.hide()
            return
        self.panel.show()
        self.panel.raise_()

    def eventFilter(self,widget,event):
        kind = event.type()
        if widget==self.header:
            if kind==QtCore.QEvent.MouseButtonPress and event.button()==QtCore.Qt.LeftButton:
                self.drag_start = event.globalPosition().toPoint() if hasattr(event,'globalPosition') else event.globalPos()
                self.drag_panel_start = self.panel.pos()
                self.dragging = False
            elif kind==QtCore.QEvent.MouseMove and self.drag_start is not None:
                point = event.globalPosition().toPoint() if hasattr(event,'globalPosition') else event.globalPos()
                delta = point-self.drag_start
                if self.dragging or delta.manhattanLength()>=W.QApplication.startDragDistance():
                    area = self.movement_rect()
                    if area is not None:
                        self.dragging = True
                        self.header.setDown(False)
                        self.header.setCursor(QtCore.Qt.ClosedHandCursor)
                        self.offset = self.drag_panel_start+delta-area.topLeft()
                        self.position()
                    return True
            elif kind==QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.LeftButton:
                dragged = self.finish_drag()
                if dragged:
                    return True  # Moving the panel must not also collapse it.
        if widget==self.ws.main and kind==QtCore.QEvent.WindowDeactivate:
            self.finish_drag()
        if kind==QtCore.QEvent.Resize:
            QtCore.QTimer.singleShot(0,self.position)
        return False

    def finish_drag(self):
        dragged = self.dragging
        self.drag_start = None
        self.dragging = False
        self.header.setCursor(QtCore.Qt.OpenHandCursor)
        if dragged:
            self.header.setDown(False)
            area = self.movement_rect()
            if area is not None:
                self.offset = self.panel.pos()-area.topLeft()
                self.save_position()
        return dragged

    def save_position(self):
        self.legacy_position = False
        self.params.SetInt('PositionVersion',2)
        self.params.SetInt('X',self.offset.x())
        self.params.SetInt('Y',self.offset.y())

    def reset_position(self):
        self.finish_drag()
        self.offset = QtCore.QPoint(0,8)
        self.save_position()
        self.position()

    def header_menu(self,point):
        menu = W.QMenu(self.header)
        reset = menu.addAction(tr('左上に戻す'))
        if menu.exec_(self.header.mapToGlobal(point))==reset:
            self.reset_position()

    def refresh(self):
        doc = App.ActiveDocument
        bodies,sketches,self.downstream = collect(doc)
        planes=[obj for obj in doc.Objects if getattr(obj,'FluxPlane',False) or getattr(obj,'FluxConstructionAxis','')] if doc else []
        meshes=[obj for obj in doc.Objects if model_mesh.is_mesh(obj)] if doc else []
        measurements=[obj for obj in doc.Objects if obj.TypeId.startswith('Measure::')] if doc else []
        import drawing
        drawings=[obj for obj in doc.Objects if drawing.is_drawing(obj)] if doc else []
        geometry=[(obj,geometry_kind(obj)) for obj in doc.Objects] if doc else []
        surfaces=[obj for obj,kind in geometry if kind=='surface'];curves=[obj for obj,kind in geometry if kind=='curve']
        import model_assembly as assembly
        components=assembly.components(doc);joints=assembly.joints(doc)
        bodies=[(o,t) for o,t in bodies if not getattr(o,'FluxComponent',False)]
        component_entries=[(o,o.Label+(tr(' [接地]',' [Grounded]') if o.Grounded else '')) for o in components]
        joint_entries=[(o,o.Label+' — '+getattr(assembly.follower_of(o),'Label','?')+' → '+getattr(o.Target,'Label','?')) for o in joints]
        component_entries=[(o,('⚠ ' if getattr(o,'AssemblyError','') else '')+t) for o,t in component_entries]
        joint_entries=[(o,('⚠ ' if getattr(o,'AssemblyError','') else '')+t) for o,t in joint_entries]
        signature = (doc.Name if doc else None,tuple((obj.Name,title,obj.Label) for obj,title in bodies),
                     tuple((obj.Name,obj.Label) for obj in sketches),tuple((obj.Name,obj.Label) for obj in planes),
                     tuple((obj.Name,obj.Label) for obj in meshes),tuple((o.Name,t) for o,t in component_entries+joint_entries),
                     tuple((obj.Name,obj.Label) for obj in measurements),tuple((obj.Name,obj.Label,kind) for obj,kind in geometry if kind),
                     tuple((obj.Name,obj.Label,getattr(drawing.page_of(obj),'Name','')) for obj in drawings))
        self.tree.blockSignals(True)
        try:
            if signature!=self.signature:
                same_doc = self.signature and signature[0]==self.signature[0]
                expanded = [self.tree.topLevelItem(i).isExpanded() for i in range(self.tree.topLevelItemCount())]
                scroll = self.tree.verticalScrollBar().value()
                self.signature = signature
                self.tree.clear()
                self.items = {}
                groups=[
                        (tr('ボディ'),bodies,'body'),(tr('スケッチ','Sketches'),[(obj,obj.Label) for obj in sketches],'sketch'),
                        (tr('構築','Construction'),[(obj,obj.Label) for obj in planes],'plane'),
                        (tr('メッシュ','Meshes'),[(obj,obj.Label) for obj in meshes],'mesh')]
                if components or joints:groups.extend([(tr('コンポーネント','Components'),component_entries,'component'),(tr('ジョイント','Joints'),joint_entries,'joint')])
                if measurements:groups.append((tr('計測','Measurements'),[(obj,obj.Label) for obj in measurements],'measure'))
                if surfaces:groups.append((tr('サーフェス','Surfaces'),[(obj,obj.Label) for obj in surfaces],'surface'))
                if curves:groups.append((tr('曲線','Curves'),[(obj,obj.Label) for obj in curves],'curve'))
                if drawings:groups.append((tr('図面','Drawings'),[(obj,obj.Label) for obj in drawings],'drawing'))
                for index,(title,entries,icon) in enumerate(groups):
                    group = W.QTreeWidgetItem(self.tree,[title+'（%d）'%len(entries)])
                    group.setFlags(QtCore.Qt.ItemIsEnabled)
                    font = group.font(0); font.setBold(True); group.setFont(0,font)
                    for obj,label in entries:
                        item = W.QTreeWidgetItem(group,[label])
                        item.setData(0,QtCore.Qt.UserRole,obj.Name)
                        item.setIcon(0,self.icons['axis' if getattr(obj,'FluxConstructionAxis','') else icon])
                        self.items[obj.Name] = item
                    group.setExpanded(expanded[index] if same_doc and index<len(expanded) else True)
                for obj in drawings:
                    import drawing_detail
                    parent=drawing_detail.hatch_parent(obj) or next((o for o in obj.InList if o.TypeId==drawing.GROUP),None) or drawing.page_of(obj)
                    if parent and parent!=obj and parent.Name in self.items:
                        item=self.items[obj.Name];old=item.parent();old.takeChild(old.indexOfChild(item));self.items[parent.Name].addChild(item)
                        self.items[parent.Name].setExpanded(True)
                if same_doc:
                    self.tree.verticalScrollBar().setValue(scroll)
            selected = {body_owner(obj).Name for obj in Gui.Selection.getSelection() if obj.Document==doc}
            for name,item in self.items.items():
                obj = doc.getObject(name)
                visible = bool(obj.Visibility)
                item.setIcon(1,self.icons['visible' if visible else 'hidden'])
                item.setToolTip(1,tr('クリックで')+(tr('非表示') if visible else tr('表示','Show')))
                item.setForeground(0,QtGui.QBrush(QtGui.QColor('#303740' if visible else '#92989e')))
                item.setSelected(name in selected)
                sketch = obj.TypeId=='Sketcher::SketchObject'
                info = (tr('回転・円形パターンの基準に選択。ダブルクリックで軸を編集。','Select as a Revolve or Circular Pattern reference. Double-click to edit the axis.') if getattr(obj,'FluxConstructionAxis','') else tr('ダブルクリックでスケッチを編集') if sketch else tr('選択して「スケッチを作成」。ダブルクリックで平面を編集。') if getattr(obj,'FluxPlane',False)
                        else tr('Mで移動。ダブルクリックでサイズ変更。Ctrlで複数選択。','M to move. Double-click to resize. Ctrl-click to select multiple meshes.') if model_mesh.is_mesh(obj)
                        else tr('ダブルクリックで分割位置を編集。Mで移動。','Double-click to edit the split. M to move.') if getattr(obj,'FluxSplitPart',False)
                        else tr('ダブルクリックでミラーの基準面を編集。Mで移動。','Double-click to edit the mirror plane. M to move.') if getattr(obj,'FluxMirror',False)
                        else tr('ダブルクリックで操作と工具を編集。Mで移動。','Double-click to edit the operation and tools. M to move.') if getattr(obj,'FluxCombine',False)
                        else tr('ダブルクリックで穴を編集。Mで移動。','Double-click to edit the hole. M to move.') if getattr(obj,'FluxHole',False)
                        else tr('ダブルクリックで寸法と位置を編集。Mで移動。','Double-click to edit dimensions and position. M to move.') if getattr(obj,'FluxPrimitive','')
                        else tr('ダブルクリックで経路・個数・間隔・向きを編集。Mで移動。','Double-click to edit path, quantity, distance and orientation. M to move.') if getattr(obj,'FluxPathPattern',False)
                        else tr('ダブルクリックで押し出しを編集。Mで移動。','Double-click to edit the extrusion. M to move.') if getattr(obj,'FluxExtent',False)
                        else tr('ダブルクリックで辺と寸法を編集。Mで移動。','Double-click to edit edges and dimensions. M to move.') if obj.TypeId in ('Part::Fillet','Part::Chamfer')
                        else tr('現在の形状：')+obj.Label+tr('\n選択して M で移動。Ctrlで複数選択。'))
                item.setToolTip(0,info+(tr('\n非表示です。右の目のアイコンで表示。') if not visible else ''))
                if obj.TypeId=='Part::Scale':
                    item.setToolTip(0,tr('ダブルクリックで尺度の倍率を編集。元形状は履歴に残ります。',
                                         'Double-click to edit scale factors. The source remains in the history.'))
                if getattr(obj,'FluxSurfaceOffset',False):
                    item.setToolTip(0,tr('ダブルクリックでオフセット距離・厚み・角の接続を編集。',
                                         'Double-click to edit offset distance, thickness or corner join.'))
                if obj.TypeId.startswith('Measure::'):
                    item.setToolTip(0,tr('保存した計測。ダブルクリックで数値を表示。右クリックで削除できます。',
                                         'Saved measurement. Double-click for values; right-click to delete.'))
                if drawing.is_drawing(obj):
                    item.setToolTip(0,tr('ダブルクリックで図面を開く／投影図・寸法・注記を編集。','Double-click to open the sheet or edit a view, dimension or note.'))
                    if obj.TypeId==drawing.PAGE:item.setIcon(1,QtGui.QIcon());item.setToolTip(1,'')
                if geometry_kind(obj):
                    item.setToolTip(0,tr('曲面・断面線。辺を選んで曲面作成や計測に使用できます。右クリックで表示・外観・出力。',
                                         'Surface or section curve. Select edges for surface creation or measurement. Right-click for visibility, appearance and export.'))
                    import native_tools
                    if native_tools.can_edit_surface(obj):
                        item.setToolTip(0,item.toolTip(0)+tr('\nダブルクリックでサーフェスの設定を再編集。','\nDouble-click to edit surface settings.'))
                if getattr(obj,'FluxComponent',False):
                    item.setToolTip(0,tr('ダブルクリックで名前・接地を編集。元形状：','Double-click to edit name/grounding. Source: ')+getattr(obj.Source,'Label','?'))
                if getattr(obj,'FluxJoint',False):
                    item.setIcon(1,QtGui.QIcon());item.setToolTip(1,'')
                    linear=str(obj.Kind)=='slider'
                    item.setIcon(0,self.icons['slider' if linear else 'rigid' if str(obj.Kind)=='rigid' else 'joint'])
                    item.setToolTip(0,tr('ダブルクリックでジョイントと移動距離を編集。','Double-click to edit the joint and distance.')+'\n'+str(obj.Distance) if linear else
                                   tr('ダブルクリックでジョイントと角度を編集。','Double-click to edit the joint and angle.')+'\n'+str(obj.Angle))
                if getattr(obj,'AssemblyError',''):
                    item.setForeground(0,QtGui.QBrush(QtGui.QColor('#ac3830')))
                    item.setToolTip(0,item.toolTip(0)+'\n'+obj.AssemblyError)
        finally:
            self.tree.blockSignals(False)
        for shortcut in self.shortcuts:
            shortcut.setEnabled(self.ws.current_sketch() is None)
        self.position()

    def select(self):
        for panel in (self.ws.component_panel,self.ws.joint_panel,self.ws.primitive_panel,self.ws.path_pattern_panel,self.ws.construction_panel,self.ws.construction_axis_panel):
            if panel is self.ws.construction_panel and panel.active and panel.kind=='along_path' and panel.picking=='reference_a':continue
            if panel.active:panel.cancel()
        if self.ws.combine_panel.active:
            self.ws.combine_panel.cancel()
        if self.ws.split_panel.active:
            self.ws.split_panel.cancel()
        if self.ws.current_sketch():
            return  # Do not replace Sketcher's edge/vertex selection.
        if self.ws.edge_panel.active:
            self.ws.edge_panel.cancel()
        if self.ws.extrusion.active:
            self.ws.extrusion.cancel()
        if self.ws.features.active and not (self.ws.features.axis_picking or self.ws.features.mirror_picking):
            self.ws.features.cancel()
        if self.ws.transform.active:
            self.ws.transform.cancel()
        if self.ws.alignment.active:
            self.ws.alignment.cancel()
        if self.ws.mesh_edit.active:
            self.ws.mesh_edit.cancel()
        if self.ws.mesh_ops.active:
            self.ws.mesh_ops.cancel()
        if self.ws.hole_panel.active:
            self.ws.hole_panel.cancel()
        if self.ws.drag_move.active:
            self.ws.drag_move.stop()
        doc = App.ActiveDocument
        if not doc:
            return
        names = [item.data(0,QtCore.Qt.UserRole) for item in self.tree.selectedItems()]
        previous = [obj for obj in Gui.Selection.getSelection() if obj.Document==doc and obj.Name in names]
        added = [doc.getObject(name) for name in names if name not in {obj.Name for obj in previous}]
        self.ws.region_picker.clear()
        Gui.Selection.clearSelection()
        for obj in previous+added:
            if obj:
                Gui.Selection.addSelection(obj)

    def object(self,item):
        doc = App.ActiveDocument
        return doc.getObject(item.data(0,QtCore.Qt.UserRole)) if doc and item and item.data(0,QtCore.Qt.UserRole) else None

    def toggle_visibility(self,item):
        obj = self.object(item)
        if obj and obj.TypeId=='TechDraw::DrawPage':return
        if not obj or self.ws.current_sketch() or getattr(obj,'FluxJoint',False):
            return
        def apply():
            obj.Visibility = not obj.Visibility
            self.refresh()
        self.ws.safe(apply)

    def activate(self,item,column=0):
        obj = self.object(item)
        if obj and column==0 and not self.ws.current_sketch():
            import drawing
            if drawing.is_drawing(obj):
                self.ws.safe(lambda:drawing.show(self.ws,obj) if obj.TypeId==drawing.PAGE else drawing.edit(self.ws,obj));return
            import native_tools
            if native_tools.can_edit_surface(obj):
                self.ws.safe(lambda:native_tools.edit_surface(self.ws,obj));return
            if obj.TypeId.startswith('Measure::'):
                import native_tools
                self.ws.safe(lambda:native_tools.measurement_details(self.ws,obj));return
            if obj.TypeId=='Part::Scale':
                import native_tools
                self.ws.safe(lambda:native_tools.edit_scale(self.ws,obj));return
            if getattr(obj,'FluxConstructionAxis',''):
                self.ws.safe(lambda:self.ws.construction_axis_panel.start(existing=obj));return
            if getattr(obj,'FluxConstructionPlane',''):
                self.ws.safe(lambda:self.ws.construction_panel.start(existing=obj));return
            if getattr(obj,'FluxPrimitive',''):
                self.ws.safe(lambda:self.ws.primitive_panel.start(existing=obj));return
            if getattr(obj,'FluxPathPattern',False):
                self.ws.safe(lambda:self.ws.path_pattern_panel.start(existing=obj));return
            if getattr(obj,'FluxComponent',False):
                self.ws.safe(lambda:self.ws.component_panel.start(existing=obj));return
            if getattr(obj,'FluxJoint',False):
                self.ws.safe(lambda:self.ws.joint_panel.start(existing=obj));return
        if obj and column==0 and getattr(obj,'FluxCombine',False) and not self.ws.current_sketch():
            self.ws.safe(lambda:self.ws.combine_panel.start(existing=obj))
            return
        if obj and column==0 and getattr(obj,'FluxMirror',False) and not self.ws.current_sketch():
            self.ws.safe(lambda:self.ws.features.start('mirror',obj.Source,existing=obj))
            return
        if obj and column==0 and getattr(obj,'FluxSplitPart',False) and not self.ws.current_sketch():
            self.ws.safe(lambda:self.ws.split_panel.start(existing=obj))
            return
        if obj and column==0 and obj.TypeId in ('Part::Fillet','Part::Chamfer') and not self.ws.current_sketch():
            self.ws.safe(lambda:self.ws.edge_panel.start(existing=obj))
            return
        if obj and column==0 and getattr(obj,'FluxExtent',False) and not self.ws.current_sketch():
            self.ws.safe(lambda:self.ws.extrusion.start(existing=obj))
            return
        if obj and column==0 and getattr(obj,'FluxHole',False) and not self.ws.current_sketch():
            self.ws.safe(lambda:self.ws.hole_panel.start(existing=obj))
            return
        if model_mesh.is_mesh(obj) and column==0 and not self.ws.current_sketch():
            def resize():
                Gui.Selection.clearSelection();Gui.Selection.addSelection(obj);self.ws.edit_mesh('scale')
            self.ws.safe(resize)
            return
        if obj and column==0 and getattr(obj,'FluxPlane',False) and not self.ws.current_sketch():
            self.ws.safe(lambda:self.ws.features.start('plane',obj,existing=obj))
            return
        if not obj or column!=0 or obj.TypeId!='Sketcher::SketchObject':
            return
        def edit():
            current = self.ws.current_sketch()
            if current and current!=obj:
                self.ws.finish_sketch()
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(obj)
            self.ws.edit_sketch()
        self.ws.safe(edit)

    def context_menu(self,point):
        item = self.tree.itemAt(point)
        obj = self.object(item)
        if not obj or self.ws.current_sketch():
            return
        menu = W.QMenu(self.tree)
        import drawing
        if drawing.is_drawing(obj):
            open_action=menu.addAction(tr('図面を開く','Open Drawing'))
            edit_action=menu.addAction(tr('編集','Edit'))
            pdf_action=menu.addAction(tr('PDF出力…','Export PDF…'))
            chosen=menu.exec_(self.tree.viewport().mapToGlobal(point))
            if chosen==open_action:self.ws.safe(lambda:drawing.show(self.ws,drawing.page_of(obj)))
            elif chosen==edit_action:self.ws.safe(lambda:drawing.edit(self.ws,obj))
            elif chosen==pdf_action:
                Gui.Selection.clearSelection();Gui.Selection.addSelection(obj);self.ws.safe(lambda:drawing.export_page(self.ws,'pdf'))
            return
        visibility = menu.addAction(tr('非表示') if obj.Visibility else tr('表示','Show'))
        if obj.TypeId.startswith('Measure::'):
            details=menu.addAction(tr('計測値を表示','Show Measurement Values'))
            remove=menu.addAction(tr('計測を削除','Delete Measurement'))
            chosen=menu.exec_(self.tree.viewport().mapToGlobal(point))
            if chosen==visibility:self.toggle_visibility(item)
            elif chosen==details:self.activate(item)
            elif chosen==remove:
                import native_tools
                self.ws.safe(lambda:native_tools.delete_measurement(obj))
            return
        if geometry_kind(obj):
            import native_tools
            edit=menu.addAction(tr('サーフェスを編集','Edit Surface')) if native_tools.can_edit_surface(obj) else None
            appearance=menu.addAction(tr('外観','Appearance'))
            measure=menu.addAction(tr('計測','Measure'))
            export=menu.addAction(tr('エクスポート…','Export…'))
            chosen=menu.exec_(self.tree.viewport().mapToGlobal(point))
            if chosen is None:return
            if chosen==visibility:self.toggle_visibility(item);return
            if chosen==edit:self.activate(item);return
            Gui.Selection.clearSelection();Gui.Selection.addSelection(obj)
            if chosen==appearance:self.ws.safe(lambda:native_tools.start(self.ws,'appearance'))
            elif chosen==measure:self.ws.safe(lambda:native_tools.start(self.ws,'native_measure'))
            elif chosen==export:self.ws.safe(self.ws.export)
            return
        component=getattr(obj,'FluxComponent',False);joint=getattr(obj,'FluxJoint',False)
        if joint:visibility.setEnabled(False)
        plane=getattr(obj,'FluxPlane',False);axis=getattr(obj,'FluxConstructionAxis','')
        create=menu.addAction(tr('スケッチを作成')) if plane else None
        edit = menu.addAction(tr('ジョイントを編集','Edit Joint') if joint else tr('コンポーネントを編集','Edit Component') if component else tr('軸を編集','Edit Axis') if axis else tr('平面を編集') if plane else tr('スケッチを編集') if obj.TypeId=='Sketcher::SketchObject' else tr('移動…'))
        duplicate=menu.addAction(tr('コンポーネントを複製','Duplicate Component')) if component else None
        ground=menu.addAction(tr('接地を解除','Unground') if obj.Grounded else tr('接地','Ground')) if component else None
        release=menu.addAction(tr('ジョイントを解除','Release Joint')) if joint or (component and obj.Driver) else None
        rotate=menu.addAction(tr('回転…','Rotate…')) if model_mesh.is_mesh(obj) else None
        resize=menu.addAction(tr('サイズ変更…','Resize…')) if model_mesh.is_mesh(obj) else None
        separate=menu.addAction(tr('部品を分離…','Separate Parts…')) if model_mesh.is_mesh(obj) else None
        cut=menu.addAction(tr('平面で切断…','Plane Cut…')) if model_mesh.is_mesh(obj) else None
        hole_edit=menu.addAction(tr('穴を編集…','Edit Hole…')) if getattr(obj,'FluxHole',False) else None
        thickness_edit=menu.addAction(tr('厚みを編集…','Edit Thickness…')) if getattr(obj,'FluxSurfaceOffset',False) else None
        primitive_edit=menu.addAction(tr('寸法と位置を編集…','Edit Dimensions and Position…')) if getattr(obj,'FluxPrimitive','') else None
        path_edit=menu.addAction(tr('パスのパターンを編集…','Edit Pattern on Path…')) if getattr(obj,'FluxPathPattern',False) else None
        extent_edit=menu.addAction(tr('押し出しを編集…','Edit Extrusion…')) if getattr(obj,'FluxExtent',False) else None
        edge_edit=menu.addAction(tr('辺と寸法を編集…','Edit Edges and Dimensions…')) if obj.TypeId in ('Part::Fillet','Part::Chamfer') else None
        split_edit=menu.addAction(tr('分割位置を編集…','Edit Split…')) if getattr(obj,'FluxSplitPart',False) else None
        combine_edit=menu.addAction(tr('操作と工具を編集…','Edit Operation and Tools…')) if getattr(obj,'FluxCombine',False) else None
        mirror_edit=menu.addAction(tr('ミラーの基準面を編集…','Edit Mirror Plane…')) if getattr(obj,'FluxMirror',False) else None
        chosen = menu.exec_(self.tree.viewport().mapToGlobal(point))
        if chosen is None:return
        if chosen in [a for a in (duplicate,ground,release) if a is not None]:
            def manage():
                Gui.Selection.clearSelection();Gui.Selection.addSelection(obj)
                if chosen==duplicate:self.ws.duplicate_component()
                elif chosen==ground:self.ws.ground_component()
                else:self.ws.release_joint()
            self.ws.safe(manage)
        elif chosen==visibility:
            self.toggle_visibility(item)
        elif primitive_edit is not None and chosen==primitive_edit:
            self.ws.safe(lambda:self.ws.primitive_panel.start(existing=obj))
        elif path_edit is not None and chosen==path_edit:
            self.ws.safe(lambda:self.ws.path_pattern_panel.start(existing=obj))
        elif combine_edit is not None and chosen==combine_edit:
            self.ws.safe(lambda:self.ws.combine_panel.start(existing=obj))
        elif mirror_edit is not None and chosen==mirror_edit:
            self.ws.safe(lambda:self.ws.features.start('mirror',obj.Source,existing=obj))
        elif split_edit is not None and chosen==split_edit:
            self.ws.safe(lambda:self.ws.split_panel.start(existing=obj))
        elif hole_edit is not None and chosen==hole_edit:
            self.ws.safe(lambda:self.ws.hole_panel.start(existing=obj))
        elif thickness_edit is not None and chosen==thickness_edit:
            self.activate(item)
        elif extent_edit is not None and chosen==extent_edit:
            self.ws.safe(lambda:self.ws.extrusion.start(existing=obj))
        elif edge_edit is not None and chosen==edge_edit:
            self.ws.safe(lambda:self.ws.edge_panel.start(existing=obj))
        elif chosen is not None and chosen in (rotate,resize,separate,cut):
            if not item.isSelected():
                self.tree.clearSelection();item.setSelected(True)
            mode='rotate' if chosen==rotate else 'scale' if chosen==resize else 'separate' if chosen==separate else 'cut'
            self.ws.safe(lambda:self.ws.edit_mesh(mode))
        elif create is not None and chosen==create:
            Gui.Selection.clearSelection();Gui.Selection.addSelection(obj);self.ws.safe(self.ws.sketch)
        elif chosen==edit:
            if component or joint or plane or axis or obj.TypeId=='Sketcher::SketchObject':
                self.activate(item)
            else:
                if not item.isSelected():
                    self.tree.clearSelection()
                    item.setSelected(True)
                self.ws.safe(self.ws.start_move)

    def close(self):
        self.finish_drag()
        self.closed = True
        self.ws.main.removeEventFilter(self)
        self.panel.hide()
        self.panel.deleteLater()
        for dock in self.native_docks:
            try: dock.show()
            except RuntimeError: pass
