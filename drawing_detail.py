"""Validated native TechDraw section, detail and decoration commands."""
import FreeCAD as App
import FreeCADGui as Gui
from pathlib import Path
from PySide import QtWidgets as W
from i18n import tr
import drawing, model

COMMANDS={
    'section':'TechDraw_SectionView',
    'detail':'TechDraw_DetailView',
    'hatch':'TechDraw_GeometricHatch',
    'face_center':'TechDraw_FaceCenterLine',
    'edge_center':'TechDraw_2LineCenterLine',
    'circle_center':'TechDraw_ExtensionCircleCenterLines',
    'erase':'TechDraw_CosmeticEraser',
}
HATCH_TYPES=('TechDraw::DrawHatch','TechDraw::DrawGeomHatch')


def start(ws,kind):
    doc=drawing.ready(ws)
    sels=Gui.Selection.getSelectionEx()
    if len(sels)!=1 or sels[0].Object.Document.Name!=doc.Name:
        raise ValueError(tr('図面上の1つのビューを選択してください。','Select one view on a drawing sheet.'))
    obj=sels[0].Object;names=list(sels[0].SubElementNames)
    if obj.TypeId==drawing.GROUP and kind in ('section','detail'):
        obj=obj.Anchor;names=[]
    if not obj or not obj.isDerivedFrom(drawing.VIEW):
        raise ValueError(tr('図面の投影図を選択してください。3Dモデルは使用できません。',
                            'Select a projected drawing view. A 3D model cannot be used here.'))
    page=drawing.page_of(obj)
    if not page:raise ValueError(tr('図面に配置されたビューを選択してください。','Select a view placed on a drawing sheet.'))
    if kind in ('section','detail'):
        names=[]
        if not obj.Source or 'Invalid' in obj.State:
            raise ValueError(tr('元モデルを参照する有効なビューを選択してください。','Select a valid view linked to a source model.'))
    elif kind in ('hatch','face_center'):
        if not names or any(not n.startswith('Face') for n in names):
            raise ValueError(tr('図面の面内部をクリックして選択してください。','Click inside a face on the drawing to select it.'))
    else:
        if not names or any(not n.startswith('Edge') for n in names):
            raise ValueError(tr('図面上の辺を選択してください。','Select edges on the drawing.'))
        if kind=='edge_center' and len(names)!=2:
            raise ValueError(tr('同じビューの2本の辺をCtrlで選択してください。','Ctrl-select two edges in the same view.'))
        if kind=='erase' and not all(is_cosmetic(obj,n) for n in names):
            raise ValueError(tr('削除する中心線・補助線を選択してください。モデルの輪郭は削除できません。',
                                'Select cosmetic edges or centerlines. Projected model outlines cannot be removed here.'))
        if kind=='circle_center':
            edges=obj.getVisibleEdges()
            try:valid=all(hasattr(edges[int(n[4:])].Curve,'Radius') for n in names)
            except (ValueError,IndexError):valid=False
            if not valid:raise ValueError(tr('中心線を付ける円・円弧を選択してください。','Select circles or circular arcs for center marks.'))
    drawing.show(ws,page)
    # Showing a sheet can activate a different view. Replay only the validated
    # selection so the native tool targets the correct page and projection.
    Gui.Selection.clearSelection()
    for name in names or ['']:Gui.Selection.addSelection(obj,name)
    command=COMMANDS[kind]
    if command not in Gui.listCommands() or not Gui.Command.get(command).isActive():
        raise ValueError(tr('この選択では操作を開始できません。','This tool is unavailable for the current selection.'))
    if kind=='erase':
        # Native erasure needs an explicit transaction when invoked from a
        # Python ribbon action, otherwise Undo can skip the removed geometry.
        with model.transaction(doc,tr('補助線を削除','Remove Cosmetic Geometry')):
            Gui.runCommand(command)
    else:Gui.runCommand(command)
    ws.native_task_opened=bool(Gui.Control.activeDialog())
    ws.compact()


def is_cosmetic(obj,name):
    for method in ('getCosmeticEdgeBySelection','getCenterLineBySelection'):
        try:
            if getattr(obj,method)(name) is not None:return True
        except (RuntimeError,ValueError,TypeError):pass
    return False


def hatch_parent(obj):
    if obj and obj.TypeId in HATCH_TYPES:
        source=obj.Source
        if source and source[0]:return source[0]


