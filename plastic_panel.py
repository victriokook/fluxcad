"""Movable face-based rib/boss editor with a transient fused preview."""
import FreeCAD as App,FreeCADGui as Gui
from PySide import QtWidgets as W
from floating_panel import FloatingPanel
from i18n import tr
import model_plastic as plastic

LABELS={'Length':('長さ','Length'),'Thickness':('厚さ','Thickness'),'Height':('高さ','Height'),
        'Diameter':('外径','Outside Diameter'),'Bore':('下穴径','Bore Diameter'),'Angle':('面内の回転角','In-plane Angle'),
        'U':('位置 U','Position U'),'V':('位置 V','Position V')}
LABELS.update(plastic.LABELS_EXTRA)
FIELD_ORDER = ('Length','Width','Diameter','Bore','Thickness','Height','Draft','Projection','HookHeight','Angle','U','V')
SNAP_NOTE_JA='スナップフックは垂直なカンチレバーと傾斜した保持リップを追加します。平面角0はリップをU方向、90はV方向に指します。このツールはジオメトリのみを作成し、材料や変形、保持強度は計算しません。'
SNAP_NOTE_EN='Snap hook adds a vertical cantilever and sloped retaining lip. Angle 0 points lip to local U, 90 to V. This tool creates geometry only; material, deflection, and retention strength are not calculated.'
GUSSET_NOTE_JA = "三角リブは、角度0°で-U側が高く、+U側へ低くなります。\n底面全体が支持面に載る位置に配置してください。\n形状のみ作成し、強度計算は行いません。"
GUSSET_NOTE_EN = "At angle 0°, the high edge is at -U;\nit slopes down toward +U.\nKeep the whole footprint on the support face.\nCreates geometry only; no strength calculation."

def configure_dimension_spin(key, spin):
    spin.setDecimals(3)
    if key=='Draft':
        spin.setRange(0,45)
        spin.setSuffix(' °')
        spin.setToolTip(tr('根元の長さ・厚さ・外径を保ち、正の抜き勾配で先端を細くします。0°は直方体リブ／円柱ボスです。ボスの下穴径は変わりません。','Positive draft narrows the tip while keeping base length, thickness or outside diameter. Zero degrees keeps a rectangular rib or cylindrical boss. The boss bore stays straight.'))
    else:
        spin.setRange(-100000 if key in ('Angle','U','V') else 0 if key=='Bore' else .001,100000)
        spin.setSuffix(' °' if key=='Angle' else ' mm')
    spin.setKeyboardTracking(False)

def feature_note(kind, default_note):
    if kind == 'rib':
        ja = "長さ・厚さは根元の寸法です。正の抜き勾配で先端を細くし、0°は直方体にします。先端の長さ・厚さは0.001 mm以上必要です。U/Vで位置、面内の回転角で向きを指定します。底面全体を選択面に収めてください。"
        en = "Length and thickness are measured at the base. Positive draft narrows the tip; 0 degrees keeps a rectangular rib. Top length and thickness must be at least 0.001 mm. Use U/V for position and In-plane Angle for orientation. Keep the whole base on the selected face."
        return tr(ja, en)
    elif kind == 'snap':
        return tr(SNAP_NOTE_JA, SNAP_NOTE_EN)
    elif kind == 'gusset':
        return tr(GUSSET_NOTE_JA, GUSSET_NOTE_EN)
    else:
        return default_note

