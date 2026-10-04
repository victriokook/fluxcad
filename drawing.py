"""Drawing workspace backed entirely by native TechDraw document objects."""
from pathlib import Path
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from i18n import tr
import model

PAGE = 'TechDraw::DrawPage'
VIEW = 'TechDraw::DrawViewPart'
GROUP = 'TechDraw::DrawProjGroup'
DIRECTIONS = [('正面','Front',(0,-1,0),(1,0,0)),
              ('上面','Top',(0,0,1),(1,0,0)),
              ('右側面','Right',(1,0,0),(0,1,0)),
              ('等角図','Isometric',(1,-1,1),(1,1,0))]
DIMENSIONS = {
    'length':'TechDraw_LengthDimension', 'horizontal':'TechDraw_HorizontalDimension',
    'vertical':'TechDraw_VerticalDimension', 'radius':'TechDraw_RadiusDimension',
    'diameter':'TechDraw_DiameterDimension', 'angle':'TechDraw_AngleDimension'}


class SceneRepair:
    """Restore native projection parenting after document Undo/Redo."""
    def __init__(self,ws):
        self.ws=ws;self.pending=set();App.addDocumentObserver(self)

    def slotUndoDocument(self,doc):self.pending.add(doc.Name)
    def slotRedoDocument(self,doc):self.pending.add(doc.Name)
    def slotDeletedDocument(self,doc):self.pending.discard(doc.Name)

    def refresh(self):
        doc=App.ActiveDocument
        if not doc or doc.Name not in self.pending:return
        if Gui.Control.activeDialog() or W.QApplication.activeModalWidget():return
        av=Gui.activeDocument().activeView()
        if not hasattr(av,'getPage'):return
        page=doc.getObject(av.getPage().Name)
        self.pending.discard(doc.Name)  # Clear before show() refreshes the workspace.
        if page and any(v.TypeId==GROUP for v in page.Views):rebuild_sheet(self.ws,page)

    def close(self):
        App.removeDocumentObserver(self);self.pending.clear()


def is_drawing(obj):
    return bool(obj and obj.TypeId.startswith('TechDraw::') and obj.TypeId!='TechDraw::DrawSVGTemplate')


def pages(doc):
    return [o for o in doc.Objects if o.TypeId==PAGE] if doc else []


def ready(ws):
    if not App.ActiveDocument:
        raise ValueError(tr('先にモデルの文書を開いてください。','Open a model document first.'))
    if ws.current_sketch() or Gui.Control.activeDialog():
        raise ValueError(tr('先に編集中の操作を完了してください。','Finish the active edit first.'))
    ws.region_picker.ticket += 1
    ws.region_picker.clear()
    return App.ActiveDocument


def page_of(obj):
    if not obj:return None
    if obj.TypeId==PAGE:return obj
    if obj.TypeId in ('TechDraw::DrawHatch','TechDraw::DrawGeomHatch'):
        return page_of(obj.Source[0]) if obj.Source and obj.Source[0] else None
    for p in pages(obj.Document):
        if any(obj.Name==v.Name or any(obj.Name==c.Name for c in getattr(v,'Views',[])) for v in p.Views):return p


def choose_page(ws):
    doc=ready(ws)
    selected={p.Name:p for o in Gui.Selection.getSelection() if o.Document==doc for p in [page_of(o)] if p}
    if len(selected)==1:return next(iter(selected.values()))
    av=Gui.activeDocument().activeView()
    if hasattr(av,'getPage'):
        p=av.getPage()
        if p and p.Document.Name==doc.Name:return doc.getObject(p.Name)
    available=pages(doc)
    if not available:raise ValueError(tr('先に「新規図面」で用紙を作成してください。','Create a sheet with New Drawing first.'))
    if len(available)==1:return available[0]
    labels=[p.Label+' ['+p.Name+']' for p in available]
    choice,ok=W.QInputDialog.getItem(ws.main,tr('図面を選択','Select Drawing'),tr('図面','Drawing'),labels,0,False)
    return available[labels.index(choice)] if ok else None


