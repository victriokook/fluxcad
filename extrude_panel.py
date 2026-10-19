"""Non-modal extrusion settings and a temporary, unpickable shape preview."""
from i18n import tr
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets as W
from pivy import coin
import model
import browser
from region_picker import format_region_area


class ExtrudePanel(QtCore.QObject):
    preferred_height = 500
    def __init__(self,ws):
        super().__init__(ws.main)
        self.ws = ws
        self.active = False
        self.closed = False
        self.overlay = None
        self.hidden = []
        self.widgets = []
        self.valid = False
        self.preview_shape = None
        self.panel = W.QFrame(ws.main)
        self.panel.setObjectName('FluxExtrudePanel')
        self.panel.setStyleSheet('QFrame#FluxExtrudePanel {background:#f6f6f6;border:1px solid #b9c9d2;}')
        layout = W.QVBoxLayout(self.panel)
        layout.setContentsMargins(10,8,10,10)
        self.heading = W.QLabel(tr('押し出し'))
        self.heading.setStyleSheet('font-weight:bold;font-size:14px;')
        layout.addWidget(self.heading)
        scroll = W.QScrollArea()
        scroll.setFrameShape(W.QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        content = W.QWidget()
        form = W.QFormLayout(content)
        form.setContentsMargins(0,4,0,4)
        form.setFieldGrowthPolicy(W.QFormLayout.AllNonFixedFieldsGrow)
        self.build_fields(form)
        self.status = W.QLabel()
        self.status.setWordWrap(True)
        form.addRow(self.status)
        hint = W.QLabel(tr('中ボタンで視点操作できます。\n確定するまでモデルには追加しません。'))
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#64727a;')
        form.addRow(hint)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        buttons = W.QHBoxLayout()
        self.accept_button = W.QPushButton(tr('確定'))
        self.accept_button.clicked.connect(self.accept)
        self.cancel_button = W.QPushButton(tr('キャンセル'))
        self.cancel_button.clicked.connect(self.cancel)
        buttons.addWidget(self.accept_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(160)
        self.timer.timeout.connect(self.update_preview)
        for combo in self.combos:
            combo.setSizeAdjustPolicy(W.QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(10)
            combo.currentIndexChanged.connect(self.schedule)
        for spin in self.spins:
            spin.valueChanged.connect(self.schedule)
        ws.main.installEventFilter(self)
        for widget in self.panel.findChildren(W.QWidget):
            widget.installEventFilter(self)
        self.panel.hide()

    def build_fields(self,form):
        self.profile = W.QListWidget()
        self.profile.setMinimumHeight(85)
        self.profile.setMaximumHeight(120)
        self.profile.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Preferred)
        self.profile.setToolTip(tr('チェックを入れた領域をまとめて押し出します。'))
        self.profile.itemChanged.connect(self.schedule)
        form.addRow(tr('領域'),self.profile)
        self.operation = W.QComboBox()
        for text,key in [(tr('新規ボディ'),'new'),(tr('結合'),'join'),(tr('切り取り'),'cut'),(tr('交差部分を残す'),'intersect')]:
            self.operation.addItem(text,key)
        form.addRow(tr('操作'),self.operation)
        self.target = W.QComboBox()
        form.addRow(tr('対象ボディ'),self.target)
        self.direction = W.QComboBox()
        for text,key in [(tr('片側'),'forward'),(tr('逆方向'),'reverse'),(tr('対称（指定距離が全長）'),'symmetric'),(tr('両側（距離を個別指定）'),'two')]:
            self.direction.addItem(text,key)
        form.addRow(tr('方向'),self.direction)
        self.distance = self.spin()
        self.distance.setValue(12)
        self.distance_label = W.QLabel(tr('距離'))
        form.addRow(self.distance_label,self.distance)
        self.second = self.spin()
        self.second.setValue(6)
        self.second_label = W.QLabel(tr('反対側'))
        form.addRow(self.second_label,self.second)
        self.combos = (self.operation,self.target,self.direction)
        self.spins = (self.distance,self.second)

    @staticmethod
    def spin():
        field = W.QDoubleSpinBox()
        field.setRange(.001,100000)
        field.setDecimals(3)
        field.setSuffix(' mm')
        field.setKeyboardTracking(False)
        return field

    def bind(self,widget):
        if widget not in self.widgets:
            self.widgets.append(widget)
            widget.installEventFilter(self)

    def start(self,sketch,regions,index=0):
        self.cancel()
        self.doc = sketch.Document
        self.sketch = sketch
        self.regions = regions
        self.signature = self.ws.region_picker.signature(sketch)
        self.selection = [(sel.ObjectName,tuple(sel.SubElementNames)) for sel in Gui.Selection.getSelectionEx()]
        self.region_selection = list(self.ws.region_picker.selections)
        self.ws.region_picker.ticket += 1
        self.ws.region_picker.clear()
        indices = model.profile_indices(regions,[index] if isinstance(index,int) else index)
        self.profile.clear()
        for i,region in enumerate(regions):
            item = W.QListWidgetItem(tr('領域 %d — %s mm²', 'Region %d — %s mm²')%(i+1,format_region_area(region['face'].Area)))
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setData(QtCore.Qt.UserRole,i)
            item.setCheckState(QtCore.Qt.Checked if i in indices else QtCore.Qt.Unchecked)
            self.profile.addItem(item)
        self.operation.setCurrentIndex(0)
        self.direction.setCurrentIndex(0)
        self.target.clear()
        bodies = [(obj,title) for obj,title in browser.collect(self.doc)[0] if obj.Shape.Solids]
        for obj,title in bodies:
            self.target.addItem(title+' — '+obj.Label,obj.Name)
        tool = model.extrusion_shapes(sketch,regions,indices,self.distance.value())
        for i,(obj,title) in enumerate(bodies):
            if tool.distToShape(model.world_shape(obj))[0]<1e-6:
                self.target.setCurrentIndex(i)
                break
        self.active = True
        self.panel.show()
        self.update_preview()
        self.position()

    def parameters(self):
        target_name = self.target.currentData()
        indices = [self.profile.item(i).data(QtCore.Qt.UserRole) for i in range(self.profile.count())
                   if self.profile.item(i).checkState()==QtCore.Qt.Checked]
        return {'indices':indices,'distance':self.distance.value(),
                'direction':self.direction.currentData(),'second':self.second.value(),
                'operation':self.operation.currentData(),
                'target':self.doc.getObject(target_name) if target_name else None}

    def schedule(self,*args):
        if not self.active:
            return
        self.accept_button.setEnabled(False)
        self.timer.start()

    def clear_preview(self):
        if self.overlay:
            graph,node = self.overlay
            try:
                if graph.findChild(node)>=0:
                    graph.removeChild(node)
            except (RuntimeError,ReferenceError):
                pass
        self.overlay = None
        for obj,visible in self.hidden:
            try:
                if obj.Document:
                    obj.Visibility = visible
            except (RuntimeError,ReferenceError):
                pass
        self.hidden = []
        self.preview_shape = None

    def show_shape(self,shape,operation):
        vertices,triangles = shape.tessellate(.1)
        node = coin.SoSeparator()
        pick = coin.SoPickStyle(); pick.style=coin.SoPickStyle.UNPICKABLE; node.addChild(pick)
        transparency = coin.SoTransparencyType(); transparency.value=coin.SoTransparencyType.SORTED_OBJECT_BLEND
        node.addChild(transparency)
        if operation=='plane':
            light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material = coin.SoMaterial()
        material.diffuseColor = (0.85,0.33,0.20) if operation=='cut' else (0.95,0.62,0.17) if operation=='plane' else (0.22,0.64,0.87)
        material.transparency = .28
        node.addChild(material)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0,len(vertices),[tuple(vertex) for vertex in vertices]); node.addChild(coords)
        normals = []
        for a,b,c in triangles:
            normal = (vertices[b]-vertices[a]).cross(vertices[c]-vertices[a])
            if normal.Length>1e-12: normal.normalize()
            normals.append(tuple(normal))
        binding=coin.SoNormalBinding(); binding.value=coin.SoNormalBinding.PER_FACE; node.addChild(binding)
        normal_node=coin.SoNormal(); normal_node.vector.setValues(0,len(normals),normals); node.addChild(normal_node)
        mesh=coin.SoIndexedFaceSet()
        mesh.coordIndex.setValues(0,len(triangles)*4,[entry for tri in triangles for entry in (*tri,-1)])
        node.addChild(mesh)
        graph=Gui.activeDocument().activeView().getSceneGraph(); graph.addChild(node)
        self.overlay=(graph,node)
        self.preview_shape=shape

    def update_preview(self):
        self.timer.stop()
        if not self.active:
            return
        if App.ActiveDocument!=self.doc:
            self.cancel()
            return
        self.clear_preview()
        self.valid = False
        self.accept_button.setEnabled(False)
        try:
            values = self.parameters()
            two = values['direction']=='two'
            self.distance_label.setText(tr('全長') if values['direction']=='symmetric' else tr('距離'))
            self.second.setVisible(two); self.second_label.setVisible(two)
            self.target.setEnabled(values['operation']!='new')
            if self.ws.region_picker.signature(self.sketch)!=self.signature:
                raise ValueError(tr('スケッチが変更されました。キャンセルして領域を選び直してください。'))
            tool = model.extrusion_shapes(self.sketch,self.regions,values['indices'],values['distance'],values['direction'],values['second'])
            result = model.extrusion_result(tool,values['target'],values['operation'])
            self.show_shape(result,values['operation'])
            if values['operation']!='new':
                target=values['target']
                self.hidden.append((target,bool(target.Visibility)))
                target.Visibility=False
            self.valid = True
            self.accept_button.setEnabled(True)
            self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('%d 領域を選択 / 結果の体積：%.3f mm³\n%s のプレビュー')%
                                (len(values['indices']),result.Volume,self.operation.currentText()))
        except Exception as error:
            self.clear_preview()
            self.status.setStyleSheet('color:#ac3830;')
            self.status.setText(str(error))

    def accept(self):
        if not self.active:
            return
        self.distance.interpretText(); self.second.interpretText()
        self.update_preview()
        if not self.active or not self.valid:
            return
        values = self.parameters()
        self.clear_preview()
        try:
            results = model.create_extrusions(self.doc,self.sketch,**values)
        except Exception as error:
            self.status.setStyleSheet('color:#ac3830;')
            self.status.setText(str(error))
            self.valid=False
            self.accept_button.setEnabled(False)
            return
        self.active=False
        self.panel.hide()
        self.ws.region_picker.clear()
        Gui.Selection.clearSelection()
        for result in results: Gui.Selection.addSelection(result)
        self.ws.refresh()
        self.ws.main.statusBar().showMessage(tr('押し出しを作成しました（%d ボディ）。Ctrl＋Zでまとめて元に戻せます。')%len(results),8000)

    def cancel(self):
        if not self.active:
            return
        self.active=False
        self.valid=False
        self.timer.stop()
        self.clear_preview()
        self.panel.hide()
        if App.ActiveDocument==self.doc:
            Gui.Selection.clearSelection()
            for name,elements in self.selection:
                obj=self.doc.getObject(name)
                if obj:
                    if elements:
                        for element in elements: Gui.Selection.addSelection(obj,element)
                    else: Gui.Selection.addSelection(obj)
            if getattr(self,'region_selection',None):
                self.ws.region_picker.restore(self.region_selection)

    def position(self):
        if not self.active or self.closed:
            return
        doc=Gui.activeDocument()
        if not doc:return
        view=doc.activeView()
        if not hasattr(view,'graphicsView'):return
        # Other tabs may leave a visible 400x300 viewer behind. Only the active
        # viewport determines the available space for this document's panel.
        v=view.graphicsView().viewport(); origin=v.mapTo(self.ws.main,QtCore.QPoint())
        width=min(310,max(1,v.width()-24))
        height=min(self.preferred_height,max(1,v.height()-24))
        top=min(110,max(8,v.height()//6),max(0,v.height()-height-12))
        self.panel.setGeometry(origin.x()+max(0,v.width()-width-12),origin.y()+top,width,height)
        self.panel.raise_()

    def refresh(self):
        if not self.active:
            return
        try:
            if App.ActiveDocument!=self.doc or not self.sketch.Document or self.ws.current_sketch():
                self.cancel()
                return
        except (RuntimeError,ReferenceError):
            self.cancel()
            return
        self.position()

    def eventFilter(self,widget,event):
        if getattr(getattr(self.ws,'cube',None),'forwarding',False):
            return False
        if not self.active:
            return False
        kind=event.type()
        if kind==QtCore.QEvent.Resize:
            QtCore.QTimer.singleShot(0,self.position)
        if kind==QtCore.QEvent.ShortcutOverride and event.key()==QtCore.Qt.Key_Escape:
            event.accept(); return True
        if kind==QtCore.QEvent.KeyPress and event.key()==QtCore.Qt.Key_Escape:
            self.cancel(); return True
        if widget in self.widgets and kind in (QtCore.QEvent.MouseButtonPress,QtCore.QEvent.MouseButtonRelease,QtCore.QEvent.MouseButtonDblClick):
            if event.button()==QtCore.Qt.LeftButton:
                return True
        return False

    def close(self):
        self.cancel()
        self.closed=True
        self.ws.main.removeEventFilter(self)
        for widget in self.widgets:
            try: widget.removeEventFilter(self)
            except RuntimeError: pass
        self.panel.deleteLater()
