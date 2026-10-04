"""Native Part surfaces and a transactional editor for Surface::Extend."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from i18n import tr
import model


PART_COMMANDS = {
    'surface_extrude': ('Part_Extrude', 'PartGui__DlgExtrusion', 'chkSolid'),
    'surface_revolve': ('Part_Revolve', 'PartGui__DlgRevolution', 'checkSolid'),
    'surface_loft': ('Part_Loft', 'PartGui__TaskLoft', 'checkSolid'),
    'surface_sweep': ('Part_Sweep', 'PartGui__TaskSweep', 'checkSolid'),
}
PART_TYPES = {'Part::Extrusion': 'surface_extrude', 'Part::Revolution': 'surface_revolve',
              'Part::Loft': 'surface_loft', 'Part::Sweep': 'surface_sweep'}


def can_edit(obj):
    return obj.TypeId == 'Surface::Extend' or (
        obj.TypeId in PART_TYPES and hasattr(obj, 'Solid') and not obj.Solid)


def ready(ws):
    if not App.ActiveDocument:
        raise ValueError(tr('先にドキュメントを開いてください。', 'Open a document first.'))
    if ws.current_sketch() or Gui.Control.activeDialog():
        raise ValueError(tr('開いている編集を終了してください。', 'Finish the current edit first.'))
    ws.region_picker.ticket += 1
    ws.region_picker.clear()
    ws.region_picker.press = None


def configure_task(ws, key, profiles=()):
    # Scope widget lookup to the new native task; hidden, deferred-deletion
    # widgets from the previous task can still have the same objectName.
    _, panel_name, checkbox_name = PART_COMMANDS[key]
    ticket = ws.region_picker.ticket
    document = Gui.activeDocument()
    seeded = False
    def initialize():
        nonlocal seeded
        if ws.region_picker.ticket != ticket or Gui.activeDocument() != document or not Gui.Control.activeDialog():
            return
        for panel in ws.main.findChildren(W.QWidget, panel_name):
            if not panel.isVisible():
                continue
            checkbox = panel.findChild(W.QCheckBox, checkbox_name)
            if checkbox:
                checkbox.setChecked(False)
                checkbox.setEnabled(False)
                checkbox.setToolTip(tr('サーフェスとして作成します。', 'Create as a surface.'))
            if key in ('surface_loft','surface_sweep') and not seeded:
                available=panel.findChild(W.QTreeWidget,'availableTreeWidget')
                add=panel.findChild(W.QPushButton,'addButton')
                if available and add:
                    for name in profiles:
                        iterator=W.QTreeWidgetItemIterator(available)
                        while iterator.value():
                            item=iterator.value()
                            if item.data(0,QtCore.Qt.UserRole)==name:
                                available.clearSelection();available.setCurrentItem(item);item.setSelected(True);add.click();break
                            iterator+=1
                    seeded=True
    initialize()
    QtCore.QTimer.singleShot(0, initialize)
    ws.ribbon_tabs.setCurrentIndex(ws.tab_indices['surface'])
    ws.native_task_opened = True
    ws.compact()


def start(ws, key):
    ready(ws)
    if key == 'surface_extend':
        return extend(ws)
    for selection in Gui.Selection.getSelectionEx():
        obj = selection.Object
        if obj.Document != App.ActiveDocument or not hasattr(obj, 'Shape') or obj.Shape.isNull() or obj.Shape.Faces:
            raise ValueError(tr('スケッチまたは輪郭線を選択してください。', 'Select sketches or profile curves.'))
        if selection.SubElementNames and len(obj.Shape.Edges) > 1:
            raise ValueError(tr('ブラウザーからスケッチ／輪郭全体を選択してください。',
                                'Select the entire sketch or profile in the browser.'))
    profiles=[obj.Name for obj in Gui.Selection.getSelection()]
    Gui.activateWorkbench('PartWorkbench')
    command = PART_COMMANDS[key][0]
    if command not in Gui.listCommands() or not Gui.Command.get(command).isActive():
        raise ValueError(tr('輪郭を選択してから開始してください。', 'Select a profile before starting this tool.'))
    Gui.runCommand(command)
    configure_task(ws, key, profiles)


def edit(ws, obj):
    ready(ws)
    if obj.Document != App.ActiveDocument or not can_edit(obj):
        raise ValueError(tr('編集するサーフェスを選択してください。', 'Select the surface to edit.'))
    if obj.TypeId == 'Surface::Extend':
        return extend(ws, obj)
    return edit_parameters(ws, obj)


class _Cancelled(Exception):
    pass


def validate(obj):
    obj.Document.recompute()
    for affected in [obj] + obj.InListRecursive:
        if 'Invalid' in affected.State or (hasattr(affected,'Shape') and
                (affected.Shape.isNull() or not affected.Shape.isValid())):
            raise ValueError(tr('この設定では形状を更新できません。', 'Cannot update the shape with these settings.'))
    if not obj.Shape.Faces or obj.Shape.Solids:
        raise ValueError(tr('有効なサーフェスを作成できません。', 'Cannot create a valid surface.'))


def edit_parameters(ws, obj):
    """Part surface view providers open Transform on setEdit, not parameters."""
    dialog = W.QDialog(ws.main); dialog.setObjectName('FluxSurfaceParameters')
    title = tr('サーフェスを編集','Edit Surface')
    dialog.setWindowTitle(title + ' — ' + obj.Label)
    layout = W.QFormLayout(dialog)
    sources = [getattr(obj,p,None) for p in ('Base','Source','Sections','Spine')]
    labels = []
    for value in sources:
        values = value if isinstance(value,(list,tuple)) else [value]
        labels.extend(v.Label for v in values if hasattr(v,'Label'))
    layout.addRow(W.QLabel(tr('参照: ','References: ') + ', '.join(dict.fromkeys(labels))))
    specs = {
        'Part::Extrusion': [('LengthFwd','長さ','Length',0,1000000,' mm'),
            ('LengthRev','逆方向の長さ','Reverse length',0,1000000,' mm'),
            ('TaperAngle','テーパ角度','Taper angle',-89,89,'°'),
            ('TaperAngleRev','逆方向のテーパ角度','Reverse taper angle',-89,89,'°'),
            ('Reversed','逆方向','Reversed'),('Symmetric','対称','Symmetric')],
        'Part::Revolution': [('Angle','角度','Angle',.001,360,'°'),('Symmetric','対称','Symmetric')],
        'Part::Loft': [('Ruled','線織面','Ruled surface'),('Closed','閉じる','Closed')],
        'Part::Sweep': [('Frenet','フレネ','Frenet')],
    }
    fields = {}; initial = {}; displayed = {}
    for prop,jp,en,*numeric in specs[obj.TypeId]:
        if prop not in obj.PropertiesList:continue
        value = getattr(obj,prop)
        if numeric:
            field = W.QDoubleSpinBox(); field.setDecimals(6); field.setRange(numeric[0],numeric[1]); field.setSuffix(numeric[2])
            value = float(value.Value if hasattr(value,'Value') else value)
            field.setValue(value); initial[prop]=value; displayed[prop]=field.value()
        else:
            field = W.QCheckBox(); field.setChecked(value)
        field.setObjectName(prop);fields[prop]=field;layout.addRow(tr(jp,en),field)
    # A revolution axis is defined in document coordinates by a point and vector.
    vectors = {}
    if obj.TypeId == 'Part::Revolution':
        for prop,jp,en in [('Base','軸の位置','Axis position'),('Axis','軸の方向','Axis direction')]:
            value = getattr(obj,prop); vectors[prop] = []
            for index,axis in enumerate('XYZ'):
                field=W.QDoubleSpinBox();field.setDecimals(6);field.setRange(-1000000,1000000)
                field.setObjectName(prop+axis);field.setValue(value[index]);vectors[prop].append((field,value[index],field.value()))
                if prop=='Base':field.setSuffix(' mm')
                layout.addRow(tr(jp,en)+' '+axis,field)
    error=W.QLabel();error.setWordWrap(True);error.setObjectName('surfaceParameterError');error.setStyleSheet('color:#b83232;');layout.addRow(error)
    buttons=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel|W.QDialogButtonBox.Apply)
    buttons.button(W.QDialogButtonBox.Apply).setText(tr('プレビュー','Preview'));layout.addRow(buttons)
    try:
        with model.transaction(obj.Document,title):
            def preview():
                try:
                    for prop,field in fields.items():
                        if isinstance(field,W.QCheckBox):setattr(obj,prop,field.isChecked())
                        else:
                            field.interpretText()
                            setattr(obj,prop,initial[prop] if field.value()==displayed[prop] else field.value())
                    for prop,components in vectors.items():
                        values=[]
                        for field,original,shown in components:
                            field.interpretText();values.append(original if field.value()==shown else field.value())
                        vector=App.Vector(*values)
                        if prop=='Axis' and vector.Length<1e-9:
                            raise ValueError(tr('回転軸の方向を指定してください。','Specify a nonzero revolution axis.'))
                        setattr(obj,prop,vector)
                    # Native legacy extrusions fall back to Dir when both
                    # lengths are zero. In the numeric editor zero means zero.
                    if obj.TypeId=='Part::Extrusion' and float(obj.LengthFwd.Value)+float(obj.LengthRev.Value)<1e-9:
                        raise ValueError(tr('押し出しの長さを0より大きくしてください。','Enter an extrusion length greater than zero.'))
                    validate(obj);error.clear();return True
                except Exception as exc:error.setText(str(exc));return False
            buttons.accepted.connect(lambda:dialog.accept() if preview() else None)
            buttons.rejected.connect(dialog.reject);buttons.button(W.QDialogButtonBox.Apply).clicked.connect(preview)
            if dialog.exec_()!=W.QDialog.Accepted:raise _Cancelled()
    except _Cancelled:pass
    finally:dialog.deleteLater()


def extend(ws, existing=None):
    """Native extension fractions refer to the source face's U/V parameter span."""
    doc = App.ActiveDocument
    if existing:
        source, names = existing.Face
    else:
        selections = Gui.Selection.getSelectionEx()
        if len(selections) != 1:
            raise ValueError(tr('延長する面を1つ選択してください。', 'Select one face to extend.'))
        selection = selections[0]
        source, names = selection.Object, list(selection.SubElementNames)
        if source.Document != doc or not hasattr(source, 'Shape'):
            raise ValueError(tr('現在のドキュメントの面を選択してください。', 'Select a face in the active document.'))
        if not names and len(source.Shape.Faces) == 1:
            names = ['Face1']
        if len(names) != 1 or not names[0].startswith('Face') or source.getSubObject(names[0]).ShapeType != 'Face':
            raise ValueError(tr('延長する面を1つ選択してください。', 'Select one face to extend.'))
    Gui.activateWorkbench('SurfaceWorkbench')
    ws.ribbon_tabs.setCurrentIndex(ws.tab_indices['surface'])
    ws.compact()
    dialog = W.QDialog(ws.main)
    dialog.setObjectName('FluxSurfaceExtend')
    title = tr('面を延長', 'Extend Face')
    dialog.setWindowTitle(title)
    layout = W.QFormLayout(dialog)
    help_text = W.QLabel(tr('面のU・V方向の範囲に対する延長率です。\nU・Vは面固有の方向で、XYZ方向とは異なります。\n曲面のパラメーター範囲を延長します。距離指定ではありません。',
                          'Extension as a percentage of the face’s U/V range.\nU/V are surface directions, separate from X/Y/Z.\nThis extends the parameter range, not a distance in mm.'))
    help_text.setWordWrap(True)
    layout.addRow(help_text)
    fields = {}
    for prop, label in [('ExtendUNeg','U −'), ('ExtendUPos','U +'), ('ExtendVNeg','V −'), ('ExtendVPos','V +')]:
        field = W.QDoubleSpinBox()
        field.setObjectName(prop); field.setDecimals(4); field.setRange(0,1000); field.setSuffix(' %')
        field.setValue(float(getattr(existing, 'Flux'+prop, getattr(existing,prop))) * 100 if existing else 5)
        layout.addRow(label, field); fields[prop] = field
    error = W.QLabel(); error.setObjectName('extensionError'); error.setWordWrap(True)
    error.setStyleSheet('color:#b83232;'); layout.addRow(error)
    buttons = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Cancel | W.QDialogButtonBox.Apply)
    buttons.button(W.QDialogButtonBox.Apply).setText(tr('プレビュー', 'Preview'))
    layout.addRow(buttons)
    previous_selection = [(s.Object,list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
    try:
        with model.transaction(doc, title):
            obj = existing or doc.addObject('Surface::Extend', 'SurfaceExtend')
            if not existing:
                obj.Label = tr('延長サーフェス','Extended Surface')
                obj.Face = (source, names)
                obj.ViewObject.ShapeColor = (0.80,0.69,0.49)
            initial = {p:float(getattr(obj,'Flux'+p,getattr(obj,p))) for p in fields}
            displayed = {p:f.value() for p,f in fields.items()}
            def preview():
                try:
                    obj.ExtendUSymetric = False; obj.ExtendVSymetric = False
                    for prop, field in fields.items():
                        field.interpretText()
                        value=initial[prop] if existing and field.value()==displayed[prop] else field.value()/100.
                        # FreeCAD 1.1 restores the extension values before the
                        # symmetry flags. Its default symmetric callback can
                        # overwrite a saved asymmetric negative value. Native
                        # expressions reapply independent stored ratios, even
                        # when reopened/recomputed without FluxCAD installed.
                        parameter='Flux'+prop
                        if parameter not in obj.PropertiesList:
                            obj.addProperty('App::PropertyFloat',parameter,'Extension ratios',
                                            'Independent U/V extension fraction')
                        setattr(obj,parameter,value)
                        obj.setExpression(prop,parameter)
                    validate(obj)
                    error.clear()
                    return True
                except Exception as exc:
                    error.setText(str(exc))
                    return False
            buttons.accepted.connect(lambda: dialog.accept() if preview() else None)
            buttons.rejected.connect(dialog.reject)
            buttons.button(W.QDialogButtonBox.Apply).clicked.connect(preview)
            if not source.Shape.Solids:
                source.Visibility = False
            obj.Visibility = True
            preview()
            Gui.Selection.clearSelection()
            if dialog.exec_() != W.QDialog.Accepted:
                raise _Cancelled()
        Gui.Selection.clearSelection(); Gui.Selection.addSelection(obj)
        return obj
    except _Cancelled:
        Gui.Selection.clearSelection()
        for source_obj, subs in previous_selection:
            if doc.getObject(source_obj.Name):
                for sub in subs or ['']:Gui.Selection.addSelection(source_obj, sub)
    finally:
        dialog.deleteLater()
