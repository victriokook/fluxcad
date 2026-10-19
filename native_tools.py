"""Validated entry points to native FreeCAD surface, inspection and display tools."""
import FreeCAD as App
import FreeCADGui as Gui
from i18n import tr


COMMANDS = {
    'native_measure': 'Std_Measure',
    'check_geometry': 'Part_CheckGeometry',
    'solid_scale': 'Part_Scale',
    'appearance': 'Std_SetAppearance',
    'surface_patch': 'Surface_Filling',
    'surface_boundary': 'Surface_GeomFillSurface',
    'surface_sections': 'Surface_Sections',
    'cross_sections': 'Part_CrossSections',
    'section_analysis': 'Std_ToggleClipPlane',
}
SURFACE_TYPES=('Surface::Filling','Surface::GeomFillSurface','Surface::Sections')


def can_edit_surface(obj):
    import surface_ops, surface_finish, curve_blend
    return obj.TypeId in SURFACE_TYPES or surface_ops.can_edit(obj) or surface_finish.can_edit(obj) or curve_blend.can_edit(obj)


def start(ws, key):
    if not App.ActiveDocument:
        raise ValueError(tr('先にドキュメントを開いてください。', 'Open a document first.'))
    if ws.current_sketch():
        raise ValueError(tr('先にスケッチの編集を終了してください。', 'Finish editing the sketch first.'))
    if Gui.Control.activeDialog():
        raise ValueError(tr('開いているタスクを確定または閉じてから実行してください。',
                            'Finish or close the current task before starting another tool.'))
    selected = Gui.Selection.getSelection()
    if key in ('solid_scale', 'check_geometry', 'cross_sections'):
        if not selected or any(not hasattr(o, 'Shape') or o.Shape.isNull() for o in selected):
            raise ValueError(tr('ボディまたは形状を選択してください。メッシュにはメッシュ用の操作を使います。',
                                'Select a body or shape. Use the mesh tools for meshes.'))
        if any(o.Document != App.ActiveDocument for o in selected):
            raise ValueError(tr('現在のドキュメントの形状を選択してください。',
                                'Select shapes in the active document.'))
    if key == 'appearance' and not selected:
        raise ValueError(tr('外観を変更するボディまたはメッシュを選択してください。',
                            'Select the bodies or meshes whose appearance you want to change.'))
    boundary=[]
    if key.startswith('surface_'):
        for selection in Gui.Selection.getSelectionEx():
            obj=selection.Object
            if obj.Document!=App.ActiveDocument or not hasattr(obj,'Shape'):
                raise ValueError(tr('現在のドキュメントの辺またはスケッチを選択してください。',
                                    'Select edges or sketches in the active document.'))
            if not selection.SubElementNames and (obj.Shape.Solids or key=='surface_sections' and len(obj.Shape.Edges)>1):
                raise ValueError(tr('使用する辺をCtrlで個別に選択してください。断面曲線は1断面につき1本の辺です。',
                                    'Ctrl-select the individual edges to use. Surface sections use one edge per section.'))
            names=selection.SubElementNames or tuple('Edge%d'%(i+1) for i in range(len(obj.Shape.Edges)))
            for name in names:
                if not name.startswith('Edge'):
                    raise ValueError(tr('曲面の作成には辺を選択してください。','Select edges to create a surface.'))
                boundary.append((obj,name))
        if key=='surface_boundary' and len(boundary)>4:
            raise ValueError(tr('境界サーフェスは2〜4本の辺で作成します。','A Boundary Surface uses 2 to 4 edges.'))
        Gui.activateWorkbench('SurfaceWorkbench')
    elif key.startswith('solid_') or key in ('check_geometry','cross_sections'):
        Gui.activateWorkbench('PartWorkbench')
    command = COMMANDS[key]
    if command not in Gui.listCommands() or not Gui.Command.get(command).isActive():
        raise ValueError(tr('この選択では操作を開始できません。選択を確認してください。',
                            'This tool is unavailable for the current selection. Check the selection.'))
    ws.region_picker.ticket+=1;ws.region_picker.clear();ws.region_picker.press=None
    Gui.runCommand(command)
    # Native task controls remain accessible; only native toolbars are compacted.
    ws.native_task_opened = True
    ws.compact()
    if key.startswith('surface_'):
        ws.ribbon_tabs.setCurrentIndex(ws.tab_indices['surface'])
        # Native Surface tasks clear preselection on entry. Feed it through the
        # native selection observer once its widgets have been initialized.
        from PySide import QtCore,QtWidgets as W
        gd=Gui.activeDocument();editing=getattr(gd.getInEdit(),'Object',None)
        def seed():
            if not boundary or editing is None or Gui.activeDocument()!=gd or getattr(gd.getInEdit(),'Object',None)!=editing:return
            Gui.Selection.clearSelection()
            for obj,name in boundary:
                Gui.Selection.addSelection(obj,name)
                if key=='surface_patch':
                    accept=ws.main.findChild(W.QPushButton,'buttonAccept')
                    if accept and accept.isVisible() and accept.isEnabled():accept.click()
        QtCore.QTimer.singleShot(0,seed)


