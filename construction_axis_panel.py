"""Movable construction-axis editor with native face and vertex selection."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore,QtWidgets as W
from pivy import coin
from floating_panel import FloatingPanel
from i18n import tr
import model_construction as refs
import model_construction_axis as axes


class ConstructionAxisPanel(FloatingPanel):
    layout_key='ConstructionAxisPanel'
    preferred_height=380

    def __init__(self,ws):
        self.ticket=0;self.picking=None;self.observing=False
        super().__init__(ws)
        policy=self.status.sizePolicy();policy.setHeightForWidth(True);self.status.setSizePolicy(policy)

    def build_fields(self,form):
        form.setRowWrapPolicy(W.QFormLayout.WrapLongRows)
        self.a_button=W.QPushButton();self.b_button=W.QPushButton();form.addRow(self.a_button);form.addRow(self.b_button)
        self.a_button.clicked.connect(lambda:self.begin_pick('reference_a'));self.b_button.clicked.connect(lambda:self.begin_pick('reference_b'))
        self.size=self.spin();self.size.setRange(.1,1000000);self.size.setValue(80);form.addRow(tr('表示長さ','Display Length'),self.size)
        self.reverse=W.QCheckBox(tr('軸の方向を反転','Reverse Axis Direction'));self.reverse.toggled.connect(self.schedule);form.addRow(self.reverse)
        self.note=W.QLabel();self.note.setWordWrap(True);form.addRow(self.note)
        for widget in (self.a_button,self.b_button,self.size):widget.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        policy=W.QSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);policy.setHeightForWidth(True);self.note.setSizePolicy(policy)
        self.combos=();self.spins=(self.size,)

    def start(self,kind='center',existing=None):
        self.cancel()
        if self.ws.current_sketch():raise ValueError(tr('先にスケッチ編集を終了してください。','Finish editing the sketch first.'))
        self.doc=self.ws.doc();self.kind=str(existing.FluxConstructionAxis) if existing else kind;self.existing=existing
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        values=axes.settings(existing) if existing else dict(size=80,reversed=False)
        self.refs={key:values.get(key) for key in ('reference_a','reference_b')}
        if not existing:
            candidates=[]
            for item in Gui.Selection.getSelectionEx():
                for sub in item.SubElementNames or ('',):
                    try:
                        ref=refs.resolve(self.doc,item.ObjectName,sub)
                        if ref[1].startswith('Vertex' if self.kind=='two_points' else 'Face'):candidates.append(ref)
                    except Exception:continue
            for key,ref in zip(self.refs,candidates):self.refs[key]=ref
        self.size.setValue(values['size']);self.reverse.setChecked(values['reversed'])
        self.initial_size=values['size'];self.displayed_size=self.size.value()
        self.heading.setText(axes.title(self.kind)+(tr('を編集',' — Edit') if existing else ''))
        self.note.setText(tr('円柱または円すいの側面を選びます。中心軸は元の形状の移動・回転に追従します。',
                            'Select a cylindrical or conical side face. The center axis follows source movement and rotation.') if self.kind=='center' else
                          tr('頂点やスケッチの端点を2つ選びます。点1から点2へ向かう方向が軸の正方向です。',
                             'Select two vertices or sketch endpoints. The positive axis points from Point 1 to Point 2.'))
        self.note.setText(self.note.text()+tr('\n表示長さは見える線だけを変えます。回転や円形パターンでは無限の軸として使えます。',
            '\nDisplay Length only changes the visible line. Revolve and Circular Pattern use the infinite axis.'))
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear();Gui.Selection.addObserver(self);self.observing=True
        self.active=True;self.picking=next((key for key in ('reference_a','reference_b')[:2 if self.kind=='two_points' else 1] if not self.refs[key]),None)
        self.panel.show();self.update_preview();self.position()

    def parameters(self):return dict(self.refs,size=self.initial_size if self.existing and self.size.value()==self.displayed_size else self.size.value(),reversed=self.reverse.isChecked())

    def begin_pick(self,key):
        if self.active:self.ticket+=1;self.picking=key;Gui.Selection.clearSelection();self.update_preview()

    def addSelection(self,docname,objname,subname,point):
        if not self.active or not self.picking or docname!=self.doc.Name:return
        ticket=self.ticket;key=self.picking
        def receive():
            if not self.active or self.ticket!=ticket or self.picking!=key:return
            try:
                ref=refs.resolve(self.doc,objname,subname)
                (refs.vertex if self.kind=='two_points' else refs.round_face)(ref)
                if self.existing and (ref[0]==self.existing or self.existing in ref[0].OutListRecursive):
                    raise ValueError(tr('この軸自身や後続の加工は参照できません。','Cannot reference this axis or its descendants.'))
                values=dict(self.refs);values[key]=ref
                if self.kind=='two_points' and all(values.values()):axes.geometry(self.kind,**values)
                self.refs[key]=ref;self.ticket+=1;self.picking=None
                if self.kind=='two_points':self.picking=next((k for k in self.refs if not self.refs[k]),None)
                Gui.Selection.clearSelection();self.update_preview()
            except Exception as error:self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;');Gui.Selection.clearSelection()
        QtCore.QTimer.singleShot(0,receive)

    def signature(self):
        result=[]
        for ref in axes.source_refs(self.kind,**self.parameters()):
            obj=ref[0] if ref else None
            result.append((obj.Name,ref[1],obj.Shape.hashCode(),str(obj.getGlobalPlacement()),str(getattr(obj,'Error',''))) if obj else None)
        return str(result),self.size.value(),self.reverse.isChecked(),self.picking

    def guide(self,shape=None):
        node=coin.SoSeparator();pick=coin.SoPickStyle();pick.style=coin.SoPickStyle.UNPICKABLE;node.addChild(pick)
        light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(.9,.5,.12);node.addChild(material)
        style=coin.SoDrawStyle();style.lineWidth=3;style.pointSize=8;node.addChild(style)
        if shape is not None:
            edge=shape.Edges[0];a=edge.valueAt(edge.FirstParameter);b=edge.valueAt(edge.LastParameter)
            direction=b-a;direction.normalize();side=direction.cross(App.Vector(0,0,1) if abs(direction.z)<.9 else App.Vector(0,1,0));side.normalize()
            length=max(.1,min(5,self.size.value()*.12));points=[a,b,b-direction*length+side*length*.4,b,b-direction*length-side*length*.4]
            coordinates=coin.SoCoordinate3();coordinates.point.setValues(0,len(points),[tuple(v) for v in points]);node.addChild(coordinates)
            line=coin.SoLineSet();line.numVertices.setValue(len(points));node.addChild(line)
            self.preview_shape=shape
        if self.kind=='two_points':
            material=coin.SoMaterial();material.diffuseColor=(.15,.5,.8);node.addChild(material)
            for index,key in enumerate(self.refs,1):
                try:point=refs.vertex(self.refs[key])
                except Exception:continue
                marker=coin.SoSeparator();node.addChild(marker);coordinates=coin.SoCoordinate3();coordinates.point.setValue(tuple(point));marker.addChild(coordinates)
                dot=coin.SoPointSet();dot.numPoints=1;marker.addChild(dot)
                translation=coin.SoTranslation();translation.translation=tuple(point);marker.addChild(translation)
                font=coin.SoFont();font.size=16;marker.addChild(font);label=coin.SoText2();label.string=str(index);marker.addChild(label)
        graph=Gui.activeDocument().activeView().getSceneGraph();graph.addChild(node);self.overlay=(graph,node)

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False);self.b_button.setVisible(self.kind=='two_points');shape=None
        for key,button,label in [('reference_a',self.a_button,tr('点1','Point 1') if self.kind=='two_points' else tr('曲面','Curved Face')),('reference_b',self.b_button,tr('点2','Point 2'))]:
            ref=self.refs[key]
            try:description='%s / %s'%(ref[0].Label,ref[1]) if ref and ref[0] else tr('選択','Select')
            except (ReferenceError,RuntimeError):description=tr('参照なし','Missing Reference')
            button.setText(label+': '+description);button.setToolTip(button.text());button.setStyleSheet('border:1px solid #258fbe;background:#e6f5ff;' if self.picking==key else '')
        try:
            values=self.parameters();axes.check_sources(self.doc,self.kind,self.existing,**values);shape=axes.build(self.kind,**values)
            if self.existing:self.hidden.append((self.existing,self.existing.Visibility));self.existing.Visibility=False
            self.status.setText(tr('「回転」「円形パターン」の参照軸として選択できます。矢印が軸の正方向です。',
                'Select this axis as the reference for Revolve or Circular Pattern. The arrow shows its positive direction.'))
            self.status.setStyleSheet('color:#3c6f62;');self.valid=True;self.accept_button.setEnabled(not self.picking)
        except Exception as error:self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;')
        self.guide(shape)
        if self.picking:
            self.status.setText(tr('点%d：画面上の頂点またはスケッチの端点をクリックしてください。','Point %d: click a vertex or sketch endpoint in the view.')%(1 if self.picking=='reference_a' else 2) if self.kind=='two_points' else
                tr('画面上の円柱または円すいの側面をクリックしてください。','Click a cylindrical or conical side face in the view.'))
            self.status.setStyleSheet('color:#247c9c;')
        try:self.last_signature=self.signature()
        except (ReferenceError,RuntimeError):self.last_signature=None

    def detach(self):
        self.ticket+=1;self.picking=None
        if self.observing:Gui.Selection.removeObserver(self);self.observing=False

    def cancel(self):self.detach();super().cancel()

    def accept(self):
        if not self.active or self.picking:return
        self.size.interpretText();self.update_preview()
        if not self.valid:return
        try:self.clear_preview();result=axes.create(self.doc,self.kind,existing=self.existing,**self.parameters())
        except Exception as error:self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;');return
        self.detach();self.active=False;self.timer.stop();self.panel.hide();self.ws.region_picker.clear()
        Gui.Selection.clearSelection();Gui.Selection.addSelection(result);self.ws.refresh()

    def refresh(self):
        if not self.active:return
        try:
            if App.ActiveDocument!=self.doc or self.ws.current_sketch() or (self.existing and not self.existing.Document):self.cancel();return
            if self.signature()!=getattr(self,'last_signature',None):self.update_preview()
        except (ReferenceError,RuntimeError):self.cancel();return
        self.position()

    def eventFilter(self,widget,event):
        if self.active and self.picking and widget in self.widgets and event.type() in (QtCore.QEvent.MouseButtonPress,QtCore.QEvent.MouseButtonRelease,QtCore.QEvent.MouseButtonDblClick) and event.button()==QtCore.Qt.LeftButton:return False
        return super().eventFilter(widget,event)
