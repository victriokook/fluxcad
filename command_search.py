"""A compact, context-aware S-key command palette."""
from i18n import tr
from PySide import QtCore,QtGui,QtWidgets as W


class CommandSearch(W.QDialog):
    def __init__(self,ws):
        super().__init__(ws.main,QtCore.Qt.Popup)
        self.ws=ws;self.setObjectName('FluxCommandSearch')
        self.setStyleSheet('QDialog#FluxCommandSearch {background:#f5f5f5;border:1px solid #bac2c9;font:12px "Yu Gothic UI";} QListWidget {background:white;border:1px solid #d3d8dc;} QListWidget::item {padding:6px;}')
        self.resize(390,340)
        layout=W.QVBoxLayout(self)
        layout.addWidget(W.QLabel(tr('コマンドを検索')))
        self.query=W.QLineEdit();self.query.setPlaceholderText(tr('名前で検索  —  Enterで実行 / Escで閉じる'))
        self.results=W.QListWidget()
        layout.addWidget(self.query);layout.addWidget(self.results)
        self.query.textChanged.connect(self.update_results)
        self.query.returnPressed.connect(self.run_selected)
        self.results.itemActivated.connect(self.run_selected)
        self.query.installEventFilter(self)

    def update_results(self):
        query=self.query.text().casefold().strip();self.results.clear()
        sketch=self.ws.current_sketch() is not None
        for key,action in self.ws.ribbon_actions.items():
            if key=='search' or not action.isEnabled():continue
            if sketch and key in self.ws.solid_action_keys:continue
            label=action.text();path=action.property('FluxMenuPath') or ''
            if query and query not in (label+' '+path).casefold():continue
            item=W.QListWidgetItem(action.icon(),label+('    '+path if path else ''),self.results)
            item.setData(QtCore.Qt.UserRole,key)
        if self.results.count():self.results.setCurrentRow(0)

    def run_selected(self,*args):
        item=self.results.currentItem()
        if not item:return
        action=self.ws.ribbon_actions[item.data(QtCore.Qt.UserRole)]
        self.accept()
        if action.isEnabled():action.trigger()

    def eventFilter(self,widget,event):
        if event.type()==QtCore.QEvent.KeyPress and event.key() in (QtCore.Qt.Key_Up,QtCore.Qt.Key_Down):
            step=1 if event.key()==QtCore.Qt.Key_Down else -1
            self.results.setCurrentRow(max(0,min(self.results.count()-1,self.results.currentRow()+step)))
            return True
        return super().eventFilter(widget,event)


def show(ws):
    dialog=getattr(ws,'search_dialog',None)
    if dialog is None:
        dialog=CommandSearch(ws);ws.search_dialog=dialog
    dialog.query.clear();dialog.update_results()
    area=ws.main.geometry();point=QtGui.QCursor.pos()
    screen=W.QApplication.screenAt(point) or W.QApplication.primaryScreen()
    bounds=screen.availableGeometry()
    if not area.contains(point):point=ws.main.mapToGlobal(ws.main.rect().center())
    dialog.move(max(bounds.left(),min(point.x(),bounds.right()-dialog.width())),
                max(bounds.top(),min(point.y(),bounds.bottom()-dialog.height())))
    dialog.show();dialog.query.setFocus()
