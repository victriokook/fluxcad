"""Pick two native faces and preview a precise body alignment."""
from i18n import tr
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from floating_panel import FloatingPanel
from transform_panel import TransformPanel
from pivy import coin
import model_align as align
import model_transform as transforms


class AlignPanel(FloatingPanel):
    layout_key='AlignPanel'
    preferred_height=500

    def __init__(self,ws):
        super().__init__(ws)
        for label in (self.details,self.note,self.status):
            policy=label.sizePolicy();policy.setHeightForWidth(True);label.setSizePolicy(policy)

    def build_fields(self,form):
        self.pick_buttons={}
        for key,title in [('source',tr('移動する面')),('target',tr('合わせ先の面'))]:
            button=W.QToolButton();button.setText(tr('面を選択'));button.setCheckable(True)
            button.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
            button.clicked.connect(lambda checked=False,k=key:self.begin_pick(k))
            form.addRow(title,button);self.pick_buttons[key]=button
        self.details=W.QLabel();self.details.setWordWrap(True);self.details.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);form.addRow(self.details)
        self.mode=W.QComboBox();self.mode.addItem(tr('面の中心を合わせる'),True);self.mode.addItem(tr('平面のみを合わせる'),False)
        form.addRow(tr('位置'),self.mode)
        self.direction=W.QComboBox();self.direction.addItem(tr('面を向かい合わせる'),True);self.direction.addItem(tr('同じ向きにそろえる'),False)
        form.addRow(tr('向き'),self.direction)
        self.gap_label=W.QLabel(tr('すき間'));self.gap=TransformPanel.number();form.addRow(self.gap_label,self.gap)
        self.angle_label=W.QLabel(tr('面内の回転'))
        self.angle=TransformPanel.number(' °',-360,360);self.angle.setSingleStep(90);form.addRow(self.angle_label,self.angle)
        tools=W.QWidget();row=W.QHBoxLayout(tools);row.setContentsMargins(0,0,0,0)
        for title,callback in [(tr('反転'),self.flip),('+90°',self.quarter_turn),(tr('面を入れ替え'),self.swap)]:
            button=W.QToolButton();button.setText(title);button.clicked.connect(callback);row.addWidget(button)
        row.addStretch();form.addRow(tools)
        self.copy=W.QCheckBox(tr('コピーを作成'));self.copy.toggled.connect(self.schedule);form.addRow(self.copy)
        self.note=W.QLabel();self.note.setWordWrap(True);form.addRow(self.note)
        for field in (self.note,self.mode,self.direction,self.gap,self.angle):field.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum)
        self.combos=(self.mode,self.direction);self.spins=(self.gap,self.angle)

    def update_fields(self):
        geometry=align.kind(align.face(*self.refs['source'])) if 'source' in self.refs else 'plane'
        cylinder=geometry=='cylinder'
        self.heading.setText(tr('位置合わせ — 同軸','Align — Coaxial') if cylinder else tr('位置合わせ'))
        self.mode.setItemText(0,tr('軸方向の中央を合わせる','Match Axial Midpoints') if cylinder else tr('面の中心を合わせる'))
        self.mode.setItemText(1,tr('軸方向の位置を保持','Keep Axial Position') if cylinder else tr('平面のみを合わせる'))
        self.direction.setItemText(0,tr('軸を逆向きにそろえる','Opposite Axis Directions') if cylinder else tr('面を向かい合わせる'))
        self.direction.setItemText(1,tr('軸を同じ向きにそろえる','Same Axis Direction') if cylinder else tr('同じ向きにそろえる'))
        self.gap_label.setText(tr('軸方向オフセット','Axial Offset') if cylinder else tr('すき間'))
        self.angle_label.setText(tr('軸まわりの回転','Axial Rotation') if cylinder else tr('面内の回転'))
        if geometry!=self.geometry_kind:
            self.geometry_kind=geometry;self.direction.setCurrentIndex(1 if cylinder else 0)
        self.note.setText(tr('円筒の側面どうしを選択します。\n基準は選択面の軸方向の中央です。緑の＋矢印の方向がオフセットの正方向です。\n位置合わせ後の追従や固定は行いません。コピーは独立した形状になります。',
                            'Select two cylindrical side faces.\nOffsets use the axial midpoint of each selected face. The green + arrow indicates the positive offset direction.\nAlignment does not create an ongoing constraint. Copies are independent.') if cylinder else
                          tr('移動する面 → 合わせ先の面の順にクリック。\nすき間は合わせ先の面の外向きが正です。\n位置合わせ後の追従や固定は行いません。コピーは独立した形状になります。'))

    def start(self):
        self.cancel();self.doc=App.ActiveDocument
        if not self.doc:raise ValueError(tr('位置合わせするボディを作成してください。'))
        self.selection=[(sel.ObjectName,tuple(sel.SubElementNames)) for sel in Gui.Selection.getSelectionEx()]
        self.refs={};self.signatures={};self.picking=None;self.ticket=0;self.observing=False;self.geometry_kind=None
        faces=[]
        for sel in Gui.Selection.getSelectionEx():
            for sub in sel.SubElementNames:
                faces.append(align.reference(self.doc,sel.ObjectName,sub))
        if len(faces)>2:raise ValueError(tr('面は移動する面と合わせ先の面の2つを選択してください。'))
        for key,ref in zip(('source','target'),faces):
            self.refs[key]=ref;self.signatures[key]=align.signature(ref[0])
        self.heading.setText(tr('位置合わせ'))
        self.gap.setValue(0);self.angle.setValue(0);self.copy.setChecked(False)
        self.mode.setCurrentIndex(0);self.direction.setCurrentIndex(0)
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.active=True;self.panel.show();Gui.Selection.addObserver(self);self.observing=True
        self.picking='source' if not faces else 'target' if len(faces)==1 else None
        Gui.Selection.clearSelection();self.update_preview();self.position()

    def begin_pick(self,key):
        if not self.active:return
        self.ticket+=1;self.picking=key;self.timer.stop();Gui.Selection.clearSelection();self.update_preview()

    def addSelection(self,docname,objname,subname,point):
        if not self.active or not self.picking or docname!=self.doc.Name:return
        ticket=self.ticket;role=self.picking
        def receive():
            if not self.active or ticket!=self.ticket or self.picking!=role:return
            try:
                ref=align.reference(self.doc,objname,subname)
                if role=='source':transforms.targets(self.doc,[ref[0]],self.copy.isChecked())
                if role=='target' and 'source' in self.refs:
                    align.prepare(self.doc,self.refs['source'],ref,copy=self.copy.isChecked(),**self.parameters())
                self.refs[role]=ref;self.signatures[role]=align.signature(ref[0]);self.ticket+=1
                if role=='source' and 'target' in self.refs and align.kind(align.face(*ref))!=align.kind(align.face(*self.refs['target'])):
                    self.refs.pop('target');self.signatures.pop('target')
                self.picking='target' if role=='source' and 'target' not in self.refs else None
                Gui.Selection.clearSelection();self.update_preview()
            except Exception as error:
                self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))
                Gui.Selection.clearSelection()
        QtCore.QTimer.singleShot(0,receive)

    def parameters(self):
        return dict(gap=self.gap.value(),angle=self.angle.value(),center=self.mode.currentData(),opposed=self.direction.currentData())

    def flip(self):self.direction.setCurrentIndex(1-self.direction.currentIndex())

    def quarter_turn(self):self.angle.setValue((self.angle.value()+90+180)%360-180)

    def swap(self):
        if not self.active or len(self.refs)!=2:return
        self.refs={'source':self.refs['target'],'target':self.refs['source']}
        self.signatures={'source':self.signatures['target'],'target':self.signatures['source']}
        self.ticket+=1;self.picking=None;self.update_preview()

    def axis_marker(self,ref):
        selected=align.face(*ref)
        if align.kind(selected)!='cylinder' or not self.overlay:return
        origin,axis=align.cylinder_axis(selected)
        u0,u1,v0,v1=selected.ParameterRange
        length=max(3,selected.Surface.Radius*2,abs(v1-v0)*.65)
        tip=origin+axis*length
        helper=min((App.Vector(1,0,0),App.Vector(0,1,0),App.Vector(0,0,1)),key=lambda v:abs(v.dot(axis)))
        wing=axis.cross(helper);wing.normalize();wing*=length*.1
        tail=tip-axis*length*.2
        points=[origin-axis*length,tip,tail+wing,tip,tail-wing]
        node=coin.SoSeparator();light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(.15,.7,.3);material.transparency=0;node.addChild(material)
        style=coin.SoDrawStyle();style.lineWidth=2;node.addChild(style)
        coords=coin.SoCoordinate3();coords.point.setValues(0,len(points),[tuple(p) for p in points]);node.addChild(coords)
        line=coin.SoLineSet();line.numVertices.setValue(len(points));node.addChild(line)
        translation=coin.SoTranslation();translation.translation=tuple(tip+axis*length*.1);node.addChild(translation)
        text=coin.SoText2();text.string='+';node.addChild(text)
        self.overlay[1].addChild(node)

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        details=[]
        for key,title in [('source',tr('移動')),('target',tr('合わせ先'))]:
            ref=self.refs.get(key);text=ref[0].Label+' / '+ref[1] if ref else tr('面を選択')
            button=self.pick_buttons[key];button.setText(text);button.setToolTip(text);button.setChecked(self.picking==key)
            if ref:details.append(title+'：'+text)
        self.details.setText('\n'.join(details))
        try:
            self.update_fields()
            for key,(obj,name) in self.refs.items():
                if align.signature(obj)!=self.signatures[key]:raise ValueError(tr('選択した形状が変更されました。「面を選択」から選び直してください。'))
            if self.picking or len(self.refs)!=2:
                self.status.setStyleSheet('color:#245b73;')
                self.status.setText(tr('移動するボディの平面または円筒の側面をクリックしてください。',
                                       'Click a planar face or cylindrical side face on the body to move.') if self.picking=='source' else
                                    tr('合わせ先の円筒の側面をクリックしてください。','Click the cylindrical side face of the target.') if self.geometry_kind=='cylinder' else
                                    tr('合わせ先の平らな面をクリックしてください。'))
                if 'source' in self.refs:
                    self.show_shape(align.face(*self.refs['source']),'new');self.axis_marker(self.refs['source'])
                return
            moving,pose=align.prepare(self.doc,self.refs['source'],self.refs['target'],copy=self.copy.isChecked(),**self.parameters())
            self.show_shape(transforms.shapes([moving],pose)[0],'new')
            self.axis_marker(self.refs['target'])
            if not self.copy.isChecked():
                self.hidden.append((moving,bool(moving.Visibility)));moving.Visibility=False
            if not self.copy.isChecked() and not transforms.changed(pose):
                raise ValueError(tr('すでに指定した位置・向きに配置されています。'))
            self.valid=True;self.accept_button.setEnabled(True);self.status.setStyleSheet('color:#245b73;')
            self.status.setText((tr('軸方向オフセット %g mm / 回転 %g°\n%sのプレビュー',
                                    'Axial offset %g mm / Rotation %g°\n%s preview') if self.geometry_kind=='cylinder' else
                                 tr('すき間 %g mm / 面内回転 %g°\n%sのプレビュー'))%(self.gap.value(),self.angle.value(),tr('コピーして位置合わせ') if self.copy.isChecked() else tr('位置合わせ')))
        except Exception as error:
            self.clear_preview();self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def detach(self):
        self.ticket+=1
        if self.observing:Gui.Selection.removeObserver(self);self.observing=False

    def accept(self):
        if not self.active:return
        for field in self.spins:field.interpretText()
        self.update_preview()
        if not self.active or not self.valid:return
        self.clear_preview()
        try:result=align.apply(self.doc,self.refs['source'],self.refs['target'],copy=self.copy.isChecked(),**self.parameters())
        except Exception as error:
            self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error));self.valid=False;self.accept_button.setEnabled(False);return
        self.detach();self.active=False;self.panel.hide();Gui.Selection.clearSelection();Gui.Selection.addSelection(result)
        self.ws.refresh();self.ws.main.statusBar().showMessage(tr('位置合わせしました。Ctrl＋Zで元に戻せます。'),8000)

    def cancel(self):
        if self.active:self.detach()
        super().cancel()

    def refresh(self):
        if not self.active:return
        try:
            if App.ActiveDocument!=self.doc or self.ws.current_sketch() or any(not obj.Document for obj,name in self.refs.values()):
                self.cancel();return
            if any(align.signature(obj)!=self.signatures[key] for key,(obj,name) in self.refs.items()):self.update_preview()
        except (RuntimeError,ReferenceError):self.cancel();return
        self.position()

    def eventFilter(self,widget,event):
        if (self.active and self.picking and widget in self.widgets and
                event.type() in (QtCore.QEvent.MouseButtonPress,QtCore.QEvent.MouseButtonRelease,QtCore.QEvent.MouseButtonDblClick)):
            if event.button()==QtCore.Qt.LeftButton:return False
        return super().eventFilter(widget,event)
