from pathlib import Path
from PySide import QtWidgets as W
from i18n import tr
import FreeCADGui as Gui
import animation_presets as presets
import render_tools

def snapshot(d):
    return presets.validate(dict(format='FluxCAD-animation',version=1,mode=d.mode.currentData(),axis=d.axis.currentData(),degrees=d.degrees.value(),frames=d.frames.value(),fps=d.fps.value(),width=d.width_spin.value(),height=d.height_spin.value(),background=d.background.currentData(),translation=[d.dx.value(),d.dy.value(),d.dz.value()]))

def apply(d,payload):
    if d.exporting:raise ValueError(tr('書き出し中は設定を読めません。','Cannot load settings while exporting.'))
    p=presets.validate(payload)
    render_tools.validate_capture(d.ws,d.doc,64,64,'White','current')
    if Gui.activeDocument().activeView()!=d.view:raise ValueError(tr('3Dビューが変更されました。','The 3D view changed.'))
    if p['mode']=='part':
        from motion_tools import source_visible
        obj=d.doc.getObject(d.source.currentData() or '')
        if obj is None or not source_visible(obj) or getattr(obj,'FluxCADInternal',False) or not hasattr(obj,'Shape') or obj.Shape.isNull() or not obj.Shape.isValid() or not obj.Shape.Solids:raise ValueError(tr('表示中の有効な対象ボディを選んでください。','Select a valid visible target body.'))
    widgets=[d.mode,d.axis,d.degrees,d.frames,d.fps,d.width_spin,d.height_spin,d.background,d.dx,d.dy,d.dz,d.slider]
    d.restore()
    blocked=[w.blockSignals(True) for w in widgets]
    try:
        for w,key in ((d.mode,'mode'),(d.axis,'axis'),(d.background,'background')):w.setCurrentIndex(w.findData(p[key]))
        for w,key in ((d.degrees,'degrees'),(d.frames,'frames'),(d.fps,'fps'),(d.width_spin,'width'),(d.height_spin,'height')):w.setValue(p[key])
        for w,value in zip((d.dx,d.dy,d.dz),p['translation']):w.setValue(value)
        d.slider.setRange(0,p['frames']-1);d.slider.setValue(0)
    finally:
        for w,old in zip(widgets,blocked):w.blockSignals(old)
    part=p['mode']=='part';d.part_box.setVisible(part)
    d.base_note.setText(tr('元の形状は残り、青い表示コピーだけが動きます。','The original stays; only a blue display copy moves.') if part else d.camera_note)
    d.position_label.setText('1 / %d'%p['frames'])
    d.status.setText(tr('設定を読み込みました。再生で確認できます。','Settings loaded. Press Play to preview.'))
    fit_dialog(d)

def save(d):
    if d.exporting:
        return
    path, _ = W.QFileDialog.getSaveFileName(
        d,
        tr('アニメーション設定を保存', 'Save Animation Settings'),
        '',
        'JSON (*.json)'
    )
    if not path:
        return
    try:
        target = Path(path)
        completed_suffix = not target.suffix
        if completed_suffix:
            target = target.with_suffix('.json')
        if completed_suffix and target.exists():
            answer = W.QMessageBox.question(
                d,
                tr('上書き確認', 'Confirm Overwrite'),
                tr('既存の設定を上書きしますか？', 'Overwrite the existing settings?'),
                W.QMessageBox.Yes | W.QMessageBox.No,
                W.QMessageBox.No
            )
            if answer != W.QMessageBox.Yes:
                return
        presets.write(target, snapshot(d))
        d.status.setText(tr('保存しました：', 'Saved: ') + str(target))
    except Exception as error:
        d.status.setText(str(error))

def load(d):
    if d.exporting:return
    path,_=W.QFileDialog.getOpenFileName(d,tr('アニメーション設定を読込','Load Animation Settings'),'','JSON (*.json)')
    if not path:return
    try:apply(d,presets.read(path))
    except Exception as error:d.status.setText(str(error))

def install(d):
    row=W.QHBoxLayout()
    d.save_preset_button=W.QPushButton(tr('設定を保存…','Save Settings…'),d)
    d.load_preset_button=W.QPushButton(tr('設定を読込…','Load Settings…'),d)
    d.save_preset_button.clicked.connect(lambda:save(d));d.load_preset_button.clicked.connect(lambda:load(d))
    row.addWidget(d.save_preset_button);row.addWidget(d.load_preset_button)
    d.layout().insertLayout(d.layout().count()-2,row)
    fit_dialog(d)


def fit_dialog(d):
    d.layout().setSpacing(3)
    d.layout().setContentsMargins(6,6,6,6)
    d.adjustSize()
    available=d.screen().availableGeometry()
    parent=d.ws.main.frameGeometry()
    x=max(available.left(),min(parent.right()-d.width()-16,available.right()-d.width()-16))
    y=max(available.top()+8,min(parent.top()+100,available.bottom()-d.height()-40))
    d.move(x,y)