def switch(ws, drawing=True):
    if ws.current_sketch() or Gui.Control.activeDialog():
        raise ValueError(tr('先に編集中の操作を完了してください。','Finish the active edit first.'))
    if drawing:
        Gui.activateWorkbench('TechDrawWorkbench')
    else:
        if Gui.activeDocument():Gui.activateView('Gui::View3DInventor',True)
        Gui.activateWorkbench('PartWorkbench')
    set_mode(ws,drawing)
    ws.compact()


def set_mode(ws, drawing):
    """Only change ribbon state; opening a page must not change the 3D camera."""
    if getattr(ws,'drawing_mode',False)==drawing:return
    ws.drawing_mode=drawing
    if drawing:ws.design_return_tab=ws.ribbon_tabs.currentIndex()
    for key,index in ws.tab_indices.items():
        ws.ribbon_tabs.setTabVisible(index,(key=='drawing') if drawing else key not in ('drawing','sketch'))
    ws.ribbon_tabs.setCurrentIndex(ws.tab_indices['drawing'] if drawing else getattr(ws,'design_return_tab',0))
    ws.workspace_button.setText(tr('図面','Drawing') if drawing else tr('デザイン','Design'))


def show(ws,page):
    if not page or not App.ActiveDocument or page.Document.Name!=App.ActiveDocument.Name:
        raise ValueError(tr('アクティブ文書の図面を選択してください。','Select a drawing in the active document.'))
    Gui.activateWorkbench('TechDrawWorkbench')
    set_mode(ws,True)
    page.ViewObject.show()
    ws.compact()
    ws.refresh()


def rebuild_sheet(ws,page):
    """Reopen only the sheet view so native TechDraw parents new projections.

    FreeCAD 1.1's Python addProjection creates the geometry, but does not call
    the native task's regroupSubViews. Reopening the sheet runs addChildrenToPage
    and setViewParents without closing the model document or changing its camera.
    """
    widget=next((w for w in ws.main.findChildren(W.QGraphicsView)
                 if w.objectName()==page.Name+'View' and w.isVisible()),None)
    pose=(widget.transform(),widget.mapToScene(widget.viewport().rect().center())) if widget else None
    page.ViewObject.hide()
    show(ws,page)
    widget=next((w for w in ws.main.findChildren(W.QGraphicsView)
                 if w.objectName()==page.Name+'View' and w.isVisible()),None)
    if pose and widget:widget.setTransform(pose[0]);widget.centerOn(pose[1])


def dialog(ws,title,name):
    d=W.QDialog(ws.main);d.setObjectName(name);d.setWindowTitle(title);d.setMinimumWidth(370)
    f=W.QFormLayout(d);f.setFieldGrowthPolicy(W.QFormLayout.AllNonFixedFieldsGrow)
    return d,f


def spin(form,name,label,value,minimum=-100000,maximum=100000,suffix=' mm'):
    w=W.QDoubleSpinBox();w.setObjectName(name);w.setRange(minimum,maximum);w.setDecimals(6);w.setSuffix(suffix);w.setValue(value)
    form.addRow(label,w);return w


def buttons(form,d):
    bb=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel)
    bb.accepted.connect(d.accept);bb.rejected.connect(d.reject);form.addRow(bb)


def new_page(ws):
    doc=ready(ws)
    d,f=dialog(ws,tr('新規図面','New Drawing'),'FluxDrawingPage')
    name=W.QLineEdit(doc.Label);name.setObjectName('drawingTitle');f.addRow(tr('図面名','Drawing Title'),name)
    size=W.QComboBox();size.setObjectName('drawingPaper')
    for code in ('A4','A3'):size.addItem(code,code)
    f.addRow(tr('用紙（横向き）','Paper (Landscape)'),size)
    scale=spin(f,'drawingScale',tr('尺度（倍率）','Scale Factor'),1,.001,1000,'')
    projection=W.QComboBox();projection.setObjectName('drawingProjection')
    projection.addItem(tr('第三角法','Third Angle'),'Third angle');projection.addItem(tr('第一角法','First Angle'),'First angle');f.addRow(tr('投影法','Projection Method'),projection)
    buttons(f,d)
    if not d.exec_():d.deleteLater();return
    with model.transaction(doc,tr('新規図面','New Drawing')):
        p=doc.addObject(PAGE,'Drawing');p.Label=name.text().strip() or tr('図面','Drawing')
        t=doc.addObject('TechDraw::DrawSVGTemplate','DrawingTemplate')
        t.Template=str(Path(__file__).parent/'templates'/('FluxCAD-'+size.currentData()+'.svg'))
        p.Template=t;p.Scale=scale.value();p.ProjectionType=projection.currentData()
        texts=dict(t.EditableTexts);texts.update(title=p.Label,scale='%g : 1'%p.Scale,projection=projection.currentText());t.EditableTexts=texts
    d.deleteLater();show(ws,p);return p


