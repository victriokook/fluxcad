"""Preview a translation or rotation, optionally creating independent copies."""
from i18n import tr
import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtWidgets as W
from pivy import coin
from extrude_panel import ExtrudePanel
import model_transform as transforms


class TransformPanel(ExtrudePanel):
    preferred_height = 570

    def build_fields(self,form):
        self.rows = {}
        def row(key,title,widget):
            label = W.QLabel(title)
            form.addRow(label,widget)
            self.rows[key] = (label,widget)
            return widget
        self.summary = W.QLabel(); self.summary.setWordWrap(True)
        form.addRow(self.summary)
        self.mode = row('mode',tr('移動タイプ'),W.QComboBox())
        self.mode.addItem(tr('回転','Rotate'),'rotate'); self.mode.addItem(tr('移動'),'translate')
        self.axis = row('axis',tr('軸（全体座標）'),W.QComboBox())
        self.axis.addItems(['X','Y','Z']); self.axis.setCurrentText('Z')
        self.angle = row('angle',tr('角度'),self.number(' °',-360,360))
        self.angle.setSingleStep(15)
        quick = W.QWidget(); layout = W.QHBoxLayout(quick);layout.setContentsMargins(0,0,0,0)
        for angle in (-90,90,180):
            button=W.QToolButton();button.setText('%+d°'%angle)
            button.setFixedSize(48,24)
            button.clicked.connect(lambda checked=False,a=angle:self.angle.setValue(a))
            layout.addWidget(button)
        layout.addStretch()
        row('quick','',quick)
        self.pivot = row('pivot',tr('回転中心'),W.QComboBox())
        for title,key in [(tr('選択全体の中心'),'selection'),(tr('原点'),'origin'),(tr('座標を指定'),'custom')]:
            self.pivot.addItem(title,key)
        self.center = [row('center'+a,tr('中心 ')+a,self.number()) for a in 'XYZ']
        self.delta = [row('delta'+a,a+tr('方向の移動量'),self.number()) for a in 'XYZ']
        self.copy = W.QCheckBox(tr('コピーを作成'))
        self.copy.toggled.connect(self.schedule);form.addRow(self.copy)
        self.note = W.QLabel(tr('複数ボディは同じ中心・軸で回転します。\nコピーは独立した形状になり、元の寸法変更には追従しません。'))
        self.note.setWordWrap(True);form.addRow(self.note)
        self.combos = (self.mode,self.axis,self.pivot)
        self.spins = (self.angle,*self.center,*self.delta)

    @staticmethod
    def number(suffix=' mm',minimum=-1e9,maximum=1e9):
        spin=W.QDoubleSpinBox();spin.setDecimals(6);spin.setRange(minimum,maximum)
        spin.setSuffix(suffix);spin.setKeyboardTracking(False)
        spin.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        return spin

    def source_signature(self):
        return [(obj.Name,obj.Shape.hashCode(),str(obj.getGlobalPlacement()),str(obj.ExpressionEngine)) for obj in self.targets]

    def start(self,objects):
        self.cancel()
        self.doc=App.ActiveDocument
        self.targets=transforms.targets(self.doc,objects)
        self.signature=self.source_signature()
        self.selection=[(sel.ObjectName,tuple(sel.SubElementNames)) for sel in Gui.Selection.getSelectionEx()]
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.heading.setText(tr('移動 / コピー'))
        self.summary.setText(tr('対象：%d ボディ\n%s')%(len(self.targets),'、'.join(obj.Label for obj in self.targets)))
        self.group_center=transforms.selection_center(self.targets)
        self.angle.setValue(0);self.copy.setChecked(False)
        self.mode.setCurrentIndex(0);self.pivot.setCurrentIndex(0)
        for field,value in zip(self.center,self.group_center):field.setValue(value)
        for field in self.delta:field.setValue(0)
        self.active=True;self.panel.show();self.update_preview();self.position()

    def parameters(self):
        pivot=self.pivot.currentData()
        center=self.group_center if pivot=='selection' else (0,0,0) if pivot=='origin' else tuple(f.value() for f in self.center)
        return dict(mode=self.mode.currentData(),axis=self.axis.currentText(),angle=self.angle.value(),
                    center=center,delta=tuple(f.value() for f in self.delta))

    def marker(self,center,axis):
        # An unpickable cross and axis make an off-center pivot visible.
        node=self.overlay[1];radius=max(.5,min(20,self.preview_shape.BoundBox.DiagonalLength*.12))
        origin=App.Vector(*center)
        light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        style=coin.SoDrawStyle();style.lineWidth=2;node.addChild(style)
        for name,vector,color in [('X',App.Vector(1,0,0),(0.9,.2,.2)),('Y',App.Vector(0,1,0),(.2,.7,.2)),('Z',App.Vector(0,0,1),(.2,.4,.9))]:
            branch=coin.SoSeparator();material=coin.SoMaterial();material.diffuseColor=color;material.transparency=0;branch.addChild(material)
            length=radius if name==axis else radius*.3
            points=coin.SoCoordinate3();points.point.setValues(0,2,[tuple(origin-vector*length),tuple(origin+vector*length)]);branch.addChild(points)
            line=coin.SoLineSet();line.numVertices.setValue(2);branch.addChild(line);node.addChild(branch)

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        rotate=self.mode.currentData()=='rotate'
        for key,pair in self.rows.items():
            visible=rotate if key in ('axis','angle','quick','pivot') or key.startswith('center') else not rotate if key.startswith('delta') else True
            for widget in pair:widget.setVisible(visible)
        values=self.parameters()
        for field,value in zip(self.center,values['center']):
            field.setEnabled(self.pivot.currentData()=='custom')
            if not field.isEnabled():
                field.blockSignals(True);field.setValue(value);field.blockSignals(False)
        try:
            if self.source_signature()!=self.signature:
                raise ValueError(tr('対象ボディが変更されました。キャンセルして選び直してください。'))
            transforms.targets(self.doc,self.targets,self.copy.isChecked())
            placement=transforms.transform(**values)
            import model_assembly as assembly
            poses=assembly.affected_poses(self.doc,{o:placement.multiply(o.getGlobalPlacement()) for o in self.targets if getattr(o,'FluxComponent',False)}) if not self.copy.isChecked() else {}
            shapes=transforms.shapes([o for o in self.targets if o not in poses],placement)+assembly.posed_shapes(poses)
            result=Part.makeCompound(shapes)
            self.show_shape(result,'new')
            if rotate:self.marker(values['center'],values['axis'])
            if not self.copy.isChecked():
                for obj in dict.fromkeys(self.targets+list(poses)):
                    self.hidden.append((obj,bool(obj.Visibility)));obj.Visibility=False
            if not self.copy.isChecked() and not transforms.changed(placement):
                raise ValueError(tr('角度または移動量を入力してください。'))
            self.valid=True;self.accept_button.setEnabled(True)
            self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('%d ボディを%sします。')%(len(self.targets),tr('コピー') if self.copy.isChecked() else tr('回転','Rotate') if rotate else tr('移動')))
        except Exception as error:
            self.clear_preview();self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def accept(self):
        if not self.active:return
        for field in self.spins:field.interpretText()
        self.update_preview()
        if not self.active or not self.valid:return
        self.clear_preview()
        try:
            results=transforms.apply(self.doc,self.targets,copy=self.copy.isChecked(),**self.parameters())
        except Exception as error:
            self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error));self.valid=False;self.accept_button.setEnabled(False);return
        self.active=False;self.panel.hide();Gui.Selection.clearSelection()
        for obj in results:Gui.Selection.addSelection(obj)
        self.ws.refresh()
        self.ws.main.statusBar().showMessage(tr('%d ボディを配置しました。Ctrl＋Zでまとめて元に戻せます。')%len(results),8000)

    def refresh(self):
        if not self.active:return
        try:
            if App.ActiveDocument!=self.doc or self.ws.current_sketch() or any(not obj.Document for obj in self.targets):
                self.cancel();return
            if self.source_signature()!=self.signature:self.update_preview()
        except (RuntimeError,ReferenceError):
            self.cancel();return
        self.position()
