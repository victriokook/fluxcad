"""Preview edge treatments, select source edges, and edit native history."""
import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore,QtWidgets as W
from pivy import coin
from i18n import tr
from floating_panel import FloatingPanel
import model
import model_edges as edges
import browser


class EdgePanel(FloatingPanel):
    layout_key='EdgePanel'
    preferred_height=460

    def build_fields(self,form):
        self.source_label=W.QLabel();self.source_label.setWordWrap(True)
        self.source_label.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);form.addRow(self.source_label)
        self.pick_button=W.QPushButton();self.pick_button.setCheckable(True)
        self.pick_button.clicked.connect(self.toggle_pick);form.addRow(self.pick_button)
        self.edge_list=W.QListWidget();self.edge_list.setMinimumHeight(100);self.edge_list.setMaximumHeight(160)
        self.edge_list.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Preferred)
        self.edge_list.itemChanged.connect(self.schedule);form.addRow(tr('加工する辺','Edges'),self.edge_list)
        self.clear_button=W.QPushButton(tr('選択をクリア','Clear Selection'))
        self.clear_button.clicked.connect(self.clear_edges);form.addRow(self.clear_button)
        self.mode=W.QComboBox();self.mode.addItem(tr('等距離','Equal Distance'),'equal');self.mode.addItem(tr('2つの距離','Two Distances'),'two')
        self.mode.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        self.mode_label=W.QLabel(tr('面取りの種類','Chamfer Type'));form.addRow(self.mode_label,self.mode)
        self.size=self.spin();self.size.setValue(1);self.size.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        self.size_label=W.QLabel();form.addRow(self.size_label,self.size)
        self.size2=self.spin();self.size2.setValue(1);self.size2.setDecimals(6);self.size2.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        self.size2_label=W.QLabel(tr('距離2','Distance 2'));form.addRow(self.size2_label,self.size2)
        self.swap_button=W.QPushButton(tr('距離1と2を入れ替え','Swap Distances 1 and 2'));self.swap_button.clicked.connect(self.swap_distances);form.addRow(self.swap_button)
        self.distance_note=W.QLabel(tr('2つの距離は、辺に接する2面にそれぞれ適用します。割り当てる側は辺ごとに異なるため、プレビューで確認してください。',
                                      'The two distances apply to the two adjacent faces. Their sides can differ for each edge; check the preview.'))
        self.distance_note.setWordWrap(True);self.distance_note.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);form.addRow(self.distance_note)
        self.note=W.QLabel(tr('辺はチェックで追加・解除できます。「辺を選択」中は加工前の形状を表示し、クリックで選択、Ctrl＋クリックで追加・解除します。',
                             'Use the checkboxes to add or remove edges. Select Edges shows the original shape: click to select, Ctrl-click to add or remove.'))
        self.note.setWordWrap(True);self.note.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);form.addRow(self.note)
        self.combos=(self.mode,);self.spins=(self.size,self.size2)

    def start(self,operation='fillet',existing=None):
        self.cancel()
        if self.ws.current_sketch():raise ValueError(tr('先にスケッチ編集を終了してください。','Finish editing the sketch first.'))
        self.doc=App.ActiveDocument;self.existing=existing;self.source=None;self.operation=edges.kind(existing) if existing else operation
        if not self.doc:raise ValueError(tr('加工するソリッドを作成してください。','Create a solid to modify.'))
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        chosen=[];size=1;size2=None
        if existing:
            self.source=existing.Base;values=edges.settings(existing);chosen=values['edges'];size=values['size'];size2=values.get('size2')
        else:
            for selected in Gui.Selection.getSelectionEx():
                obj=selected.Object
                # Resolve a nested object path before interpreting its edge numbers.
                for name in selected.SubElementNames or ['']:
                    resolved=obj.getSubObject(name,1) or obj if name else obj
                    resolved=browser.body_owner(resolved)
                    if self.source and resolved!=self.source:
                        raise ValueError(tr('同じボディの辺を選択してください。','Select edges of the same body.'))
                    if not hasattr(resolved,'Shape') or hasattr(resolved,'Mesh'):
                        raise ValueError(tr('この加工はソリッド用です。','This operation requires a solid.'))
                    self.source=resolved
                    edge=name.rsplit('.',1)[-1]
                    if edge.startswith('Edge'):chosen.append(edge)
        if self.source:edges.source_shape(self.source,existing)
        self.signature=edges.signature(self.source) if self.source else None
        self.heading.setText(edges.title(self.operation,bool(existing)))
        self.mode.setCurrentIndex(int(size2 is not None));self.size.setDecimals(6 if self.operation=='chamfer' else 3)
        self.size.setValue(size);self.size2.setValue(size if size2 is None else size2)
        self.initial_sizes=(size,size if size2 is None else size2);self.displayed_sizes=(self.size.value(),self.size2.value())
        self.picking=not chosen;self.press=None
        self.populate(chosen)
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.active=True;self.panel.show();self.update_preview();self.position()

    def parameters(self):
        values=[initial if field.value()==displayed else field.value()
                for field,initial,displayed in zip((self.size,self.size2),self.initial_sizes,self.displayed_sizes)]
        return dict(size=values[0],size2=values[1] if self.operation=='chamfer' and self.mode.currentData()=='two' else None)

    def swap_distances(self):
        if not self.active or self.operation!='chamfer' or self.mode.currentData()!='two':return
        for field in self.spins:field.interpretText()
        values=self.parameters();self.size.setValue(values['size2']);self.size2.setValue(values['size'])
        self.initial_sizes=(values['size2'],values['size']);self.displayed_sizes=(self.size.value(),self.size2.value())
        self.update_preview()

    def dimension_fields(self):
        chamfer=self.operation=='chamfer';two=chamfer and self.mode.currentData()=='two'
        self.mode_label.setVisible(chamfer);self.mode.setVisible(chamfer)
        for widget in (self.size2_label,self.size2,self.swap_button,self.distance_note):widget.setVisible(two)
        self.size_label.setText(tr('半径','Radius') if not chamfer else tr('距離1','Distance 1') if two else tr('距離','Distance'))
        self.preferred_height=560 if two else 490 if chamfer else 460

    def populate(self,chosen=()):
        blocked=self.edge_list.blockSignals(True);self.edge_list.clear()
        if self.source:
            shape=edges.source_shape(self.source,self.existing)
            for i,edge in enumerate(shape.Edges):
                name='Edge%d'%(i+1);item=W.QListWidgetItem(tr('辺 %d — %.3f mm','Edge %d — %.3f mm')%(i+1,edge.Length),self.edge_list)
                item.setData(QtCore.Qt.UserRole,name);item.setFlags(item.flags()|QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked if name in chosen else QtCore.Qt.Unchecked)
        self.edge_list.blockSignals(blocked)

    def selected_edges(self):
        return [self.edge_list.item(i).data(QtCore.Qt.UserRole) for i in range(self.edge_list.count())
                if self.edge_list.item(i).checkState()==QtCore.Qt.Checked]

    def toggle_pick(self):
        if not self.active:return
        self.picking=not self.picking
        if self.source and edges.signature(self.source)!=self.signature:
            self.signature=edges.signature(self.source);self.populate();self.picking=True
        self.update_preview()

    def clear_edges(self):
        if self.active:self.populate();self.picking=True;self.update_preview()

    def displayed_source(self):return edges.pose(edges.source_shape(self.source,self.existing),self.existing)

    def wires(self,shape,chosen):
        for selection,color,width in ((range(len(shape.Edges)),(.3,.36,.4),1),
                                       ([int(name[4:])-1 for name in chosen],(1,.62,.05),3)):
            points=[];counts=[]
            for i in selection:
                path=shape.Edges[i].discretize(Deflection=.08);points.extend(path);counts.append(len(path))
            if not points:continue
            node=coin.SoSeparator();light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
            material=coin.SoMaterial();material.diffuseColor=color;material.transparency=0;node.addChild(material)
            style=coin.SoDrawStyle();style.lineWidth=width;node.addChild(style)
            coords=coin.SoCoordinate3();coords.point.setValues(0,len(points),[tuple(p) for p in points]);node.addChild(coords)
            line=coin.SoLineSet();line.numVertices.setValues(0,len(counts),counts);node.addChild(line);self.overlay[1].addChild(node)

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        self.dimension_fields()
        self.pick_button.setChecked(self.picking)
        self.pick_button.setText(tr('選択を終了してプレビュー','Finish Selection / Preview') if self.picking else tr('辺を選択','Select Edges'))
        self.source_label.setText(self.source.Label if self.source else tr('加工するボディの辺をクリックしてください。','Click an edge on the body to modify.'))
        try:
            if self.source and edges.signature(self.source)!=self.signature:
                raise ValueError(tr('元の形状が変わりました。「辺を選択」で選び直してください。',
                                    'The source changed. Use Select Edges to reselect.'))
            chosen=self.selected_edges()
            if self.picking:
                if self.source:
                    shape=self.displayed_source();self.show_shape(shape,'new');self.wires(shape,chosen)
                self.status.setText(tr('%d 辺を選択。選択を終了すると加工結果を表示します。',
                                       '%d edges selected. Finish selection to preview the result.')%len(chosen))
            else:
                if not self.source:raise ValueError(tr('加工する辺を選択してください。','Select edges to modify.'))
                shape=edges.preview(self.source,self.operation,chosen,existing=self.existing,**self.parameters())
                self.show_shape(shape,'new');self.valid=True;self.accept_button.setEnabled(True)
                self.status.setText(tr('%d 辺 / 体積 %.3f mm³','%d edges / Volume %.3f mm³')%(len(chosen),shape.Volume))
            if self.source and self.overlay:
                hidden=self.existing or self.source;self.hidden.append((hidden,bool(hidden.Visibility)));hidden.Visibility=False
            self.status.setStyleSheet('color:#245b73;')
        except Exception as error:
            self.clear_preview();self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def pick(self,widget,point,additive):
        if not self.picking:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        try:
            if self.source and edges.signature(self.source)!=self.signature:
                raise ValueError(tr('元の形状が変わりました。辺を選び直してください。','The source changed. Reselect the edges.'))
            origin,direction=self.ray(widget,point);node=Gui.activeDocument().activeView().getCameraNode()
            candidates=[(self.source,self.displayed_source())] if self.source else [
                (obj,model.world_shape(obj)) for obj,title in browser.collect(self.doc)[0] if obj.Visibility and len(obj.Shape.Solids)==1]
            obstacles=[shape for obj,shape in candidates]
            for obj,title in browser.collect(self.doc)[0]:
                if obj.Visibility and obj not in [self.source,self.existing] and all(obj!=o for o,s in candidates):obstacles.append(model.world_shape(obj))
            hits=[]
            for obj,shape in candidates:
                length=(shape.BoundBox.Center-origin).Length+shape.BoundBox.DiagonalLength+1
                ray=Part.makeLine(origin,origin+direction*length)
                for i,edge in enumerate(shape.Edges):
                    distance,points,_=edge.distToShape(ray)
                    for hit,_ in points:
                        depth=(hit-origin).dot(direction)
                        if depth<=0:continue
                        scale=self.ws.mouse.camera_height(node)/widget.height()
                        if not hasattr(node,'height'):scale*=depth/node.focalDistance.getValue()
                        if distance>scale*7:continue
                        sight=Part.makeLine(origin,hit)
                        blocked=any(any((v.Point-origin).Length<(hit-origin).Length-max(1e-5,scale*.2)
                                        for v in obstacle.section(sight).Vertexes) for obstacle in obstacles)
                        if not blocked:hits.append((round(distance/scale,2),depth,obj,'Edge%d'%(i+1)))
            if not hits:raise ValueError(tr('見えている辺の近くをクリックしてください。','Click near a visible edge.'))
            _,_,obj,name=min(hits,key=lambda x:(x[0],x[1]))
            if self.source is None:self.source=obj;self.signature=edges.signature(obj);self.populate()
            chosen=self.selected_edges() if additive else []
            if name in chosen:chosen.remove(name)
            else:chosen.append(name)
            self.populate(chosen);self.update_preview()
        except Exception as error:
            self.valid=False;self.accept_button.setEnabled(False);self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def accept(self):
        if not self.active:return
        for field in self.spins:field.interpretText()
        self.update_preview()
        if not self.active or not self.valid:return
        self.clear_preview()
        try:result=edges.create(self.doc,self.source,self.operation,self.selected_edges(),existing=self.existing,**self.parameters())
        except Exception as error:
            self.valid=False;self.accept_button.setEnabled(False);self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error));return
        self.active=False;self.timer.stop();self.panel.hide();self.ws.region_picker.clear()
        Gui.Selection.clearSelection();Gui.Selection.addSelection(result);self.ws.refresh()
        self.ws.main.statusBar().showMessage(tr('加工を更新しました。履歴から再編集、Ctrl＋Zで元に戻せます。',
                                               'Edge treatment updated. Edit from history; Ctrl+Z to undo.'),8000)

    def refresh(self):
        if not self.active:return
        try:
            if App.ActiveDocument!=self.doc or self.ws.current_sketch() or (self.source and not self.source.Document) or (self.existing and not self.existing.Document):
                self.cancel();return
            if self.source and self.valid and edges.signature(self.source)!=self.signature:self.update_preview()
        except (RuntimeError,ReferenceError):self.cancel();return
        self.position()

    def eventFilter(self,widget,event):
        if getattr(getattr(self.ws,'cube',None),'forwarding',False):return False
        if self.active and widget in self.widgets:
            if event.type()==QtCore.QEvent.MouseButtonPress and event.button()==QtCore.Qt.LeftButton:
                self.press=(widget,QtCore.QPointF(event.position()));return True
            if event.type()==QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.LeftButton:
                press=self.press;self.press=None
                if press and press[0]==widget and (event.position()-press[1]).manhattanLength()<W.QApplication.startDragDistance():
                    self.pick(widget,event.position(),bool(event.modifiers()&QtCore.Qt.ControlModifier))
                return True
        return super().eventFilter(widget,event)
