"""Plane selection and preview for two independently editable split bodies."""
import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore,QtWidgets as W
from floating_panel import FloatingPanel
from i18n import tr
import browser
import model
import model_split as split


class SplitPanel(FloatingPanel):
    layout_key='SplitPanel'
    preferred_height=480

    def build_fields(self,form):
        self.body=W.QComboBox();form.addRow(tr('対象ボディ','Body'),self.body)
        self.mode=W.QComboBox()
        for label,key in [('XY','XY'),('XZ','XZ'),('YZ','YZ'),(tr('選択した面・構築平面','Selected Face / Plane'),'face')]:self.mode.addItem(label,key)
        form.addRow(tr('切断平面','Splitting Plane'),self.mode)
        self.reference_button=W.QPushButton(tr('面・構築平面を選択','Select Face / Plane'))
        self.reference_button.setCheckable(True);self.reference_button.clicked.connect(self.select_reference);form.addRow(self.reference_button)
        self.reference_label=W.QLabel();self.reference_label.setWordWrap(True);form.addRow(self.reference_label)
        self.cut_offset=self.spin();self.cut_offset.setRange(-100000,100000);form.addRow(tr('オフセット','Offset'),self.cut_offset)
        self.center_button=W.QPushButton(tr('ボディの中央に合わせる','Center on Body'))
        self.center_button.clicked.connect(self.center);form.addRow(self.center_button)
        self.show_plane=W.QCheckBox(tr('切断平面を表示','Show Splitting Plane'));self.show_plane.setChecked(True)
        self.show_plane.toggled.connect(self.schedule);form.addRow(self.show_plane)
        self.note=W.QLabel(tr('青とオレンジの2つのボディに分割します。オフセットは平面の法線方向が正です。\n選択した面はボディ全体を横切る平面として扱います。',
                             'Creates separate blue and orange bodies. Positive offset follows the plane normal.\nA selected face is extended as a plane across the body.'))
        self.note.setWordWrap(True);form.addRow(self.note)
        for field in (self.body,self.mode,self.reference_button,self.reference_label,self.cut_offset,self.note):
            field.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum)
        self.body.currentIndexChanged.connect(self.body_changed)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.combos=(self.body,self.mode);self.spins=(self.cut_offset,)

    def start(self,existing=None):
        self.cancel()
        if self.ws.current_sketch():raise ValueError(tr('先にスケッチ編集を終了してください。','Finish editing the sketch first.'))
        self.doc=App.ActiveDocument
        if not self.doc:raise ValueError(tr('分割するソリッドを作成してください。','Create a solid to split.'))
        self.existing=split.operation(existing) if existing else None
        self.reference=None;self.face='';self.picking=False;self.press=None
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        bodies=[o for o,t in browser.collect(self.doc)[0] if len(o.Shape.Solids)==1 and not getattr(o,'FluxSplit',False)]
        selected=[];selected_ref=None
        for s in Gui.Selection.getSelectionEx():
            if hasattr(s.Object,'Mesh'):raise ValueError(tr('ソリッドを選択してください。メッシュは対象外です。','Select a solid. Meshes are not supported.'))
            for name in s.SubElementNames or ['']:
                obj=(s.Object.getSubObject(name,1) or s.Object) if name else s.Object
                owner=browser.body_owner(obj)
                if hasattr(owner,'Shape') and len(owner.Shape.Solids)==1 and not getattr(owner,'FluxSplit',False) and owner not in selected:
                    selected.append(owner)
                face=name.rsplit('.',1)[-1] if name else 'Face1' if getattr(obj,'FluxPlane',False) else ''
                if face.startswith('Face'):selected_ref=(obj,face)
        self.source=self.existing.FluxBodySource if self.existing else selected[0] if selected else bodies[0] if len(bodies)==1 else None
        if self.source and self.source not in bodies:bodies.insert(0,self.source)
        blocked=self.body.blockSignals(True);self.body.clear();self.body.addItem(tr('ボディを選択','Select Body'),None)
        for obj in bodies:self.body.addItem(obj.Label,obj.Name)
        self.body.setCurrentIndex(self.body.findData(self.source.Name) if self.source else 0);self.body.blockSignals(blocked)
        self.body.setEnabled(self.existing is None)
        self.heading.setText(tr('ボディ分割を編集','Edit Split Body') if self.existing else tr('ボディを分割','Split Body'))
        if self.existing:
            values=split.settings(self.existing);self.reference=values['reference'];self.face=values['face']
            self.mode.setCurrentIndex(self.mode.findData(values['mode']));self.cut_offset.setValue(values['offset'])
        else:
            self.mode.setCurrentIndex(3 if selected_ref else 0);self.cut_offset.setValue(0)
            if selected_ref:self.reference,self.face=selected_ref
            if self.source and not selected_ref:self.center()
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.last_signature=self.signature();self.active=True;self.panel.show();self.update_preview();self.position()

    def signature(self):
        def sig(obj):return (obj.Name,obj.Shape.hashCode(),str(obj.getGlobalPlacement())) if obj else None
        return sig(self.source),sig(self.reference),tuple((p.Name,str(p.getGlobalPlacement())) for p in split.outputs(self.existing)) if self.existing else ()

    def parameters(self):
        return dict(mode=self.mode.currentData(),reference=self.reference if self.mode.currentData()=='face' else None,
                    face=self.face if self.mode.currentData()=='face' else '',offset=self.cut_offset.value())

    def body_changed(self):
        if not self.active:return
        self.source=self.doc.getObject(self.body.currentData()) if self.body.currentData() else None
        self.center();self.update_preview()

    def mode_changed(self):
        if not self.active:return
        self.picking=False;self.center();self.update_preview()

    def center(self):
        try:
            if self.source:
                values=self.parameters();values['offset']=0
                origin,normal=split.plane(**values)
                self.cut_offset.setValue((model.world_shape(self.source).BoundBox.Center-origin).dot(normal))
            if self.active:self.update_preview()
        except Exception as error:
            if self.active:self.status.setText(str(error))

    def select_reference(self):
        if not self.active:return
        self.picking=not self.picking
        if self.picking:
            blocked=self.mode.blockSignals(True);self.mode.setCurrentIndex(3);self.mode.blockSignals(blocked)
        self.update_preview()

    def pick(self,widget,point):
        try:
            origin,direction=self.ray(widget,point)
            candidates=[(o,model.world_shape(o)) for o,t in browser.collect(self.doc)[0] if o.Visibility]
            candidates += [(o,model.world_shape(o)) for o in self.doc.Objects if getattr(o,'FluxPlane',False) and o.Visibility]
            if self.source and all(o!=self.source for o,s in candidates):candidates.append((self.source,model.world_shape(self.source)))
            hits=[]
            for obj,shape in candidates:
                length=(shape.BoundBox.Center-origin).Length+shape.BoundBox.DiagonalLength+1
                ray=Part.makeLine(origin,origin+direction*length)
                for i,face in enumerate(shape.Faces):
                    for v in face.section(ray).Vertexes:hits.append(((v.Point-origin).Length,obj,'Face%d'%(i+1)))
            if not hits:raise ValueError(tr('平らな面または構築平面をクリックしてください。','Click a planar face or construction plane.'))
            _,ref,face=min(hits,key=lambda h:h[0]);split.plane('face',ref,face)
            if self.source:split.check_reference(self.doc,self.source,ref,self.existing)
            self.reference,self.face=ref,face;self.cut_offset.setValue(0);self.picking=False
            self.update_preview()
        except Exception as error:
            self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;')

    def show_shapes(self,items):
        # ExtrudePanel owns one graph root; collect several colored shapes under it.
        root=None
        for shape,style in items:
            self.show_shape(shape,style)
            graph,node=self.overlay
            if root is None:root=(graph,node)
            else:graph.removeChild(node);root[1].addChild(node)
        self.overlay=root

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        selecting=self.mode.currentData()=='face';self.reference_button.setVisible(selecting);self.reference_label.setVisible(selecting)
        self.reference_button.setChecked(self.picking)
        self.reference_label.setText(self.reference.Label+' / '+self.face if self.reference else tr('基準面を選択してください。','Select a reference face.'))
        try:
            self.last_signature=self.signature()
            if self.picking:
                if self.existing:self.show_shapes([(model.world_shape(self.source),'new')]);self.hide_results()
                self.status.setText(tr('平らな面または構築平面をクリックしてください。','Click a planar face or construction plane.'));return
            if not self.source:raise ValueError(tr('分割するボディを選択してください。','Select the body to split.'))
            values=self.parameters();split.check_reference(self.doc,self.source,values['reference'],self.existing)
            parts,marker=split.preview(self.source,**values);self.preview_parts=parts
            placed={p.Side:p for p in split.outputs(self.existing)} if self.existing else {}
            items=[]
            for i,shape in enumerate(parts):
                shape=shape.copy()
                if self.existing and i not in placed:continue
                if i in placed:shape.Placement=placed[i].getGlobalPlacement().multiply(shape.Placement)
                items.append((shape,'new' if i==0 else 'plane'))
            if self.show_plane.isChecked():items.append((marker,'plane'))
            self.show_shapes(items);self.hide_results()
            self.valid=True;self.accept_button.setEnabled(True);self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('2 ボディ / 青 %.3f mm³ / オレンジ %.3f mm³','2 bodies / Blue %.3f mm³ / Orange %.3f mm³')%tuple(p.Volume for p in parts))
        except Exception as error:
            self.clear_preview();self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def hide_results(self):
        targets=[self.source]+([self.existing]+self.existing.InListRecursive if self.existing else [])
        for obj in targets:
            if obj and hasattr(obj,'Visibility'):
                self.hidden.append((obj,bool(obj.Visibility)));obj.Visibility=False

    def accept(self):
        if not self.active:return
        self.cut_offset.interpretText();self.update_preview()
        if not self.active or not self.valid:return
        self.clear_preview()
        try:result=split.create(self.doc,self.source,existing=self.existing,**self.parameters())
        except Exception as error:
            self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;');self.valid=False;self.accept_button.setEnabled(False);return
        self.active=False;self.timer.stop();self.panel.hide();self.ws.region_picker.clear();Gui.Selection.clearSelection()
        for part in split.outputs(result):Gui.Selection.addSelection(part)
        self.ws.refresh()
        self.ws.main.statusBar().showMessage(tr('ボディを分割しました。部品を個別に移動でき、履歴から切断位置を変更できます。',
                                               'Body split. Move each part independently; edit the cutting position from history.'),8000)

    def refresh(self):
        if not self.active:return
        try:
            if App.ActiveDocument!=self.doc or self.ws.current_sketch() or any(o and not o.Document for o in (self.source,self.reference,self.existing)):
                self.cancel();return
            if self.signature()!=self.last_signature:self.update_preview()
        except (RuntimeError,ReferenceError):self.cancel();return
        self.position()

    def eventFilter(self,widget,event):
        if getattr(getattr(self.ws,'cube',None),'forwarding',False):return False
        if self.active and self.picking and widget in self.widgets:
            kind=event.type()
            if kind==QtCore.QEvent.MouseButtonPress and event.button()==QtCore.Qt.LeftButton:
                self.press=(widget,QtCore.QPointF(event.position()));return True
            if kind==QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.LeftButton:
                press=self.press;self.press=None
                if press and press[0]==widget and (event.position()-press[1]).manhattanLength()<W.QApplication.startDragDistance():self.pick(widget,event.position())
                return True
        return super().eventFilter(widget,event)
