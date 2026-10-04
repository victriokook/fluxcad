"""Preview mesh separation and planar cuts without changing the source."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui,QtWidgets as W
from pivy import coin
from i18n import tr
from mesh_panel import MeshPanel
from transform_panel import TransformPanel
import model_mesh as meshes
import model_mesh_edit as edit


class MeshOperationsPanel(MeshPanel):
    preferred_height=570
    colors=[(.25,.58,.82),(.24,.66,.46),(.85,.53,.23),(.66,.42,.77)]

    def build_fields(self,form):
        self.rows={}
        def row(key,title,widget):
            label=W.QLabel(title);form.addRow(label,widget);self.rows[key]=(label,widget);return widget
        self.summary=W.QLabel();self.summary.setWordWrap(True)
        self.summary.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Preferred);form.addRow(self.summary)
        self.mode=row('mode',tr('操作'),W.QComboBox())
        self.mode.addItem(tr('平面で切断','Plane Cut'),'cut');self.mode.addItem(tr('部品を分離','Separate Parts'),'separate')
        self.plane=row('plane',tr('切断平面','Cutting plane'),W.QComboBox())
        for title,axis in [('XY (Z)','Z'),('YZ (X)','X'),('XZ (Y)','Y')]:self.plane.addItem(title,axis)
        self.plane.currentIndexChanged.connect(self.center_plane)
        self.coordinate=row('coordinate',tr('位置（全体座標）','Position (world)'),TransformPanel.number())
        self.center_button=W.QPushButton(tr('メッシュの中央に合わせる','Center on mesh'));self.center_button.clicked.connect(self.center_plane)
        row('center','',self.center_button)
        self.side=row('side',tr('残す側','Keep'),W.QComboBox())
        for title,key in [(tr('両側を別々に残す','Both sides, separately'),'both'),(tr('負方向だけ','Negative side'),'negative'),(tr('正方向だけ','Positive side'),'positive')]:self.side.addItem(title,key)
        self.close_faces=W.QCheckBox(tr('切断面を閉じる','Close cut faces'));self.close_faces.setChecked(True)
        self.close_faces.toggled.connect(self.schedule);row('close','',self.close_faces)
        self.result_list=W.QListWidget();self.result_list.setMaximumHeight(115);self.result_list.setMinimumHeight(70)
        self.result_list.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Preferred);form.addRow(self.result_list)
        self.note=W.QLabel(tr('確定すると結果を別メッシュとして作成し、元のメッシュを非表示で残します。結果は元の形状変更には追従しません。',
                              'Confirm creates independent result meshes and keeps the hidden original. Later source changes do not update the results.'))
        self.note.setWordWrap(True);self.note.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Preferred);form.addRow(self.note)
        self.combos=(self.mode,self.plane,self.side);self.spins=(self.coordinate,)

    def center_plane(self,*args):
        if not self.active:return
        self.coordinate.setValue(tuple(self.sources[0].BoundBox.Center)['XYZ'.index(self.plane.currentData())])

    def start(self,objects,mode='cut'):
        self.cancel();self.doc=App.ActiveDocument;self.targets=meshes.targets(self.doc,objects)
        if len(self.targets)!=1:
            raise ValueError(tr('分離・切断するメッシュを1つ選択してください。','Select one mesh to separate or cut.'))
        self.source=self.targets[0];self.sources=[meshes.world_mesh(self.source)]
        self.selection=[(sel.ObjectName,tuple(sel.SubElementNames)) for sel in Gui.Selection.getSelectionEx()]
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        self.poses=[str(self.source.getGlobalPlacement())];self.dirty=False
        self.mode.setCurrentIndex(self.mode.findData(mode));self.plane.setCurrentIndex(0);self.side.setCurrentIndex(0)
        self.close_faces.setChecked(self.sources[0].isSolid() and not self.sources[0].hasNonUniformOrientedFacets())
        self.coordinate.setValue(self.sources[0].BoundBox.Center.z)
        self.results=[];self.cache_key=None;self.observing=True;App.addDocumentObserver(self)
        self.summary.setText(self.source.Label+tr('\n三角形数：%s','\nTriangles: %s')%format(self.sources[0].CountFacets,','))
        self.active=True;self.panel.show();self.update_preview();self.position()

    def parameters(self):
        return dict(axis=self.plane.currentData(),coordinate=self.coordinate.value(),side=self.side.currentData(),close=self.close_faces.isChecked())

    def add_triangles(self,node,mesh,color):
        branch=coin.SoSeparator();material=coin.SoMaterial();material.diffuseColor=color;branch.addChild(material)
        vertices,triangles=mesh.Topology
        coords=coin.SoCoordinate3();coords.point.setValues(0,len(vertices),[tuple(v) for v in vertices]);branch.addChild(coords)
        faces=coin.SoIndexedFaceSet();faces.coordIndex.setValues(0,len(triangles)*4,[v for tri in triangles for v in (*tri,-1)])
        branch.addChild(faces);node.addChild(branch)

    def show_results(self):
        node=coin.SoSeparator();pick=coin.SoPickStyle();pick.style=coin.SoPickStyle.UNPICKABLE;node.addChild(pick)
        for i,(mesh,title) in enumerate(self.results):self.add_triangles(node,mesh,self.colors[i%len(self.colors)])
        if self.mode.currentData()=='cut':
            plane=coin.SoSeparator();material=coin.SoMaterial();material.diffuseColor=(.95,.7,.25);material.transparency=.75;plane.addChild(material)
            box=self.sources[0].BoundBox;center=App.Vector(box.Center);index='XYZ'.index(self.plane.currentData());center[index]=self.coordinate.value()
            axes=[i for i in range(3) if i!=index];half=max(.5,max(getattr(box,'XYZ'[i]+'Length') for i in axes)*.6)
            vertices=[]
            for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]:
                p=App.Vector(center);p[axes[0]]+=x*half;p[axes[1]]+=y*half;vertices.append(tuple(p))
            coords=coin.SoCoordinate3();coords.point.setValues(0,4,vertices);plane.addChild(coords)
            face=coin.SoFaceSet();face.numVertices.setValue(4);plane.addChild(face)
            line=coin.SoIndexedLineSet();line.coordIndex.setValues(0,6,[0,1,2,3,0,-1]);plane.addChild(line);node.addChild(plane)
        graph=Gui.activeDocument().activeView().getSceneGraph();graph.addChild(node);self.overlay=(graph,node)
        self.hidden.append((self.source,bool(self.source.Visibility)));self.source.Visibility=False

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        mode=self.mode.currentData()
        self.heading.setText(tr('メッシュを平面で切断','Mesh Plane Cut') if mode=='cut' else tr('メッシュの部品を分離','Separate Mesh Parts'))
        for key,pair in self.rows.items():
            for widget in pair:widget.setVisible(key=='mode' or mode=='cut')
        self.valid=False;self.accept_button.setEnabled(False)
        try:
            if self.stale():raise ValueError(tr('対象メッシュが変更されました。キャンセルして選び直してください。','The mesh changed. Cancel and select it again.'))
            values=self.parameters();key=(mode,tuple(values.items()) if mode=='cut' else None)
            if key!=self.cache_key:
                self.clear_preview();self.results=[];self.cache_key=None;self.result_list.clear()
                self.results=edit.cut(self.sources[0],**values) if mode=='cut' else edit.separate(self.sources[0])
                self.show_results();self.cache_key=key
                for i,(mesh,title) in enumerate(self.results):
                    item=W.QListWidgetItem(title+tr(' — %s 三角形',' — %s triangles')%format(mesh.CountFacets,','),self.result_list)
                    item.setForeground(QtGui.QColor.fromRgbF(*self.colors[i%len(self.colors)]))
            self.valid=True;self.accept_button.setEnabled(True);self.status.setStyleSheet('color:#245b73;')
            suffix=tr('切断面を閉じました。','Cut faces are closed.') if mode=='cut' and values['close'] else tr('切断面は開いたままです。','Cut faces are left open.') if mode=='cut' else tr('離れている部分ごとに分離します。','Each disconnected part becomes a separate mesh.')
            self.status.setText(tr('結果：%d メッシュ\n','Result: %d meshes\n')%len(self.results)+suffix)
        except Exception as error:
            self.clear_preview();self.results=[];self.cache_key=None;self.result_list.clear()
            self.status.setStyleSheet('color:#ac3830;');self.status.setText(str(error))

    def cancel(self):
        super().cancel();self.results=[];self.cache_key=None

    def accept(self):
        if not self.active:return
        self.coordinate.interpretText();self.update_preview()
        if not self.valid:return
        self.clear_preview();self.unobserve()
        try:results=edit.create_results(self.doc,self.source,self.results,self.heading.text())
        except Exception as error:
            self.dirty=True;self.valid=False;self.accept_button.setEnabled(False);self.status.setText(str(error));return
        self.active=False;self.panel.hide();self.sources=[];self.results=[];self.cache_key=None
        Gui.Selection.clearSelection()
        for obj in results:Gui.Selection.addSelection(obj)
        self.ws.refresh();self.ws.main.statusBar().showMessage(tr('結果を作成しました。元のメッシュは非表示で残しています。Ctrl＋Zで元に戻せます。',
                                                               'Result meshes created. The hidden original is retained. Press Ctrl+Z to undo.'),10000)
