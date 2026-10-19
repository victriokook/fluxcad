"""Pick a planar drilling face and position, with a non-destructive preview."""
import math
import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtWidgets as W
from pivy import coin
from i18n import tr
from floating_panel import FloatingPanel
import browser
import model
import model_hole as holes
import model_thread as threads


class HolePanel(FloatingPanel):
    layout_key = 'HolePanel'
    preferred_height = 555

    def build_fields(self, form):
        self.face_button = W.QPushButton(tr('面を選択', 'Select Face'))
        self.face_button.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Fixed)
        self.face_button.setCheckable(True); self.face_button.clicked.connect(self.select_face)
        form.addRow(tr('穴を開ける面', 'Drilling face'), self.face_button)
        self.face_label = W.QLabel(); self.face_label.setWordWrap(True); form.addRow(self.face_label)
        self.face_label.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Minimum)
        self.kind = W.QComboBox()
        for title,key in ((tr('通常の穴','Simple'),'simple'),(tr('ザグリ穴','Counterbore'),'counterbore'),
                          (tr('皿穴','Countersink'),'countersink'),(tr('ねじ穴','Threaded'),'threaded')):
            self.kind.addItem(title,key)
        self.kind.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Fixed)
        form.addRow(tr('穴の種類','Hole type'),self.kind)
        self.mode = W.QComboBox()
        self.mode.addItem(tr('貫通', 'Through All'), True)
        self.mode.addItem(tr('深さを指定', 'Distance'), False)
        self.mode.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Fixed)
        form.addRow(tr('範囲', 'Extent'), self.mode)
        self.diameter = self.spin(); self.diameter.setValue(8)
        self.diameter_label=W.QLabel(tr('直径','Diameter'));form.addRow(self.diameter_label, self.diameter)
        self.depth = self.spin(); self.depth.setValue(10)
        self.depth_label = W.QLabel(tr('深さ','Depth')); form.addRow(self.depth_label,self.depth)
        self.depth.setToolTip(tr('選択した面から穴の底までの全体の深さです。',
                                 'Total depth measured from the selected face to the flat hole bottom.'))
        self.head_diameter = self.spin(); self.head_diameter.setValue(14)
        self.head_depth = self.spin(); self.head_depth.setValue(3)
        self.angle = self.spin(); self.angle.setSuffix('°'); self.angle.setRange(1,179); self.angle.setValue(90)
        self.angle.setToolTip(tr('円すいの全角です。半角ではありません。', 'Full included cone angle, not the half angle.'))
        self.head_diameter_label = W.QLabel()
        self.head_depth_label = W.QLabel(tr('ザグリ深さ','Recess depth'))
        self.angle_label = W.QLabel(tr('皿角度','Sink angle'))
        for label,field in ((self.head_diameter_label,self.head_diameter),
                            (self.head_depth_label,self.head_depth),(self.angle_label,self.angle)):
            form.addRow(label,field)
        self.recess_hint = W.QLabel(); self.recess_hint.setWordWrap(True)
        self.recess_hint.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);form.addRow(self.recess_hint)
        self.thread_type=W.QComboBox()
        for title,key in ((tr('メートル並目','Metric coarse'),threads.TYPES[0]),(tr('メートル細目','Metric fine'),threads.TYPES[1])):
            self.thread_type.addItem(title,key)
        self.thread_size=W.QComboBox();self.thread_catalog_type=None
        self.thread_direction=W.QComboBox()
        for title,key in ((tr('右ねじ','Right hand'),'Right'),(tr('左ねじ','Left hand'),'Left')):self.thread_direction.addItem(title,key)
        self.thread_full=W.QComboBox()
        self.thread_full.addItem(tr('穴と同じ深さ','Full hole depth'),True)
        self.thread_full.addItem(tr('深さを指定','Specify depth'),False)
        self.thread_depth=self.spin();self.thread_depth.setValue(threads.DEFAULTS['thread_depth'])
        self.thread_rows=[]
        for text,field in ((tr('ねじ規格','Standard'),self.thread_type),(tr('呼び径 × ピッチ','Size × pitch'),self.thread_size),
                           (tr('ねじ方向','Handedness'),self.thread_direction),(tr('ねじ範囲','Thread extent'),self.thread_full),
                           (tr('ねじ深さ','Thread depth'),self.thread_depth)):
            label=W.QLabel(text);form.addRow(label,field);self.thread_rows.append((label,field))
            field.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        self.model_thread=W.QCheckBox(tr('ねじ山を実体化','Model thread'))
        self.model_thread.toggled.connect(self.schedule);form.addRow(self.model_thread)
        self.thread_hint=W.QLabel();self.thread_hint.setWordWrap(True);form.addRow(self.thread_hint)
        self.u = self.spin(); self.v = self.spin()
        for field in (self.u, self.v):field.setRange(-100000,100000);field.setDecimals(4)
        form.addRow(tr('面内 U', 'Face U'), self.u); form.addRow(tr('面内 V', 'Face V'), self.v)
        self.snap = W.QCheckBox(tr('クリック位置をスナップ', 'Snap Clicked Position')); self.snap.setChecked(True)
        self.step = self.spin(); self.step.setValue(1)
        for field in (self.diameter,self.depth,self.head_diameter,self.head_depth,self.angle,self.u,self.v,self.step):
            field.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Fixed)
        form.addRow(self.snap); form.addRow(tr('スナップ間隔', 'Snap spacing'), self.step)
        note = W.QLabel(tr('平らな面をクリックして穴を配置します。\nその後は同じ面をクリックして位置を変更できます。\nU・Vはボディの配置原点を面に投影した点が基準です。数値入力はスナップしません。',
                            'Click a planar face to place the hole, then click that face to reposition it.\nU and V are measured from the body placement origin projected onto the face. Numeric inputs are not snapped.'))
        note.setWordWrap(True); note.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Minimum); form.addRow(note)
        for label in (self.face_label,self.recess_hint,self.thread_hint,note):
            policy=W.QSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);policy.setHeightForWidth(True);label.setSizePolicy(policy)
        self.combos = (self.kind,self.mode,self.thread_type,self.thread_size,self.thread_direction,self.thread_full)
        self.spins = (self.diameter,self.depth,self.head_diameter,self.head_depth,self.angle,self.u,self.v,self.thread_depth)

    def populate_threads(self):
        kind=self.thread_type.currentData()
        if self.thread_catalog_type==kind:return
        previous=self.thread_size.currentData()
        self.thread_size.blockSignals(True)
        try:
            self.thread_size.clear()
            for size,diameter,pitch,drill in threads.catalog(kind):self.thread_size.addItem(size.replace('x',' × '),size)
            preferred=previous or ('M6x1.0' if kind==threads.TYPES[0] else 'M6x0.75')
            index=self.thread_size.findData(preferred)
            if index<0:index=self.thread_size.findData('M6x1.0' if kind==threads.TYPES[0] else 'M6x0.75')
            self.thread_size.setCurrentIndex(max(0,index));self.thread_catalog_type=kind
        finally:self.thread_size.blockSignals(False)

    def update_fields(self):
        kind = self.kind.currentData()
        threaded=kind=='threaded';recess=kind in ('counterbore','countersink')
        self.preferred_height=650 if threaded else 555
        self.diameter.setVisible(not threaded);self.diameter_label.setVisible(not threaded)
        for label,field in self.thread_rows:label.setVisible(threaded);field.setVisible(threaded)
        self.model_thread.setVisible(threaded);self.thread_hint.setVisible(threaded)
        self.thread_depth.setEnabled(not self.thread_full.currentData())
        if threaded:
            self.populate_threads()
            info=threads.specification(self.thread_type.currentData(),self.thread_size.currentData())
            self.thread_hint.setText(tr('公差等級：6H / 下穴径：%g mm\n','Class: 6H / Tap drill: %g mm\n')%info[3]+
                (tr('ねじ山を生成します（1〜50ピッチ）。計算に数秒かかります。',
                    'Generates helical geometry (1–50 pitches). Calculation takes a few seconds.') if self.model_thread.isChecked() else
                 tr('軽量表示：下穴とねじ情報を保存します。STL・STEPにねじ山を出す場合は実体化してください。',
                    'Lightweight: stores a tap-drill hole and thread data. Enable modeling for threads in STL/STEP.')))
        for label,field,visible in ((self.head_diameter_label,self.head_diameter,recess),
                                    (self.head_depth_label,self.head_depth,kind=='counterbore'),
                                    (self.angle_label,self.angle,kind=='countersink')):
            label.setVisible(visible);field.setVisible(visible)
        self.head_diameter_label.setText(tr('ザグリ径','Recess diameter') if kind=='counterbore' else tr('皿穴径','Sink diameter'))
        self.depth_label.setText(tr('全体の深さ','Total depth') if recess else tr('深さ','Depth'))
        self.depth.setEnabled(not self.mode.currentData())
        self.recess_hint.setVisible(recess)
        if kind=='counterbore':
            self.recess_hint.setText(tr('ザグリ深さ・全体の深さは、どちらも選択面からの距離です。',
                                        'Recess depth and total depth are both measured from the selected face.'))
        elif kind=='countersink':
            try:
                recess=holes.recess_depth(kind,self.diameter.value(),self.head_diameter.value(),self.head_depth.value(),self.angle.value())
                self.recess_hint.setText(tr('皿角度は全角です。皿穴部分の深さ：%g mm',
                                            'Angle is the full included angle. Recess depth: %g mm')%recess)
            except ValueError:self.recess_hint.setText('')

        import parameters
        tool = self.existing.Tool if getattr(self,'existing',None) else None
        parameters.lock_fields(tool, {'U':self.u,'V':self.v,'Diameter':self.diameter,'Depth':self.depth,
                                     'HeadDiameter':self.head_diameter,'HeadDepth':self.head_depth,'SinkAngle':self.angle})
        if self.mode.currentData():self.depth.setEnabled(False)
        self.kind.setEnabled(not tool or not any(parameters.expression(tool,p) for p in ('Diameter','HeadDiameter','HeadDepth','SinkAngle')))
        self.mode.setEnabled(not tool or not parameters.expression(tool,'Depth'))

    def start(self, existing=None):
        self.cancel()
        self.doc = App.ActiveDocument
        if not self.doc:raise ValueError(tr('穴あけするソリッドを作成してください。', 'Create a solid before drilling.'))
        self.existing = existing
        self.source = None; self.face_name = None; self.press = None; self.picking_face = True
        self.selection = [(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        self.heading.setText(tr('穴を編集', 'Edit Hole') if existing else tr('穴', 'Hole'))
        for field,key in ((self.u,'u'),(self.v,'v'),(self.diameter,'diameter'),(self.depth,'depth'),
                          (self.head_diameter,'head_diameter'),(self.head_depth,'head_depth'),(self.angle,'angle')):
            field.setValue(holes.DEFAULTS[key])
        self.remember_position(holes.DEFAULTS['u'],holes.DEFAULTS['v'])
        self.kind.setCurrentIndex(0)
        self.mode.setCurrentIndex(0)
        self.thread_type.setCurrentIndex(0);self.thread_direction.setCurrentIndex(0)
        self.thread_full.setCurrentIndex(0);self.thread_depth.setValue(threads.DEFAULTS['thread_depth'])
        self.model_thread.setChecked(False)
        if self.thread_size.count():self.thread_size.setCurrentIndex(self.thread_size.findData(threads.DEFAULTS['thread_size']))
        self.update_fields()  # Clear the previous feature's locks before a face pick.
        if existing:
            self.source, self.face_name = holes.source_face(existing)
            values = holes.settings(existing)
            for field,key in ((self.u,'u'),(self.v,'v'),(self.diameter,'diameter'),(self.depth,'depth'),
                              (self.head_diameter,'head_diameter'),(self.head_depth,'head_depth'),(self.angle,'angle')):
                field.setValue(values[key])
            self.remember_position(values['u'],values['v'])
            self.kind.setCurrentIndex(self.kind.findData(values['kind']))
            self.mode.setCurrentIndex(0 if values['through'] else 1)
            if values['kind']=='threaded':
                self.thread_type.setCurrentIndex(self.thread_type.findData(values['thread_type']));self.populate_threads()
                self.thread_size.setCurrentIndex(self.thread_size.findData(values['thread_size']))
                self.thread_direction.setCurrentIndex(self.thread_direction.findData(values['thread_direction']))
                self.thread_full.setCurrentIndex(0 if values['thread_full'] else 1)
                self.thread_depth.setValue(values['thread_depth']);self.model_thread.setChecked(values['model_thread'])
            self.picking_face = False
            self.signature = holes.signature(self.source, stable_frame=holes.use_stable_frame(self.existing))
        else:
            selected = Gui.Selection.getSelectionEx()
            if any(hasattr(s.Object,'Mesh') for s in selected):
                raise ValueError(tr('この穴あけはソリッド用です。メッシュは対象外です。', 'This Hole tool works on solids, not meshes.'))
            refs = [(s,name,i) for s in selected for i,name in enumerate(s.SubElementNames)]
            if len(refs) == 1:
                sel,name,index = refs[0]
                self.source,self.face_name = holes.reference(self.doc,sel.ObjectName,name)
                f,origin,a,b,n = holes.frame(self.source,self.face_name)
                point = (sel.PickedPoints[index] if index < len(sel.PickedPoints)
                         else self.source.getGlobalPlacement().multVec(f.CenterOfMass))
                local=self.source.getGlobalPlacement().inverse().multVec(point)
                if abs((local-origin).dot(n))>1e-5:
                    point=self.source.getGlobalPlacement().multVec(f.CenterOfMass)
                self.set_point(point, snap=False)
                self.signature = holes.signature(self.source, stable_frame=holes.use_stable_frame(self.existing)); self.picking_face = False
        self.ws.region_picker.ticket += 1; self.ws.region_picker.clear()
        self.remember_dimensions()
        self.active = True; self.panel.show(); self.update_preview(); self.position()

    def pose(self):
        return self.existing.getGlobalPlacement() if self.existing else App.Placement()

    def remember_position(self, u, v):
        self.position_exact = {'u': float(u), 'v': float(v)}
        self.position_shown = {'u': self.u.value(), 'v': self.v.value()}

    def position_values(self):
        values = {'u': self.u.value(), 'v': self.v.value()}
        exact = getattr(self, 'position_exact', {})
        shown = getattr(self, 'position_shown', {})
        for key in ('u', 'v'):
            if key in exact and key in shown and values[key] == shown[key]:
                values[key] = exact[key]
        return values

    def set_point(self, point, snap=True):
        u, v = holes.coordinates(self.source, self.face_name, self.pose().inverse().multVec(point), stable_frame=holes.use_stable_frame(self.existing))
        if snap and self.snap.isChecked():
            step = self.step.value()
            u, v = (math.copysign(math.floor(abs(x) / step + .5) * step, x) for x in (u, v))
        previous = self.position_values()
        if self.u.isEnabled():
            self.u.setValue(u)
        else:
            u = previous['u']
        if self.v.isEnabled():
            self.v.setValue(v)
        else:
            v = previous['v']
        self.remember_position(u, v)

    def parameters(self):
        position = self.position_values()
        values = dict(u=position['u'], v=position['v'], diameter=self.diameter.value(),
                      depth=self.depth.value(), through=self.mode.currentData(), kind=self.kind.currentData(),
                      head_diameter=self.head_diameter.value(), head_depth=self.head_depth.value(), angle=self.angle.value())
        if values['kind'] == 'threaded':
            values.update(thread_type=self.thread_type.currentData(), thread_size=self.thread_size.currentData(),
                          thread_direction=self.thread_direction.currentData(), model_thread=self.model_thread.isChecked(),
                          thread_full=self.thread_full.currentData(), thread_depth=self.thread_depth.value())
        values['stable_frame'] = holes.use_stable_frame(self.existing)
        return self.dimension_values(values)

    def select_face(self):
        if self.active:self.picking_face=True;self.update_preview()

    def pick(self, widget, point):
        if App.ActiveDocument != self.doc:self.cancel();return
        try:
            origin,direction = self.ray(widget,point)
            if self.picking_face:
                candidates = [(obj,model.world_shape(obj)) for obj,title in browser.collect(self.doc)[0]
                              if obj.Visibility and obj != self.existing]
                if self.existing:candidates=[]
                if self.source:
                    shape=model.world_shape(self.source);shape.Placement=self.pose().multiply(shape.Placement)
                    candidates=[(o,s) for o,s in candidates if o!=self.source]+[(self.source,shape)]
                hits=[]
                for obj,shape in candidates:
                    length=(shape.BoundBox.Center-origin).Length+shape.BoundBox.DiagonalLength+1
                    ray=Part.makeLine(origin,origin+direction*length)
                    for index,face in enumerate(shape.Faces):
                        for vertex in face.section(ray).Vertexes:
                            hits.append(((vertex.Point-origin).Length,obj,'Face%d'%(index+1),vertex.Point))
                if not hits:raise ValueError(tr('ソリッドの平らな面をクリックしてください。', 'Click a planar face of a solid.'))
                distance,source,name,hit = min(hits,key=lambda x:x[0])
                holes.frame(source,name)  # Reject the front curved face, never pick through it.
                self.source,self.face_name = source,name
                self.signature=holes.signature(source, stable_frame=holes.use_stable_frame(self.existing));self.picking_face=False
            else:
                if holes.signature(self.source, stable_frame=holes.use_stable_frame(self.existing))!=self.signature:
                    raise ValueError(tr('元の形状が変更されました。「面を選び直す」を押してください。',
                                        'The source changed. Click Reselect Face.'))
                face,center,a,b,n = holes.frame(self.source,self.face_name)
                pose=self.pose().multiply(self.source.getGlobalPlacement())
                center=pose.multVec(center);n=pose.Rotation.multVec(n)
                denominator=direction.dot(n)
                if abs(denominator)<1e-9:raise ValueError(tr('面が真横を向いています。視点を回転してください。', 'The face is edge-on. Rotate the view.'))
                distance=(center-origin).dot(n)/denominator
                if distance<0:raise ValueError(tr('面を見える向きに回転してください。', 'Rotate the view to see the face.'))
                hit=origin+direction*distance
            self.set_point(hit);self.update_preview()
        except Exception as error:
            self.valid=False;self.accept_button.setEnabled(False)
            self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def marker(self):
        position=self.position_values()
        center,u,v,n = holes.placement_frame(self.source,self.face_name,position['u'],position['v'], stable_frame=holes.use_stable_frame(self.existing))
        pose=self.pose();center=pose.multVec(center);u=pose.Rotation.multVec(u);v=pose.Rotation.multVec(v);n=pose.Rotation.multVec(n)
        center+=n*.003
        radii=[self.diameter.value()/2]
        if self.kind.currentData() in ('counterbore','countersink'):radii.append(self.head_diameter.value()/2)
        elif self.kind.currentData()=='threaded':
            info=threads.specification(self.thread_type.currentData(),self.thread_size.currentData());radii=[info[1]/2,info[3]/2]
        radius=max(radii)
        points=[center+u*(r*math.cos(i*math.pi/32))+v*(r*math.sin(i*math.pi/32)) for r in radii for i in range(65)]
        node=coin.SoSeparator();light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(1,.68,.05);material.transparency=0;node.addChild(material)
        style=coin.SoDrawStyle();style.lineWidth=2;node.addChild(style)
        coords=coin.SoCoordinate3();coords.point.setValues(0,len(points),[tuple(p) for p in points]);node.addChild(coords)
        line=coin.SoLineSet();line.numVertices.setValues(0,len(radii),[65]*len(radii));node.addChild(line)
        for direction,label,color in ((u,'U',(1,.25,.18)),(v,'V',(.2,.8,.35))):
            axis=coin.SoSeparator();material=coin.SoMaterial();material.diffuseColor=color;axis.addChild(material)
            coords=coin.SoCoordinate3();coords.point.setValues(0,2,[tuple(center),tuple(center+direction*radius*1.5)]);axis.addChild(coords)
            line=coin.SoLineSet();line.numVertices.setValue(2);axis.addChild(line)
            translation=coin.SoTranslation();translation.translation=tuple(center+direction*radius*1.6);axis.addChild(translation)
            text=coin.SoText2();text.string=label;axis.addChild(text);node.addChild(axis)
        self.overlay[1].addChild(node)

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        self.update_fields()
        self.position()
        self.face_button.setChecked(self.picking_face)
        self.face_button.setText(tr('面を選択', 'Select Face') if not self.face_name else tr('面を選び直す', 'Reselect Face'))
        self.face_label.setText(self.source.Label+' / '+self.face_name if self.face_name else tr('平らな面をクリックしてください。', 'Click a planar face.'))
        try:
            if self.picking_face:
                if self.existing:
                    shape=model.world_shape(self.source);shape.Placement=self.pose().multiply(shape.Placement)
                    self.show_shape(shape,'new');self.hidden.append((self.existing,bool(self.existing.Visibility)));self.existing.Visibility=False
                self.status.setStyleSheet('color:#245b73;')
                self.status.setText(tr('穴を開ける平らな面をクリックしてください。', 'Click the planar face to drill.'))
                return
            if holes.signature(self.source, stable_frame=holes.use_stable_frame(self.existing))!=self.signature:
                raise ValueError(tr('元の形状が変更されました。「面を選び直す」を押してください。', 'The source changed. Click Reselect Face.'))
            result=holes.preview(self.source,self.face_name,**self.parameters())
            result.Placement=self.pose().multiply(result.Placement)
            self.show_shape(result,'new');self.marker()
            hidden=self.existing or self.source;self.hidden.append((hidden,bool(hidden.Visibility)));hidden.Visibility=False
            self.valid=True;self.accept_button.setEnabled(True)
            self.status.setStyleSheet('color:#245b73;')
            self.status.setText(self.kind.currentText()+'\n'+tr('直径 %g mm / %s\n面をクリックして位置変更できます。',
                                   'Diameter %g mm / %s\nClick the face to reposition.')%(self.diameter.value(),
                                   tr('貫通','Through All') if self.mode.currentData() else tr('深さ %g mm','Depth %g mm')%self.depth.value()))
            if self.kind.currentData()=='threaded':
                self.status.setText(self.thread_size.currentText()+' / 6H / '+self.thread_direction.currentText()+'\n'+
                    tr('面をクリックして位置変更できます。','Click the face to reposition.'))
        except Exception as error:
            self.clear_preview();self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def accept(self):
        if not self.active:return
        for field in self.spins:field.interpretText()
        self.update_preview()
        if not self.active or not self.valid:return
        self.clear_preview()
        try:result=holes.create(self.doc,self.source,self.face_name,existing=self.existing,**self.parameters())
        except Exception as error:
            self.valid=False;self.accept_button.setEnabled(False);self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error));return
        self.active=False;self.timer.stop();self.panel.hide();self.ws.region_picker.clear()
        Gui.Selection.clearSelection();Gui.Selection.addSelection(result);self.ws.refresh()
        self.ws.main.statusBar().showMessage(tr('穴を作成・更新しました。履歴のダブルクリックで編集、Ctrl＋Zで元に戻せます。',
                                               'Hole created or updated. Double-click its history entry to edit; Ctrl+Z to undo.'),8000)

    def refresh(self):
        if not self.active:return
        try:
            if App.ActiveDocument!=self.doc or self.ws.current_sketch() or (self.source and not self.source.Document) or (self.existing and not self.existing.Document):
                self.cancel();return
            if self.source and not self.picking_face and holes.signature(self.source, stable_frame=holes.use_stable_frame(self.existing))!=self.signature and self.valid:self.update_preview()
        except (RuntimeError,ReferenceError):self.cancel();return
        self.position()

    def eventFilter(self,widget,event):
        if getattr(getattr(self.ws,'cube',None),'forwarding',False):return False
        if self.active and widget in self.widgets:
            kind=event.type()
            if kind==QtCore.QEvent.MouseButtonPress and event.button()==QtCore.Qt.LeftButton:
                self.press=(widget,QtCore.QPointF(event.position()));return True
            if kind==QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.LeftButton:
                press=self.press;self.press=None
                if press and press[0]==widget and (event.position()-press[1]).manhattanLength()<W.QApplication.startDragDistance():
                    self.pick(widget,event.position())
                return True
        return super().eventFilter(widget,event)

    def remember_dimensions(self):
        keys = ('diameter', 'depth', 'head_diameter', 'head_depth', 'angle', 'thread_depth')
        self.dimension_exact = holes.settings(self.existing) if self.existing else {}
        self.dimension_shown = {key: getattr(self, key).value() for key in keys}

    def dimension_values(self, values):
        exact = getattr(self, 'dimension_exact', {})
        shown = getattr(self, 'dimension_shown', {})
        for key in ('diameter', 'depth', 'head_diameter', 'head_depth', 'angle', 'thread_depth'):
            if key in values and key in exact and key in shown and getattr(self, key).value() == shown[key]:
                values[key] = exact[key]
        return values
