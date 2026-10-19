"""Movable signed-mm dimension editor with a transient shape preview."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from floating_panel import FloatingPanel
from i18n import tr
import model_scale_dimensions as scale


class ScaleDimensionsPanel(FloatingPanel):
    layout_key = 'ScaleDimensionsPanel'
    preferred_height = 430
    preferred_width = 450

    def build_fields(self, form):
        self.target_label = W.QLabel()
        self.target_label.setWordWrap(True)
        form.addRow(self.target_label)
        table = W.QWidget()
        grid = W.QGridLayout(table)
        grid.setContentsMargins(0, 0, 0, 0)
        self.before_heading = W.QLabel()
        for column, label in enumerate((W.QLabel(tr('軸', 'Axis')), self.before_heading,
                                       W.QLabel(tr('増減量', 'Change')), W.QLabel(tr('変更後', 'Result')))):
            grid.addWidget(label, 0, column)
        self.before = {}; self.delta = {}; self.after = {}
        for row, axis in enumerate(scale.AXES, 1):
            grid.addWidget(W.QLabel(axis), row, 0)
            self.before[axis] = W.QLabel()
            grid.addWidget(self.before[axis], row, 1)
            spin = W.QDoubleSpinBox()
            spin.setObjectName('Delta'+axis)
            spin.setDecimals(3); spin.setRange(-1000000, 1000000)
            spin.setSingleStep(1); spin.setSuffix(' mm')
            spin.setKeyboardTracking(False)
            spin.setMinimumWidth(120)
            spin.setToolTip(tr('全体寸法の増減量。+5は5 mm拡大、-2は2 mm縮小です。',
                               'Change in total dimension: +5 enlarges by 5 mm; -2 shrinks by 2 mm.'))
            self.delta[axis] = spin
            grid.addWidget(spin, row, 2)
            self.after[axis] = W.QLabel()
            grid.addWidget(self.after[axis], row, 3)
        form.addRow(table)
        self.reset_button=W.QPushButton(tr('開始時の値に戻す','Reset to Starting Values'))
        self.reset_button.setObjectName('FluxResetDimensionChanges')
        self.reset_button.clicked.connect(self.reset_changes)
        form.addRow(self.reset_button)
        self.note = W.QLabel()
        self.note.setWordWrap(True)
        form.addRow(self.note)
        self.combos = ()
        self.spins = tuple(self.delta.values())

    def start(self, existing=None):
        self.cancel()
        self.doc = App.ActiveDocument
        if not self.doc or self.ws.current_sketch() or Gui.Control.activeDialog():
            raise ValueError(tr('編集を終了してボディを選択してください。', 'Finish the current edit and select a body.'))
        self.existing = existing
        if existing:
            if existing.Document != self.doc or not getattr(existing, 'FluxDimensionScale', False):
                raise ValueError(tr('寸法変更の履歴を選択してください。', 'Select a Resize by Dimensions feature.'))
            self.source = existing.Source
        else:
            from browser import body_owner
            selected = list(dict.fromkeys(body_owner(o) for o in Gui.Selection.getSelection()))
            if len(selected) != 1:
                raise ValueError(tr('寸法を変更するボディを1つ選択してください。', 'Select one body to resize.'))
            self.source = selected[0]
        self.base_shape = scale.source_shape(self.source)
        self.source_signature = self.signature()
        self.selection = [(s.ObjectName, tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        self.heading.setText(tr('寸法で拡大・縮小', 'Resize by Dimensions'))
        self.target_label.setText(self.source.Label)
        self.before_heading.setText(tr('元の寸法', 'Source Size') if existing else tr('現在寸法', 'Current Size'))
        self.original = scale.dimensions(self.base_shape)
        self.initial = scale.changes(existing) if existing else (0, 0, 0)
        for axis, size, delta in zip(scale.AXES, self.original, self.initial):
            self.before[axis].setText('%.3f mm' % size)
            self.before[axis].setToolTip('%.9f mm' % size)
            self.delta[axis].setValue(delta)
        self.initial_displayed = tuple(field.value() for field in self.spins)
        from parameters import lock_fields
        lock_fields(existing, {'Delta'+axis: field for axis, field in self.delta.items()})
        self.note.setText(tr('中心位置を保ち、穴や肉厚を含む全体を伸縮します。\nX・Y・Zはモデルの座標軸です。画面の縦横ではありません。',
                            'Keeps the bounding-box center and scales the whole body, including holes and wall thickness.\nX/Y/Z are model axes, not screen directions.') +
                          (tr('\n再編集の増減量は元形状からの合計です。結果を移動・回転しても、寸法変更の軸は加工前のままです。',
                              '\nWhen editing, changes are totals relative to the source. Moving/rotating the result does not change the original resize axes.') if existing else ''))
        self.ws.region_picker.ticket += 1; self.ws.region_picker.clear()
        self.active = True; self.panel.show(); self.update_preview(); self.position()

    def signature(self):
        return (self.source.Shape.hashCode(), str(self.source.getGlobalPlacement()),
                tuple(self.source.State),
                (str(self.existing.getGlobalPlacement()), scale.changes(self.existing),
                 tuple(self.existing.ExpressionEngine)) if self.existing else None)

    def values(self):
        # Opening and confirming an editor must not round untouched parameters.
        return tuple(old if field.value() == shown else field.value()
                     for field, old, shown in zip(self.spins, self.initial, self.initial_displayed))

    def update_preview(self):
        self.timer.stop()
        if not self.active: return
        if App.ActiveDocument != self.doc: self.cancel(); return
        self.clear_preview(); self.valid = False; self.accept_button.setEnabled(False)
        try:
            if self.signature() != self.source_signature:
                raise ValueError(tr('形状が変更されました。開き直して寸法を確認してください。',
                                    'The shape changed. Reopen this tool to read its dimensions.'))
            delta = self.values()
            for axis, size, change in zip(scale.AXES, self.original, delta):
                self.after[axis].setText('%.3f mm' % (size+change))
                self.after[axis].setToolTip('%.9f mm' % (size+change))
            shape = scale.preview(self.source, delta, self.existing)
            if all(abs(a-b) < 1e-12 for a, b in zip(delta, self.initial)):
                self.status.setText(tr('増減量を入力してください。例：+5 / -2 mm', 'Enter a change, for example +5 / -2 mm.'))
                self.status.setStyleSheet('color:#245b73;'); return
            self.show_shape(shape, 'new')
            target = self.existing or self.source
            self.hidden.append((target, bool(target.Visibility))); target.Visibility = False
            self.valid = True; self.accept_button.setEnabled(True)
            self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('変更後の形状をプレビューしています。', 'Previewing the resized shape.'))
        except Exception as error:
            self.clear_preview(); self.status.setText(str(error)); self.status.setStyleSheet('color:#ac3830;')

    def accept(self):
        if not self.active: return
        for spin in self.spins: spin.interpretText()
        self.update_preview()
        if not self.valid: return
        self.clear_preview()
        try:
            result = scale.apply(self.doc, self.source, self.values(), self.existing)
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
            if self.signature() != self.source_signature: self.update_preview()
        except (RuntimeError, ReferenceError): self.cancel(); return
        self.position()

    def reset_changes(self):
        if not self.active:
            return
        for field, initial in zip(self.spins, self.initial):
            if field.isEnabled():
                blocked = field.blockSignals(True)
                try:
                    field.setValue(initial)
                finally:
                    field.blockSignals(blocked)
        self.update_preview()
