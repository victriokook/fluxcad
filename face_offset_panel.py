import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from floating_panel import FloatingPanel
from i18n import tr
import model_face_offset as offset
from face_offset_settings import save_settings
from types import SimpleNamespace


class FaceOffsetPanel(FloatingPanel):
    layout_key = 'FaceOffsetPanel'
    preferred_height = 200
    preferred_width = 350



    def build_fields(self, form):
        self.target_label = W.QLabel()
        self.target_label.setWordWrap(True)
        form.addRow(self.target_label)
        spin = W.QDoubleSpinBox()
        spin.setObjectName('Distance')
        spin.setDecimals(3); spin.setRange(-1e6, 1e6)
        spin.setSingleStep(0.1); spin.setSuffix(' mm')
        spin.setKeyboardTracking(False)
        spin.setMinimumWidth(200)
        self.spin = spin
        form.addRow(tr('距離 (Distance)', 'Distance'), spin)
        self.note = W.QLabel()
        self.note.setWordWrap(True)
        form.addRow(self.note)
        self.save_settings_button = W.QPushButton(tr('設定を保存…', 'Save settings…'))
        self.save_settings_button.setObjectName('SaveOffsetSettings')
        self.save_settings_button.clicked.connect(self.save_settings_dialog)
        form.addRow(self.save_settings_button)
        self.combos = ()
        self.spins = (self.spin,)

    def start(self, existing=None):
        self.cancel()
        self.doc = App.ActiveDocument
        if not self.doc or self.ws.current_sketch() or Gui.Control.activeDialog():
            raise ValueError(tr('編集を終了してボディを選択してください。', 'Finish the current edit and select a body.'))
        self.existing = existing

        if existing:
            if existing.Document != self.doc or not getattr(existing, 'FluxFaceOffset', False):
                raise ValueError(tr('既存のオフセット特徴を選択してください。', 'Select an existing Face Offset feature.'))
            source = existing.Source
            faces = list(existing.FaceNames)
            initial_distance = existing.Distance.Value
        else:
            selected = list(dict.fromkeys(o for o in Gui.Selection.getSelectionEx()))
            if len(selected) != 1:
                raise ValueError(tr('1つのオブジェクトとその面を選択してください。', 'Select one object with faces.'))
            record = selected[0]

            if not getattr(record, 'SubElementNames', None):
                raise ValueError(tr('面を選択してください。', 'Select faces.'))
            source = record.Object
            faces = list(record.SubElementNames)
            initial_distance = 0.0
        self.source = source
        self.faces = faces
        if existing:
            self.existing_faces = list(self.faces)
        else:
            self.existing_faces = None
        self.initial_distance = initial_distance
        self.base_shape = offset.source_shape(self.source)
        self.source_signature = (self.source.Shape.hashCode(), str(self.source.getGlobalPlacement()))
        if self.existing:
            sig_extra = ((str(self.existing.getGlobalPlacement()), self.existing.Distance.Value, tuple(self.existing.FaceNames)),)
            self.source_signature += sig_extra
        self.heading.setText(tr('面オフセット', 'Face Offset'))
        self.target_label.setText(f"{self.source.Label} ({len(self.faces)} faces)")
        self.spin.setValue(self.initial_distance)
        self.initial_displayed = self.spin.value()
        self.note.setText(tr('+は外向き、-は内向きです。', '+ is outward, - is inward.'))
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        self.active = True; self.panel.show(); self.update_preview(); self.position()

    def values(self):
        return self.spin.value() if abs(self.spin.value() - self.initial_displayed) > 1e-9 else self.initial_distance

    def update_preview(self):
        self.timer.stop()
        if not self.active: return
        if App.ActiveDocument != self.doc: self.cancel(); return
        self.clear_preview(); self.valid = False; self.accept_button.setEnabled(False)
        try:
            sig = (self.source.Shape.hashCode(), str(self.source.getGlobalPlacement()))
            if self.existing:
                sig += ((str(self.existing.getGlobalPlacement()), self.existing.Distance.Value, tuple(self.existing.FaceNames)),)
            if sig != self.source_signature:
                raise ValueError(tr('形状が変更されました。開き直してください。', 'Shape changed. Reopen tool.'))
            dist = self.values()
            shape = offset.preview(self.source, self.faces, dist, self.existing)
            if abs(dist - self.initial_distance) < 1e-9:
                self.status.setText(tr('距離を入力してください。', 'Enter a distance.'))
                self.status.setStyleSheet('color:#245b73;'); return
            self.show_shape(shape, 'new')
            target = self.existing or self.source
            self.hidden.append((target, bool(target.Visibility))); target.Visibility = False
            self.valid = True; self.accept_button.setEnabled(True)
            self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('プレビューしています。', 'Previewing.'))
        except Exception as error:
            self.clear_preview(); self.status.setText(str(error)); self.status.setStyleSheet('color:#ac3830;')

    def accept(self):
        if not self.active: return
        self.spin.interpretText()
        self.update_preview()
        if not self.valid: return
        self.clear_preview()
        try:
            result = offset.apply(self.doc, self.source, self.faces, self.values(), self.existing)
        except Exception as error:
            self.status.setText(str(error)); self.status.setStyleSheet('color:#ac3830;'); return
        self.active = False; self.timer.stop(); self.panel.hide()
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(result); self.ws.refresh()

    def refresh(self):
        if not self.active: return
        try:
            if (App.ActiveDocument != self.doc or self.ws.current_sketch() or not self.source.Document
                    or (self.existing and not self.existing.Document)):
                self.cancel(); return
            sig = (self.source.Shape.hashCode(), str(self.source.getGlobalPlacement()))
            if self.existing:
                sig += ((str(self.existing.getGlobalPlacement()), self.existing.Distance.Value, tuple(self.existing.FaceNames)),)
            if sig != self.source_signature: self.update_preview()
        except (RuntimeError, ReferenceError): self.cancel(); return
        self.position()

    def save_settings_dialog(self):
        if not self.active:
            return
        try:
            distance = self.spin.interpretText()
            if not self.doc or not self.source:
                raise ValueError(tr('No active document or source.', 'No active document or source.'))
            if App.ActiveDocument != self.doc:
                raise ValueError('Document changed')
            current_signature = (int(self.source.Shape.hashCode()), str(self.source.getGlobalPlacement()))
            if self.existing:
                existing_data = ((str(self.existing.getGlobalPlacement()), self.existing.Distance.Value, tuple(self.existing.FaceNames)),)
                current_signature = current_signature + existing_data
            else:
                existing_data = None
            if current_signature != self.source_signature:
                raise ValueError(tr('Source signature mismatch.', 'Source signature mismatch.'))
            offset.preview(self.source, self.faces, self.values(), self.existing)
            save_context = (self.doc, self.source, self.existing, tuple(self.faces), self.values(), self.source_signature)
            filename, _ = W.QFileDialog.getSaveFileName(self.panel, tr('設定を保存', 'Save settings'), '', 'JSON (*.json)')
            if not filename:
                return
            original_filename = filename
            if not filename.lower().endswith('.json'):
                filename += '.json'
            from pathlib import Path
            if filename != original_filename and Path(filename).exists():
                answer = W.QMessageBox.question(self.panel, tr('上書き確認', 'Confirm Overwrite'), tr('既存の設定を上書きしますか？', 'Overwrite the existing settings?'), W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
                if answer != W.QMessageBox.Yes:
                    return
            if not self.active or App.ActiveDocument != self.doc or save_context != (self.doc, self.source, self.existing, tuple(self.faces), self.values(), self.source_signature):
                raise ValueError(tr('対象または入力が変更されました。保存をやり直してください。', 'The target or input changed. Save settings again.'))
            final_signature = (int(self.source.Shape.hashCode()), str(self.source.getGlobalPlacement()))
            if self.existing:
                final_signature += ((str(self.existing.getGlobalPlacement()), self.existing.Distance.Value, tuple(self.existing.FaceNames)),)
            if final_signature != save_context[-1]:
                raise ValueError(tr('形状が変更されました。開き直してください。', 'Shape changed. Reopen tool.'))
            save_settings(SimpleNamespace(Source=self.source, FaceNames=self.faces, Distance=self.values()), filename)
            self.status.setText(tr('設定を保存しました。', 'Settings saved.'))
            self.status.setStyleSheet('color:#245b73;')
        except Exception as e:
            self.status.setText(str(e))
            self.status.setStyleSheet('color:red;')