class PlasticPanel(FloatingPanel):
    layout_key='PlasticPanel';preferred_height=650;preferred_width=440
    def build_fields(self,form):
        self.target=W.QLabel();form.addRow(self.target)
        self.fields={};self.labels={}
        for key in FIELD_ORDER:
            label=LABELS[key]
            spin=W.QDoubleSpinBox();spin.setObjectName('Plastic'+key)
            configure_dimension_spin(key,spin)
            self.fields[key]=spin;self.labels[key]=W.QLabel(tr(*label));form.addRow(self.labels[key],spin)
        note=W.QLabel(tr('選択面から外向きに追加し、元のボディと結合します。U/Vは元形状の原点を面に投影した位置が基準です。下穴はボス内部だけで、元の板を貫通しません。',
                           'Adds outward from the selected face and joins the source. U/V use the source origin projected onto the face. The boss bore does not drill through the original plate.'))
        self.note=note;self.default_note=note.text();note.setWordWrap(True);form.addRow(note);self.combos=();self.spins=tuple(self.fields.values())
        self.build_position_controls(form)
    def build_flip_control(self,form):
        self.flip_button = W.QPushButton(tr("180°回転","Rotate 180°"))
        self.flip_button.setToolTip(tr("三角リブや爪を支持面内で180°回転します。押し出す方向は変わりません。", "Rotates the triangular rib or hook 180° within the support plane. The extrusion direction stays the same."))
        self.flip_button.clicked.connect(lambda checked=False: self.rotate_half_turn())
        form.addRow(self.flip_button)

    def configure_flip_control(self):
        shown = self.kind in ('gusset', 'snap')
        self.flip_button.setVisible(shown)
        self.flip_button.setEnabled(shown and self.fields['Angle'].isEnabled())

    def rotate_half_turn(self):
        if not self.active or self.kind not in ('gusset', 'snap') or not self.fields['Angle'].isEnabled():
            return
        try:
            angle = float(self.values()['Angle'])
            if not (-360 <= angle <= 360):
                raise ValueError(tr("回転角は-360〜360°にしてください。", "Angle must be between -360 and 360 degrees."))
            result = (angle + 360) % 360 - 180
            spin = self.fields['Angle']
            old = spin.blockSignals(True)
            try:
                spin.setValue(result)
            finally:
                spin.blockSignals(old)
            self.initial['Angle'] = result
            self.displayed['Angle'] = spin.value()
            self.update_preview()
        except Exception as error:
            self.clear_preview()
            self.valid = False
            self.accept_button.setEnabled(False)
            self.status.setText(str(error))
            self.status.setStyleSheet('color:#ac3830;')

    def build_position_controls(self, form):
        self.position_row = W.QWidget()
        layout = W.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
    
        self.center_button = W.QPushButton(tr("面の中心", "Face Center"))
        self.center_button.setToolTip(tr("面の中心は選択された面の重心に位置します。", "Face Center positions at selected face center of mass."))
    
        self.origin_button = W.QPushButton(tr("U/V = 0", "U/V = 0"))
        self.origin_button.setToolTip(tr("U/V=0 は、ソースの原点がサポート平面に投影された位置を使用します。", "U/V=0 uses source origin projected on support plane."))
    
        def connect_center():
            self.set_position('center')
        def connect_origin():
            self.set_position('origin')
        
        self.center_button.clicked.connect(lambda checked=False: connect_center())
        self.origin_button.clicked.connect(lambda checked=False: connect_origin())
    
        layout.addWidget(self.center_button)
        layout.addWidget(self.origin_button)
        self.position_row.setLayout(layout)
        form.addRow(self.position_row)
        self.build_flip_control(form)

    def set_position(self, mode):
        if not self.active or (self.fields['U'].isEnabled() == False) or (self.fields['V'].isEnabled() == False):
            return
    
        try:
            if mode == 'center':
                face, origin, u, v, n, pose = plastic.reference_frame(self.source, self.face, stable=plastic.use_stable_frame(self.existing))
                delta = face.CenterOfMass - origin
                values = {'U': delta.dot(u), 'V': delta.dot(v)}
            elif mode == 'origin':
                values = {'U': 0., 'V': 0.}
            else:
                raise ValueError('Unknown position mode')
        
            for key, value in values.items():
                spin = self.fields[key]
                old = spin.blockSignals(True)
                try:
                    spin.setValue(value)
                finally:
                    spin.blockSignals(old)
        
            self.initial['U'] = values['U']
            self.initial['V'] = values['V']
            self.displayed['U'] = self.fields['U'].value()
            self.displayed['V'] = self.fields['V'].value()
        
            self.update_preview()
        except Exception as error:
            self.clear_preview()
            self.valid = False
            self.accept_button.setEnabled(False)
            self.status.setText(str(error))
            self.status.setStyleSheet('color:#ac3830;')

    def position(self):
        super().position()
        if self.active and self.scroll is not None and self.scroll.widget() is not None:
            content = self.scroll.widget()
            content.setMinimumWidth(0)
            content.setMaximumWidth(max(0, self.scroll.viewport().width()))

    def start(self,kind=None,existing=None):
        self.cancel();self.doc=App.ActiveDocument
        if not self.doc or self.ws.current_sketch() or Gui.Control.activeDialog():
            raise ValueError(tr('編集を終了し、ボディの平面を1つ選択してください。','Finish editing and select one planar solid face.'))
        self.existing=existing
        if existing:
            if existing.Document!=self.doc or getattr(existing,'FluxPlastic','') not in plastic.FIELDS:raise ValueError('Invalid plastic feature')
            self.kind=existing.FluxPlastic;self.source,self.face=plastic.support(existing);values=plastic.settings(existing)
        else:
            self.kind=kind
            from model_hole import reference,frame
            selected=Gui.Selection.getSelectionEx()
            if len(selected)!=1 or len(selected[0].SubElementNames)!=1:
                raise ValueError(tr('ボディの平面を1つ選択してください。','Select one planar face of a solid.'))
            self.source,self.face=reference(self.doc,selected[0].ObjectName,selected[0].SubElementNames[0])
            values=plastic.DEFAULTS[kind].copy();face,origin,u,v,n,pose=plastic.reference_frame(self.source,self.face)
            center=face.CenterOfMass-origin;values.update(U=center.dot(u),V=center.dot(v))
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        self.note.setText(feature_note(self.kind,self.default_note))
        self.heading.setText(plastic.title(self.kind));self.target.setText(self.source.Label+' / '+self.face)
        for key,spin in self.fields.items():
            shown=key in values;spin.setVisible(shown);self.labels[key].setVisible(shown)
            if shown:spin.setValue(values[key])
        self.initial=values.copy();self.displayed=self.values(raw=True)
        from parameters import lock_fields
        lock_fields(existing,self.fields)
        self.configure_flip_control()
        for button in (self.center_button,self.origin_button):
            button.setEnabled(all(self.fields[k].isEnabled() for k in ('U','V')))
        self.source_signature=self.signature()
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.active=True;self.panel.show();self.update_preview();self.position()
    def values(self,raw=False):
        return {k:(self.fields[k].value() if raw or self.fields[k].value()!=self.displayed[k] else self.initial[k]) for k in plastic.FIELDS[self.kind]}
    def signature(self):
        pose = self.source.getGlobalPlacement()
        if plastic.use_stable_frame(self.existing):
            pose = plastic.coordinate_pose(self.source)
        current = None
        if self.existing:
            current = (str(self.existing.getGlobalPlacement()), plastic.settings(self.existing), tuple(self.existing.ExpressionEngine), plastic.support(self.existing))
        return (self.source.Shape.hashCode(), str(pose), tuple(self.source.State), current)
    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        try:
            if self.signature()!=self.source_signature:raise ValueError(tr('元形状が変更されました。開き直してください。','Source changed. Reopen this tool.'))
            shape=plastic.preview(self.source,self.face,self.kind,self.values(),self.existing)
            self.show_shape(shape,'new');target=self.existing or self.source
            self.hidden.append((target,bool(target.Visibility)));target.Visibility=False
            self.valid=True;self.accept_button.setEnabled(True);self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('元のボディと結合した形状をプレビューしています。','Previewing the joined body.'))
        except Exception as error:self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;')
    def accept(self):
        if not self.active:return
        for spin in self.spins:spin.interpretText()
        self.update_preview()
        if not self.valid:return
        self.clear_preview()
        try:obj=plastic.apply(self.doc,self.source,self.face,self.kind,self.values(),self.existing)
        except Exception as error:self.status.setText(str(error));return
        self.active=False;self.timer.stop();self.panel.hide();Gui.Selection.clearSelection();Gui.Selection.addSelection(obj);self.ws.refresh()
    def refresh(self):
        if not self.active:
            return
        try:
            if App.ActiveDocument != self.doc or self.ws.current_sketch() or not self.source.Document or (self.existing and not self.existing.Document):
                self.cancel()
                return
            try:
                changed = self.signature() != self.source_signature
            except Exception:
                changed = True
            if changed:
                self.update_preview()
        except (RuntimeError, ReferenceError):
            self.cancel()
            return
        self.position()