def sheet_settings(ws,page=None):
    ready(ws);p=page or choose_page(ws)
    if not p:return
    d,f=dialog(ws,tr('用紙設定','Sheet Settings'),'FluxDrawingSheet')
    name=W.QLineEdit(p.Label);name.setObjectName('drawingTitle');f.addRow(tr('図面名','Drawing Title'),name)
    scale=spin(f,'drawingScale',tr('尺度（倍率）','Scale Factor'),p.Scale,.001,1000,'')
    projection=W.QComboBox();projection.setObjectName('drawingProjection')
    for ja,en,value in [('第三角法','Third Angle','Third angle'),('第一角法','First Angle','First angle')]:projection.addItem(tr(ja,en),value)
    projection.setCurrentIndex(projection.findData(str(p.ProjectionType)));f.addRow(tr('投影法','Projection Method'),projection)
    fields={}
    if p.Template and hasattr(p.Template,'EditableTexts'):
        for key,value in p.Template.EditableTexts.items():
            w=W.QLineEdit(value);w.setObjectName('titleblock_'+key);fields[key]=w
            label={'title':tr('表題','Title'),'scale':tr('表題欄の尺度','Title-block Scale'),
                   'projection':tr('表題欄の投影法','Title-block Projection'),'sheet':tr('シート番号','Sheet Number')}.get(key,key)
            f.addRow(label,w)
    hint=W.QLabel(tr('尺度は「用紙に従う」図に反映されます。表題欄の文字も編集できます。','Scale applies to views using Page scale. Title-block text can also be edited.'));hint.setWordWrap(True);f.addRow(hint)
    buttons(f,d)
    if d.exec_():
        with model.transaction(p.Document,tr('用紙設定','Sheet Settings')):
            p.Label=name.text().strip() or p.Label;p.Scale=scale.value();p.ProjectionType=projection.currentData()
            for v in p.Views:
                if v.TypeId==GROUP:
                    v.ProjectionType=p.ProjectionType
                    for child in v.Views:
                        if child.Name!=v.Anchor.Name:child.autoPosition()
            if fields:
                texts={k:w.text() for k,w in fields.items()}
                original=p.Template.EditableTexts
                if 'scale' in texts and texts['scale']==original['scale']:texts['scale']='%g : 1'%p.Scale
                if 'projection' in texts and texts['projection']==original['projection']:texts['projection']=projection.currentText()
                p.Template.EditableTexts=texts
    d.deleteLater();show(ws,p)


def sources(doc):
    selected=[o for o in Gui.Selection.getSelection() if o.Document==doc and hasattr(o,'Shape') and not is_drawing(o) and not o.Shape.isNull()]
    if not selected:raise ValueError(tr('ブラウザーで図面にするボディ・スケッチ・曲面を選択してください。','Select bodies, sketches or surfaces in the browser for the drawing view.'))
    if any('Invalid' in o.State for o in selected):raise ValueError(tr('選択した形状にエラーがあります。','A selected source has an error.'))
    return selected


