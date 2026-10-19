"""Movable component management and non-destructive as-built joint editing."""
import math
import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore,QtWidgets as W
from pivy import coin
from floating_panel import FloatingPanel
from transform_panel import TransformPanel
from i18n import tr
import model
import browser
import model_axis
import model_assembly as assembly


class AssemblyPanel(FloatingPanel):
    @staticmethod
    def signature(obj):
        return (obj.Shape.hashCode(),str(obj.getGlobalPlacement()),bool(getattr(obj,'Grounded',False)),
                getattr(getattr(obj,'Driver',None),'Name',None))

    def check_sources(self,objects):
        for obj in objects:
            if not obj or not obj.Document or self.signature(obj)!=self.signatures.get(obj.Name):
                raise ValueError(tr('部品が変更されました。キャンセルして開き直してください。','Components changed. Cancel and reopen the panel.'))

    def begin(self):
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.active=True;self.panel.show();self.update_preview();self.position()

    def hide(self,objects):
        for obj in objects:
            self.hidden.append((obj,bool(obj.Visibility)));obj.Visibility=False

    def finish(self,result):
        self.active=False;self.timer.stop();self.panel.hide();self.ws.region_picker.clear()
        Gui.Selection.clearSelection()
        for obj in result:Gui.Selection.addSelection(obj)
        self.ws.refresh()

    def refresh(self):
        if not self.active:return
        try:
            if App.ActiveDocument!=self.doc or self.ws.current_sketch():self.cancel();return
            if self.valid:
                try:self.check_sources(self.candidates)
                except Exception:self.update_preview()
        except (RuntimeError,ReferenceError):self.cancel();return
        self.position()

    def wrap(self,label):
        label.setWordWrap(True)
        policy=W.QSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);policy.setHeightForWidth(True)
        label.setSizePolicy(policy)
        return label


class ComponentPanel(AssemblyPanel):
    layout_key='ComponentPanel';preferred_height=490

    def build_fields(self,form):
        self.name=W.QLineEdit();form.addRow(tr('名前','Name'),self.name)
        self.sources=W.QListWidget();self.sources.setMinimumHeight(110);self.sources.setMaximumHeight(180)
        self.sources.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Preferred)
        self.sources_label=W.QLabel(tr('元ボディ','Source Bodies'));form.addRow(self.sources_label,self.sources)
        self.grounded=W.QCheckBox(tr('接地（位置を固定）','Ground (fix position)'));form.addRow(self.grounded)
        self.keep=W.QCheckBox(tr('元ボディも表示する','Also show source bodies'));form.addRow(self.keep)
        self.note=self.wrap(W.QLabel());form.addRow(self.note)
        self.name.textChanged.connect(self.schedule);self.sources.itemChanged.connect(self.schedule)
        self.grounded.toggled.connect(self.schedule);self.keep.toggled.connect(self.schedule)
        self.combos=();self.spins=()

    def start(self,existing=None):
        self.cancel();self.doc=App.ActiveDocument;self.existing=existing
        if not self.doc:raise ValueError(tr('先にボディを作成してください。','Create a body first.'))
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        self.candidates=([existing] if existing else [o for o,t in browser.collect(self.doc)[0] if not getattr(o,'FluxComponent',False)])
        if not self.candidates:raise ValueError(tr('コンポーネントにする元ボディを作成してください。','Create source bodies for components.'))
        chosen={browser.body_owner(o) for o in Gui.Selection.getSelection()}
        self.sources.blockSignals(True);self.sources.clear()
        for obj in self.candidates:
            item=W.QListWidgetItem(obj.Label+' ['+obj.Name+']',self.sources);item.setData(QtCore.Qt.UserRole,obj.Name)
            item.setFlags(item.flags()|QtCore.Qt.ItemIsUserCheckable);item.setCheckState(QtCore.Qt.Checked if obj in chosen else QtCore.Qt.Unchecked)
        self.sources.blockSignals(False)
        self.name.setText(existing.Label if existing else '')
        self.name.setPlaceholderText(tr('空欄なら元ボディ名を使用','Blank uses source body names'))
        self.grounded.setChecked(bool(existing.Grounded) if existing else False);self.keep.setChecked(False)
        self.sources.setVisible(not existing);self.sources_label.setVisible(not existing);self.keep.setVisible(not existing)
        self.heading.setText(tr('コンポーネントを編集','Edit Component') if existing else tr('コンポーネントを作成','Create Components'))
        self.note.setText(tr('ボディ1つにつき部品を1つ作成します。元ボディの寸法変更が反映され、部品の位置は独立します。元形状は履歴から編集できます。接地した部品は動かせません。',
                            'Creates one component per body. Source dimensions update every instance; positions are independent. Edit source geometry through its history. Grounded components cannot move.'))
        self.signatures={o.Name:self.signature(o) for o in self.candidates};self.begin()

    def chosen(self):
        return [self.doc.getObject(self.sources.item(i).data(QtCore.Qt.UserRole)) for i in range(self.sources.count())
                if self.sources.item(i).checkState()==QtCore.Qt.Checked]

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        try:
            objects=[self.existing] if self.existing else self.chosen();self.check_sources(objects)
            if not objects:raise ValueError(tr('元ボディにチェックを入れてください。','Check at least one source body.'))
            if self.existing and not self.name.text().strip():raise ValueError(tr('名前を入力してください。','Enter a name.'))
            if self.existing and self.existing.Driver and self.grounded.isChecked():
                raise ValueError(tr('ジョイントを先に解除してください。','Release the joint before grounding this component.'))
            self.show_shape(Part.makeCompound([model.world_shape(o) for o in objects]),'new')
            if self.existing or not self.keep.isChecked():self.hide(objects)
            self.valid=True;self.accept_button.setEnabled(True);self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('%d 個の部品。確定するまで変更しません。','%d components. Changes apply only on Confirm.')%len(objects))
        except Exception as error:self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def accept(self):
        if not self.active:return
        self.update_preview()
        if not self.valid:return
        self.clear_preview()
        try:
            result=([assembly.edit_component(self.existing,self.name.text(),self.grounded.isChecked())] if self.existing else
                    assembly.create_components(self.doc,self.chosen(),self.name.text(),self.grounded.isChecked(),self.keep.isChecked()))
            self.finish(result)
        except Exception as error:self.valid=False;self.accept_button.setEnabled(False);self.status.setText(str(error))