def edit_surface(ws, obj):
    import surface_ops, surface_finish, curve_blend
    if curve_blend.can_edit(obj):return curve_blend.edit(ws,existing=obj)
    if surface_finish.can_edit(obj):
        return surface_finish.offset(ws,existing=obj)
    if surface_ops.can_edit(obj):
        return surface_ops.edit(ws,obj)
    if ws.current_sketch() or Gui.Control.activeDialog():
        raise ValueError(tr('開いている編集を終了してください。','Finish the current edit first.'))
    if obj.Document!=App.ActiveDocument or obj.TypeId not in SURFACE_TYPES:
        raise ValueError(tr('編集するサーフェスを選択してください。','Select the surface to edit.'))
    Gui.activateWorkbench('SurfaceWorkbench')
    ws.region_picker.ticket+=1;ws.region_picker.clear();ws.region_picker.press=None
    if not Gui.activeDocument().setEdit(obj.Name):
        raise ValueError(tr('サーフェスの編集を開始できません。','Cannot start editing this surface.'))
    ws.native_task_opened=True
    ws.ribbon_tabs.setCurrentIndex(ws.tab_indices['surface']);ws.compact()


def edit_scale(ws, obj):
    """Part::Scale has no native factor editor (default setEdit moves it)."""
    from PySide import QtWidgets as W
    import model
    if ws.current_sketch() or Gui.Control.activeDialog():
        raise ValueError(tr('開いている編集を終了してください。', 'Finish the current edit first.'))
    if obj.Document != App.ActiveDocument or obj.TypeId != 'Part::Scale':
        raise ValueError(tr('尺度変更の履歴を選択してください。', 'Select a Scale feature.'))
    dialog = W.QDialog(ws.main)
    dialog.setObjectName('FluxScaleEdit')
    dialog.setWindowTitle(tr('尺度を編集', 'Edit Scale'))
    layout = W.QFormLayout(dialog)
    uniform = W.QCheckBox(tr('均一に拡大・縮小', 'Uniform scaling'))
    uniform.setObjectName('uniform');uniform.setChecked(obj.Uniform);layout.addRow(uniform)
    fields = {};initial = {};displayed = {}
    for prop,label in [('UniformScale',tr('倍率','Factor')),('XScale','X'),('YScale','Y'),('ZScale','Z')]:
        field = W.QDoubleSpinBox()
        field.setObjectName(prop);field.setDecimals(6);field.setRange(.000001,1000000)
        initial[prop]=getattr(obj,prop)
        field.setValue(initial[prop]);displayed[prop]=field.value();layout.addRow(label,field);fields[prop]=field
    def enabled():
        for prop,field in fields.items():field.setEnabled((prop=='UniformScale')==uniform.isChecked())
    uniform.toggled.connect(enabled);enabled()
    buttons=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addRow(buttons)
    try:
        if dialog.exec_()!=W.QDialog.Accepted:return
        with model.transaction(obj.Document,tr('尺度を編集','Edit Scale')):
            obj.Uniform=uniform.isChecked()
            for prop,field in fields.items():
                field.interpretText()
                setattr(obj,prop,initial[prop] if field.value()==displayed[prop] else field.value())
            obj.Document.recompute()
            for affected in [obj]+obj.InListRecursive:
                if hasattr(affected,'Shape') and (affected.Shape.isNull() or not affected.Shape.isValid()):
                    raise ValueError(tr('この倍率では形状を更新できません。', 'Cannot update the shape with these factors.'))
    finally:dialog.deleteLater()


def measurement_details(ws, obj):
    from PySide import QtWidgets as W
    labels={'Distance':tr('距離','Distance'),'DistanceX':tr('X方向の距離','Distance X'),
            'DistanceY':tr('Y方向の距離','Distance Y'),'DistanceZ':tr('Z方向の距離','Distance Z'),
            'Length':tr('長さ','Length'),'Angle':tr('角度','Angle'),'Area':tr('面積','Area'),
            'Radius':tr('半径','Radius'),'Position1':tr('点1','Point 1'),'Position2':tr('点2','Point 2'),
            'Position':tr('位置','Position'),'CenterOfMass':tr('重心','Center of Mass')}
    rows=[]
    for prop in obj.PropertiesList:
        kind=obj.getTypeIdOfProperty(prop)
        if kind in ('App::PropertyLength','App::PropertyDistance','App::PropertyAngle','App::PropertyArea','App::PropertyVolume','App::PropertyVector'):
            rows.append('%s: %s'%(labels.get(prop,prop),getattr(obj,prop)))
    W.QMessageBox.information(ws.main,obj.Label,'\n'.join(rows) or obj.Label)


def delete_measurement(obj):
    import model
    if not obj.TypeId.startswith('Measure::'):
        raise ValueError(tr('計測を選択してください。','Select a measurement.'))
    # Saved native measurements belong to a display group, not a dependent feature.
    dependents=[parent for parent in obj.InList if not (
        parent.TypeId=='App::DocumentObjectGroup' and
        parent.ViewObject.TypeId=='MeasureGui::ViewProviderMeasureGroup' and obj in parent.Group)]
    if dependents:
        raise ValueError(tr('この計測は他の項目から参照されています。','Other objects reference this measurement.'))
    with model.transaction(obj.Document,tr('計測を削除','Delete Measurement')):
        obj.Document.removeObject(obj.Name)