def insert_view(ws,group=False,existing=None):
    doc=ready(ws)
    src=list(existing.Source) if existing else sources(doc)
    p=page_of(existing) if existing else choose_page(ws)
    if not p:return
    group=existing.TypeId==GROUP if existing else group
    d,f=dialog(ws,tr('三面図','Projected Views') if group else tr('ベースビュー','Base View'),'FluxDrawingView')
    summary=W.QLabel(', '.join(o.Label for o in src));summary.setWordWrap(True);f.addRow(tr('元モデル','Source'),summary)
    directions=W.QComboBox();directions.setObjectName('viewDirection')
    for ja,en,vec,x in DIRECTIONS:directions.addItem(tr(ja,en),en)
    target=existing.Anchor if group and existing else existing
    if target:
        # Preserve an arbitrary imported direction unless the user changes it.
        found=next((i for i,(_,_,v,_) in enumerate(DIRECTIONS) if App.Vector(*v).normalize().isEqual(App.Vector(target.Direction).normalize(),1e-7)),None)
        if found is None:directions.addItem(tr('現在の方向','Current Direction'),'Current');found=directions.count()-1
        directions.setCurrentIndex(found)
    original_direction=directions.currentIndex()
    f.addRow(tr('基準方向','Base Direction'),directions)
    perpage=W.QCheckBox(tr('用紙に従う','Use Page Scale'));perpage.setObjectName('viewPageScale');perpage.setChecked(not existing or str(existing.ScaleType)=='Page');f.addRow(perpage)
    scale=spin(f,'viewScale',tr('尺度（倍率）','Scale Factor'),existing.Scale if existing else p.Scale,.001,1000,'')
    scale.setEnabled(not perpage.isChecked());perpage.toggled.connect(lambda checked:scale.setEnabled(not checked))
    x=spin(f,'viewX','X',existing.X.Value if existing else p.Template.Width.Value*.43)
    y=spin(f,'viewY','Y',existing.Y.Value if existing else p.Template.Height.Value*.55)
    hidden=W.QCheckBox(tr('隠線を表示','Show Hidden Lines'));hidden.setObjectName('viewHidden');hidden.setChecked(bool(target and getattr(target,'HardHidden',False)));f.addRow(hidden)
    note=W.QLabel(tr('X・Yは用紙左下からのmm。確定後は図の枠をドラッグして配置できます。','X/Y are mm from the lower-left of the sheet. After confirming, drag the view frame to reposition.'));note.setWordWrap(True);f.addRow(note)
    buttons(f,d)
    if not d.exec_():d.deleteLater();return
    with model.transaction(doc,tr('投影図を編集','Edit Drawing View') if existing else tr('投影図を作成','Create Drawing View')):
        v=existing or doc.addObject(GROUP if group else VIEW,'ProjectionGroup' if group else 'BaseView')
        if not existing:
            v.Source=src;p.addView(v)
            if group:
                v.ProjectionType=p.ProjectionType
                for label in ('Front','Top','Right'):v.addProjection(label)
        target=v.Anchor if group else v
        if directions.currentData()!='Current' and (not existing or directions.currentIndex()!=original_direction):
            _,_,vec,xdir=DIRECTIONS[directions.currentIndex()];target.Direction=App.Vector(*vec)
            if group:target.RotationVector=App.Vector(*xdir)
            else:target.XDirection=App.Vector(*xdir)
        v.ScaleType='Page' if perpage.isChecked() else 'Custom'
        if not perpage.isChecked():v.Scale=scale.value()
        v.X=x.value();v.Y=y.value()
        for item in v.Views if group else [v]:item.HardHidden=hidden.isChecked()
        if group:
            for child in v.Views:
                if child.Name!=v.Anchor.Name:child.autoPosition()
    p.requestPaint()
    d.deleteLater()
    if group and not existing:rebuild_sheet(ws,p)
    else:show(ws,p)
    return v


def annotation(ws,existing=None):
    ready(ws);p=page_of(existing) if existing else choose_page(ws)
    if not p:return
    d,f=dialog(ws,tr('注記','Note'),'FluxDrawingNote')
    text=W.QPlainTextEdit('\n'.join(existing.Text) if existing else '');text.setObjectName('noteText');f.addRow(text)
    x=spin(f,'noteX','X',existing.X.Value if existing else p.Template.Width.Value*.25)
    y=spin(f,'noteY','Y',existing.Y.Value if existing else 35)
    font=spin(f,'noteSize',tr('文字高さ','Text Height'),existing.TextSize.Value if existing else 3.5,.5,50)
    buttons(f,d)
    if d.exec_() and text.toPlainText().strip():
        with model.transaction(p.Document,tr('注記','Note')):
            note=existing or p.Document.addObject('TechDraw::DrawViewAnnotation','Note')
            if not existing:p.addView(note)
            note.Text=text.toPlainText().splitlines();note.X=x.value();note.Y=y.value();note.TextSize=font.value()
        d.deleteLater();show(ws,p);return note
    d.deleteLater()


