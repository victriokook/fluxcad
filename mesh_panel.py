"""Mesh size and rotation preview using cached triangles, never a BRep conversion."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets as W
from pivy import coin
from i18n import tr
from extrude_panel import ExtrudePanel
from transform_panel import TransformPanel
import model_mesh as meshes
import model_transform


class MeshPanel(ExtrudePanel):
    preferred_height=555

    def build_fields(self,form):
        self.rows={}
        def row(key,title,widget):
            label=W.QLabel(title);form.addRow(label,widget);self.rows[key]=(label,widget);return widget
        self.summary=W.QLabel();self.summary.setWordWrap(True)
        self.summary.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Preferred);form.addRow(self.summary)
        self.mode=row('mode',tr('操作'),W.QComboBox())
        self.mode.addItem(tr('サイズ変更','Resize'),'scale');self.mode.addItem(tr('回転','Rotate'),'rotate')
        self.uniform=W.QCheckBox(tr('縦横比を固定','Lock proportions'));self.uniform.setChecked(True)
        row('uniform','',self.uniform);self.uniform.toggled.connect(self.lock_changed)
        self.factor=row('factor',tr('倍率','Scale factor'),TransformPanel.number(' ×',.000001,1e6))
        self.factor.setValue(1);self.factor.valueChanged.connect(self.factor_changed)
        self.sizes=[row('size'+a,a+tr('寸法',' size'),TransformPanel.number(' mm',.000001,1e9)) for a in 'XYZ']
        for i,field in enumerate(self.sizes):field.valueChanged.connect(lambda value,index=i:self.size_changed(index,value))
        self.axis=row('axis',tr('軸（全体座標）'),W.QComboBox());self.axis.addItems(['X','Y','Z']);self.axis.setCurrentText('Z')
        self.angle=row('angle',tr('角度'),TransformPanel.number(' °',-360,360));self.angle.setSingleStep(15)
        self.pivot=row('pivot',tr('基準点','Pivot'),W.QComboBox())
        for label,key in [(tr('選択全体の中心'),'selection'),(tr('原点'),'origin'),(tr('座標を指定'),'custom')]:self.pivot.addItem(label,key)
        self.center=[row('center'+a,tr('中心 ')+a,TransformPanel.number()) for a in 'XYZ']
        note=W.QLabel(tr('寸法は全体のX・Y・Z軸方向の外形寸法です。複数選択時は全体を一緒に変更します。',
                            'Sizes are the overall bounds along the world X, Y and Z axes. Multiple meshes transform together.'))
        note.setWordWrap(True);note.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Preferred);form.addRow(note)
        self.combos=(self.mode,self.axis,self.pivot)
        self.spins=(*self.sizes,self.factor,self.angle,*self.center)

    def set_number(self,field,value):
        field.blockSignals(True);field.setValue(value);field.blockSignals(False)

    def factor_changed(self,value):
        if not self.active:return
        for field,length in zip(self.sizes,self.lengths):self.set_number(field,length*value)
        self.schedule()

    def size_changed(self,index,value):
        if not self.active or not self.uniform.isChecked() or self.lengths[index]<1e-9:return
        self.set_number(self.factor,value/self.lengths[index]);self.factor_changed(self.factor.value())

    def lock_changed(self,checked):
        if self.active:
            if checked:
                index=next(i for i,length in enumerate(self.lengths) if length>1e-9)
                self.size_changed(index,self.sizes[index].value())
            self.schedule()

    def start(self,objects,mode='scale'):
        self.cancel();self.doc=App.ActiveDocument;self.targets=meshes.targets(self.doc,objects)
        self.selection=[(sel.ObjectName,tuple(sel.SubElementNames)) for sel in Gui.Selection.getSelectionEx()]
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.sources=[meshes.world_mesh(obj) for obj in self.targets]
        bbox=App.BoundBox()
        for mesh in self.sources:bbox.add(mesh.BoundBox)
        self.lengths=(bbox.XLength,bbox.YLength,bbox.ZLength);self.group_center=tuple(bbox.Center)
        self.poses=[str(obj.getGlobalPlacement()) for obj in self.targets]
        self.dirty=False;self.observing=True;App.addDocumentObserver(self)
        self.mode.setCurrentIndex(self.mode.findData(mode));self.pivot.setCurrentIndex(0)
        self.uniform.setChecked(True);self.factor.setValue(1);self.angle.setValue(0)
        for field,value in zip(self.sizes,self.lengths):self.set_number(field,value)
        for field,value in zip(self.center,self.group_center):self.set_number(field,value)
        self.heading.setText(tr('メッシュを変更','Transform Mesh'))
        self.summary.setText(tr('対象：%d メッシュ / %s 三角形','Selected: %d meshes / %s triangles')%
                             (len(self.targets),format(sum(m.CountFacets for m in self.sources),',')))
        self.active=True
        try:self.build_preview();self.panel.show();self.update_preview();self.position()
        except Exception:self.cancel();raise

    def slotChangedObject(self,obj,prop):
        if self.active and obj in self.targets and prop in ('Mesh','Placement'):self.dirty=True

    def stale(self):
        return self.dirty or self.poses!=[str(obj.getGlobalPlacement()) for obj in self.targets]

    def build_preview(self):
        self.clear_preview()
        node=coin.SoSeparator();pick=coin.SoPickStyle();pick.style=coin.SoPickStyle.UNPICKABLE;node.addChild(pick)
        self.matrix_node=coin.SoMatrixTransform();node.addChild(self.matrix_node)
        material=coin.SoMaterial();material.diffuseColor=(.3,.66,.86);node.addChild(material)
        # Store triangles only once per operation; number edits update one matrix.
        for mesh in self.sources:
            vertices,triangles=mesh.Topology;branch=coin.SoSeparator()
            coords=coin.SoCoordinate3();coords.point.setValues(0,len(vertices),[tuple(v) for v in vertices]);branch.addChild(coords)
            faces=coin.SoIndexedFaceSet();faces.coordIndex.setValues(0,len(triangles)*4,[v for tri in triangles for v in (*tri,-1)])
            branch.addChild(faces);node.addChild(branch)
        graph=Gui.activeDocument().activeView().getSceneGraph();graph.addChild(node);self.overlay=(graph,node)
        for obj in self.targets:self.hidden.append((obj,bool(obj.Visibility)));obj.Visibility=False

    def parameters(self):
        pivot=self.pivot.currentData()
        center=self.group_center if pivot=='selection' else (0,0,0) if pivot=='origin' else tuple(f.value() for f in self.center)
        if self.mode.currentData()=='rotate':
            return dict(rotation=model_transform.transform(mode='rotate',axis=self.axis.currentText(),angle=self.angle.value(),center=center))
        factors=(self.factor.value(),)*3 if self.uniform.isChecked() else tuple(field.value()/length if length>1e-9 else 1 for field,length in zip(self.sizes,self.lengths))
        return dict(factors=factors,center=center)

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.valid=False;self.accept_button.setEnabled(False)
        rotate=self.mode.currentData()=='rotate'
        for key,pair in self.rows.items():
            visible=(rotate if key in ('angle','axis') else not rotate if key.startswith('size') or key in ('factor','uniform')
                     else self.pivot.currentData()=='custom' if key.startswith('center') else True)
            for widget in pair:widget.setVisible(visible)
        self.factor.setEnabled(self.uniform.isChecked())
        for field,length in zip(self.sizes,self.lengths):field.setEnabled(length>1e-9)
        for field,value in zip(self.center,self.group_center if self.pivot.currentData()=='selection' else (0,0,0)):
            field.setEnabled(self.pivot.currentData()=='custom')
            if not field.isEnabled():self.set_number(field,value)
        try:
            if self.stale():
                self.clear_preview()
                raise ValueError(tr('対象メッシュが変更されました。キャンセルして選び直してください。','The mesh changed. Cancel and select it again.'))
            values=self.parameters()
            matrix=values['rotation'].toMatrix() if rotate else meshes.scaling(**values)
            # Coin uses row vectors; transpose FreeCAD's column-vector matrix.
            self.matrix_node.matrix.setValue(*(getattr(matrix,'A%d%d'%(j+1,i+1)) for i in range(4) for j in range(4)))
            changed=abs(self.angle.value())>1e-10 if rotate else any(abs(f-1)>1e-10 for f in values['factors'])
            self.valid=changed;self.accept_button.setEnabled(changed);self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('角度または寸法を指定し、確定してください。','Enter an angle or size, then confirm.'))
        except Exception as error:self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def unobserve(self):
        if getattr(self,'observing',False):App.removeDocumentObserver(self);self.observing=False

    def cancel(self):
        self.unobserve();super().cancel();self.sources=[]

    def accept(self):
        if not self.active:return
        for field in self.spins:field.interpretText()
        self.update_preview()
        if not self.valid:return
        values=self.parameters();self.clear_preview();self.unobserve()
        try:results=meshes.apply(self.doc,self.targets,**values)
        except Exception as error:
            self.status.setText(str(error));self.valid=False;self.accept_button.setEnabled(False)
            self.dirty=True;return
        self.active=False;self.panel.hide();self.sources=[];Gui.Selection.clearSelection()
        for obj in results:Gui.Selection.addSelection(obj)
        self.ws.refresh();self.ws.main.statusBar().showMessage(tr('メッシュを変更しました。Ctrl＋Zで元に戻せます。','Mesh updated. Press Ctrl+Z to undo.'),8000)

    def refresh(self):
        if not self.active:return
        try:
            if App.ActiveDocument!=self.doc or self.ws.current_sketch() or any(not obj.Document for obj in self.targets):self.cancel();return
            if self.stale():self.update_preview()
        except (RuntimeError,ReferenceError):self.cancel();return
        self.position()