def view_settings(ws):
    doc=drawing.ready(ws);selected=Gui.Selection.getSelection()
    if len(selected)!=1 or selected[0].Document.Name!=doc.Name or not selected[0].isDerivedFrom(drawing.VIEW):
        raise ValueError(tr('図面の投影図・断面図・詳細図を1つ選択してください。',
                            'Select one drawing view, section or detail.'))
    obj=selected[0];page=drawing.page_of(obj)
    if not page:raise ValueError(tr('用紙上のビューを選択してください。','Select a view on a sheet.'))
    d,f=drawing.dialog(ws,tr('図の配置と表示','View Placement and Display'),'FluxDrawingDisplay')
    caption=W.QLineEdit(obj.Caption);caption.setObjectName('viewCaption');f.addRow(tr('キャプション','Caption'),caption)
    x=drawing.spin(f,'displayX','X',obj.X.Value);y=drawing.spin(f,'displayY','Y',obj.Y.Value)
    width=drawing.spin(f,'displayLineWidth',tr('輪郭の線幅','Outline Width'),obj.ViewObject.LineWidth.Value,.01,5)
    background=W.QCheckBox(tr('面を白抜きで表示','Use White Faces'));background.setObjectName('displayWhite');background.setChecked(obj.ViewObject.FaceColor[:3]==(1.0,1.0,1.0));f.addRow(background)
    cut=None;pattern=None;hscale=None;rotation=None
    if hasattr(obj,'CutSurfaceDisplay'):
        cut=W.QComboBox();cut.setObjectName('cutDisplay')
        labels={'Hide':('非表示','Hidden'),'Color':('色','Color'),'SvgHatch':('画像ハッチング','Image Hatch'),
                'PatHatch':('幾何ハッチング','Geometric Hatch')}
        for value in obj.getEnumerationsOfProperty('CutSurfaceDisplay'):
            ja,en=labels.get(value,(value,value));cut.addItem(tr(ja,en),value)
        cut.setCurrentIndex(cut.findData(str(obj.CutSurfaceDisplay)));f.addRow(tr('切断面の表示','Cut-face Display'),cut)
        pattern=W.QComboBox();pattern.setObjectName('cutPattern')
        pat=Path(obj.PatIncluded) if obj.PatIncluded else Path(obj.FileGeomPattern)
        values=[]
        if pat.is_file():
            values=[line[1:].split(',',1)[0].strip() for line in pat.read_text(encoding='utf-8-sig',errors='replace').splitlines() if line.startswith('*')]
        if obj.NameGeomPattern not in values:values.insert(0,obj.NameGeomPattern)
        pattern.addItems(values);pattern.setCurrentText(obj.NameGeomPattern);f.addRow(tr('幾何パターン','Geometric Pattern'),pattern)
        hscale=drawing.spin(f,'cutScale',tr('ハッチング尺度','Hatch Scale'),obj.HatchScale,.01,1000,'')
        rotation=drawing.spin(f,'cutRotation',tr('ハッチング角度','Hatch Rotation'),obj.HatchRotation,-360,360,'°')
        def pattern_enabled():pattern.setEnabled(cut.currentData()=='PatHatch')
        cut.currentIndexChanged.connect(pattern_enabled);pattern_enabled()
    note=W.QLabel(tr('X・Yは用紙左下からのmm（投影グループ内ではグループからの相対位置）。',
                       'X/Y are mm from the sheet lower-left, or relative to a projection group.'));note.setWordWrap(True);f.addRow(note)
    baseline={field:(field.value(),original) for field,original in ((x,obj.X.Value),(y,obj.Y.Value),(width,obj.ViewObject.LineWidth.Value))}
    if cut:
        baseline.update({hscale:(hscale.value(),obj.HatchScale),rotation:(rotation.value(),obj.HatchRotation)})
    drawing.buttons(f,d)
    if d.exec_():
        with model.transaction(doc,tr('図の配置と表示','View Placement and Display')):
            obj.Caption=caption.text();obj.X=display_value(x,baseline);obj.Y=display_value(y,baseline);obj.ViewObject.LineWidth=display_value(width,baseline)
            if background.isChecked():obj.ViewObject.FaceColor=(1.0,1.0,1.0)
            elif obj.ViewObject.FaceColor[:3]==(1.0,1.0,1.0):obj.ViewObject.FaceColor=(.945,.953,.961)
            if cut:
                obj.CutSurfaceDisplay=cut.currentData();obj.NameGeomPattern=pattern.currentText();obj.HatchScale=display_value(hscale,baseline);obj.HatchRotation=display_value(rotation,baseline)
        page.requestPaint()
    d.deleteLater();drawing.show(ws,page)



def display_value(field, baseline):
    displayed, original = baseline[field]
    value = field.value()
    return original if value == displayed else value
