"""Surface offset/thickening using the native, serializable Part::Offset."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets as W
from i18n import tr
import model
import surface_ops


def can_edit(obj):
    return obj.TypeId == 'Part::Offset' and getattr(obj,'FluxSurfaceOffset',False)


def selected_source():
    selections=Gui.Selection.getSelectionEx()
    if len(selections)!=1:
        raise ValueError(tr('サーフェス1つ、または同じボディの面を選択してください。',
                            'Select one surface, or faces of a single body.'))
    selection=selections[0];source=selection.Object;names=list(selection.SubElementNames)
    if source.Document!=App.ActiveDocument or not hasattr(source,'Shape') or source.Shape.isNull():
        raise ValueError(tr('現在のドキュメントの面を選択してください。','Select faces in the active document.'))
    if any('Invalid' in o.State for o in [source]+source.OutListRecursive):
        raise ValueError(tr('参照元の形状エラーを修正してください。','Fix the source geometry error first.'))
    if names:
        if any(not n.startswith('Face') or source.getSubObject(n).ShapeType!='Face' for n in names):
            raise ValueError(tr('辺ではなく面を選択してください。','Select faces rather than edges.'))
    elif source.Shape.Solids or not source.Shape.Faces:
        raise ValueError(tr('サーフェス全体、またはボディの面を選択してください。',
                            'Select an entire surface or individual faces of a body.'))
    return source,names


class _Cancelled(Exception):
    pass


def offset(ws, fill=False, existing=None):
    surface_ops.ready(ws)
    doc=App.ActiveDocument
    if existing:
        if existing.Document!=doc or not can_edit(existing):
            raise ValueError(tr('編集するオフセットまたは厚みを選択してください。',
                                'Select an offset or thicken feature to edit.'))
        source=existing.Source;names=[];fill=bool(existing.Fill)
    else:source,names=selected_source()
    title=tr('厚み付け','Thicken') if fill else tr('オフセット面','Offset Surface')
    dialog=W.QDialog(ws.main);dialog.setObjectName('FluxSurfaceOffset');dialog.setWindowTitle(title)
    layout=W.QFormLayout(dialog)
    note=W.QLabel(tr('正の距離は面の法線方向、負の距離はその反対です。\nプレビューで方向を確認してください。',
                    'Positive distance follows the surface normal; negative goes the other way.\nUse Preview to check the direction.'))
    note.setWordWrap(True);layout.addRow(note)
    reference=W.QLabel(tr('参照: ','Reference: ')+source.Label+(' / '+', '.join(names) if names else ''))
    reference.setWordWrap(True);layout.addRow(reference)
    distance=W.QDoubleSpinBox();distance.setObjectName('offsetDistance');distance.setDecimals(6)
    distance.setRange(-100000,100000);distance.setSuffix(' mm');distance.setValue(existing.Value if existing else 1.)
    layout.addRow(tr('厚さ（符号付き）','Thickness (signed)') if fill else tr('距離','Distance'),distance)
    join=W.QComboBox();join.setObjectName('offsetJoin')
    # OCC tangent join and self-intersection flags are not implemented; do not
    # offer controls which cannot provide the behavior their labels suggest.
    join.addItem(tr('丸める','Arc'),'Arc');join.addItem(tr('交差','Intersection'),'Intersection')
    join.setCurrentIndex(max(0,join.findData(str(existing.Join))) if existing else 0)
    layout.addRow(tr('角の接続','Corner join'),join)
    result=W.QLabel();result.setObjectName('offsetResult');result.setWordWrap(True);layout.addRow(result)
    error=W.QLabel();error.setObjectName('offsetError');error.setWordWrap(True);error.setStyleSheet('color:#b83232;');layout.addRow(error)
    buttons=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel|W.QDialogButtonBox.Apply)
    buttons.button(W.QDialogButtonBox.Apply).setText(tr('プレビュー','Preview'));layout.addRow(buttons)
    original=float(existing.Value) if existing else 1.;shown=distance.value()
    previous=[(s.Object,list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
    try:
        with model.transaction(doc,title):
            if existing:obj=existing
            else:
                # A native binder keeps selected faces and parent placements
                # associative, without a FluxCAD document proxy.
                input_shape=source
                if names:
                    input_shape=model._internal(model._profile_binder(doc,source,names,tr('面の参照','Surface reference')))
                    doc.recompute()
                obj=doc.addObject('Part::Offset','Thicken' if fill else 'SurfaceOffset')
                obj.Label=title;obj.Source=input_shape;obj.Fill=fill;obj.Mode='Skin'
                obj.addProperty('App::PropertyBool','FluxSurfaceOffset','FluxCAD');obj.FluxSurfaceOffset=True;obj.setEditorMode('FluxSurfaceOffset',2)
                obj.ViewObject.ShapeColor=(.72,.79,.85) if fill else (.80,.69,.49)
            def preview():
                try:
                    distance.interpretText();value=original if existing and distance.value()==shown else distance.value()
                    if abs(value)<1e-7:
                        raise ValueError(tr('0以外の距離を指定してください。','Enter a nonzero distance.'))
                    obj.Value=value;obj.Join=join.currentData();doc.recompute()
                    if any('Invalid' in o.State for o in obj.OutListRecursive):
                        raise ValueError(tr('参照元の形状エラーを修正してください。','Fix the source geometry error first.'))
                    for affected in [obj]+obj.InListRecursive:
                        if 'Invalid' in affected.State or (hasattr(affected,'Shape') and (affected.Shape.isNull() or not affected.Shape.isValid())):
                            raise ValueError(tr('この距離では形状を作成できません。距離や角の接続を変更してください。',
                                                'Cannot create the shape at this distance. Change the distance or corner join.'))
                    if not obj.Shape.Faces or bool(obj.Shape.Solids)!=fill:
                        raise ValueError(tr('厚み付けに必要な閉じた立体を作成できません。' if fill else 'オフセット面を作成できません。',
                                            'Cannot create a closed solid for thickening.' if fill else 'Cannot create an offset surface.'))
                    if fill:
                        if len(obj.Shape.Solids)!=1 or obj.Shape.Volume<=1e-9:
                            raise ValueError(tr('1つにつながった立体を作成してください。','The result must be one connected solid.'))
                        result.setText(tr('体積: %.3f mm³','Volume: %.3f mm³')%obj.Shape.Volume)
                    else:result.setText(tr('面積: %.3f mm²','Area: %.3f mm²')%obj.Shape.Area)
                    error.clear();return True
                except Exception as exc:error.setText(str(exc));result.clear();return False
            buttons.accepted.connect(lambda:dialog.accept() if preview() else None)
            buttons.rejected.connect(dialog.reject);buttons.button(W.QDialogButtonBox.Apply).clicked.connect(preview)
            if not source.Shape.Solids:source.Visibility=False
            obj.Visibility=True;Gui.Selection.clearSelection();preview()
            if dialog.exec_()!=W.QDialog.Accepted:raise _Cancelled()
        Gui.Selection.clearSelection();Gui.Selection.addSelection(obj)
        return obj
    except _Cancelled:
        Gui.Selection.clearSelection()
        for selected,subs in previous:
            if doc.getObject(selected.Name):
                for sub in subs or ['']:Gui.Selection.addSelection(selected,sub)
    finally:dialog.deleteLater()


def refine(ws):
    """Remove redundant splits with the native Part::Refine, retaining links."""
    surface_ops.ready(ws)
    selected=Gui.Selection.getSelectionEx()
    if not selected or any(s.SubElementNames or s.Object.Document!=App.ActiveDocument or
                           not hasattr(s.Object,'Shape') or s.Object.Shape.isNull() for s in selected):
        raise ValueError(tr('ブラウザーから形状全体を選択してください。','Select whole shapes in the browser.'))
    if any('Invalid' in o.State for s in selected for o in [s.Object]+s.Object.OutListRecursive):
        raise ValueError(tr('参照元の形状エラーを修正してください。','Fix the source geometry error first.'))
    doc=App.ActiveDocument;created=[]
    with model.transaction(doc,tr('形状を簡略化','Refine Shape')):
        for selection in selected:
            source=selection.Object
            obj=doc.addObject('Part::Refine','Refine');obj.Label=tr('簡略化','Refined')+' — '+source.Label;obj.Source=source
            doc.recompute()
            if obj.Shape.isNull() or not obj.Shape.isValid() or 'Invalid' in obj.State:
                raise ValueError(tr('この形状を簡略化できません。','Cannot refine this shape.'))
            source.Visibility=False;obj.ViewObject.ShapeColor=source.ViewObject.ShapeColor;created.append(obj)
    Gui.Selection.clearSelection()
    for obj in created:Gui.Selection.addSelection(obj)
    return created
