"""Movable parameter table and dimension assignments; edits apply atomically."""
import FreeCAD as App
from PySide import QtCore, QtWidgets as W
from i18n import tr
import parameters as data
import parameter_csv


class ParameterDialog(W.QDialog):
    def __init__(self, ws):
        super().__init__(ws.main)
        self.ws = ws; self.doc = App.ActiveDocument
        self.setObjectName('FluxParameterDialog')
        self.setWindowTitle(tr('パラメータを変更', 'Change Parameters'))
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.resize(980,610); self.setMinimumSize(660,420); self.setSizeGripEnabled(True)
        layout = W.QVBoxLayout(self)
        layout.addWidget(W.QLabel(self.doc.Label + tr(' — 名前付き寸法と式', ' — Named dimensions and expressions')))
        self.tabs = W.QTabWidget(); layout.addWidget(self.tabs)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setUsesScrollButtons(False)
        self.tabs.tabBar().setElideMode(QtCore.Qt.ElideNone)
        page = W.QWidget(); p = W.QVBoxLayout(page)
        hint = W.QLabel(tr('例：幅 = 60 mm、穴位置 = 幅 / 2。名前に日本語も使えます。既存の名前・単位は固定です。',
                           'Example: Width = 60 mm, HolePosition = Width / 2. Japanese names are supported. Existing names and unit types are fixed.'))
        hint.setWordWrap(True); p.addWidget(hint)
        self.table = W.QTableWidget(0,4); self.table.setObjectName('FluxParameterTable')
        self.table.setHorizontalHeaderLabels([tr('名前','Name'),tr('種類','Type'),tr('値または式','Value or Expression'),tr('計算結果','Result')])
        self.table.horizontalHeader().setSectionResizeMode(W.QHeaderView.Stretch)
        self.table.setSelectionBehavior(W.QAbstractItemView.SelectRows); self.table.setSelectionMode(W.QAbstractItemView.SingleSelection)
        p.addWidget(self.table)
        buttons = W.QHBoxLayout()
        self.add_button = W.QPushButton(tr('追加','Add')); self.add_button.clicked.connect(self.add_row)
        self.remove_button = W.QPushButton(tr('削除','Remove')); self.remove_button.clicked.connect(self.remove_row)
        self.import_button = W.QPushButton(tr('インポート','Import')); self.import_button.setObjectName('FluxParameterImport'); self.import_button.clicked.connect(self.import_csv)
        self.export_button = W.QPushButton(tr('エクスポート','Export')); self.export_button.setObjectName('FluxParameterExport'); self.export_button.clicked.connect(self.export_csv)
        buttons.addWidget(self.add_button); buttons.addWidget(self.remove_button); buttons.addWidget(self.import_button); buttons.addWidget(self.export_button); buttons.addStretch(); p.addLayout(buttons)
        self.tabs.addTab(page,tr('パラメータ','Parameters'))
        page = W.QWidget(); p = W.QVBoxLayout(page)
        hint = W.QLabel(tr('寸法と同じ種類のパラメータを選びます。「固定値」は式を解除して現在値を残します。',
                           'Choose a parameter of the same type. Fixed Value removes the expression and keeps the current value.'))
        hint.setWordWrap(True); p.addWidget(hint)
        self.bindings = W.QTableWidget(0,4); self.bindings.setObjectName('FluxParameterBindings')
        self.bindings.setHorizontalHeaderLabels([tr('対象','Object'),tr('寸法','Dimension'),tr('現在値','Current Value'),tr('パラメータ','Parameter')])
        self.bindings.horizontalHeader().setSectionResizeMode(W.QHeaderView.Stretch)
        self.bindings.setEditTriggers(W.QAbstractItemView.NoEditTriggers); p.addWidget(self.bindings)
        self.tabs.addTab(page,tr('寸法への割り当て','Dimension Assignments'))
        self.status = W.QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        box = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Apply | W.QDialogButtonBox.Cancel)
        self.apply_button = box.button(W.QDialogButtonBox.Apply); self.ok_button = box.button(W.QDialogButtonBox.Ok)
        self.apply_button.setText(tr('適用','Apply')); box.button(W.QDialogButtonBox.Cancel).setText(tr('閉じる','Close'))
        self.apply_button.clicked.connect(self.apply_changes); box.accepted.connect(self.accept_changes); box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.tabs.currentChanged.connect(lambda i:self.refresh_bindings() if i==1 else None)
        self.reload()

    def entries(self):
        return [dict(name=self.table.item(i,0).text().strip(),kind=self.table.cellWidget(i,1).currentData(),
                     formula=self.table.item(i,2).text()) for i in range(self.table.rowCount())]

    def insert_row(self, row, existing=False):
        i = self.table.rowCount(); self.table.insertRow(i)
        name = W.QTableWidgetItem(row['name'])
        if existing: name.setFlags(name.flags() & ~QtCore.Qt.ItemIsEditable)
        self.table.setItem(i,0,name)
        combo = W.QComboBox()
        for label,key in [(tr('長さ (mm)','Length (mm)'),'length'),(tr('角度 (°)','Angle (°)'),'angle'),(tr('数値','Number'),'number')]:combo.addItem(label,key)
        combo.setCurrentIndex(combo.findData(row['kind'])); combo.setEnabled(not existing); self.table.setCellWidget(i,1,combo)
        self.table.setItem(i,2,W.QTableWidgetItem(row['formula']))
        result = W.QTableWidgetItem(row.get('result',tr('適用後に表示','Shown after Apply')))
        result.setFlags(result.flags() & ~QtCore.Qt.ItemIsEditable); self.table.setItem(i,3,result)

    def reload(self):
        self.expected = data.fingerprint(self.doc)
        self.table.setRowCount(0); self.bindings.setRowCount(0); self.targets = data.dimensions(self.doc)
        for row in data.rows(self.doc):self.insert_row(row,True)
        self.refresh_bindings()

    def add_row(self):
        names = {r['name'] for r in self.entries()}; index = 1
        while 'Length%d' % index in names:index += 1
        self.insert_row(dict(name='Length%d' % index,kind='length',formula='10 mm'))
        self.table.setCurrentCell(self.table.rowCount()-1,0); self.table.editItem(self.table.currentItem())

    def remove_row(self):
        row = self.table.currentRow()
        if row >= 0:self.table.removeRow(row)

    def binding_edits(self):
        return [dict(object=t['object'],path=t['path'],parameter=self.bindings.cellWidget(i,3).currentData()) for i,t in enumerate(self.targets)]

    def refresh_bindings(self):
        previous = {(b['object'],b['path']):b['parameter'] for b in self.binding_edits()} if self.bindings.rowCount() else {}
        self.bindings.setRowCount(0); entries = self.entries()
        for i,t in enumerate(self.targets):
            self.bindings.insertRow(i)
            for col,field in enumerate(('owner_label','label','value')):
                item = W.QTableWidgetItem(t[field]); item.setToolTip(t['object']+'.'+t['path']+('\n'+t['expression'] if t['expression'] else ''))
                self.bindings.setItem(i,col,item)
            combo = W.QComboBox(); combo.addItem(tr('固定値（式なし）','Fixed Value (No Expression)'),None)
            if t['expression']:combo.addItem(tr('現在の式を保持','Keep Current Expression')+': '+t['expression'],data.KEEP)
            for row in entries:
                if row['kind']==t['kind']:combo.addItem(row['name'],row['name'])
            selected = previous.get((t['object'],t['path']),data.assigned(self.doc,t)); found = combo.findData(selected)
            if found < 0 and selected:
                combo.addItem(tr('見つかりません: ','Missing: ')+selected,selected); found=combo.count()-1
            combo.setCurrentIndex(max(0,found)); self.bindings.setCellWidget(i,3,combo)

    def import_csv(self):
        self.import_button.setFocus()
        path, _ = W.QFileDialog.getOpenFileName(self, tr('CSV読込', 'Import CSV'), '', 'CSV (*.csv)')
        if not path:
            return
        try:
            incoming = parameter_csv.read_csv(path)
            saved = {r['name']: r['kind'] for r in data.rows(self.doc)}
            for row in incoming:
                if row['name'] in saved and saved[row['name']] != row['kind']:
                    raise ValueError(tr('種類が一致しません', 'Parameter type mismatch'))
            merged = parameter_csv.merge_entries(self.entries(), incoming)
            self.refresh_bindings()
            self.table.setRowCount(0)
            for row in merged:
                self.insert_row(row, row['name'] in saved)
            self.refresh_bindings()
            self.status.setStyleSheet('color:#247458;')
            self.status.setText(tr('読み込みました。確認して適用してください。', 'Imported. Review and Apply.'))
        except Exception as error:
            self.status.setStyleSheet('color:#b33725;')
            self.status.setText(str(error))

    def export_csv(self):
        from pathlib import Path
        self.export_button.setFocus()
        path, _ = W.QFileDialog.getSaveFileName(self, tr('CSV 書出', 'Export CSV'), '', 'CSV (*.csv)')
        if not path:
            return
        try:
            target = Path(path)
            completed_suffix = not target.suffix
            if completed_suffix:
                target = target.with_suffix('.csv')
            if completed_suffix and target.exists():
                answer = W.QMessageBox.question(self, tr('上書き確認', 'Confirm Overwrite'), tr('次の CSV を上書きしますか？\n%s', 'Overwrite this CSV?\n%s') % str(target), W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
                if answer != W.QMessageBox.Yes:
                    return
            parameter_csv.write_csv(target, self.entries())
            self.status.setStyleSheet('color:#247458;')
            self.status.setText(tr('書き出しました：', 'Exported: ') + str(target))
        except Exception as error:
            self.status.setStyleSheet('color:#b33725;')
            self.status.setText(str(error))

    def apply_changes(self):
        try:
            if App.ActiveDocument != self.doc:raise ValueError(tr('対象文書が変更されました。開き直してください。','The active document changed. Reopen the dialog.'))
            self.apply_button.setFocus(); self.refresh_bindings()
            data.apply(self.doc,self.entries(),self.binding_edits(),expected=self.expected)
            self.reload(); self.ws.refresh()
            self.status.setStyleSheet('color:#247458;'); self.status.setText(tr('適用しました。Ctrl＋Zで元に戻せます。','Applied. Use Ctrl+Z to undo.'))
            return True
        except Exception as error:
            self.status.setStyleSheet('color:#b33725;'); self.status.setText(str(error)); return False

    def accept_changes(self):
        if self.apply_changes():self.accept()


def show(ws):
    if not App.ActiveDocument:raise ValueError(tr('文書を開いてください。','Open a document first.'))
    if ws.current_sketch():raise ValueError(tr('スケッチ編集を終了してからパラメータを変更してください。','Finish sketch editing before changing parameters.'))
    prior = getattr(ws,'parameter_dialog',None)
    if prior and prior.isVisible():prior.raise_();prior.activateWindow();return prior
    dialog = ParameterDialog(ws); ws.parameter_dialog = dialog; dialog.show();return dialog
