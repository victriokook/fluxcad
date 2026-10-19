"""Movable interference inspector; results and highlighting never enter the document."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from pivy import coin
from floating_panel import FloatingPanel
from i18n import tr
import model_interference as interference


class InterferencePanel(FloatingPanel):
    layout_key = 'InterferencePanel'
    preferred_width = 410
    preferred_height = 760

    def __init__(self, ws):
        super().__init__(ws)
        self.running = False
        self.worker = QtCore.QTimer(self)
        self.worker.setInterval(10)
        self.worker.timeout.connect(self.next_pair)
        self.accept_button.setText(tr('計算', 'Calculate'))
        self.cancel_button.setText(tr('閉じる', 'Close'))
        for label in self.panel.findChildren(W.QLabel):
            if label.text() == tr('中ボタンで視点操作できます。\n確定するまでモデルには追加しません。'):
                label.setText(tr('中ボタンで視点操作できます。\n検査結果はモデルや履歴に追加しません。',
                                 'Use the middle button to navigate.\nInspection results are not added to the model or history.'))

    def build_fields(self, form):
        self.scope = W.QComboBox()
        self.scope.addItem(tr('表示中のボディすべて', 'All Visible Bodies'), 'visible')
        self.scope.addItem(tr('チェックしたボディ', 'Checked Bodies'), 'checked')
        self.scope.currentIndexChanged.connect(self.inputs_changed)
        form.addRow(tr('対象', 'Scope'), self.scope)
        self.targets = W.QListWidget()
        self.targets.setMinimumHeight(85); self.targets.setMaximumHeight(140)
        self.targets.itemChanged.connect(self.inputs_changed)
        form.addRow(self.targets)
        self.minimum = W.QDoubleSpinBox()
        self.minimum.setObjectName('minimumInterferenceVolume')
        self.minimum.setDecimals(6); self.minimum.setRange(0, 1000000)
        self.minimum.setValue(.000001); self.minimum.setSuffix(' mm³')
        self.minimum.setKeyboardTracking(False)
        self.minimum.valueChanged.connect(self.inputs_changed)
        form.addRow(tr('最小干渉体積', 'Minimum Volume'), self.minimum)
        self.results = W.QTreeWidget()
        self.results.setColumnCount(2)
        self.results.setHeaderLabels([tr('ボディの組み合わせ', 'Body Pair'), tr('体積 (mm³)', 'Volume (mm³)')])
        self.results.setRootIsDecorated(False); self.results.setMinimumHeight(130)
        self.results.setSelectionMode(W.QAbstractItemView.SingleSelection)
        self.results.header().setSectionResizeMode(0,W.QHeaderView.Stretch)
        self.results.header().setSectionResizeMode(1,W.QHeaderView.ResizeToContents)
        self.results.currentItemChanged.connect(self.highlight)
        form.addRow(self.results)
        note = W.QLabel(tr('行を選ぶと干渉部分を赤く透過表示します。面・辺で接するだけの部分は干渉に含みません。体積は組み合わせごとの値です。',
                           'Select a row to see the overlap in red through the bodies. Face/edge contact is excluded. Volumes are reported per pair.'))
        note.setWordWrap(True); form.addRow(note)
        self.combos = (); self.spins = ()

    def populate(self, checked):
        blocked = self.targets.blockSignals(True)
        self.targets.clear()
        for obj, title in interference.candidates(self.doc):
            label = title+' — '+obj.Label
            if not interference.visible(obj): label += tr('（非表示）', ' (hidden)')
            item = W.QListWidgetItem(label, self.targets)
            item.setToolTip(label)
            item.setData(QtCore.Qt.UserRole, obj.Name)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            included = interference.visible(obj) if self.scope.currentData() == 'visible' else obj.Name in checked
            item.setCheckState(QtCore.Qt.Checked if included else QtCore.Qt.Unchecked)
        self.targets.blockSignals(blocked)

    def checked_names(self):
        return {self.targets.item(i).data(QtCore.Qt.UserRole) for i in range(self.targets.count())
                if self.targets.item(i).checkState() == QtCore.Qt.Checked}

    def start(self):
        self.cancel(); self.doc = App.ActiveDocument
        if not self.doc or self.ws.current_sketch() or Gui.Control.activeDialog():
            raise ValueError(tr('編集を終了してボディのある文書を開いてください。',
                                'Finish the current edit and open a document with solid bodies.'))
        from browser import body_owner
        selected = {body_owner(o).Name for o in Gui.Selection.getSelection() if o.Document == self.doc}
        available = {o.Name for o, title in interference.candidates(self.doc)}
        selected &= available
        self.selection = [(s.ObjectName, tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        self.scope.setCurrentIndex(1 if len(selected) >= 2 else 0)
        self.populate(selected or available)
        self.targets.setEnabled(self.scope.currentData() == 'checked')
        self.heading.setText(tr('干渉チェック', 'Interference'))
        self.ws.region_picker.ticket += 1; self.ws.region_picker.clear()
        self.document_snapshot = interference.snapshot(self.doc)
        self.active = True; self.panel.show(); self.position(); self.accept()

    def clear_results(self):
        self.worker.stop(); self.running = False; self.valid = False
        self.iterator = None; self.hits = []; self.failures = []
        self.clear_preview()
        blocked = self.results.blockSignals(True)
        self.results.clear(); self.results.blockSignals(blocked)
        self.accept_button.setEnabled(True)

    def inputs_changed(self, *args):
        if not self.active: return
        self.clear_results()
        if self.sender() == self.scope: self.populate(self.checked_names())
        self.targets.setEnabled(self.scope.currentData() == 'checked')
        self.status.setStyleSheet('color:#245b73;')
        self.status.setText(tr('条件が変わりました。「計算」で検査します。', 'Settings changed. Click Calculate to inspect.'))

    def accept(self):
        if not self.active: return
        if App.ActiveDocument != self.doc: self.cancel(); return
        self.minimum.interpretText()
        self.clear_results()
        try:
            self.document_snapshot = interference.snapshot(self.doc)
            selected = self.checked_names()
            objects = [o for o, title in interference.candidates(self.doc)
                       if (interference.visible(o) if self.scope.currentData() == 'visible' else o.Name in selected)]
            entries = interference.prepare(self.doc, objects, self.minimum.value())
            self.iterator = iter(interference.pairs(entries))
            self.total = len(entries)*(len(entries)-1)//2
            self.finished_pairs = 0; self.running = True
            self.accept_button.setEnabled(False)
            self.status.setStyleSheet('color:#245b73;')
            self.status.setText(tr('計算中：0 / %d 組', 'Checking: 0 / %d pairs') % self.total)
            self.worker.start()
        except Exception as error:
            self.status.setStyleSheet('color:#ac3830;'); self.status.setText(str(error))

    def stale(self):
        self.clear_results()
        checked = self.checked_names(); self.populate(checked)
        self.document_snapshot = interference.snapshot(self.doc)
        self.status.setStyleSheet('color:#ac3830;')
        self.status.setText(tr('形状・配置・表示が変わりました。「計算」で再検査してください。',
                               'Geometry, placement or visibility changed. Click Calculate again.'))

    def next_pair(self):
        if not self.active or not self.running: return
        try:
            if App.ActiveDocument != self.doc: self.cancel(); return
            if interference.snapshot(self.doc) != self.document_snapshot: self.stale(); return
            pair = next(self.iterator, None)
            if pair is None:
                self.worker.stop(); self.running = False; self.valid = not self.failures
                self.accept_button.setEnabled(True)
                self.status.setStyleSheet('color:#ac3830;' if self.failures else 'color:#245b73;')
                self.status.setText(tr('検査未完了：計算できない組が %d 組あります。干渉を %d 組検出。',
                                       'Incomplete: %d pairs failed; %d interfering pairs found.') % (len(self.failures),len(self.hits)) if self.failures else
                                    tr('%d 組を検査：干渉 %d 組（最小体積を超えるもの）。',
                                       '%d pairs checked: %d interfering pairs above the minimum volume.') % (self.total,len(self.hits)))
                for i in range(self.results.topLevelItemCount()):
                    item = self.results.topLevelItem(i)
                    if item.data(0, QtCore.Qt.UserRole) is not None:
                        self.results.setCurrentItem(item); break
                return
            first, second = pair
            try:
                hit = interference.check_pair(first, second, self.minimum.value())
                if hit:
                    index = len(self.hits); self.hits.append(hit)
                    item = W.QTreeWidgetItem(self.results, [' / '.join(hit['labels']), '%.6g' % hit['volume']])
                    item.setData(0, QtCore.Qt.UserRole, index)
                    item.setToolTip(0,first['label']+' ['+first['name']+'] / '+second['label']+' ['+second['name']+']')
                    item.setToolTip(1, '%.12g mm³' % hit['volume'])
            except Exception as error:
                text = first['label']+' / '+second['label']+': '+str(error)
                self.failures.append(text)
                item = W.QTreeWidgetItem(self.results, [first['label']+' / '+second['label'], tr('計算失敗','Failed')])
                item.setToolTip(0,text); item.setToolTip(1,text)
            self.finished_pairs += 1
            self.status.setText(tr('計算中：%d / %d 組', 'Checking: %d / %d pairs') % (self.finished_pairs,self.total))
        except (RuntimeError,ReferenceError):
            self.cancel()

    def highlight(self, current=None, previous=None):
        self.clear_preview()
        if not self.active or current is None: return
        if interference.snapshot(self.doc) != self.document_snapshot: self.stale(); return
        index = current.data(0, QtCore.Qt.UserRole)
        if index is None or not 0 <= index < len(self.hits): return
        self.show_shape(self.hits[index]['shape'], 'cut')
        # See buried interference through opaque bodies without changing any
        # object's display properties, visibility or document modified flag.
        depth = coin.SoDepthBuffer(); depth.test = False; depth.write = False
        self.overlay[1].insertChild(depth,0)

    def refresh(self):
        if not self.active: return
        try:
            if App.ActiveDocument != self.doc or self.ws.current_sketch(): self.cancel(); return
            if interference.snapshot(self.doc) != self.document_snapshot: self.stale()
        except (RuntimeError,ReferenceError): self.cancel(); return
        self.position()

    def cancel(self):
        if hasattr(self,'worker'): self.worker.stop()
        self.running = False; self.iterator = None
        super().cancel()
        self.hits = []; self.failures = []
