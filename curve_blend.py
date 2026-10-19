"""Native, associative Surface blend curves with editable endpoint controls."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets as W
from i18n import tr
import model, surface_ops

TYPE='Surface::FeatureBlendCurve'


def can_edit(obj):return obj.TypeId==TYPE


def edge(reference):
    source,names=reference
    if not source or len(names)!=1 or not names[0].startswith('Edge') or 'Invalid' in source.State:
        raise ValueError(tr('参照元の辺を修復してください。','Repair the referenced source edge first.'))
    shape=source.getSubObject(names[0])
    if shape is None or shape.isNull() or shape.ShapeType!='Edge' or not shape.isValid() or shape.Length<1e-8:
        raise ValueError(tr('有効な辺を選択してください。','Select a valid edge.'))
    return shape


def selected_edges(doc):
    result=[]
    for s in Gui.Selection.getSelectionEx():
        obj=s.Object
        if obj.Document!=doc or not hasattr(obj,'Shape'):
            raise ValueError(tr('現在の文書の辺を2本選択してください。','Select two edges in the active document.'))
        names=list(s.SubElementNames)
        if not names and len(obj.Shape.Edges)==1 and not obj.Shape.Faces:names=['Edge1']
        if not names:raise ValueError(tr('辺をCtrlで個別に選択してください。','Ctrl-select individual edges.'))
        for name in names:
            reference=(obj,[name]);edge(reference)
            if any(obj==a and name==n[0] for a,n in result):raise ValueError(tr('異なる辺を2本選択してください。','Select two distinct edges.'))
            result.append(reference)
    if len(result)!=2:raise ValueError(tr('接続する辺をCtrlで2本選択してください。','Ctrl-select the two edges to connect.'))
    return result


def nearest_ends(references):
    a,b=(edge(r) for r in references)
    choices=[((a.valueAt(u)-b.valueAt(v)).Length,i,j)
             for i,u in enumerate((a.FirstParameter,a.LastParameter))
             for j,v in enumerate((b.FirstParameter,b.LastParameter))]
    return min(choices)[1:]


def description(reference):
    obj,names=reference
    if getattr(obj,'FluxCADInternal',False) and hasattr(obj,'Support') and obj.Support:
        source,paths=obj.Support[0]
        return source.Label+' / '+', '.join(paths)
    return obj.Label+' / '+', '.join(names)


def validate(obj):
    doc=obj.Document;doc.recompute()
    references=[obj.StartEdge,obj.EndEdge]
    for r in references:edge(r)
    a,b=(edge(r) for r in references)
    p=a.valueAt(a.FirstParameter+(a.LastParameter-a.FirstParameter)*obj.StartParameter)
    q=b.valueAt(b.FirstParameter+(b.LastParameter-b.FirstParameter)*obj.EndParameter)
    if (p-q).Length<1e-7:
        raise ValueError(tr('接続位置が同じです。離れた2点を指定してください。','The connection points coincide. Choose two separated points.'))
    for affected in [obj]+obj.InListRecursive:
        if 'Invalid' in affected.State or (hasattr(affected,'Shape') and (affected.Shape.isNull() or not affected.Shape.isValid())):
            raise ValueError(tr('この設定では接続曲線を作成できません。','Cannot create a valid blend curve with these settings.'))
    if len(obj.Shape.Edges)!=1 or obj.Shape.Faces or obj.Shape.Length<1e-7:
        raise ValueError(tr('有効な1本の接続曲線を作成できません。','Cannot create a valid single connecting curve.'))


def edit(ws,existing=None):
    surface_ops.ready(ws);doc=App.ActiveDocument
    if existing and (existing.Document!=doc or not can_edit(existing)):
        raise ValueError(tr('編集するブレンド曲線を選択してください。','Select the blend curve to edit.'))
    references=[existing.StartEdge,existing.EndEdge] if existing else selected_edges(doc)
    for r in references:edge(r)
    Gui.activateWorkbench('SurfaceWorkbench');ws.ribbon_tabs.setCurrentIndex(ws.tab_indices['surface']);ws.compact()
    dialog=W.QDialog(ws.main);dialog.setObjectName('FluxBlendCurve');dialog.setMinimumWidth(400)
    title=tr('ブレンド曲線','Blend Curve');dialog.setWindowTitle(title)
    layout=W.QFormLayout(dialog)
    help=W.QLabel(tr('選択した辺の間に1本の曲線を追加します。元の辺は残ります。\n位置は辺のパラメーター範囲の割合（0%・100%が端点）です。',
                    'Add a curve between the selected edges; source edges remain.\nPosition is a fraction of the edge parameter range (0% and 100% are endpoints).'))
    help.setWordWrap(True);layout.addRow(help)
    controls={}
    for side,ja,en,reference in zip(('Start','End'),('開始側','終了側'),('Start','End'),references):
        heading=W.QLabel(tr(ja,en)+' — '+description(reference));heading.setWordWrap(True);layout.addRow(heading)
        pos=W.QDoubleSpinBox();pos.setObjectName(side+'Position');pos.setRange(0,100);pos.setDecimals(6);pos.setSuffix(' %')
        layout.addRow(tr('接続位置','Connection Position'),pos)
        mode=W.QComboBox();mode.setObjectName(side+'Continuity')
        for value,jp,english in [(0,'G0：位置','G0: Position'),(1,'G1：接線','G1: Tangent'),(2,'G2：曲率','G2: Curvature')]:mode.addItem(tr(jp,english),value)
        layout.addRow(tr('連続性','Continuity'),mode)
        size=W.QDoubleSpinBox();size.setObjectName(side+'Size');size.setRange(.001,1000);size.setDecimals(6)
        layout.addRow(tr('接線の強さ','Tangent Strength'),size)
        reverse=W.QCheckBox(tr('接線方向を反転','Reverse Tangent'));reverse.setObjectName(side+'Reverse');layout.addRow(reverse)
        def enabled(index,m=mode,s=size,r=reverse):s.setEnabled(m.currentData()!=0);r.setEnabled(m.currentData()!=0)
        mode.currentIndexChanged.connect(enabled)
        controls[side]=(pos,mode,size,reverse)
    message=W.QLabel();message.setObjectName('blendError');message.setWordWrap(True);message.setStyleSheet('color:#b83232');layout.addRow(message)
    result=W.QLabel();result.setObjectName('blendResult');layout.addRow(result)
    buttons=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel|W.QDialogButtonBox.Apply)
    buttons.button(W.QDialogButtonBox.Apply).setText(tr('プレビュー','Preview'));layout.addRow(buttons)
    old_selection=[(s.Object,list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
    try:
        with model.transaction(doc,title):
            obj=existing
            if not existing:
                links=[]
                for source,names in references:
                    helper=model._internal(model._profile_binder(doc,source,names,tr('ブレンド参照','Blend reference')))
                    helper.MakeFace=False;links.append((helper,['Edge1']))
                doc.recompute()
                start,end=nearest_ends(links)
                obj=doc.addObject(TYPE,'BlendCurve')
                obj.StartEdge=links[0];obj.EndEdge=links[1];obj.StartParameter=start;obj.EndParameter=end
                obj.StartSize=1 if start==1 else -1;obj.EndSize=1 if end==0 else -1
                obj.Label=title;obj.ViewObject.LineColor=(.10,.55,.75);obj.ViewObject.LineWidth=3
            initial={};shown={}
            for side,(pos,mode,size,reverse) in controls.items():
                initial[side]=(float(getattr(obj,side+'Parameter')),float(getattr(obj,side+'Size')))
                pos.setValue(initial[side][0]*100);size.setValue(abs(initial[side][1]));reverse.setChecked(initial[side][1]<0)
                mode.setCurrentIndex(mode.findData(getattr(obj,side+'Continuity')))
                size.setEnabled(mode.currentData()!=0);reverse.setEnabled(mode.currentData()!=0)
                shown[side]=(pos.value(),size.value(),reverse.isChecked())
            def preview():
                try:
                    for side,(pos,mode,size,reverse) in controls.items():
                        pos.interpretText();size.interpretText()
                        parameter=initial[side][0] if pos.value()==shown[side][0] else pos.value()/100
                        weight=initial[side][1] if (size.value(),reverse.isChecked())==shown[side][1:] else size.value()*(-1 if reverse.isChecked() else 1)
                        if mode.currentData()!=0 and abs(weight)<1e-9:raise ValueError(tr('接線の強さを0より大きくしてください。','Enter a tangent strength greater than zero.'))
                        setattr(obj,side+'Parameter',parameter);setattr(obj,side+'Continuity',mode.currentData());setattr(obj,side+'Size',weight)
                    validate(obj);message.clear();result.setText(tr('曲線の長さ：','Curve length: ')+'%.6g mm'%obj.Shape.Length);return True
                except Exception as exc:message.setText(str(exc));result.clear();return False
            buttons.accepted.connect(lambda:dialog.accept() if preview() else None)
            buttons.rejected.connect(dialog.reject);buttons.button(W.QDialogButtonBox.Apply).clicked.connect(preview)
            obj.Visibility=True;preview();Gui.Selection.clearSelection()
            if dialog.exec_()!=W.QDialog.Accepted:raise surface_ops._Cancelled()
        Gui.Selection.clearSelection();Gui.Selection.addSelection(obj);return obj
    except surface_ops._Cancelled:
        Gui.Selection.clearSelection()
        for source,names in old_selection:
            if doc.getObject(source.Name):
                for name in names or ['']:Gui.Selection.addSelection(source,name)
    finally:dialog.deleteLater()
