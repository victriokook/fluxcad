"""Target/tool picking and cancellable previews for solid booleans."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore,QtWidgets as W
from floating_panel import FloatingPanel
from i18n import tr
import browser
import model
import model_combine as combine


class CombinePanel(FloatingPanel):
    layout_key='CombinePanel'
    preferred_height=530

    def __init__(self,ws):
        super().__init__(ws)
        policy=W.QSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);policy.setHeightForWidth(True)
        for label in (self.note,self.status):label.setSizePolicy(policy)

    def build_fields(self,form):
        self.operation=W.QComboBox()
        for key in ('join','cut','intersect'):self.operation.addItem(combine.label(key),key)
        form.addRow(tr('操作','Operation'),self.operation)
        self.target=W.QComboBox();form.addRow(tr('対象ボディ','Target Body'),self.target)
        self.pick_target=W.QPushButton(tr('対象を画面で選択','Pick Target'));self.pick_target.setCheckable(True)
        self.pick_target.clicked.connect(lambda:self.begin_pick('target'));form.addRow(self.pick_target)
        self.tools=W.QListWidget();self.tools.setMinimumHeight(100);self.tools.setMaximumHeight(145)
        form.addRow(tr('工具ボディ','Tool Bodies'),self.tools)
        self.pick_tools=W.QPushButton();self.pick_tools.setCheckable(True);self.pick_tools.clicked.connect(lambda:self.begin_pick('tools'))
        form.addRow(self.pick_tools)
        self.keep=W.QCheckBox(tr('工具ボディを保持','Keep Tool Bodies'));form.addRow(self.keep)
        self.keep.toggled.connect(self.schedule)
        self.note=W.QLabel();self.note.setWordWrap(True);form.addRow(self.note)
        for field in (self.target,self.operation,self.tools,self.pick_target,self.pick_tools):
            field.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Preferred)
        self.target.currentIndexChanged.connect(self.target_changed)
        self.tools.itemChanged.connect(self.tools_changed)
        self.combos=(self.operation,self.target);self.spins=()
        self.ticket=0;self.observing=False;self.picking=None

    def resolve(self,name,subname=''):
        obj=self.doc.getObject(name)
        if obj and subname:obj=obj.getSubObject(subname,1) or obj
        if obj:obj=browser.body_owner(obj)
        combine.solid(obj)
        if obj not in self.candidates:
            raise ValueError(tr('現在の独立したボディを選択してください。','Select a current, independent body.'))
        return obj

    def start(self,operation='join',existing=None):
        self.cancel()
        if self.ws.current_sketch():raise ValueError(tr('先にスケッチ編集を終了してください。','Finish editing the sketch first.'))
        self.doc=App.ActiveDocument;self.existing=existing;self.picking=None;self.source=None
        if not self.doc:raise ValueError(tr('ソリッドボディを作成してください。','Create solid bodies first.'))
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        self.candidates=[o for o,t in browser.collect(self.doc)[0] if o.Shape.Solids and not getattr(o,'FluxSplit',False)]
        if existing:
            self.candidates=[o for o in self.candidates if o!=existing and existing not in o.OutListRecursive]
            for obj in [existing.FluxBodySource]+list(existing.Tools):
                if obj and obj not in self.candidates:self.candidates.insert(0,obj)
            self.source=existing.FluxBodySource;chosen=list(existing.Tools);operation=str(existing.Operation)
        else:
            selected=[]
            for s in Gui.Selection.getSelectionEx():
                for sub in s.SubElementNames or ['']:
                    obj=self.resolve(s.ObjectName,sub)
                    if obj not in selected:selected.append(obj)
            self.source=selected[0] if selected else None;chosen=selected[1:]
        self.heading.setText(tr('結合を編集','Edit Combine') if existing else tr('結合','Combine'))
        self.operation.setCurrentIndex(self.operation.findData(operation));self.keep.setChecked(bool(existing.KeepTools) if existing else False)
        blocked=self.target.blockSignals(True);self.target.clear();self.target.addItem(tr('— 選択 —','— Select —'),None)
        for obj in self.candidates:self.target.addItem(obj.Label+' ['+obj.Name+']',obj.Name)
        self.target.setCurrentIndex(self.target.findData(self.source.Name) if self.source else 0);self.target.blockSignals(blocked)
        self.target.setEnabled(existing is None);self.pick_target.setEnabled(existing is None)
        self.populate_tools(chosen)
        self.signatures={o.Name:self.signature(o) for o in self.candidates}
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.active=True;self.panel.show();Gui.Selection.addObserver(self);self.observing=True
        Gui.Selection.clearSelection()
        self.picking='target' if not self.source else 'tools' if not chosen else None
        self.update_preview();self.position()

    @staticmethod
    def signature(obj):return obj.Shape.hashCode(),str(obj.getGlobalPlacement())

    def chosen_tools(self):
        return [self.doc.getObject(self.tools.item(i).data(QtCore.Qt.UserRole)) for i in range(self.tools.count())
                if self.tools.item(i).checkState()==QtCore.Qt.Checked]

    def populate_tools(self,chosen):
        blocked=self.tools.blockSignals(True);self.tools.clear()
        for obj in self.candidates:
            if obj==self.source:continue
            item=W.QListWidgetItem(obj.Label+' ['+obj.Name+']',self.tools);item.setToolTip(item.text())
            item.setData(QtCore.Qt.UserRole,obj.Name);item.setFlags(item.flags()|QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if obj in chosen else QtCore.Qt.Unchecked)
        self.tools.blockSignals(blocked)

    def target_changed(self):
        if not self.active:return
        chosen=self.chosen_tools();self.source=self.doc.getObject(self.target.currentData()) if self.target.currentData() else None
        self.populate_tools(chosen);self.ticket+=1;self.picking=None;self.update_preview()

    def tools_changed(self,*args):
        if not self.active:return
        self.ticket+=1;self.picking=None;self.schedule()

    def begin_pick(self,role):
        if not self.active:return
        self.ticket+=1;self.picking=None if self.picking==role else role
        Gui.Selection.clearSelection();self.update_preview()

    def addSelection(self,docname,objname,subname,point):
        if not self.active or not self.picking or docname!=self.doc.Name:return
        role=self.picking;ticket=self.ticket
        def receive():
            if not self.active or self.picking!=role or ticket!=self.ticket:return
            try:
                obj=self.resolve(objname,subname)
                if self.signature(obj)!=self.signatures.get(obj.Name):
                    raise ValueError(tr('形状が変わりました。キャンセルして開き直してください。',
                                        'Geometry changed. Cancel and reopen the operation.'))
                if role=='target':
                    self.target.setCurrentIndex(self.target.findData(obj.Name))
                    self.picking='tools' if not self.chosen_tools() else None
                else:
                    if obj==self.source:raise ValueError(tr('対象とは別のボディを工具に選択してください。','Choose a tool different from the target.'))
                    if self.source:combine.validate(self.doc,self.source,[obj],self.existing)
                    item=next(i for i in (self.tools.item(j) for j in range(self.tools.count())) if i.data(QtCore.Qt.UserRole)==obj.Name)
                    blocked=self.tools.blockSignals(True)
                    item.setCheckState(QtCore.Qt.Unchecked if item.checkState()==QtCore.Qt.Checked else QtCore.Qt.Checked)
                    self.tools.blockSignals(blocked)
                self.ticket+=1;Gui.Selection.clearSelection();self.update_preview()
            except Exception as error:
                self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error));Gui.Selection.clearSelection()
        QtCore.QTimer.singleShot(0,receive)

    def parameters(self):
        tools=self.chosen_tools()
        if not self.source:raise ValueError(tr('対象ボディを選択してください。','Select the target body.'))
        for obj in [self.source]+tools:
            if not obj or self.signature(obj)!=self.signatures.get(obj.Name):
                raise ValueError(tr('形状が変わりました。キャンセルして開き直してください。','Geometry changed. Cancel and reopen the operation.'))
        combine.validate(self.doc,self.source,tools,self.existing)
        return dict(target=self.source,tools=tools,operation=self.operation.currentData(),keep_tools=self.keep.isChecked())

    def hide_objects(self,objects):
        for obj in dict.fromkeys(objects):
            if obj and hasattr(obj,'Visibility'):
                self.hidden.append((obj,bool(obj.Visibility)));obj.Visibility=False

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        self.pick_target.setChecked(self.picking=='target');self.pick_tools.setChecked(self.picking=='tools')
        self.pick_tools.setText(tr('工具の選択を完了／プレビュー','Finish Tool Selection / Preview') if self.picking=='tools' else tr('工具を画面で選択','Pick Tool Bodies'))
        self.note.setText(tr('工具のクリックで追加・解除します。工具はまとめて扱い、交差ではその全体と対象の重なりを残します。保持をONにすると工具がブラウザーに残り、移動や編集で結果も更新します。',
                            'Click tools to add/remove them. Intersect keeps the target overlapping the union of all tools. Kept tools remain in the browser; moving or editing them updates the result.'))
        self.status.setStyleSheet('color:#245b73;')
        try:
            if self.picking:
                if self.existing:
                    self.hide_objects([self.existing]+self.existing.InListRecursive)
                    for obj in [self.source]+list(self.existing.Tools):
                        self.hidden.append((obj,bool(obj.Visibility)));obj.Visibility=True
                self.status.setText(tr('対象ボディをクリックしてください。','Click the target body.') if self.picking=='target' else
                                    tr('工具 %d 個を選択中。クリックで追加・解除し「選択を完了」を押してください。',
                                       '%d tools selected. Click to add/remove, then finish selection.')%len(self.chosen_tools()))
                return
            values=self.parameters();shape=combine.placed(combine.preview(values['target'],values['tools'],values['operation']),self.existing)
            self.show_shape(shape,'new')
            hide=[self.source]+values['tools']+([self.existing]+self.existing.InListRecursive if self.existing else [])
            self.hide_objects(hide)
            self.valid=True;self.accept_button.setEnabled(True)
            self.status.setText(tr('工具 %d 個 / 結果 %d 立体 / 体積 %.3f mm³','%d tools / %d resulting solids / Volume %.3f mm³')%
                                (len(values['tools']),len(shape.Solids),shape.Volume))
        except Exception as error:
            self.clear_preview();self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def detach(self):
        self.ticket+=1;self.picking=None
        if self.observing:Gui.Selection.removeObserver(self);self.observing=False

    def accept(self):
        if not self.active:return
        self.update_preview()
        if not self.active or not self.valid:return
        self.clear_preview()
        try:result=combine.create(self.doc,existing=self.existing,**self.parameters())
        except Exception as error:
            self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;');self.valid=False;self.accept_button.setEnabled(False);return
        self.detach();self.active=False;self.timer.stop();self.panel.hide();Gui.Selection.clearSelection();Gui.Selection.addSelection(result)
        self.ws.refresh();self.ws.main.statusBar().showMessage(tr('確定しました。履歴から対象・工具の組み合わせを確認し、操作や工具を再編集できます。',
                                                                'Confirmed. Open history to review the inputs or edit the operation and tools.'),8000)

    def cancel(self):
        if self.active:self.detach()
        super().cancel()

    def refresh(self):
        if not self.active:return
        try:
            if App.ActiveDocument!=self.doc or self.ws.current_sketch() or (self.existing and not self.existing.Document):
                self.cancel();return
            objects=([self.source] if self.source else [])+self.chosen_tools()
            if self.valid and any(not obj or self.signature(obj)!=self.signatures.get(obj.Name) for obj in objects):self.update_preview()
        except (RuntimeError,ReferenceError):self.cancel();return
        self.position()

    def eventFilter(self,widget,event):
        if (self.active and self.picking and widget in self.widgets and
                event.type() in (QtCore.QEvent.MouseButtonPress,QtCore.QEvent.MouseButtonRelease,QtCore.QEvent.MouseButtonDblClick)):
            if event.button()==QtCore.Qt.LeftButton:return False
        return super().eventFilter(widget,event)
