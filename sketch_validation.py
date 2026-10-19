"""Keep native coincidence repair and its geometry recompute in one Undo step."""
from i18n import tr
import FreeCAD as App
from PySide import QtWidgets as W
import model


def protect_coincidence_repair(ws, sketch):
    panels = ws.main.findChildren(W.QWidget, 'SketcherGui__TaskSketcherValidation')
    if not panels:
        raise ValueError(tr('スケッチ検証画面を初期化できませんでした。',
                            'Could not initialize the sketch validation panel.'))
    panel = panels[-1]
    # Narrow Japanese task docks clipped the tolerance value's leading zero.
    panel.setMinimumWidth(max(400,panel.minimumWidth()))
    for button in panel.findChildren(W.QPushButton):
        button.setToolTip(button.text())
    find = panel.findChild(W.QPushButton, 'findButton')
    fix = panel.findChild(W.QPushButton, 'fixButton')
    if not find or not fix:
        raise ValueError(tr('スケッチ検証画面の修復ボタンが見つかりません。',
                            'The sketch validation repair button is unavailable.'))
    doc, name = sketch.Document, sketch.Name
    detected = [None]
    def signature():
        obj = doc.getObject(name)
        return (obj.Shape.hashCode(), obj.GeometryCount, obj.ConstraintCount) if obj else None
    # The native Find callback is already connected, so capture its result after
    # detection. Do not repair cached candidates following a geometry edit.
    def remember():
        detected[0] = signature()
    find.clicked.connect(remember)
    if not fix.clicked.disconnect():
        fix.setEnabled(False)
        raise ValueError(tr('修復ボタンを初期化できませんでした。',
                            'Could not initialize the repair button.'))
    def repair():
        try:
            if App.ActiveDocument!=doc or doc.getObject(name) is None or ws.current_sketch():
                raise ValueError(tr('対象のスケッチで検証画面を開き直してください。',
                                    'Reopen validation for the target sketch.'))
            if detected[0] is None or detected[0]!=signature():
                fix.setEnabled(False)
                raise ValueError(tr('スケッチが変わりました。もう一度「検査」を押してください。',
                                    'The sketch changed. Run Find again before repairing.'))
            valid_dependents = [obj for obj in sketch.InListRecursive
                                if hasattr(obj,'Shape') and not obj.Shape.isNull() and obj.Shape.isValid()]
            with model.transaction(doc,tr('スケッチの一致を修復','Repair Sketch Coincidences')):
                sketch.makeMissingPointOnPointCoincident()
                # The native dialog commits before recomputing, so an Undo can
                # restore constraints yet retain the moved endpoint positions.
                # Recompute while the native document transaction is still open.
                doc.recompute()
                if sketch.solve()!=0:
                    raise ValueError(tr('拘束が成立しないため修復を取り消しました。',
                                        'The constraints could not be solved; the repair was undone.'))
                if any(obj.Shape.isNull() or not obj.Shape.isValid() or 'Invalid' in obj.State
                       for obj in valid_dependents):
                    raise ValueError(tr('後の加工を更新できないため修復を取り消しました。',
                                        'A dependent feature could not be updated; the repair was undone.'))
            ws.region_picker.clear()
            fix.setEnabled(False)
            find.click()  # Clear native markers and report any remaining candidates.
        except Exception as error:
            W.QMessageBox.warning(ws.main,tr('スケッチを検証・修復','Validate / Repair Sketch'),str(error))
    fix.clicked.connect(repair)
    fix.setToolTip(tr('検出した一致拘束を追加します。端点の変更もCtrl＋Zで元に戻せます。',
                      'Add the detected coincidences. Ctrl+Z also restores the endpoint positions.'))
