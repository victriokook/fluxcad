from ellipse_resize_ui import linked_edit_note
import FreeCAD as App
from PySide import QtWidgets as W
from i18n import tr
import ellipse_resize as core
import ellipse_positioned,ellipse_center

def show(ws):
    sketch=ws.current_sketch()
    if not sketch:raise ValueError(tr('先にスケッチを編集してください。','Edit the sketch first.'))
    items=core.candidates(sketch);initial=core.selected_candidate(sketch,items);ws.select_sketch_geometry()
    if not items:raise ValueError(tr('数値指定で作成した楕円がありません。','No supported dimensioned ellipses in this sketch.'))
    doc=sketch.Document;name=sketch.Name;expected=core.fingerprint(sketch)
    dialog=W.QDialog(ws.main);dialog.setObjectName('FluxEllipseCenterEdit');dialog.setWindowTitle(tr('楕円の中心位置を変更','Move Ellipse Center'));dialog.setMinimumWidth(460)
    form=W.QFormLayout(dialog);choice=W.QComboBox();choice.setObjectName('FluxCenterChoice')
    for entry in items:choice.addItem(ellipse_positioned.label(entry))
    choice.setCurrentIndex(initial)
    form.addRow(tr('対象の楕円','Target Ellipse'),choice)
    fields={};baseline={}
    for key in ('x','y'):
        field=W.QDoubleSpinBox();field.setObjectName('FluxCenter'+key.upper());field.setDecimals(3);field.setRange(-1000000,1000000);field.setSuffix(' mm');fields[key]=field;form.addRow(tr('中心','Center ')+key.upper()+tr('（スケッチ座標）',' (sketch coordinates)'),field)
    origin=W.QPushButton(tr('原点に戻す','Set to Origin'));origin.setObjectName('FluxCenterOrigin');form.addRow(origin)
    note=W.QLabel(tr('幅・高さを保ち、スケッチ座標の中心X/Yを変更します。','Move the center in sketch X/Y, keeping full widths.')+'\n'+linked_edit_note());note.setWordWrap(True);form.addRow(note)
    buttons=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel);form.addRow(buttons);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
    def fill():
        entry=items[choice.currentIndex()];state=ellipse_center.settings(sketch,entry['index'])
        for key,field in fields.items():
            field.setValue(state[key]);expr=state[key+'_expression'];field.setEnabled(not bool(expr));field.setToolTip(expr or '');baseline[key]=(field.value(),state[key])
        origin.setEnabled(not state['x_expression'] and not state['y_expression'])
    def reset():
        for field in fields.values():
            if field.isEnabled():field.setValue(0)
    origin.clicked.connect(reset);choice.currentIndexChanged.connect(lambda *args:fill());fill()
    if not dialog.exec_():return
    if App.ActiveDocument is not doc or doc.getObject(name) is not sketch or ws.current_sketch() is not sketch:raise ValueError(tr('編集中のスケッチが変更されました。','The edited sketch changed.'))
    values={key:baseline[key][1] if field.value()==baseline[key][0] else field.value() for key,field in fields.items()}
    ellipse_center.move(sketch,items[choice.currentIndex()]['index'],values['x'],values['y'],expected=expected);ws.refresh()