class JointPanel(AssemblyPanel):
    layout_key='JointPanel';preferred_height=650

    def build_fields(self,form):
        self.moving=W.QComboBox();self.anchor=W.QComboBox();self.kind=W.QComboBox()
        form.setRowWrapPolicy(W.QFormLayout.WrapLongRows)
        for kind in ('rigid','revolute','slider'):self.kind.addItem(assembly.joint_label(kind),kind)
        form.addRow(tr('動く部品','Moving part'),self.moving);form.addRow(tr('基準部品','Anchor part'),self.anchor)
        form.addRow(tr('種類','Type'),self.kind)
        self.note=self.wrap(W.QLabel());form.addRow(self.note)
        self.rows=[]
        def row(text,field):
            label=W.QLabel(text) if text else None
            if label:form.addRow(label,field)
            else:form.addRow(field)
            self.rows.append((label,field));return field
        self.angle=row(tr('角度','Angle'),TransformPanel.number('°',-360000,360000));self.angle.setSingleStep(5)
        self.distance=row(tr('移動距離','Distance'),TransformPanel.number(' mm',-1e6,1e6));self.distance.setSingleStep(1)
        self.slider=W.QSlider(QtCore.Qt.Horizontal);self.slider.setRange(0,1000);row('',self.slider)
        self.limited=W.QCheckBox(tr('可動範囲を制限','Limit motion'));row('',self.limited)
        self.minimum=row(tr('最小角度','Minimum'),TransformPanel.number('°',-360000,360000))
        self.maximum=row(tr('最大角度','Maximum'),TransformPanel.number('°',-360000,360000))
        self.distance_limited=W.QCheckBox(tr('移動範囲を制限','Limit travel'));row('',self.distance_limited)
        self.distance_minimum=row(tr('最小距離','Minimum'),TransformPanel.number(' mm',-1e6,1e6))
        self.distance_maximum=row(tr('最大距離','Maximum'),TransformPanel.number(' mm',-1e6,1e6))
        self.axis=W.QComboBox()
        for name in ('X','Y','Z'):self.axis.addItem(name,name)
        self.axis.addItem(tr('方向を指定','Custom direction'),'custom');self.axis.setCurrentIndex(2)
        row(tr('回転軸','Rotation axis'),self.axis);self.axis_label=self.rows[-1][0]
        self.pick_button=W.QPushButton(tr('辺・円筒面から軸を取得','Capture axis from edge / cylinder'))
        self.pick_button.setCheckable(True);self.pick_button.clicked.connect(self.toggle_pick);row('',self.pick_button)
        self.origin=[row(tr('軸の原点 ','Origin ')+a,TransformPanel.number()) for a in 'XYZ']
        self.vector=[row(tr('軸方向 ','Direction ')+a,TransformPanel.number('')) for a in 'XYZ']
        self.axis_hint=self.wrap(W.QLabel(tr('軸は基準部品の座標です。取得した辺・面の軸はその時点の座標を保持します。形状変更後の再取得もできます。',
                                          'Axis coordinates are in the anchor frame. Capturing an edge/face stores its current axis; recapture after geometry changes if needed.')))
        row('',self.axis_hint)
        self.limited.toggled.connect(self.schedule);self.distance_limited.toggled.connect(self.schedule);self.slider.valueChanged.connect(self.slide)
        for field in (self.moving,self.anchor,self.kind,self.axis,self.pick_button):field.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        self.combos=(self.moving,self.anchor,self.kind,self.axis)
        self.spins=(*self.origin,*self.vector,self.angle,self.minimum,self.maximum,self.distance,self.distance_minimum,self.distance_maximum)
        self.picking=False;self.observing=False;self.ticket=0;self.raw={}

    def set_vector(self,key,values):
        fields=self.origin if key=='origin' else self.vector
        for field,value in zip(fields,values):field.setValue(value)
        self.raw[key]=(tuple(values),tuple(field.value() for field in fields))

    def get_vector(self, key):
        fields = self.origin if key == 'origin' else self.vector
        raw, original = self.raw[key]
        return tuple(value if field.value() == shown else field.value() for field, value, shown in zip(fields, raw, original))

    def start(self,kind='rigid',existing=None):
        self.cancel();self.doc=App.ActiveDocument;self.existing=existing;self.picking=False
        if not self.doc or len(assembly.components(self.doc))<2:
            raise ValueError(tr('先にコンポーネントを2つ以上作成してください。','Create at least two components first.'))
        self.candidates=assembly.components(self.doc)
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        selected=[o for o in Gui.Selection.getSelection() if o in self.candidates]
        moving=assembly.follower_of(existing) if existing else selected[0] if selected else None
        anchor=existing.Target if existing else selected[1] if len(selected)>1 else None
        for combo,chosen in ((self.moving,moving),(self.anchor,anchor)):
            combo.blockSignals(True);combo.clear();combo.addItem(tr('— 選択 —','— Select —'),None)
            for obj in self.candidates:combo.addItem(obj.Label+' ['+obj.Name+']',obj.Name)
            combo.setCurrentIndex(combo.findData(chosen.Name) if chosen else 0);combo.blockSignals(False);combo.setEnabled(not existing)
        values=assembly.settings(existing) if existing else assembly.parameters(kind=kind)
        self.kind.setCurrentIndex(self.kind.findData(values['kind']))
        self.set_vector('origin',values['origin']);self.set_vector('axis',values['axis'])
        principal=next((name for name,v in [('X',(1,0,0)),('Y',(0,1,0)),('Z',(0,0,1))] if values['axis']==v),'custom')
        self.axis.setCurrentIndex(self.axis.findData(principal))
        self.angle.setValue(values['angle']);self.limited.setChecked(values['limited'])
        self.minimum.setValue(values['minimum']);self.maximum.setValue(values['maximum'])
        self.distance.setValue(values['distance']);self.distance_limited.setChecked(values['distance_limited'])
        self.distance_minimum.setValue(values['distance_minimum']);self.distance_maximum.setValue(values['distance_maximum'])
        self.scalar_baseline={key:(values[key],getattr(self,key).value()) for key in ('angle','minimum','maximum','distance','distance_minimum','distance_maximum')} if existing else {}
        self.heading.setText(tr('ジョイントを編集','Edit Joint') if existing else tr('現在の位置でジョイント','As-built Joint'))
        self.signatures={o.Name:self.signature(o) for o in self.candidates}
        Gui.Selection.addObserver(self);self.observing=True;self.begin()

    def targets(self):
        return tuple(self.doc.getObject(combo.currentData()) if combo.currentData() else None for combo in (self.moving,self.anchor))

    def values(self):
        direction=self.get_vector('axis') if self.axis.currentData()=='custom' else {'X':(1,0,0),'Y':(0,1,0),'Z':(0,0,1)}[self.axis.currentData()]
        return assembly.parameters(kind=self.kind.currentData(),origin=self.get_vector('origin'),axis=direction,
                                   angle=self.scalar_value('angle'),limited=self.limited.isChecked(),minimum=self.scalar_value('minimum'),maximum=self.scalar_value('maximum'),
                                   distance=self.scalar_value('distance'),distance_limited=self.distance_limited.isChecked(),
                                   distance_minimum=self.scalar_value('distance_minimum'),distance_maximum=self.scalar_value('distance_maximum'))

    def motion_fields(self):
        return ((self.distance,self.distance_limited,self.distance_minimum,self.distance_maximum,50) if self.kind.currentData()=='slider'
                else (self.angle,self.limited,self.minimum,self.maximum,180))

    def slide(self,value):
        if not self.active:return
        self.motion_fields()[0].setValue(self.slide_min+(self.slide_max-self.slide_min)*value/1000)

    def update_fields(self):
        rotate=self.kind.currentData()=='revolute'
        linear=self.kind.currentData()=='slider';movable=rotate or linear
        rotation_fields=[self.angle,self.limited,self.minimum,self.maximum,*self.origin]
        linear_fields=[self.distance,self.distance_limited,self.distance_minimum,self.distance_maximum]
        for label,field in self.rows:
            visible=(rotate if field in rotation_fields else linear if field in linear_fields else movable)
            if field in self.vector:visible=movable and self.axis.currentData()=='custom'
            if label:label.setVisible(visible)
            field.setVisible(visible)
        self.preferred_height=650 if rotate or (linear and self.axis.currentData()=='custom') else 550 if linear else 365
        if not movable and self.picking:self.picking=False;self.ticket+=1
        self.axis_label.setText(tr('移動軸','Translation axis') if linear else tr('回転軸','Rotation axis'))
        self.note.setText(tr('現在の配置を基準に接続します。0 mmが接続時の位置です。正の距離は緑の矢印方向、負の距離は逆方向に動きます。',
                            'Connects parts at their current placement. Zero mm is the connected position. Positive distance moves along the green arrow; negative distance reverses it.') if linear else
                          tr('現在の配置を基準に接続します。角度0°が接続時の位置です。部品の接触面を自動で合わせる機能ではありません。',
                             'Connects parts at their current placement. Zero degrees is the position when connected; mating faces are not automatically aligned.'))
        for field in self.vector:field.setEnabled(self.axis.currentData()=='custom')
        current,limited,minimum,maximum,step=self.motion_fields()
        for field in (minimum,maximum):field.setEnabled(limited.isChecked())
        extent=max(step,math.ceil(abs(current.value())/step)*step)
        self.slide_min=minimum.value() if limited.isChecked() else -extent
        self.slide_max=maximum.value() if limited.isChecked() else extent
        self.slider.setEnabled(self.slide_min<self.slide_max)
        self.slider.blockSignals(True)
        self.slider.setValue(round(1000*(current.value()-self.slide_min)/max(1e-9,self.slide_max-self.slide_min)))
        self.slider.blockSignals(False);self.pick_button.setChecked(self.picking)

    def toggle_pick(self):
        if not self.active:return
        self.picking=not self.picking;self.ticket+=1;Gui.Selection.clearSelection();self.update_preview()

    def addSelection(self,docname,objname,subname,point):
        if not self.active or not self.picking or docname!=self.doc.Name:return
        ticket=self.ticket
        def receive():
            if not self.active or not self.picking or self.ticket!=ticket:return
            try:
                moving,target=self.targets();self.check_sources([target])
                ref,sub=model_axis.reference(self.doc,objname,subname)
                origin,direction,kind=model_axis.geometry(ref,sub)
                inverse=target.getGlobalPlacement().inverse()
                self.set_vector('origin',tuple(inverse.multVec(origin)))
                self.set_vector('axis',tuple(inverse.Rotation.multVec(direction)))
                self.axis.setCurrentIndex(self.axis.findData('custom'));self.picking=False;self.ticket+=1
                Gui.Selection.clearSelection();self.update_preview()
            except Exception as error:self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))
        QtCore.QTimer.singleShot(0,receive)

    def marker(self,target,values):
        world=target.getGlobalPlacement();origin=world.multVec(App.Vector(*values['origin']))
        if values['kind']=='slider':
            moving,_=self.targets();origin=world.multVec(assembly.relative_pose(moving,target,self.existing).Base)
        direction=world.Rotation.multVec(App.Vector(*values['axis']))
        length=max(3,min(150,self.preview_shape.BoundBox.DiagonalLength*.75))
        node=self.overlay[1];light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(.15,.8,.3);material.transparency=0;node.addChild(material)
        style=coin.SoDrawStyle();style.lineWidth=3;node.addChild(style)
        coords=coin.SoCoordinate3();coords.point.setValues(0,2,[tuple(origin-direction*length),tuple(origin+direction*length)]);node.addChild(coords)
        line=coin.SoLineSet();line.numVertices.setValue(2);node.addChild(line)
        if values['kind']=='slider':
            # Arrowhead makes the sign of a linear distance visible, even for custom axes.
            side=direction.cross(App.Vector(0,0,1))
            if side.Length<1e-6:side=direction.cross(App.Vector(0,1,0))
            side.normalize();tip=origin+direction*length;back=tip-direction*length*.16
            head=coin.SoCoordinate3();head.point.setValues(0,3,[tuple(back+side*length*.07),tuple(tip),tuple(back-side*length*.07)]);node.addChild(head)
            lines=coin.SoLineSet();lines.numVertices.setValue(3);node.addChild(lines)

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        self.update_fields();self.position()
        try:
            moving,target=self.targets();self.check_sources([moving,target])
            if self.picking:
                self.status.setStyleSheet('color:#245b73;');self.status.setText(tr('直線の辺、または円筒の側面をクリックしてください。','Click a straight edge or cylindrical side face.'));return
            values=self.values();poses=assembly.preview(self.doc,moving,target,self.existing,**values)
            self.show_shape(Part.makeCompound(assembly.posed_shapes(poses)),'new')
            if values['kind']!='rigid':self.marker(target,values)
            self.hide(poses);self.valid=True;self.accept_button.setEnabled(True)
            self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('%d 部品を更新。確定するまで配置は変わりません。','Updates %d components. Placements change only on Confirm.')%len(poses))
        except Exception as error:self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def unobserve(self):
        self.ticket+=1;self.picking=False
        if self.observing:Gui.Selection.removeObserver(self);self.observing=False

    def eventFilter(self,widget,event):
        if (self.active and self.picking and widget in self.widgets and
                event.type() in (QtCore.QEvent.MouseButtonPress,QtCore.QEvent.MouseButtonRelease,QtCore.QEvent.MouseButtonDblClick)):
            if event.button()==QtCore.Qt.LeftButton:return False
        return super().eventFilter(widget,event)

    def cancel(self):
        if hasattr(self,'observing'):self.unobserve()
        super().cancel()

    def accept(self):
        if not self.active:return
        for field in self.spins:field.interpretText()
        self.update_preview()
        if not self.valid:return
        self.clear_preview()
        try:
            moving,target=self.targets()
            result=assembly.create_joint(self.doc,moving,target,self.existing,**self.values())
            self.unobserve();self.finish([result])
        except Exception as error:self.valid=False;self.accept_button.setEnabled(False);self.status.setText(str(error))

    def scalar_value(self, key):
        value = getattr(self, key).value()
        baseline = self.scalar_baseline.get(key)
        return baseline[0] if baseline is not None and value == baseline[1] else value
