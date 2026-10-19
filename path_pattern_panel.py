"""Preview and re-edit linked body patterns along a sketch path."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets as W
from pivy import coin
from floating_panel import FloatingPanel
from i18n import tr
import browser
import model_path_pattern as pattern


class PathPatternPanel(FloatingPanel):
    layout_key='PathPatternPanel'
    preferred_height=520

    def __init__(self,ws):
        super().__init__(ws)
        policy=self.status.sizePolicy();policy.setHeightForWidth(True);self.status.setSizePolicy(policy)

    def build_fields(self,form):
        form.setRowWrapPolicy(W.QFormLayout.WrapLongRows)
        self.body=W.QComboBox();form.addRow(tr('ボディ','Body'),self.body)
        self.path=W.QComboBox();form.addRow(tr('経路','Path'),self.path)
        self.count=W.QSpinBox();self.count.setRange(2,200);self.count.setValue(4);self.count.setKeyboardTracking(False)
        form.addRow(tr('個数（元を含む）','Quantity'),self.count)
        self.count.setToolTip(tr('元のボディを含めた個数です。','Includes the original body.'))
        self.mode=W.QComboBox()
        for label,key in [(tr('経路全体','Entire Path'),'full'),(tr('間隔','Spacing'),'spacing'),(tr('全体の距離','Extent'),'extent')]:self.mode.addItem(label,key)
        form.addRow(tr('距離の指定','Distribution'),self.mode)
        self.distance=self.spin();self.distance.setRange(.001,1000000);self.distance.setValue(10)
        self.distance_label=W.QLabel(tr('間隔','Spacing'));form.addRow(self.distance_label,self.distance)
        self.orientation=W.QComboBox()
        self.orientation.addItem(tr('向きを保つ','Keep Orientation'),'fixed');self.orientation.addItem(tr('経路に合わせる','Follow Tangent'),'tangent')
        form.addRow(tr('向き','Orientation'),self.orientation)
        self.reverse=W.QCheckBox(tr('経路を逆向きにたどる','Reverse Path Direction'));self.reverse.toggled.connect(self.schedule);form.addRow(self.reverse)
        self.note=W.QLabel(tr('元のボディは現在位置に残り、経路の始点からの変化量に沿って複製します。経路に重ねる場合は先に元のボディを始点へ配置してください。\n閉じた経路全体では一周に等間隔で配置します。複製は結合せず、全体を1つのパターンとして扱います。',
            'The original stays in place; copies follow the displacement from the path start. Position the original at the start to place copies on the path.\nEntire closed paths use equal spacing without repeating the start. Copies remain separate solids in one pattern.'))
        self.note.setWordWrap(True);form.addRow(self.note)
        for widget in (self.body,self.path,self.count,self.mode,self.distance,self.orientation):widget.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        policy=W.QSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);policy.setHeightForWidth(True);self.note.setSizePolicy(policy)
        self.combos=(self.body,self.path,self.mode,self.orientation);self.spins=(self.count,self.distance)
        self.cache_key=None;self.cache_shape=None

    def start(self,existing=None):
        self.cancel()
        if self.ws.current_sketch():raise ValueError(tr('先にスケッチ編集を終了してください。','Finish editing the sketch first.'))
        self.doc=self.ws.doc();self.existing=existing
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        selected=Gui.Selection.getSelection()
        bodies=[o for o,t in browser.collect(self.doc)[0]]
        if existing and existing.FluxBodySource and existing.FluxBodySource not in bodies:bodies.insert(0,existing.FluxBodySource)
        def allowed(obj):return not existing or (obj!=existing and existing not in obj.OutListRecursive)
        bodies=[o for o in bodies if allowed(o)]
        paths=[]
        for obj in self.doc.Objects:
            if not allowed(obj) or getattr(obj,'FluxCADInternal',False) or not hasattr(obj,'Shape'):continue
            try:pattern.Path(obj);paths.append(obj)
            except Exception:continue
        if existing and existing.FluxPath and existing.FluxPath not in paths:paths.insert(0,existing.FluxPath)
        for combo,options,label in ((self.body,bodies,tr('ボディを選択','Select Body')),(self.path,paths,tr('経路を選択','Select Path'))):
            combo.clear();combo.addItem(label,None)
            for obj in options:combo.addItem(obj.Label,obj.Name)
        source=existing.FluxBodySource if existing else next((o for o in selected if o in bodies),bodies[0] if len(bodies)==1 else None)
        path=existing.FluxPath if existing else next((o for o in selected if o in paths),paths[0] if len(paths)==1 else None)
        if source:self.body.setCurrentIndex(self.body.findData(source.Name))
        if path:self.path.setCurrentIndex(self.path.findData(path.Name))
        values=pattern.settings(existing) if existing else pattern.validate()
        self.count.setValue(values['count']);self.distance.setValue(values['distance'])
        self.initial_distance=(values['mode'],values['distance'],self.distance.value()) if existing else None
        self.mode.setCurrentIndex(self.mode.findData(values['mode']));self.orientation.setCurrentIndex(self.orientation.findData(values['orientation']));self.reverse.setChecked(values['reverse'])
        self.heading.setText(pattern.title()+(tr('を編集',' — Edit') if existing else ''))
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.cache_key=None;self.active=True;self.panel.show();self.update_preview();self.position()

    def sources(self):
        return self.doc.getObject(self.body.currentData()) if self.body.currentData() else None,self.doc.getObject(self.path.currentData()) if self.path.currentData() else None

    def parameters(self):
        distance=self.distance.value()
        initial=getattr(self,'initial_distance',None)
        if initial is not None and self.mode.currentData()==initial[0] and distance==initial[2]:
            distance=initial[1]
        return dict(count=self.count.value(),mode=self.mode.currentData(),distance=distance,orientation=self.orientation.currentData(),reverse=self.reverse.isChecked())

    def signature(self):
        def sig(obj):return (obj.Name,obj.Shape.hashCode(),str(obj.getGlobalPlacement()),str(getattr(obj,'Error',''))) if obj else None
        return tuple(sig(o) for o in self.sources()),tuple(self.parameters().items()),str(self.existing.getGlobalPlacement()) if self.existing else None

    def path_marker(self,path):
        curve=pattern.Path(path);reverse=self.reverse.isChecked();start,direction=curve.at(0,reverse)
        # Unpickable guide shares the preview root and disappears on cancel.
        parent=self.existing.getGlobalPlacement() if self.existing else App.Placement()
        points=[parent.multVec(curve.at(curve.length*i/64,reverse)[0]) for i in range(65)]
        node=coin.SoSeparator();self.overlay[1].addChild(node)
        light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(.28,.61,.48);material.transparency=0;node.addChild(material)
        style=coin.SoDrawStyle();style.lineWidth=2;style.pointSize=7;node.addChild(style)
        coordinates=coin.SoCoordinate3();coordinates.point.setValues(0,len(points),[tuple(v) for v in points]);node.addChild(coordinates)
        line=coin.SoLineSet();line.numVertices.setValue(len(points));node.addChild(line)
        length=max(.5,min(5,curve.length*.04));up=App.Vector(0,0,1) if abs(direction.z)<.9 else App.Vector(0,1,0)
        side=direction.cross(up);side.normalize();end=start+direction*length
        arrow=[start,end,end-direction*length*.3+side*length*.2,end,end-direction*length*.3-side*length*.2]
        coordinates=coin.SoCoordinate3();coordinates.point.setValues(0,len(arrow),[tuple(parent.multVec(v)) for v in arrow]);node.addChild(coordinates)
        line=coin.SoLineSet();line.numVertices.setValue(len(arrow));node.addChild(line)
        point=coin.SoPointSet();point.numPoints=1;node.addChild(point)
        return parent.multVec(start)

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        mode=self.mode.currentData();self.distance.setVisible(mode!='full');self.distance_label.setVisible(mode!='full')
        self.distance_label.setText(tr('間隔','Spacing') if mode=='spacing' else tr('全体の距離','Extent'))
        try:
            source,path=self.sources();pattern.check_sources(self.doc,source,path,self.existing)
            signature=self.signature();key=signature[:2]
            if key!=self.cache_key:
                self.cache_shape,self.path_length,self.extent=pattern.build(source,path,**self.parameters());self.cache_key=key
            result=self.cache_shape.copy()
            if self.existing:result.Placement=self.existing.getGlobalPlacement().multiply(result.Placement)
            self.show_shape(result,'new')
            start=self.path_marker(path)
            hidden=self.existing or source;self.hidden.append((hidden,hidden.Visibility));hidden.Visibility=False
            self.status.setText(tr('経路長: %.3f mm\n配置範囲: %.3f mm ／ %d個の立体','Path length: %.3f mm\nPlacement extent: %.3f mm / %d solids')%(self.path_length,self.extent,len(result.Solids)))
            self.status.setText(self.status.text()+tr('\n経路の始点（緑の矢印）:\nX %.3f / Y %.3f / Z %.3f mm','\nPath start (green arrow):\nX %.3f / Y %.3f / Z %.3f mm')%tuple(start))
            self.status.setStyleSheet('color:#3c6f62;');self.valid=True;self.accept_button.setEnabled(True);self.last_signature=signature
        except Exception as error:self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;')

    def accept(self):
        if not self.active:return
        for field in self.spins:field.interpretText()
        self.update_preview()
        if not self.valid:return
        try:
            self.clear_preview();source,path=self.sources()
            result=pattern.create(self.doc,source,path,existing=self.existing,**self.parameters())
        except Exception as error:self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;');return
        self.active=False;self.timer.stop();self.panel.hide();self.ws.region_picker.clear()
        Gui.Selection.clearSelection();Gui.Selection.addSelection(result);self.ws.refresh()

    def refresh(self):
        if not self.active:return
        try:
            if App.ActiveDocument!=self.doc or self.ws.current_sketch() or (self.existing and not self.existing.Document):self.cancel();return
            if self.signature()!=getattr(self,'last_signature',None):self.update_preview()
        except (RuntimeError,ReferenceError):self.cancel();return
        self.position()
