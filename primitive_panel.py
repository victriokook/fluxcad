import primitive_precision
"""Movable dimension/position editor for the four creation primitives."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets as W
from floating_panel import FloatingPanel
from i18n import tr
import model_primitives as primitives


class PrimitivePanel(FloatingPanel):
    layout_key='PrimitivePanel'
    preferred_height=650

    def __init__(self,ws):
        super().__init__(ws)
        policy=self.status.sizePolicy();policy.setHeightForWidth(True);self.status.setSizePolicy(policy)

    def build_fields(self,form):
        form.setRowWrapPolicy(W.QFormLayout.WrapLongRows)
        self.form=form;self.fields={};self.labels={}
        def field(key,label,widget):
            self.fields[key]=widget;self.labels[key]=W.QLabel(label)
            widget.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
            form.addRow(self.labels[key],widget)
            return widget
        self.path=field('path',tr('経路','Path'),W.QComboBox())
        for key,label in [('width',tr('底面の横幅','Base Width')),('depth',tr('底面の縦高さ','Base Height')),('height',tr('ドームの高さ','Dome Height')),('thickness',tr('肉厚（0＝中実）','Wall (0 = solid)')),('diameter',tr('直径','Diameter')),('section',tr('断面直径','Section Diameter')),
                          ('pitch',tr('ピッチ','Pitch')),('turns',tr('巻き数','Turns')),
                          ('wall',tr('肉厚','Wall Thickness')),('length',tr('長さ','Length'))]:
            field(key,label,self.spin())
        for key in ('width','depth','height'):self.fields[key].setRange(.01,100000)
        self.fields['thickness'].setRange(0,100000)
        self.fields['turns'].setSuffix('');self.fields['turns'].setRange(.25,50);self.fields['turns'].setSingleStep(.25)
        self.left=field('left',tr('巻き方向','Winding'),W.QComboBox())
        self.left.addItem(tr('右巻き','Right-handed'),False);self.left.addItem(tr('左巻き','Left-handed'),True)
        self.axis=field('axis',tr('軸方向','Axis'),W.QComboBox())
        for axis in ('Z','X','Y'):self.axis.addItem(axis,axis)
        for key in ('x','y','z'):
            spin=field(key,tr('位置 ','Position ')+key.upper(),self.spin());spin.setRange(-100000,100000)
        self.note=W.QLabel();self.note.setWordWrap(True);form.addRow(self.note)
        self.combos=(self.path,self.left,self.axis)
        self.spins=tuple(w for w in self.fields.values() if isinstance(w,W.QDoubleSpinBox))
        self.cache_key=None;self.cache_shape=None

    def start(self,kind=None,existing=None):
        self.cancel()
        if self.ws.current_sketch():raise ValueError(tr('先にスケッチ編集を終了してください。','Finish editing the sketch first.'))
        self.kind=existing.FluxPrimitive if existing else kind
        if self.kind not in primitives.KINDS:raise ValueError('Unknown primitive')
        self.preferred_height={'dome':500,'sphere':330,'torus':410,'coil':510,'pipe':460}[self.kind]
        self.doc=self.ws.doc();self.existing=existing
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        values=primitives.settings(existing) if existing else primitives.defaults(self.kind)
        self.heading.setText(primitives.title(self.kind)+(tr('を編集',' — Edit') if existing else ''))
        self.path.clear();self.path.addItem(tr('直線（長さを指定）','Straight (specify length)'),None)
        if self.kind=='pipe':
            selected=Gui.Selection.getSelection()
            paths=[]
            for obj in self.doc.Objects:
                if getattr(obj,'FluxCADInternal',False) or not hasattr(obj,'Shape'):continue
                try:primitives.check_path(self.doc,obj,existing);paths.append(obj)
                except Exception:continue
            for obj in paths:self.path.addItem(obj.Label,obj.Name)
            source=values['path'] if existing else next((o for o in selected if o in paths),None)
            if source:self.path.setCurrentIndex(self.path.findData(source.Name))
            elif existing and existing.UsePath:
                self.path.addItem(tr('経路がありません — 選び直してください','Missing path — select a replacement'),'__missing__')
                self.path.setCurrentIndex(self.path.count()-1)
        for key,value in values.items():
            if key in ('left','path'):continue
            self.fields[key].setValue(value)
        primitive_precision.lock_dimensions(existing,self.kind,self.fields)
        if self.kind=='dome':
            import model_dome
            model_dome.lock_fields(existing,self.fields)
        self.left.setCurrentIndex(1 if values.get('left') else 0);self.axis.setCurrentIndex(0)
        base=existing.Placement.Base if existing else App.Vector()
        for key,value in zip(('x','y','z'),base):self.fields[key].setValue(value)
        if self.kind=='dome':primitives.model_dome.remember_editor(self.fields)
        else:primitive_precision.remember(self.fields)
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.cache_key=None;self.active=True;self.panel.show();self.update_preview();self.position()

    def parameters(self):
        primitive_precision.lock_position(self.existing,self.fields)
        result={k:self.fields[k].value() for k in primitives.defaults(self.kind) if k not in ('path','left')}
        if self.kind=='coil':result['left']=self.left.currentData()
        if self.kind=='pipe':
            name=self.path.currentData()
            result['path']=self.doc.getObject(name) if name else None
            if name and result['path'] is None:raise ValueError(tr('経路が削除されています。','The path has been deleted.'))
        if self.kind=='dome':result=primitives.model_dome.editor_values(self.existing,self.fields,result)
        else:
            primitive_precision.lock_dimensions(self.existing,self.kind,self.fields)
            result=primitive_precision.values(self.existing,self.fields,result)
        return result

    def pose(self):
        primitive_precision.lock_position(self.existing,self.fields)
        position=tuple(self.fields[k].value() for k in ('x','y','z'))
        if self.existing:
            if self.kind=='dome':position=primitives.model_dome.editor_position(self.existing,self.fields,position)
            else:position=primitive_precision.position(self.existing,self.fields,position)
            result=App.Placement(self.existing.Placement);result.Base=App.Vector(*position);return result
        return primitives.placement(position,'Z' if self.kind=='pipe' and self.path.currentData() else self.axis.currentData())

    def signature(self):
        values=self.parameters();path=values.get('path')
        return (tuple((k,v) for k,v in values.items() if k!='path'),
                (path.Name,path.Shape.hashCode(),str(path.getGlobalPlacement())) if path else None,
                str(self.existing.getGlobalPlacement()) if self.existing else None)

    def visible_fields(self):
        path_mode=self.kind=='pipe' and self.path.currentData() is not None
        keys=set(primitives.defaults(self.kind))|{'x','y','z'}
        if not self.existing and self.kind!='sphere' and not path_mode:keys.add('axis')
        if path_mode:keys.discard('length')
        for key,widget in self.fields.items():widget.setVisible(key in keys);self.labels[key].setVisible(key in keys)
        self.labels['diameter'].setText(tr('中心径','Centerline Diameter') if self.kind in ('torus','coil') else tr('外径','Outside Diameter') if self.kind=='pipe' else tr('直径','Diameter'))
        self.labels['section'].setText(tr('線径','Wire Diameter') if self.kind=='coil' else tr('断面直径','Section Diameter'))
        for key in ('x','y','z'):self.labels[key].setText((tr('オフセット ','Offset ') if path_mode else tr('位置 ','Position '))+key.upper())
        self.note.setText(dict(dome=primitives.model_dome.note(),sphere=tr('中心位置と直径を指定します。','Specify the center and diameter.'),
            torus=tr('中心径は管の中心を通る円の直径です。外径 = 中心径 + 断面直径。','Centerline diameter is measured through the tube center. Outside diameter = centerline + section diameter.'),
            coil=tr('丸線のコイルを作成します。ピッチは1回転の高さです。中心線の高さ = ピッチ × 巻き数。','Creates a round-wire coil. Pitch is the rise per turn. Centerline height = pitch × turns.'),
            pipe=tr('経路には輪郭が1つにつながったスケッチを選びます。直線なら長さを指定できます。端をふさがない中空パイプです。','Select a sketch containing one connected path, or specify a straight length. Hollow pipes have no end caps.'))[self.kind])


    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False);self.visible_fields()
        try:
            values=self.parameters();signature=self.signature()
            if self.kind=='dome':
                hint=primitives.model_dome.thickness_hint(values)
                if hint:self.note.setText(self.note.text()+'\n'+hint)
            if self.kind=='pipe':primitives.check_path(self.doc,values['path'],self.existing)
            key=(self.kind,signature[:2])
            if key!=self.cache_key:
                self.cache_shape=primitives.shape(self.kind,**values);self.cache_key=key
            shape=self.cache_shape.copy();pose=self.pose()
            primitive_precision.check_placement(self.existing,pose)
            if self.existing:pose=self.existing.getGlobalPlacement().multiply(self.existing.Placement.inverse()).multiply(pose)
            shape.Placement=pose.multiply(shape.Placement)
            self.show_shape(shape,'new')
            if self.kind=='dome':
                volume_note=primitives.model_dome.material_volume_note(shape)
                if volume_note:self.note.setText(self.note.text()+'\n'+volume_note)
            if self.existing:self.hidden.append((self.existing,self.existing.Visibility));self.existing.Visibility=False
            self.status.setText(tr('新規ボディとして作成します。','Creates a new body.') if not self.existing else tr('寸法と位置を更新します。','Updates dimensions and position.'))
            if self.kind=='coil':self.status.setText(self.status.text()+tr('\n中心線の高さ: %.3f mm','\nCenterline height: %.3f mm')%(values['pitch']*values['turns']))
            self.status.setStyleSheet('color:#3c6f62;');self.valid=True;self.accept_button.setEnabled(True)
            self.last_signature=signature
        except Exception as error:self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;')

    def accept(self):
        if not self.active:return
        for spin in self.spins:spin.interpretText()
        self.update_preview()
        if not self.valid:return
        if (self.kind!='dome' and primitive_precision.unchanged(self.existing,self.parameters(),self.pose())) or (self.kind=='dome' and primitive_precision.unchanged_dome(self.existing,self.parameters(),self.pose())):
            self.cancel();self.ws.refresh();return
        try:
            self.clear_preview()
            obj=primitives.create(self.doc,self.kind,existing=self.existing,pose=self.pose(),**self.parameters())
        except Exception as error:
            self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;');return
        self.active=False;self.timer.stop();self.panel.hide();self.ws.region_picker.clear()
        Gui.Selection.clearSelection();Gui.Selection.addSelection(obj);self.ws.refresh()

    def refresh(self):
        if not self.active:
            return
        try:
            if App.ActiveDocument != self.doc or self.ws.current_sketch() or (self.existing and not self.existing.Document):
                self.cancel()
                return
            if self.existing:
                name = self.existing.Name
                if not isinstance(name, str) or self.doc.getObject(name) != self.existing:
                    self.cancel()
                    return
            if self.signature() != getattr(self, 'last_signature', None):
                self.update_preview()
        except (RuntimeError, ReferenceError):
            self.cancel()
            return
        except ValueError as error:
            self.clear_preview()
            self.valid = False
            self.accept_button.setEnabled(False)
            self.status.setText(str(error))
        self.position()