def dimension(ws,kind):
    doc=ready(ws);sels=Gui.Selection.getSelectionEx()
    if (not sels or any(s.Object.Document!=doc or not s.Object.isDerivedFrom(VIEW) or not s.SubElementNames or
                       any(not n.startswith(('Edge','Vertex')) for n in s.SubElementNames) for s in sels)):
        raise ValueError(tr('図面上の辺、またはCtrlで2点・2辺を選択してください。3Dモデルの辺は使えません。',
                            'Select an edge on the drawing, or Ctrl-select two vertices/edges. Use drawing geometry.'))
    targets={page_of(s.Object).Name for s in sels if page_of(s.Object)}
    if len(targets)!=1:raise ValueError(tr('同じ図面の要素を選択してください。','Select elements on the same drawing sheet.'))
    Gui.activateWorkbench('TechDrawWorkbench');set_mode(ws,True)
    Gui.runCommand(DIMENSIONS[kind]);ws.native_task_opened=bool(Gui.Control.activeDialog());ws.compact()


def edit_selected(ws):
    selected=[o for o in Gui.Selection.getSelection() if is_drawing(o)]
    if len(selected)!=1:raise ValueError(tr('図面・投影図・寸法・注記を1つ選択してください。','Select one sheet, view, dimension or note.'))
    return edit(ws,selected[0])


def edit(ws,obj):
    doc=ready(ws)
    if not obj or obj.Document.Name!=doc.Name:raise ValueError(tr('アクティブ文書の項目を選択してください。','Select an item in the active document.'))
    if obj.TypeId==PAGE:return sheet_settings(ws,obj)
    if obj.TypeId in (VIEW,GROUP):return insert_view(ws,existing=obj)
    if obj.TypeId=='TechDraw::DrawProjGroupItem':
        group=next((o for o in obj.InList if o.TypeId==GROUP),None)
        if group:return insert_view(ws,existing=group)
    if obj.TypeId=='TechDraw::DrawViewAnnotation':return annotation(ws,obj)
    p=page_of(obj)
    if p:show(ws,p)
    Gui.activeDocument().setEdit(obj.Name);ws.native_task_opened=bool(Gui.Control.activeDialog());ws.compact()


def toggle_frames(ws):
    p=choose_page(ws)
    if p:
        show(ws,p)
        # ShowFrames is a legacy, inactive property in FreeCAD 1.1. The native
        # toggle is intentionally disabled in Auto/Always modes; an explicit
        # user toggle selects Manual mode (enum value 3).
        App.ParamGet('User parameter:BaseApp/Preferences/Mod/TechDraw/View').SetInt('ViewFrameMode',3)
        Gui.runCommand('TechDraw_ToggleFrame')


def open_page(ws):
    p=choose_page(ws)
    if p:show(ws,p)


def export_page(ws,kind,path=None):
    p=choose_page(ws)
    if not p:return
    import TechDrawGui
    if path is None:
        path,_=W.QFileDialog.getSaveFileName(ws.main,tr('図面を出力','Export Drawing'),p.Label+'.'+kind,kind.upper()+' (*.'+kind+')')
    if not path:return
    path=Path(path)
    if path.suffix.lower()!='.'+kind:path=Path(str(path)+'.'+kind)
    show(ws,p);p.Document.recompute()
    # Native exporters omit the on-screen frames and editable-field markers.
    getattr(TechDrawGui,'exportPageAsPdf' if kind=='pdf' else 'exportPageAsSvg')(p,str(path))
    if not path.exists() or not path.stat().st_size:raise RuntimeError(tr('図面を出力できませんでした。','Drawing export failed.'))
    ws.main.statusBar().showMessage(tr('図面を出力しました：','Drawing exported: ')+str(path),8000)
    return path
