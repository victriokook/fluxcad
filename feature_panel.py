"""Modeling controls sharing the extrusion preview overlay."""
from i18n import tr
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from floating_panel import FloatingPanel
from pivy import coin
import model_axis
import model_mirror
import model
import model_features as features
import model_sections
import model_planes


class FeaturePanel(FloatingPanel):
    layout_key = "FeaturePanel"
    preferred_height = 520

    def __init__(self,ws):
        super().__init__(ws)
        policy=W.QSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);policy.setHeightForWidth(True)
        self.status.setSizePolicy(policy)

    def build_fields(self,form):
        self.rows = {}
        def row(key,title,widget):
            label = W.QLabel(title)
            form.addRow(label,widget)
            self.rows[key] = (label,widget)
            return widget
        self.profile = row('profile',tr('プロファイル'),W.QComboBox())
        self.axis_mode=row('axis_mode',tr('軸の指定','Axis Type'),W.QComboBox())
        for title,key in ((tr('全体座標の軸','World Axis'),'world'),(tr('辺・円筒面・構築軸','Edge / Cylinder / Axis'),'reference'),
                          (tr('方向を数値で指定','Direction Vector'),'vector')):self.axis_mode.addItem(title,key)
        self.axis = row('axis',tr('軸（全体座標）'),W.QComboBox())
        self.axis.addItems(['X','Y','Z'])
        self.axis_pick=row('axis_pick',tr('参照軸','Reference Axis'),W.QPushButton())
        self.axis_pick.setCheckable(True);self.axis_pick.clicked.connect(self.begin_axis_pick)
        self.axis_pick.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        self.vector=[]
        for component in 'XYZ':
            field=row('vector_'+component,tr('軸の方向 ','Axis Direction ')+component,self.spin())
            field.setRange(-100000,100000);field.setDecimals(6);field.setSuffix('');self.vector.append(field)
        self.axis_mode.currentIndexChanged.connect(self.axis_mode_changed)
        self.axis_ref=None;self.axis_signature=None;self.axis_picking=False;self.axis_ticket=0;self.axis_observing=False
        self.count = row('count',tr('個数（元を含む）'),W.QSpinBox())
        self.count.setRange(2,200);self.count.setValue(3);self.count.setKeyboardTracking(False)
        self.spacing = row('spacing',tr('1個ごとの間隔'),self.spin())
        self.spacing.setRange(-100000,100000);self.spacing.setValue(10)
        self.distribution=row('distribution',tr('距離の指定','Distance Type'),W.QComboBox())
        self.distribution.addItem(tr('間隔','Spacing'),'spacing')
        self.distribution.addItem(tr('全長','Extent'),'extent')
        self.second_direction=row('second_direction',tr('方向2','Direction 2'),W.QComboBox())
        self.second_direction.addItems([tr('使わない','Off'),tr('使う','On')])
        self.axis2=row('axis2',tr('方向2の軸','Axis 2'),W.QComboBox());self.axis2.addItems(['X','Y','Z'])
        self.count2=row('count2',tr('方向2の個数','Quantity 2'),W.QSpinBox())
        self.count2.setRange(2,200);self.count2.setValue(2);self.count2.setKeyboardTracking(False)
        self.spacing2=row('spacing2',tr('方向2の距離','Distance 2'),self.spin())
        self.spacing2.setRange(-100000,100000);self.spacing2.setValue(10)
        for field in (self.spacing,self.spacing2):field.setDecimals(6)
        self.distribution.currentIndexChanged.connect(self.distribution_changed)
        self.second_direction.currentIndexChanged.connect(self.pattern_axis_changed)
        self.axis.currentIndexChanged.connect(self.pattern_axis_changed)
        self.previous_distribution='spacing'
        self.angle = row('angle',tr('角度'),self.spin())
        self.angle.setRange(.001,360);self.angle.setSuffix(' °');self.angle.setValue(360)
        self.reverse = row('reverse',tr('方向'),W.QComboBox())
        self.reverse.addItems([tr('正方向'),tr('逆方向')])
        self.center = []
        for axis in 'XYZ':
            field = row(axis,tr('軸の通過点 ')+axis,self.spin())
            field.setRange(-100000,100000);field.setValue(0)
            field.setDecimals(6)
            self.center.append(field)
        self.plane = row('plane',tr('ミラー平面'),W.QComboBox())
        self.plane.addItems(['YZ','XZ','XY'])
        self.plane.addItem(tr('選択した面・構築平面','Selected Face / Plane'))
        self.plane.currentIndexChanged.connect(self.mirror_mode_changed)
        self.mirror_pick=row('mirror_pick',tr('基準面','Reference Plane'),W.QPushButton())
        self.mirror_pick.setCheckable(True);self.mirror_pick.clicked.connect(self.begin_mirror_pick)
        self.mirror_ref=None;self.mirror_signature=None;self.mirror_picking=False
        for field in (self.plane,self.mirror_pick):field.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        self.plane_offset = row('offset',tr('面の位置'),self.spin())
        self.plane_offset.setRange(-100000,100000);self.plane_offset.setValue(0);self.plane_offset.setDecimals(6)
        self.thickness = row('thickness',tr('厚さ'),self.spin())
        self.thickness.setValue(1)
        self.side = row('side',tr('厚さの方向'),W.QComboBox())
        self.side.addItems([tr('内側'),tr('外側')])
        self.faces = row('faces',tr('開ける面'),W.QListWidget())
        self.faces.setMaximumHeight(140)
        self.faces.setMinimumHeight(100)
        self.faces.itemChanged.connect(self.schedule)
        self.section_list = row('sections',tr('断面の順序'),W.QListWidget())
        self.section_list.setMinimumHeight(90);self.section_list.setMaximumHeight(125)
        self.available = row('available',tr('追加する断面'),W.QComboBox())
        self.available.setSizeAdjustPolicy(W.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.available.setMinimumContentsLength(10)
        controls = row('section_controls','',W.QWidget())
        buttons = W.QHBoxLayout(controls);buttons.setContentsMargins(0,0,0,0);buttons.setSpacing(4)
        for text,callback in [(tr('追加'),self.add_section),(tr('削除'),self.remove_section),('↑',lambda:self.move_section(-1)),('↓',lambda:self.move_section(1))]:
            button=W.QToolButton();button.setText(text)
            button.setFixedSize(26 if text in ('↑','↓') else 48,26)
            button.clicked.connect(callback);buttons.addWidget(button)
        buttons.addStretch()
        self.loft_mode = row('loft_mode',tr('つなぎ方'),W.QComboBox())
        self.loft_mode.addItems([tr('滑らかにつなぐ'),tr('断面間を直線でつなぐ')])
        self.sweep_profile = row('sweep_profile',tr('断面'),W.QComboBox())
        self.sweep_path = row('sweep_path',tr('経路'),W.QComboBox())
        self.frame_mode = row('frame_mode',tr('断面の向き'),W.QComboBox())
        self.frame_mode.addItems([tr('ねじれを抑える'),tr('経路の曲がりに追従')])
        self.corner_mode = row('corner_mode',tr('角のつなぎ方'),W.QComboBox())
        self.corner_mode.addItems([tr('変形して接続'),tr('角を合わせる'),tr('丸く接続')])
        self.note = W.QLabel()
        self.note.setWordWrap(True);form.addRow(self.note)
        self.combos = (self.profile,self.axis,self.axis_mode,self.reverse,self.plane,self.side,
                       self.distribution,self.second_direction,self.axis2,
                       self.loft_mode,self.sweep_profile,self.sweep_path,self.frame_mode,self.corner_mode)
        self.spins = (self.count,self.spacing,self.angle,*self.center,*self.vector,self.plane_offset,self.thickness,self.count2,self.spacing2)
        for field in (self.distribution,self.second_direction,self.axis2,self.count2,self.spacing2):
            field.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        policy=W.QSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);policy.setHeightForWidth(True)
        self.note.setSizePolicy(policy)

    def axis_mode_changed(self,*args):
        if not self.active or self.kind not in ('revolve','circular'):return
        self.axis_ticket+=1
        self.axis_picking=self.axis_mode.currentData()=='reference' and self.axis_ref is None
        if self.axis_picking:Gui.Selection.clearSelection()
        self.update_preview()

    def begin_axis_pick(self):
        if not self.active:return
        self.axis_ticket+=1;self.axis_picking=True
        Gui.Selection.clearSelection();self.update_preview()

    def addSelection(self,docname,objname,subname,point):
        if self.active and self.kind=='mirror':
            self.receive_mirror(docname,objname,subname);return
        if not self.active or not self.axis_picking or docname!=self.doc.Name:return
        ticket=self.axis_ticket
        def receive():
            if not self.active or not self.axis_picking or ticket!=self.axis_ticket:return
            try:
                ref=model_axis.reference(self.doc,objname,subname,self.existing)
                self.axis_ref=ref;self.axis_signature=model_axis.signature(ref[0])
                self.axis_ticket+=1;self.axis_picking=False
                Gui.Selection.clearSelection();self.update_preview()
            except Exception as error:
                self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error));Gui.Selection.clearSelection()
        QtCore.QTimer.singleShot(0,receive)

    def mirror_mode_changed(self,*args):
        if not self.active or self.kind!='mirror':return
        self.axis_ticket+=1
        self.mirror_picking=self.plane.currentIndex()==3 and self.mirror_ref is None
        if self.mirror_picking:Gui.Selection.clearSelection()
        self.update_preview()

    def begin_mirror_pick(self):
        if not self.active or self.kind!='mirror':return
        self.axis_ticket+=1;self.mirror_picking=True
        Gui.Selection.clearSelection();self.update_preview()

    def receive_mirror(self,docname,objname,subname):
        if not self.mirror_picking or docname!=self.doc.Name:return
        ticket=self.axis_ticket
        def receive():
            if not self.active or self.kind!='mirror' or not self.mirror_picking or ticket!=self.axis_ticket:return
            try:
                ref=model_mirror.resolve(self.doc,objname,subname,self.existing)
                self.mirror_ref=ref;self.mirror_signature=model_mirror.signature(ref[0])
                self.axis_ticket+=1;self.mirror_picking=False
                Gui.Selection.clearSelection();self.update_preview()
            except Exception as error:
                self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error));Gui.Selection.clearSelection()
        QtCore.QTimer.singleShot(0,receive)

    def mirror_fields(self):
        linked=self.plane.currentIndex()==3
        for widget in self.rows['mirror_pick']:widget.setVisible(linked)
        self.rows['offset'][0].setText(tr('面からのオフセット','Plane Offset') if linked else tr('面の位置（%s）')%{'YZ':'X','XZ':'Y','XY':'Z'}[self.plane.currentText()])
        title=tr('面・構築平面を選択','Select Face / Plane')
        if self.mirror_ref:
            try:title=self.mirror_ref[0].Label+' / '+self.mirror_ref[1]
            except (RuntimeError,ReferenceError):pass
        self.mirror_pick.setText(title);self.mirror_pick.setToolTip(title);self.mirror_pick.setChecked(self.mirror_picking)
        self.preferred_height=420 if linked else 310
        self.note.setText(tr('元のボディを残し、別のボディを作ります。基準面の変更に追従します。オレンジの矢印がオフセットの正方向です。',
                            'Creates a separate body and keeps the source. Follows changes to the reference plane. The orange arrow shows positive offset.') if linked else
                          tr('元のボディを残し、別のボディを作ります。平面の位置は全体座標で指定します。'))

    def axis_fields(self):
        mode=self.axis_mode.currentData()
        for key in ('axis','axis_pick','X','Y','Z','vector_X','vector_Y','vector_Z'):
            visible=(key=='axis' and mode=='world' or key=='axis_pick' and mode=='reference' or
                     key in ('X','Y','Z') and mode!='reference' or key.startswith('vector_') and mode=='vector')
            for widget in self.rows[key]:widget.setVisible(visible)
        ref=self.axis_ref
        title=tr('辺・円筒面・構築軸を選択','Select Edge / Cylinder / Axis')
        if ref:
            try:title=ref[0].Label+' / '+ref[1]
            except (RuntimeError,ReferenceError):pass
        self.axis_pick.setText(title);self.axis_pick.setToolTip(title);self.axis_pick.setChecked(self.axis_picking)
        self.preferred_height=590 if mode=='vector' else 400 if mode=='reference' else 480

    def detach_axis(self):
        self.axis_ticket+=1;self.axis_picking=False;self.mirror_picking=False
        if self.axis_observing:Gui.Selection.removeObserver(self);self.axis_observing=False

    def cancel(self):
        if self.active:self.detach_axis()
        super().cancel()

    def eventFilter(self,widget,event):
        if (self.active and (self.axis_picking or self.mirror_picking) and widget in self.widgets and
                event.type() in (QtCore.QEvent.MouseButtonPress,QtCore.QEvent.MouseButtonRelease,QtCore.QEvent.MouseButtonDblClick)):
            if event.button()==QtCore.Qt.LeftButton:return False
        return super().eventFilter(widget,event)

    def distribution_changed(self,*args):
        mode=self.distribution.currentData()
        if self.active and self.kind=='linear' and mode!=self.previous_distribution:
            converted=[(field,field.value()*(count-1) if mode=='extent' else field.value()/(count-1))
                       for field,count in ((self.spacing,self.count.value()),(self.spacing2,self.count2.value()))]
            if any(not field.minimum()<=value<=field.maximum() for field,value in converted):
                blocked=self.distribution.blockSignals(True)
                self.distribution.setCurrentIndex(self.distribution.findData(self.previous_distribution))
                self.distribution.blockSignals(blocked)
                W.QToolTip.showText(self.distribution.mapToGlobal(QtCore.QPoint(0,self.distribution.height())),
                    tr('換算後の距離が入力範囲を超えます。距離か個数を小さくしてください。',
                       'The converted distance exceeds the input range. Reduce the distance or quantity.'),self.distribution)
                return
            for field,value in converted:field.setValue(value)
        self.previous_distribution=mode

    def pattern_axis_changed(self,*args):
        if not self.active or self.kind!='linear':return
        if self.axis2.currentText()==self.axis.currentText():
            self.axis2.setCurrentText(next(axis for axis in 'XYZ' if axis!=self.axis.currentText()))

    def start(self,kind,source,regions=None,index=0,existing=None,faces=None,sections=None):
        self.cancel()
        if kind=='hole':
            self.ws.hole_panel.start(existing=existing)
            return
        if kind=='plane':
            self.start_plane(source.Document if source else App.ActiveDocument,existing)
            return
        if kind in ('loft','sweep'):
            self.start_sections(kind,source,existing,sections or [])
            return
        self.doc = source.Document
        self.source = source
        self.existing = existing
        self.kind = kind
        self.rows['plane'][0].setText(tr('ミラー平面'))
        self.preferred_height = 460 if kind=='linear' else 310 if kind=='mirror' else 440
        self.regions = regions
        self.signature = (source.Shape.hashCode(),str(source.getGlobalPlacement()))
        self.selection = [(sel.ObjectName,tuple(sel.SubElementNames)) for sel in Gui.Selection.getSelectionEx()]
        self.ws.region_picker.ticket += 1
        title = {'revolve':tr('回転'),'linear':tr('矩形状パターン','Rectangular Pattern'),'circular':tr('円形パターン'),'mirror':tr('ミラー'),'shell':tr('シェル')}[kind]
        self.heading.setText(title+(tr('を編集') if existing else ''))
        self.profile.clear()
        for i,region in enumerate(regions or []):
            self.profile.addItem(tr('領域 %d — 面積 %.2f mm²')%(i+1,region['face'].Area))
        self.profile.setCurrentIndex(index)
        values = features.settings(existing) if existing else {}
        axis=values.get('axis','Y' if kind=='revolve' else 'Z' if kind=='circular' else 'X')
        self.axis.setCurrentText(axis if isinstance(axis,str) else 'Z')
        self.axis_mode.setCurrentIndex(self.axis_mode.findData(values.get('axis_mode','world')))
        direction=tuple(features.axis_vector(axis)) if isinstance(axis,str) else axis
        for field,value in zip(self.vector,direction):field.setValue(value)
        self.initial_vector=direction;self.displayed_vector=tuple(field.value() for field in self.vector)
        self.axis_ref=(values['reference'],values['subelement']) if kind in ('revolve','circular') and values.get('reference') else None
        self.axis_signature=model_axis.signature(self.axis_ref[0]) if self.axis_ref else None
        self.axis_picking=False
        self.count.setValue(values.get('count',3))
        self.spacing.setValue(values.get('spacing',10))
        self.distribution.setCurrentIndex(self.distribution.findData(values.get('distribution','spacing')))
        self.previous_distribution=self.distribution.currentData()
        self.second_direction.setCurrentIndex(int(values.get('count2',1)>1))
        self.axis2.setCurrentText(values.get('axis2',next(axis for axis in 'XYZ' if axis!=self.axis.currentText())))
        self.count2.setValue(max(2,values.get('count2',2)))
        self.spacing2.setValue(values.get('spacing2',10))
        self.rows['axis'][0].setText(tr('方向1の軸','Axis 1') if kind=='linear' else tr('軸（全体座標）'))
        self.rows['count'][0].setText(tr('方向1の個数','Quantity 1') if kind=='linear' else tr('個数（元を含む）'))
        self.angle.setValue(values.get('angle',360))
        self.reverse.setCurrentIndex(int(values.get('reverse',False)))
        self.initial_center=values.get('center',(0,0,0))
        for field,value in zip(self.center,self.initial_center):field.setValue(value)
        self.displayed_center=tuple(field.value() for field in self.center)
        self.plane.model().item(3).setEnabled(kind=='mirror')
        self.mirror_ref=(values['reference'],values['subelement']) if kind=='mirror' and values.get('reference') else None
        if kind=='mirror' and not existing:
            selection=Gui.Selection.getSelectionEx()
            for selected in selection[1:] if len(selection)>1 else selection:
                for sub in selected.SubElementNames or ('',):
                    try:self.mirror_ref=model_mirror.resolve(self.doc,selected.ObjectName,sub)
                    except Exception:continue
                    break
                if self.mirror_ref:break
        self.mirror_signature=model_mirror.signature(self.mirror_ref[0]) if self.mirror_ref else None
        self.plane.setCurrentIndex(3 if self.mirror_ref or values.get('plane')=='reference' else self.plane.findText(values.get('plane','YZ')))
        self.mirror_picking=kind=='mirror' and self.plane.currentIndex()==3 and self.mirror_ref is None
        self.plane_offset.setValue(values.get('offset',0))
        self.initial_plane_offset=values.get('offset',0);self.displayed_plane_offset=self.plane_offset.value()
        self.thickness.setValue(values.get('thickness',1))
        self.side.setCurrentIndex(0 if values.get('inward',True) else 1)
        self.faces.clear()
        if kind=='shell':
            chosen = values.get('faces',faces or [])
            for i,face in enumerate(source.Shape.Faces):
                name = 'Face%d'%(i+1)
                item = W.QListWidgetItem(tr('面 %d（%.2f mm²）')%(i+1,face.Area),self.faces)
                item.setData(QtCore.Qt.UserRole,name)
                item.setFlags(item.flags()|QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked if name in chosen else QtCore.Qt.Unchecked)
        if kind=='mirror':
            visible = {'plane','offset'}
        elif kind=='shell':
            visible = {'thickness','side','faces'}
        else:
            visible = {'axis'}
            if kind=='revolve' and not existing:visible.add('profile')
            if kind!='revolve':visible.add('count')
            if kind=='linear':visible.update(('spacing','distribution','second_direction'))
            else:visible.update(('axis_mode','angle','reverse','X','Y','Z'))
        for key,widgets in self.rows.items():
            for widget in widgets:widget.setVisible(key in visible)
        notes = {
            'revolve':tr('新規ボディを作成します。辺・円筒面の軸は参照元に追従します。緑の矢印が回転軸の正方向です。',
                         'Creates a new body. An edge/cylinder axis follows its reference. The green arrow shows the positive axis direction.'),
            'linear':tr('複製は結合せず、パターン全体で選択・移動できます。逆向きは間隔を負にします。'),
            'circular':tr('複製は結合せず、パターン全体で選択・移動できます。360°は一周に等間隔、それ以外は両端を含めて配置します。'),
            'mirror':tr('元のボディを残し、別のボディを作ります。平面の位置は全体座標で指定します。'),
            'shell':tr('チェックした面を開けます。内側は外形を維持し、外側は外形が広がります。')}
        self.note.setText(notes[kind])
        self.active = True
        if kind in ('revolve','circular','mirror'):
            Gui.Selection.addObserver(self);self.axis_observing=True
        self.panel.show();self.update_preview();self.position()

    def start_plane(self,doc,existing=None):
        self.cancel();self.doc=doc;self.source=None;self.existing=existing;self.kind='plane'
        self.preferred_height=290
        self.selection=[(sel.ObjectName,tuple(sel.SubElementNames)) for sel in Gui.Selection.getSelectionEx()]
        self.ws.region_picker.ticket+=1
        self.heading.setText(tr('オフセット平面')+(tr('を編集') if existing else ''))
        self.rows['plane'][0].setText(tr('基準平面'))
        self.plane.model().item(3).setEnabled(False)
        self.plane.setCurrentText(existing.BasePlane if existing else 'XY')
        self.plane_offset.setValue(existing.Offset.Value if existing else 10)
        for key,widgets in self.rows.items():
            for widget in widgets:widget.setVisible(key in ('plane','offset'))
        self.note.setText(tr('全体座標の基準平面から、指定距離だけ離れた平面を作ります。作成した平面を選んで「スケッチを作成」を押してください。'))
        self.active=True;self.panel.show();self.update_preview();self.position()

    def start_sections(self,kind,source,existing,selected):
        self.doc=source.Document;self.source=source;self.existing=existing;self.kind=kind
        self.preferred_height=470 if kind=='loft' else 420
        self.selection=[(sel.ObjectName,tuple(sel.SubElementNames)) for sel in Gui.Selection.getSelectionEx()]
        self.ws.region_picker.ticket+=1
        path=None
        if existing:
            selected,path=model_sections.sources(existing)
        elif kind=='sweep':
            path=selected[1] if len(selected)>1 else None
            selected=selected[:1]
        candidates=[obj for obj in self.doc.Objects if obj.TypeId=='Sketcher::SketchObject'
                    and not getattr(obj,'FluxCADInternal',False)]
        for obj in selected+([path] if path else []):
            if obj not in candidates:candidates.append(obj)
        if existing:
            candidates=[obj for obj in candidates if obj!=existing and existing not in obj.OutListRecursive]
        self.section_signatures={obj.Name:(obj.Shape.hashCode(),str(obj.getGlobalPlacement())) for obj in candidates}
        for combo in (self.available,self.sweep_profile,self.sweep_path):
            combo.clear();combo.addItem(tr('— 選択 —'),None)
            for obj in candidates:combo.addItem('%s [%s]'%(obj.Label,obj.Name),obj.Name)
        self.section_list.clear()
        for obj in selected:self.append_section(obj)
        self.sweep_profile.setCurrentIndex(self.sweep_profile.findData(selected[0].Name) if selected else 0)
        self.sweep_path.setCurrentIndex(self.sweep_path.findData(path.Name) if path else 0)
        self.loft_mode.setCurrentIndex(int(existing.Ruled) if existing and kind=='loft' else 0)
        self.frame_mode.setCurrentIndex(int(existing.Frenet) if existing and kind=='sweep' else 0)
        self.corner_mode.setCurrentIndex(existing.getEnumerationsOfProperty('Transition').index(existing.Transition)
                                         if existing and kind=='sweep' else 1)
        visible = {'sections','available','section_controls','loft_mode'} if kind=='loft' else {'sweep_profile','sweep_path','frame_mode','corner_mode'}
        for key,widgets in self.rows.items():
            for widget in widgets:widget.setVisible(key in visible)
        self.heading.setText((tr('ロフト') if kind=='loft' else tr('スイープ'))+(tr('を編集') if existing else ''))
        self.note.setText(tr('断面をつなぐ順に追加します。↑↓で順序を変更できます。各スケッチには閉じた輪郭を1つ描いてください。')
                          if kind=='loft' else tr('断面は閉じた輪郭1つ、経路はつながった線です。断面を経路の端に、経路と直角に配置してください。'))
        self.active=True;self.panel.show();self.update_preview();self.position()

    def append_section(self,obj):
        item=W.QListWidgetItem('%s [%s]'%(obj.Label,obj.Name),self.section_list)
        item.setData(QtCore.Qt.UserRole,obj.Name)
        self.section_list.setCurrentItem(item)

    def add_section(self):
        name=self.available.currentData()
        if not name:return
        if any(self.section_list.item(i).data(QtCore.Qt.UserRole)==name for i in range(self.section_list.count())):return
        obj=self.doc.getObject(name)
        if obj:self.append_section(obj);self.schedule()

    def remove_section(self):
        row=self.section_list.currentRow()
        if row>=0:self.section_list.takeItem(row);self.schedule()

    def move_section(self,delta):
        row=self.section_list.currentRow();target=row+delta
        if row<0 or not 0<=target<self.section_list.count():return
        item=self.section_list.takeItem(row);self.section_list.insertItem(target,item)
        self.section_list.setCurrentItem(item);self.schedule()

    def section_object(self,name):
        obj=self.doc.getObject(name) if name else None
        if not obj:raise ValueError(tr('断面・経路のスケッチを指定してください。'))
        if (obj.Shape.hashCode(),str(obj.getGlobalPlacement()))!=self.section_signatures.get(name):
            raise ValueError(tr('スケッチが変更されました。キャンセルして選び直してください。'))
        return obj

    def parameters(self):
        if self.kind=='plane':return {'base':self.plane.currentText(),'offset':self.plane_offset.value()}
        if self.kind=='loft':
            return {'sections':[self.section_object(self.section_list.item(i).data(QtCore.Qt.UserRole)) for i in range(self.section_list.count())],
                    'ruled':bool(self.loft_mode.currentIndex())}
        if self.kind=='sweep':
            return {'sections':[self.section_object(self.sweep_profile.currentData())],
                    'path':self.section_object(self.sweep_path.currentData()),
                    'frenet':bool(self.frame_mode.currentIndex()),'transition':self.corner_mode.currentIndex()}
        if self.kind=='mirror':
            offset=self.plane_offset.value()
            if self.existing and offset==self.displayed_plane_offset:offset=self.initial_plane_offset
            values=dict(plane=self.plane.currentText(),offset=offset)
            if self.plane.currentIndex()==3:
                if not self.mirror_ref:raise ValueError(tr('ミラーの基準面を選択してください。','Select the mirror reference plane.'))
                ref,sub=self.mirror_ref
                if model_mirror.signature(ref)!=self.mirror_signature:
                    raise ValueError(tr('基準面が変更されました。「基準面」から選び直してください。','The reference plane changed. Reselect the Reference Plane.'))
                model_mirror.validate(self.doc,ref,sub,self.existing)
                values.update(plane='reference',reference=ref,subelement=sub)
            return values
        if self.kind=='shell':
            faces = [self.faces.item(i).data(QtCore.Qt.UserRole) for i in range(self.faces.count())
                     if self.faces.item(i).checkState()==QtCore.Qt.Checked]
            return {'faces':faces,'thickness':self.thickness.value(),'inward':self.side.currentIndex()==0}
        common = {'axis':self.axis.currentText(),'center':tuple(field.value() for field in self.center),
                  'angle':self.angle.value(),'reverse':bool(self.reverse.currentIndex())}
        if self.kind in ('revolve','circular'):
            # Display rounding must not move an existing axis on an angle-only edit.
            if common['center']==self.displayed_center:common['center']=self.initial_center
            mode=self.axis_mode.currentData()
            if mode=='reference':
                if not self.axis_ref:raise ValueError(tr('軸となる辺・円筒面を選択してください。','Select an edge or cylinder to define the axis.'))
                ref,subelement=self.axis_ref
                if model_axis.signature(ref)!=self.axis_signature:
                    raise ValueError(tr('参照形状が変更されました。「参照軸」から選び直してください。',
                                        'The reference geometry changed. Reselect the Reference Axis.'))
                model_axis.validate(self.doc,ref,subelement,self.existing)
                common.update(reference=ref,subelement=subelement)
            elif mode=='vector':
                direction=tuple(field.value() for field in self.vector)
                common['axis']=self.initial_vector if direction==self.displayed_vector else direction
        if self.kind!='revolve':common.update(count=self.count.value(),spacing=self.spacing.value())
        if self.kind=='linear':
            common.update(count2=self.count2.value() if self.second_direction.currentIndex() else 1,
                          axis2=self.axis2.currentText(),spacing2=self.spacing2.value(),distribution=self.distribution.currentData())
        return common

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:
            self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        try:
            if self.kind=='mirror':
                self.mirror_fields()
                if self.mirror_picking:
                    if self.existing:
                        self.hidden.append((self.existing,bool(self.existing.Visibility)));self.existing.Visibility=False
                    self.status.setStyleSheet('color:#245b73;')
                    self.status.setText(tr('平らな面をクリックしてください。構築平面はブラウザーからも選べます。',
                                           'Click a planar face. Construction planes can also be selected in the browser.'))
                    return
            if self.kind in ('revolve','circular'):
                self.axis_fields()
                if self.axis_picking:
                    if self.existing:
                        self.hidden.append((self.existing,bool(self.existing.Visibility)));self.existing.Visibility=False
                    source=getattr(self.existing,'FluxBodySource',None) or self.source
                    self.hidden.append((source,bool(source.Visibility)));source.Visibility=True
                    self.status.setStyleSheet('color:#245b73;')
                    self.status.setText(tr('直線の辺・円筒の側面・構築軸をクリックしてください。ブラウザーからも構築軸を選べます。',
                                           'Click a straight edge, cylindrical side face or construction axis. You can also select a construction axis in the browser.'))
                    return
            if self.kind not in ('loft','sweep','plane') and (self.source.Shape.hashCode(),str(self.source.getGlobalPlacement()))!=self.signature:
                raise ValueError(tr('元の形状が変更されました。キャンセルして選び直してください。'))
            values = self.parameters()
            if self.kind=='linear':
                self.preferred_height=460 if values['count2']>1 else 350
                for key in ('axis2','count2','spacing2'):
                    for widget in self.rows[key]:widget.setVisible(values['count2']>1)
                for i in range(3):self.axis2.model().item(i).setEnabled(self.axis2.itemText(i)!=values['axis'])
                extent=values['distribution']=='extent'
                self.rows['spacing'][0].setText(tr('方向1の全長','Extent 1') if extent else tr('方向1の間隔','Spacing 1'))
                self.rows['spacing2'][0].setText(tr('方向2の全長','Extent 2') if extent else tr('方向2の間隔','Spacing 2'))
                self.note.setText(tr('個数は元の位置を含み、合計200個まで。軸は全体座標です。負の距離で逆向きに並べます。全長は最初と最後の配置原点の距離です。',
                                     'Quantities include the original, up to 200 instances total. Axes use world coordinates. Negative distances reverse the direction. Extent is the distance between the first and last instance origins.'))
            if self.kind=='plane':
                self.rows['offset'][0].setText(tr('距離（%s）')%{'XY':'Z','XZ':'Y','YZ':'X'}[values['base']])
                result=model_planes.preview(**values)
            elif self.kind=='loft':
                result = model_sections.loft_shape(**values)
            elif self.kind=='sweep':
                result = model_sections.sweep_shape(values['sections'][0],values['path'],values['frenet'],values['transition'])
            elif self.kind=='mirror':
                result = features.mirror_shape(self.source,**values)
            elif self.kind=='shell':
                result = features.shell_shape(self.source,**values)
            elif self.kind=='revolve':
                face = model.world_shape(self.source).Faces[0] if self.existing else features.profile_face(self.source,self.regions[self.profile.currentIndex()])
                result = features.revolve_shape(face,**values)
            else:
                result = features.pattern_shape(self.source,self.kind,**values)
            if self.kind!='plane':result = features.placed_preview(result,self.existing)
            self.show_shape(result,'plane' if self.kind=='plane' else 'new')
            if self.kind in ('revolve','circular'):self.axis_marker(values,result)
            if self.kind=='mirror':self.mirror_marker(values,result)
            hidden = self.existing or (self.source if self.kind not in ('revolve','mirror','loft','sweep') else None)
            if hidden:
                self.hidden.append((hidden,bool(hidden.Visibility)));hidden.Visibility=False
            self.valid=True;self.accept_button.setEnabled(True)
            self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('構築平面のプレビュー') if self.kind=='plane' else tr('プレビュー：%d個の立体／体積 %.3f mm³')%(len(result.Solids),result.Volume))
        except Exception as error:
            self.clear_preview();self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def mirror_marker(self,values,result):
        origin,normal=model_mirror.frame(**values)
        # Center the finite guide on the reflected source, projected onto the
        # infinite mirror plane; the selected face need not cover the body.
        center=model.world_shape(self.source).BoundBox.Center
        center-=normal*(center-origin).dot(normal)
        length=max(5,model.world_shape(self.source).BoundBox.DiagonalLength*.7)
        helper=min((App.Vector(1,0,0),App.Vector(0,1,0),App.Vector(0,0,1)),key=lambda v:abs(v.dot(normal)))
        x=normal.cross(helper);x.normalize();x*=length;y=normal.cross(x)
        tip=center+normal*length*.65;tail=tip-normal*length*.16;wing=x*.08
        points=[center-x-y,center+x-y,center+x+y,center-x+y,center-x-y,center,tip,tail+wing,tip,tail-wing]
        node=coin.SoSeparator();light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(.9,.52,.12);material.transparency=0;node.addChild(material)
        style=coin.SoDrawStyle();style.lineWidth=2;node.addChild(style)
        coords=coin.SoCoordinate3();coords.point.setValues(0,len(points),[tuple(p) for p in points]);node.addChild(coords)
        line=coin.SoLineSet();line.numVertices.setValues(0,2,[5,5]);node.addChild(line);self.overlay[1].addChild(node)

    def axis_marker(self,values,result):
        origin,direction=model_axis.values(values['axis'],values['center'],values['reverse'],values.get('reference'),values.get('subelement',''))
        if self.existing:
            origin=self.existing.Placement.multVec(origin);direction=self.existing.Placement.Rotation.multVec(direction)
        length=max(5,result.BoundBox.DiagonalLength*.4);tip=origin+direction*length
        helper=min((App.Vector(1,0,0),App.Vector(0,1,0),App.Vector(0,0,1)),key=lambda v:abs(v.dot(direction)))
        wing=direction.cross(helper);wing.normalize();wing*=length*.07;tail=tip-direction*length*.16
        points=[origin-direction*length,tip,tail+wing,tip,tail-wing]
        node=coin.SoSeparator();light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(.1,.7,.25);material.transparency=0;node.addChild(material)
        style=coin.SoDrawStyle();style.lineWidth=2;node.addChild(style)
        coords=coin.SoCoordinate3();coords.point.setValues(0,len(points),[tuple(p) for p in points]);node.addChild(coords)
        line=coin.SoLineSet();line.numVertices.setValue(len(points));node.addChild(line)
        self.overlay[1].addChild(node)

    def accept(self):
        if not self.active:return
        for field in self.spins:field.interpretText()
        self.update_preview()
        if not self.active or not self.valid:return
        self.clear_preview()
        try:
            if self.kind=='plane':
                result=model_planes.create(self.doc,existing=self.existing,**self.parameters())
            elif self.kind in ('loft','sweep'):
                result = model_sections.create(self.doc,self.kind,existing=self.existing,**self.parameters())
            elif self.kind=='mirror':
                result = features.create_mirror(self.doc,self.source,existing=self.existing,**self.parameters())
            elif self.kind=='shell':
                result = features.create_shell(self.doc,self.source,existing=self.existing,**self.parameters())
            elif self.kind=='revolve':
                result = features.create_revolution(self.doc,self.source,index=self.profile.currentIndex(),existing=self.existing,**self.parameters())
            else:
                result = features.create_pattern(self.doc,self.source,self.kind,existing=self.existing,**self.parameters())
        except Exception as error:
            self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))
            self.valid=False;self.accept_button.setEnabled(False);return
        self.detach_axis();self.active=False;self.panel.hide();self.ws.region_picker.clear()
        Gui.Selection.clearSelection();Gui.Selection.addSelection(result);self.ws.refresh()
        self.ws.main.statusBar().showMessage(tr('確定しました。履歴のダブルクリックで編集、Ctrl＋Zで元に戻せます。'),8000)

    def refresh(self):
        if not self.active:return
        try:
            if (App.ActiveDocument!=self.doc or (self.source is not None and not self.source.Document) or self.ws.current_sketch()
                    or (self.existing is not None and not self.existing.Document)):
                self.cancel();return
        except (RuntimeError,ReferenceError):
            self.cancel();return
        if self.kind in ('revolve','circular') and self.axis_ref and not self.axis_picking and self.axis_mode.currentData()=='reference':
            try:changed=model_axis.signature(self.axis_ref[0])!=self.axis_signature
            except (RuntimeError,ReferenceError):changed=True
            if changed and self.valid:self.update_preview()
        if self.kind=='mirror' and self.mirror_ref and not self.mirror_picking and self.plane.currentIndex()==3:
            try:changed=model_mirror.signature(self.mirror_ref[0])!=self.mirror_signature
            except (RuntimeError,ReferenceError):changed=True
            if changed and self.valid:self.update_preview()
        self.position()
