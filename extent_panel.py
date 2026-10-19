"""Extrude with distance, an associative end plane, or through-all cutting."""
import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore,QtWidgets as W
from floating_panel import FloatingPanel
from i18n import tr
import model
import model_extents as extents
import browser


class ExtentPanel(FloatingPanel):
    layout_key='ExtrudePanel'
    preferred_height=760

    def build_fields(self,form):
        super().build_fields(form)
        self.extent=W.QComboBox()
        for title,key in ((tr('距離','Distance'),'distance'),(tr('面まで（平面）','To Face (Plane)'),'face'),
                          (tr('貫通','Through All'),'through')):self.extent.addItem(title,key)
        form.insertRow(3,tr('範囲','Extent'),self.extent)
        self.start_offset=self.spin();self.start_offset.setRange(-100000,100000);self.start_offset.setValue(0)
        self.start_offset_label=W.QLabel(tr('開始オフセット','Start Offset'))
        self.start_offset.setToolTip(tr('0はスケッチ面。正は片側方向、負はその反対に開始面を移動します。方向を切り替えても開始位置は変わりません。',
                                       'Zero starts at the sketch. Positive moves the start along the sketch forward normal; negative moves it backward. Changing Direction keeps the same start plane.'))
        form.insertRow(3,self.start_offset_label,self.start_offset)
        self.offset_note=W.QLabel(tr('＋は片側方向、−はその反対へ。距離・対称・勾配の基準もこの開始面です。',
                                     'Positive shifts forward; negative shifts backward. Length, symmetry and taper use this start plane.'))
        self.offset_note.setWordWrap(True);form.insertRow(4,self.offset_note)
        self.taper=W.QDoubleSpinBox();self.taper_second=W.QDoubleSpinBox()
        for field in (self.taper,self.taper_second):
            field.setRange(-89,89);field.setDecimals(3);field.setSuffix('°');field.setKeyboardTracking(False)
            field.setToolTip(tr('正：先端を広げる / 負：先端を狭める。開始面を基準に勾配を付けます。',
                               'Positive: widen the end. Negative: narrow the end. Taper is measured from the start plane.'))
        self.taper_label=W.QLabel(tr('勾配角','Taper Angle'))
        self.taper_second_label=W.QLabel(tr('反対側の勾配角','Reverse Taper'))
        form.addRow(self.taper_label,self.taper);form.addRow(self.taper_second_label,self.taper_second)
        self.taper_note=W.QLabel(tr('正の角度で先端を広げ、負の角度で狭めます。穴の内壁にも勾配が付きます。',
                                    'Positive widens the end; negative narrows it. Hole walls are tapered too.'))
        self.taper_note.setWordWrap(True);form.addRow(self.taper_note)
        self.spins=(*self.spins,self.start_offset,self.taper,self.taper_second)
        self.face_button=W.QPushButton(tr('終点の面を選択','Select End Face'))
        self.face_button.setCheckable(True);self.face_button.clicked.connect(self.select_face)
        self.face_label=W.QLabel();self.face_label.setWordWrap(True)
        form.addRow(self.face_button);form.addRow(self.face_label)
        self.end_offset=self.spin();self.end_offset.setRange(-100000,100000);self.end_offset.setValue(0)
        self.end_offset_label=W.QLabel(tr('終点オフセット','End Offset'))
        self.end_offset.setToolTip(tr('選んだ面から押し出し方向に測ります。＋は面を越えて延長、−は手前で停止します。逆方向でも＋はその方向へ延長します。',
                                     'Measured from the selected face along the extrusion direction. Positive extends beyond it; negative stops short. In Reverse, positive extends farther in the reverse direction.'))
        form.addRow(self.end_offset_label,self.end_offset)
        self.end_offset_note=W.QLabel(tr('＋は面を越えて延長、−は手前で停止。距離は押し出し方向に測り、斜めの終点面も平行にずらします。',
                                         'Positive extends beyond the face; negative stops short. Distance is along the extrusion direction; an angled end plane shifts parallel to itself.'))
        self.end_offset_note.setWordWrap(True);form.addRow(self.end_offset_note)
        self.spins=(*self.spins,self.end_offset)
        self.extent_note=W.QLabel();self.extent_note.setWordWrap(True);form.addRow(self.extent_note)
        self.combos=(*self.combos,self.extent)
        for field in (*self.combos,*self.spins,self.face_button):field.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        for label in (self.face_label,self.extent_note,self.taper_note,self.offset_note,self.end_offset_note):label.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum)
        self.extent.currentIndexChanged.connect(self.extent_changed)
        self.existing=None;self.limit=None;self.face_name='';self.picking_face=False;self.press=None
        self.observed=()

    def extent_changed(self,*args):
        mode=self.extent.currentData()
        self.picking_face=mode=='face' and self.limit is None
        if mode=='through':
            if not self.existing:self.operation.setCurrentIndex(self.operation.findData('cut'))
            self.direction.setCurrentIndex(self.direction.findData('symmetric'))
        elif mode=='face' and self.direction.currentData() not in ('forward','reverse'):
            self.direction.setCurrentIndex(0)
        self.schedule()

    def start(self,sketch=None,regions=None,index=0,existing=None):
        self.cancel();self.existing=existing;self.limit=None;self.face_name='';self.picking_face=False;self.press=None
        self.remember_dimensions()
        import parameters
        parameters.lock_fields(extents.tool(existing) if existing else None,
            {'Distance':self.distance,'Second':self.second,'TaperAngle':self.taper,'TaperAngleRev':self.taper_second,
             'StartOffset':self.start_offset,'EndOffset':self.end_offset})
        self.operation.setEnabled(True);self.profile.setEnabled(True)
        self.extent.setCurrentIndex(0)
        self.taper.setValue(0);self.taper_second.setValue(0)
        self.start_offset.setValue(0)
        self.end_offset.setValue(0)
        if not existing:
            self.heading.setText(tr('押し出し','Extrude'))
            super().start(sketch,regions,index)
            return
        self.doc=existing.Document;self.sketch=extents.tool(existing).SourceSketch
        self.regions=[];self.region_selection=[]
        self.signature=self.ws.region_picker.signature(self.sketch)
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        self.heading.setText(tr('押し出しを編集','Edit Extrusion'))
        self.profile.clear()
        for i,face in enumerate(extents.stored_faces(existing)):
            item=W.QListWidgetItem(tr('領域 %d — %.2f mm²')%(i+1,face.Area))
            item.setData(QtCore.Qt.UserRole,i);item.setCheckState(QtCore.Qt.Checked);self.profile.addItem(item)
        self.profile.setEnabled(False)
        values=extents.settings(existing)
        self.limit=values['limit'];self.face_name=values['face_name']
        self.operation.setCurrentIndex(self.operation.findData(values['operation']));self.operation.setEnabled(False)
        self.target.clear()
        if values['target']:self.target.addItem(values['target'].Label,values['target'].Name)
        self.extent.setCurrentIndex(self.extent.findData(values['extent']))
        self.direction.setCurrentIndex(self.direction.findData(values['direction']))
        self.distance.setValue(values['distance']);self.second.setValue(values['second'])
        self.taper.setValue(values['taper']);self.taper_second.setValue(values['taper_second'])
        self.start_offset.setValue(values['start_offset'])
        self.end_offset.setValue(values['end_offset'])
        self.remember_dimensions(values)
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.active=True;self.panel.show();self.update_preview();self.position()

    def parameters(self):
        values=super().parameters()
        values.update(extent=self.extent.currentData(),limit=self.limit if self.extent.currentData()=='face' else None,
                      face_name=self.face_name if self.extent.currentData()=='face' else '',
                      start_offset=self.start_offset.value(),
                      end_offset=self.end_offset.value() if self.extent.currentData()=='face' else 0,
                      taper=self.taper.value(),
                      taper_second=self.taper_second.value() if self.extent.currentData()=='distance' and self.direction.currentData()=='two' else 0)
        if values['operation']=='new':values['target']=None
        return self.dimension_values(values)

    def select_face(self):
        if self.active:self.picking_face=True;self.update_preview()

    def update_fields(self,values):
        mode=values['extent'];two=mode=='distance' and values['direction']=='two'
        self.offset_note.setVisible(bool(values['start_offset']))
        self.distance.setVisible(mode=='distance');self.distance_label.setVisible(mode=='distance')
        self.distance_label.setText(tr('全長') if values['direction']=='symmetric' else tr('距離'))
        self.second.setVisible(two);self.second_label.setVisible(two)
        self.taper.setVisible(True);self.taper_label.setVisible(True)
        self.taper_second.setVisible(two);self.taper_second_label.setVisible(two)
        self.taper_note.setVisible(True)
        self.taper_note.setText(tr('正の角度で先端を広げ、負の角度で狭めます。穴の内壁にも勾配が付きます。',
                                   'Positive widens the end; negative narrows it. Hole walls are tapered too.'))
        self.target.setEnabled(values['operation']!='new' and not self.existing)
        self.face_button.setVisible(mode=='face');self.face_label.setVisible(mode=='face')
        self.end_offset.setVisible(mode=='face');self.end_offset_label.setVisible(mode=='face');self.end_offset_note.setVisible(mode=='face')
        self.face_button.setChecked(self.picking_face)
        self.face_label.setText(self.limit.Label+' / '+self.face_name if self.limit and self.limit.Document else tr('終点の面を選択してください。','Select the end face.'))
        self.direction.setItemText(2,tr('両方向','Both Directions') if mode=='through' else tr('対称（指定距離が全長）'))
        for i in range(self.direction.count()):
            allowed=(mode=='distance' or i<2 or (mode=='through' and i==2))
            self.direction.model().item(i).setEnabled(allowed)
        for i in range(self.operation.count()):self.operation.model().item(i).setEnabled(mode!='through' or self.operation.itemData(i)=='cut')
        self.extent.model().item(2).setEnabled(not self.existing or values['operation']=='cut')
        self.extent_note.setVisible(mode!='distance')
        self.extent_note.setText(tr('終点の平面まで押し出します。面の外側も同じ平面として延長します。面の移動にも追従します。',
                                    'Extrudes to the selected plane, extending it beyond the face boundary. Follows movement of that plane.') if mode=='face' else
                                 tr('対象ボディの厚さに合わせて切り抜きます。両方向は開始面の両側を貫通します。',
                                    'Cuts through the target thickness. Both Directions cuts on both sides of the start plane.'))

    def watches(self):
        values=self.parameters()
        return extents.signature([self.sketch,values['target'],values['limit']])

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        try:
            values=self.parameters();self.update_fields(values)
            if self.ws.region_picker.signature(self.sketch)!=self.signature:
                raise ValueError(tr('スケッチが変更されました。キャンセルして領域を選び直してください。'))
            if self.picking_face and values['extent']=='face':
                # Reveal the original boolean target while selecting an end face.
                if self.existing:
                    self.hidden.append((self.existing,bool(self.existing.Visibility)));self.existing.Visibility=False
                    if values['target']:
                        target=values['target'];self.hidden.append((target,bool(target.Visibility)));target.Visibility=True
                self.status.setStyleSheet('color:#245b73;');self.status.setText(tr('終点にする平らな面か構築平面をクリックしてください。',
                                                                               'Click a planar face or construction plane for the end.'))
                return
            faces=extents.stored_faces(self.existing) if self.existing else extents.profile_faces(self.sketch,self.regions,values.pop('indices'))
            values.pop('indices',None)
            result=extents.preview(faces,self.sketch,**values)
            if self.existing:result.Placement=self.existing.Placement.multiply(result.Placement)
            self.show_shape(result,values['operation'])
            hidden=self.existing or (values['target'] if values['operation']!='new' else None)
            if hidden:self.hidden.append((hidden,bool(hidden.Visibility)));hidden.Visibility=False
            self.valid=True;self.accept_button.setEnabled(True);self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('結果の体積：%.3f mm³\n%s のプレビュー','Result volume: %.3f mm³\n%s preview')%(result.Volume,self.operation.currentText()))
        except Exception as error:
            self.clear_preview();self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))
        finally:
            try:self.observed=self.watches()
            except (RuntimeError,ReferenceError):self.observed=()

    def accept(self):
        if not self.active:return
        for spin in self.spins:spin.interpretText()
        self.update_preview()
        if not self.active or not self.valid:return
        values=self.parameters();self.clear_preview()
        try:
            if values['extent']=='distance' and not self.existing and not values['taper'] and not values['taper_second'] and not values['start_offset']:
                for key in ('extent','limit','face_name','taper','taper_second','start_offset','end_offset'):values.pop(key)
                results=model.create_extrusions(self.doc,self.sketch,**values)
            else:results=extents.create(self.doc,self.sketch,existing=self.existing,**values)
        except Exception as error:
            self.valid=False;self.accept_button.setEnabled(False);self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error));return
        self.active=False;self.timer.stop();self.panel.hide();self.ws.region_picker.clear()
        Gui.Selection.clearSelection()
        for result in results:Gui.Selection.addSelection(result)
        self.ws.refresh()
        self.ws.main.statusBar().showMessage(tr('押し出しを作成・更新しました。Ctrl＋Zで元に戻せます。',
                                               'Extrusion created or updated. Ctrl+Z to undo.'),8000)

    def ray(self,widget,point):
        view=Gui.activeDocument().activeView();node=view.getCameraNode();rotation=view.getCameraOrientation()
        height=self.ws.mouse.camera_height(node)
        offset=rotation.multVec(App.Vector((point.x()-widget.width()/2)*height/widget.height(),(widget.height()/2-point.y())*height/widget.height(),0))
        origin=App.Vector(*node.position.getValue().getValue());direction=rotation.multVec(App.Vector(0,0,-1))
        if hasattr(node,'height'):origin+=offset
        else:direction=direction*node.focalDistance.getValue()+offset;direction.normalize()
        return origin,direction

    def pick_face(self,widget,point):
        try:
            origin,direction=self.ray(widget,point)
            candidates=[o for o,title in browser.collect(self.doc)[0]]
            candidates += [o for o in self.doc.Objects if getattr(o,'FluxPlane',False)]
            if self.existing and extents.tool(self.existing).Target:candidates.append(extents.tool(self.existing).Target)
            excluded=[self.existing,*self.existing.InListRecursive] if self.existing else []
            hits=[]
            for obj in set(candidates):
                if obj in excluded or not obj.Visibility:continue
                shape=model.world_shape(obj);length=(shape.BoundBox.Center-origin).Length+shape.BoundBox.DiagonalLength+1
                ray=Part.makeLine(origin,origin+direction*length)
                for i,face in enumerate(shape.Faces):
                    for vertex in face.section(ray).Vertexes:hits.append(((vertex.Point-origin).Length,obj,'Face%d'%(i+1)))
            if not hits:raise ValueError(tr('終点にする平らな面をクリックしてください。','Click a planar end face.'))
            _,obj,name=min(hits,key=lambda x:x[0]);extents.plane(obj,name)
            self.limit,self.face_name=obj,name;self.picking_face=False;self.update_preview()
        except Exception as error:
            self.valid=False;self.accept_button.setEnabled(False);self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def refresh(self):
        super().refresh()
        if not self.active:return
        try:
            if self.existing and not self.existing.Document:self.cancel();return
            if self.observed!=self.watches():self.update_preview()
        except (RuntimeError,ReferenceError):self.cancel()

    def eventFilter(self,widget,event):
        if getattr(getattr(self.ws,'cube',None),'forwarding',False):return False
        if self.active and self.picking_face and widget in self.widgets:
            if event.type()==QtCore.QEvent.MouseButtonPress and event.button()==QtCore.Qt.LeftButton:
                self.press=(widget,QtCore.QPointF(event.position()));return True
            if event.type()==QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.LeftButton:
                press=self.press;self.press=None
                if press and press[0]==widget and (event.position()-press[1]).manhattanLength()<W.QApplication.startDragDistance():self.pick_face(widget,event.position())
                return True
        return super().eventFilter(widget,event)

    def remember_dimensions(self, values=None):
        self.dimension_exact = dict(values or {})
        self.dimension_shown = {key: getattr(self, key).value() for key in ('distance', 'second', 'taper', 'taper_second', 'start_offset', 'end_offset')}

    def dimension_values(self, values):
        exact = getattr(self, 'dimension_exact', {})
        shown = getattr(self, 'dimension_shown', {})
        for key in ('distance', 'second', 'taper', 'taper_second', 'start_offset', 'end_offset'):
            if key == 'end_offset' and values['extent'] != 'face':
                continue
            if key == 'taper_second' and not (values['extent'] == 'distance' and values['direction'] == 'two'):
                continue
            if key in exact and key in shown and getattr(self, key).value() == shown[key]:
                values[key] = exact[key]
        return values
