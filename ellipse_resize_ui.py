import FreeCAD as App
from PySide import QtWidgets as W
from i18n import tr
import ellipse_resize as core
import parameters
import ellipse_positioned

def show(ws):
    sketch = ws.current_sketch()
    if not sketch:
        raise ValueError(tr('先にスケッチを編集してください。', 'Edit the sketch first.'))
    items = core.candidates(sketch)
    initial = core.selected_candidate(sketch, items)
    ws.select_sketch_geometry()
    if not items:
        raise ValueError(tr('数値指定で作成した楕円がありません。', 'No supported dimensioned ellipses in this sketch.'))
    doc = sketch.Document
    name = sketch.Name
    expected = core.fingerprint(sketch)
    dialog = W.QDialog(ws.main)
    dialog.setObjectName('FluxEllipseResize')
    dialog.setWindowTitle(tr('楕円の横幅・縦高さを変更', 'Resize Ellipse'))
    dialog.setMinimumWidth(420)
    form = W.QFormLayout(dialog)
    choice = W.QComboBox()
    choice.setObjectName('FluxEllipseChoice')
    for entry in items:
        choice.addItem(ellipse_positioned.label(entry))
    choice.setCurrentIndex(initial)
    form.addRow(tr('対象の楕円', 'Target Ellipse'), choice)
    width = W.QDoubleSpinBox()
    height = W.QDoubleSpinBox()
    baseline = {}
    for field, key in ((width, 'FluxResizeWidth'), (height, 'FluxResizeHeight')):
        field.setObjectName(key)
        field.setDecimals(3)
        field.setRange(.002, 1000000)
        field.setSuffix(' mm')
    form.addRow(tr('横幅（全長）', 'Width (full length)'), width)
    form.addRow(tr('縦高さ（全長）', 'Height (full length)'), height)
    note = W.QLabel(tr('数値指定で作った楕円の全長を変更します。\n長短軸の入替は再作成してください。', 'Edit full lengths of a numeric ellipse.\nRecreate to swap major/minor axes.')+'\n'+linked_edit_note())
    note.setWordWrap(True)
    form.addRow(note)
    buttons = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Cancel)
    form.addRow(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    def fill():
        entry = items[choice.currentIndex()]
        for key, field in (('width', width), ('height', height)):
            field.setValue(entry[key])
            expr = parameters.expression(sketch, 'Constraints[%d]' % entry[key + '_index'])
            field.setEnabled(not bool(expr))
            field.setToolTip(expr or '')
            baseline[key] = (field.value(), entry[key])
    choice.currentIndexChanged.connect(lambda *args: fill())
    fill()
    if not dialog.exec_():
        return
    if App.ActiveDocument is not doc or doc.getObject(name) is not sketch or ws.current_sketch() is not sketch:
        raise ValueError(tr('編集中のスケッチが変更されました。', 'The edited sketch changed.'))
    entry = items[choice.currentIndex()]
    values = {key: baseline[key][1] if field.value() == baseline[key][0] else field.value() for key, field in (('width', width), ('height', height))}
    core.resize(sketch, entry['index'], values['width'], values['height'], expected=expected)
    ws.refresh()

def linked_edit_note():
    return tr('連動欄は読み取り専用です。ツールチップの式を確認し、参照元の寸法を編集してください。', 'Linked fields are read-only. Check the expression tooltip and edit the referenced dimension.')
