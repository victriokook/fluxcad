"""Movable construction-plane preview with native face, edge and vertex picking."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from pivy import coin
from floating_panel import FloatingPanel
from i18n import tr
import model_construction as planes


class ConstructionPanel(FloatingPanel):
    layout_key='ConstructionPanel'
    preferred_height=450

    def __init__(self,ws):
        self.ticket=0;self.picking=None;self.observing=False
        super().__init__(ws)
        policy=self.status.sizePolicy();policy.setHeightForWidth(True);self.status.setSizePolicy(policy)

    def build_fields(self,form):
        form.setRowWrapPolicy(W.QFormLayout.WrapLongRows)
        self.base=W.QComboBox()
        for label,key in [('XY','XY'),('XZ','XZ'),('YZ','YZ'),(tr('選択した面','Selected Face'),'face')]:self.base.addItem(label,key)
        self.base_label=W.QLabel(tr('基準平面','Reference Plane'));form.addRow(self.base_label,self.base)
        self.a_button=W.QPushButton();self.b_button=W.QPushButton();self.c_button=W.QPushButton();self.axis_button=W.QPushButton()
        form.addRow(self.a_button);form.addRow(self.b_button);form.addRow(self.c_button)
        self.path_all_button=W.QPushButton(tr('経路全体を使用','Use Entire Path'));self.path_all_button.clicked.connect(self.use_entire_path);form.addRow(self.path_all_button)
        self.path_mode=W.QComboBox();self.path_mode.addItem(tr('比率','Proportional'),'fraction');self.path_mode.addItem(tr('距離','Distance'),'distance')
        self.path_mode_label=W.QLabel(tr('位置の指定','Position Mode'));form.addRow(self.path_mode_label,self.path_mode)
        self.fraction=self.spin();self.fraction.setRange(0,100);self.fraction.setDecimals(6);self.fraction.setSuffix(' %');self.fraction.setValue(50)
        self.fraction_label=W.QLabel(tr('位置','Position'));form.addRow(self.fraction_label,self.fraction)
        self.path_distance=self.spin();self.path_distance.setRange(0,1000000);self.path_distance.setDecimals(6);self.path_distance.setValue(10)
        self.path_distance_label=W.QLabel(tr('経路上の距離','Distance Along Path'));form.addRow(self.path_distance_label,self.path_distance)
        self.path_reverse=W.QCheckBox(tr('終点から測る','Measure from End'));self.path_reverse.toggled.connect(self.schedule);form.addRow(self.path_reverse)
        self.axis=W.QComboBox()
        for label,key in [('X','X'),('Y','Y'),('Z','Z'),(tr('選択した直線辺','Selected Straight Edge'),'edge')]:self.axis.addItem(label,key)
        self.axis_label=W.QLabel(tr('回転軸','Rotation Axis'));form.addRow(self.axis_label,self.axis);form.addRow(self.axis_button)
        self.angle=self.spin();self.angle.setRange(-180,180);self.angle.setValue(45);self.angle.setSuffix(' °')
        self.angle_label=W.QLabel(tr('角度','Angle'));form.addRow(self.angle_label,self.angle)
        self.distance=self.spin();self.distance.setRange(-1000000,1000000);self.distance.setDecimals(6);self.distance.setValue(10)
        self.offset_label=W.QLabel(tr('距離','Distance'));form.addRow(self.offset_label,self.distance)
        self.reverse=W.QCheckBox(tr('法線を反転','Flip Normal'));self.reverse.toggled.connect(self.schedule);form.addRow(self.reverse)
        self.size=self.spin();self.size.setRange(.1,1000000);self.size.setValue(80)
        form.addRow(tr('表示サイズ','Display Size'),self.size)
        self.note=W.QLabel();self.note.setWordWrap(True);form.addRow(self.note)
        for widget in (self.base,self.axis,self.angle,self.distance,self.size,self.a_button,self.b_button,self.c_button,self.axis_button,self.path_all_button,self.path_mode,self.fraction,self.path_distance):widget.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
        policy=W.QSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Minimum);policy.setHeightForWidth(True);self.note.setSizePolicy(policy)
        for button,key in [(self.a_button,'reference_a'),(self.b_button,'reference_b'),(self.c_button,'reference_c'),(self.axis_button,'axis_reference')]:button.clicked.connect(lambda checked=False,k=key:self.begin_pick(k))
        self.combos=(self.base,self.axis,self.path_mode);self.spins=(self.angle,self.distance,self.size,self.fraction,self.path_distance)

    def start(self,kind='midplane',existing=None):
        self.cancel()
        if self.ws.current_sketch():raise ValueError(tr('先にスケッチ編集を終了してください。','Finish editing the sketch first.'))
        self.kind=str(existing.FluxConstructionPlane) if existing else kind;self.existing=existing;self.doc=self.ws.doc()
        self.selection=[(s.ObjectName,tuple(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
        values=planes.settings(existing) if existing else dict(base='XY',axis='X',angle=0 if self.kind in ('tangent','along_path') else 45,size=80)
        values.setdefault('offset',10)
        for key,value in dict(path_mode='fraction',fraction=.5,path_distance=10,path_reverse=False).items():values.setdefault(key,value)
        self.refs={key:values.get(key) for key in ('reference_a','reference_b','reference_c','axis_reference')}
        if not existing:
            faces=[];edges=[];vertices=[];face_points=[];paths=[]
            for item in Gui.Selection.getSelectionEx():
                for index,sub in enumerate(item.SubElementNames or ('',)):
                    try:
                        ref=planes.resolve(self.doc,item.ObjectName,sub)
                        if self.kind=='along_path' and (not ref[1] or ref[1].startswith('Edge')):paths.append(ref)
                        if ref[1].startswith('Face'):
                            if self.kind not in ('offset','tangent'):planes.face(ref)
                            faces.append(ref)
                            picked=getattr(item,'PickedPoints',[]);face_points.append(picked[index] if index<len(picked) else None)
                        elif ref[1].startswith('Edge'):planes.edge(ref);edges.append(ref)
                        elif ref[1].startswith('Vertex'):planes.vertex(ref);vertices.append(ref)
                    except Exception:continue
            if faces:self.refs['reference_a']=faces[0]
            if self.kind=='midplane' and len(faces)>1:self.refs['reference_b']=faces[1]
            if self.kind in ('angle','offset'):
                if faces:values['base']='face'
                if self.kind=='angle' and edges:values['axis']='edge';self.refs['axis_reference']=edges[0]
            if self.kind=='three_points':
                for index,key in enumerate(('reference_a','reference_b','reference_c')):self.refs[key]=vertices[index] if len(vertices)>index else None
            if self.kind=='tangent' and faces:
                try:values['angle']=planes.tangent_angle(faces[0],face_points[0])
                except ValueError:pass
            if self.kind=='along_path':self.refs['reference_a']=paths[0] if paths else None
        self.base.setCurrentIndex(self.base.findData(values['base']));self.axis.setCurrentIndex(self.axis.findData(values['axis']))
        self.angle.setValue(values['angle']);self.size.setValue(values['size']);self.distance.setValue(values['offset'])
        self.reverse.setChecked(values.get('reversed',False))
        self.path_mode.setCurrentIndex(self.path_mode.findData(values['path_mode']));self.fraction.setValue(values['fraction']*100)
        self.path_distance.setValue(values['path_distance']);self.path_reverse.setChecked(values['path_reverse'])
        self.original_values=values;self.original_display={'angle':self.angle.value(),'size':self.size.value(),'offset':self.distance.value(),'fraction':self.fraction.value()/100,'path_distance':self.path_distance.value()}
        self.heading.setText(planes.title(self.kind)+(tr('を編集',' — Edit') if existing else ''))
        self.note.setText(tr('平行な2つの面を選びます。参照面を変更すると平面とスケッチも追従します。表示サイズはスケッチの原点に影響しません。',
                            'Select two parallel faces. The plane and attached sketches follow their references. Display size does not change the sketch origin.') if self.kind=='midplane' else
                          tr('基準平面上の直線辺または軸を中心に回転します。軸の向きに対して角度の正負で傾く側を切り替えます。',
                             'Rotate about a straight edge or axis in the reference plane. Positive and negative angles tilt to opposite sides of the axis.'))
        if self.kind=='offset':self.note.setText(tr('基準面から垂直に距離を指定します。緑の矢印が正方向です。負の距離で反対側へ作成できます。表示サイズを変えてもスケッチの原点は動きません。',
            'Enter the perpendicular distance from the reference plane. The green arrow points in the positive direction. Use a negative distance for the opposite side. Display size does not move the sketch origin.'))
        if self.kind=='three_points':self.note.setText(tr('頂点やスケッチの端点を3つ選びます。点1が原点、点1→点2がX方向になります。一直線上の3点は使えません。緑の矢印が面の正方向です。',
            'Select three vertices or sketch endpoints. Point 1 is the origin; Point 1 to Point 2 defines X. Collinear points cannot define a plane. The green arrow is the positive normal.'))
        if self.kind=='tangent':self.note.setText(tr('円柱または円すいの側面を選びます。クリックした位置から角度を調整できます。角度は選択面の基準方向から測ります。緑の矢印が面の正方向です。',
            'Select a cylindrical or conical side face. Adjust the angle from the clicked position. Angles are measured from the face\'s reference direction. The green arrow is the positive normal.'))
        if self.kind=='along_path':self.note.setText(tr('辺をクリックし、位置を比率または距離で指定します。「経路全体を使用」でつながったスケッチ全体を使えます。青いSが測定の始点、緑の矢印が平面の正方向です。',
            'Click an edge and set its position by proportion or distance. Use Entire Path selects the connected sketch. Blue S marks the measuring start; the green arrow is the plane normal.'))
        self.ws.region_picker.ticket+=1;self.ws.region_picker.clear()
        Gui.Selection.addObserver(self);self.observing=True;self.active=True;self.panel.show()
        if self.kind=='midplane' and not self.refs['reference_a']:self.picking='reference_a'
        elif self.kind=='midplane' and not self.refs['reference_b']:self.picking='reference_b'
        elif self.kind=='three_points':self.picking=next((key for key in ('reference_a','reference_b','reference_c') if not self.refs[key]),None)
        elif self.kind in ('tangent','along_path') and not self.refs['reference_a']:self.picking='reference_a'
        self.update_preview();self.position()

    def parameters(self):
        values=dict(self.refs,base=self.base.currentData(),axis=self.axis.currentData(),angle=self.angle.value(),size=self.size.value(),offset=self.distance.value(),reversed=self.reverse.isChecked(),path_mode=self.path_mode.currentData(),fraction=self.fraction.value()/100,path_distance=self.path_distance.value(),path_reverse=self.path_reverse.isChecked())
        if self.existing:
            for key in ('angle','size','offset','fraction','path_distance'):
                if values[key]==self.original_display[key]:values[key]=self.original_values[key]
        return values

    def use_entire_path(self):
        if not self.active or self.kind!='along_path' or not self.refs['reference_a']:return
        try:
            ref=(self.refs['reference_a'][0],'');planes.path_curve(ref)
            self.refs['reference_a']=ref;self.ticket+=1;self.picking=None;Gui.Selection.clearSelection();self.update_preview()
        except Exception as error:self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;')

    def begin_pick(self,key):
        if not self.active:return
        self.ticket+=1;self.picking=key;Gui.Selection.clearSelection();self.update_preview()

    def addSelection(self,docname,objname,subname,point):
        if not self.active or not self.picking or docname!=self.doc.Name:return
        ticket=self.ticket;key=self.picking
        def receive():
            if not self.active or self.picking!=key or self.ticket!=ticket:return
            try:
                ref=planes.resolve(self.doc,objname,subname)
                (planes.path_curve if self.kind=='along_path' else planes.round_face if self.kind=='tangent' else planes.vertex if self.kind=='three_points' else planes.edge if key=='axis_reference' else planes.face)(ref)
                # Check this reference alone, even when the other is not selected yet.
                if ref[0].Document!=self.doc or (self.existing and (ref[0]==self.existing or self.existing in ref[0].OutListRecursive)):
                    raise ValueError(tr('この平面自身や後続の加工は参照できません。','Cannot reference this plane or its descendants.'))
                if self.kind=='three_points':
                    values=dict(self.refs);values[key]=ref
                    refs=[values[k] for k in ('reference_a','reference_b','reference_c')]
                    for other_key,other in self.refs.items():
                        if other_key!=key and other_key!='axis_reference' and other and (planes.vertex(other)-planes.vertex(ref)).Length<1e-7:
                            raise ValueError(tr('位置の異なる3つの点を選択してください。','Select three points at different positions.'))
                    if all(refs):planes.points_frame(*refs)
                self.refs[key]=ref;self.ticket+=1;self.picking=None
                if self.kind=='tangent':self.angle.setValue(planes.tangent_angle(ref,point))
                if self.kind=='midplane' and key=='reference_a' and not self.refs['reference_b']:self.picking='reference_b'
                elif self.kind=='three_points':self.picking=next((k for k in ('reference_a','reference_b','reference_c') if not self.refs[k]),None)
                Gui.Selection.clearSelection();self.update_preview()
            except Exception as error:
                self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;');Gui.Selection.clearSelection()
        QtCore.QTimer.singleShot(0,receive)

    def signature(self):
        refs=[]
        for ref in planes.references(self.kind,**self.parameters()):
            obj=ref[0] if ref else None
            refs.append((obj.Name,ref[1],obj.Shape.hashCode(),str(obj.getGlobalPlacement()),str(getattr(obj,'Error',''))) if obj else None)
        return str(refs),self.base.currentData(),self.axis.currentData(),self.angle.value(),self.size.value(),self.distance.value(),self.reverse.isChecked(),self.path_mode.currentData(),self.fraction.value(),self.path_distance.value(),self.path_reverse.isChecked(),self.picking

    def point_guide(self):
        points=[]
        for index,key in enumerate(('reference_a','reference_b','reference_c'),1):
            try:points.append((index,planes.vertex(self.refs[key])))
            except Exception:continue
        if not points:return
        if not self.overlay:
            root=coin.SoSeparator();pick=coin.SoPickStyle();pick.style=coin.SoPickStyle.UNPICKABLE;root.addChild(pick)
            graph=Gui.activeDocument().activeView().getSceneGraph();graph.addChild(root);self.overlay=(graph,root)
        node=coin.SoSeparator();self.overlay[1].addChild(node)
        light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(.15,.5,.8);material.transparency=0;node.addChild(material)
        style=coin.SoDrawStyle();style.pointSize=9;style.lineWidth=2;node.addChild(style)
        for index,point in points:
            marker=coin.SoSeparator();node.addChild(marker)
            coordinates=coin.SoCoordinate3();coordinates.point.setValue(tuple(point));marker.addChild(coordinates)
            dot=coin.SoPointSet();dot.numPoints=1;marker.addChild(dot)
            translation=coin.SoTranslation();translation.translation=tuple(point);marker.addChild(translation)
            font=coin.SoFont();font.size=16;marker.addChild(font)
            label=coin.SoText2();label.string=str(index);marker.addChild(label)
        if len(points)>1:
            path=[tuple(point) for index,point in points]
            if len(path)==3:path.append(path[0])
            coordinates=coin.SoCoordinate3();coordinates.point.setValues(0,len(path),path);node.addChild(coordinates)
            line=coin.SoLineSet();line.numVertices.setValue(len(path));node.addChild(line)
        if self.valid:
            frame,center=planes.points_frame(self.refs['reference_a'],self.refs['reference_b'],self.refs['reference_c'],self.reverse.isChecked())
            normal=frame.Rotation.multVec(App.Vector(0,0,1));side=frame.Rotation.multVec(App.Vector(1,0,0));length=max(1,min(15,self.size.value()*.15))
            tip=center+normal*length
            path=[center,tip,tip-normal*length*.25+side*length*.12,tip,tip-normal*length*.25-side*length*.12]
            material=coin.SoMaterial();material.diffuseColor=(.16,.62,.4);material.transparency=0;node.addChild(material)
            coordinates=coin.SoCoordinate3();coordinates.point.setValues(0,len(path),[tuple(v) for v in path]);node.addChild(coordinates)
            line=coin.SoLineSet();line.numVertices.setValue(len(path));node.addChild(line)

    def offset_guide(self):
        values=self.parameters();frame,center,normal=planes.offset_frame(values['base'],values['reference_a'])
        length=max(1,min(15,values['size']*.15));tip=center+normal*length
        side=frame.Rotation.multVec(App.Vector(1,0,0))
        points=[center,tip,tip-normal*length*.25+side*length*.12,tip,tip-normal*length*.25-side*length*.12]
        node=coin.SoSeparator();self.overlay[1].addChild(node)
        light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(.16,.62,.4);material.transparency=0;node.addChild(material)
        style=coin.SoDrawStyle();style.lineWidth=3;node.addChild(style)
        coordinates=coin.SoCoordinate3();coordinates.point.setValues(0,len(points),[tuple(v) for v in points]);node.addChild(coordinates)
        line=coin.SoLineSet();line.numVertices.setValue(len(points));node.addChild(line)

    def tangent_guide(self):
        values=self.parameters();frame,center=planes.tangent_frame(values['reference_a'],values['angle'],values['reversed'])
        normal=frame.Rotation.multVec(App.Vector(0,0,1));side=frame.Rotation.multVec(App.Vector(1,0,0))
        length=max(1,min(15,values['size']*.15));tip=center+normal*length
        points=[center,tip,tip-normal*length*.25+side*length*.12,tip,tip-normal*length*.25-side*length*.12]
        node=coin.SoSeparator();self.overlay[1].addChild(node)
        light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(.16,.62,.4);material.transparency=0;node.addChild(material)
        style=coin.SoDrawStyle();style.lineWidth=3;style.pointSize=9;node.addChild(style)
        coordinates=coin.SoCoordinate3();coordinates.point.setValues(0,len(points),[tuple(v) for v in points]);node.addChild(coordinates)
        line=coin.SoLineSet();line.numVertices.setValue(len(points));node.addChild(line)
        dot=coin.SoPointSet();dot.numPoints=1;node.addChild(dot)

    def path_guide(self):
        values=self.parameters();frame,curve,distance=planes.path_frame(values['reference_a'],values['path_mode'],values['fraction'],values['path_distance'],values['path_reverse'],values['angle'],values['reversed'])
        node=coin.SoSeparator();self.overlay[1].addChild(node)
        light=coin.SoLightModel();light.model=coin.SoLightModel.BASE_COLOR;node.addChild(light)
        material=coin.SoMaterial();material.diffuseColor=(.15,.5,.8);material.transparency=0;node.addChild(material)
        style=coin.SoDrawStyle();style.lineWidth=2;style.pointSize=8;node.addChild(style)
        stations=sorted(set([curve.length*i/64 for i in range(65)]+[curve.length-s if values['path_reverse'] else s for s in curve.ends]))
        path=[tuple(curve.at(s,values['path_reverse'])[0]) for s in stations]
        coordinates=coin.SoCoordinate3();coordinates.point.setValues(0,len(path),path);node.addChild(coordinates)
        line=coin.SoLineSet();line.numVertices.setValue(len(path));node.addChild(line)
        marker=coin.SoSeparator();node.addChild(marker);coordinates=coin.SoCoordinate3();coordinates.point.setValue(path[0]);marker.addChild(coordinates)
        dot=coin.SoPointSet();dot.numPoints=1;marker.addChild(dot)
        translation=coin.SoTranslation();translation.translation=path[0];marker.addChild(translation)
        font=coin.SoFont();font.size=16;marker.addChild(font);label=coin.SoText2();label.string='S';marker.addChild(label)
        normal=frame.Rotation.multVec(App.Vector(0,0,1));side=frame.Rotation.multVec(App.Vector(1,0,0));center=frame.Base
        length=max(1,min(15,values['size']*.15));tip=center+normal*length
        points=[center,tip,tip-normal*length*.25+side*length*.12,tip,tip-normal*length*.25-side*length*.12]
        material=coin.SoMaterial();material.diffuseColor=(.16,.62,.4);node.addChild(material)
        coordinates=coin.SoCoordinate3();coordinates.point.setValues(0,len(points),[tuple(v) for v in points]);node.addChild(coordinates)
        line=coin.SoLineSet();line.numVertices.setValue(len(points));node.addChild(line)
        dot=coin.SoPointSet();dot.numPoints=1;node.addChild(dot)
        return curve.length,distance

    def update_preview(self):
        self.timer.stop()
        if not self.active:return
        if App.ActiveDocument!=self.doc:self.cancel();return
        self.clear_preview();self.valid=False;self.accept_button.setEnabled(False)
        angled=self.kind=='angle';mid=self.kind=='midplane';offset=self.kind=='offset';points=self.kind=='three_points';tangent=self.kind=='tangent';path=self.kind=='along_path'
        for widget in (self.path_all_button,self.path_mode,self.path_mode_label,self.path_reverse):widget.setVisible(path)
        self.path_all_button.setEnabled(bool(self.refs['reference_a']) and bool(self.refs['reference_a'][1]))
        for widget in (self.fraction,self.fraction_label):widget.setVisible(path and self.path_mode.currentData()=='fraction')
        for widget in (self.path_distance,self.path_distance_label):widget.setVisible(path and self.path_mode.currentData()=='distance')
        for widget in (self.base,self.base_label):widget.setVisible(not (mid or points or tangent or path))
        for widget in (self.axis,self.axis_label):widget.setVisible(angled)
        for widget in (self.angle,self.angle_label):widget.setVisible(angled or tangent or path)
        self.angle_label.setText(tr('面内の回転','In-plane Rotation') if path else tr('角度','Angle'))
        for widget in (self.distance,self.offset_label):widget.setVisible(offset)
        self.a_button.setVisible(mid or points or tangent or path or self.base.currentData()=='face');self.b_button.setVisible(mid or points)
        self.c_button.setVisible(points);self.reverse.setVisible(points or tangent or path)
        self.axis_button.setVisible(angled and self.axis.currentData()=='edge')
        if ((self.picking=='reference_a' and not self.a_button.isVisible()) or
                (self.picking=='axis_reference' and not self.axis_button.isVisible())):
            self.ticket+=1;self.picking=None
        for button,key,label in [(self.a_button,'reference_a',tr('経路','Path') if path else tr('曲面','Curved Face') if tangent else tr('点1','Point 1') if points else tr('面1','Face 1') if mid else tr('基準面','Reference Face')),
                                 (self.b_button,'reference_b',tr('点2','Point 2') if points else tr('面2','Face 2')),
                                 (self.c_button,'reference_c',tr('点3','Point 3')),(self.axis_button,'axis_reference',tr('軸の辺','Axis Edge'))]:
            ref=self.refs[key]
            try:description='%s / %s'%(ref[0].Label,ref[1] or tr('経路全体','Entire Path')) if ref and ref[0] else tr('選択','Select')
            except (ReferenceError,RuntimeError):description=tr('参照なし','Missing Reference')
            button.setText(label+': '+description);button.setToolTip(button.text());button.setStyleSheet('border:1px solid #258fbe;background:#e6f5ff;' if self.picking==key else '')
        try:
            values=self.parameters();planes.check_sources(self.doc,self.kind,self.existing,**values)
            shape=planes.build(self.kind,**values);self.show_shape(shape,'plane')
            if offset:self.offset_guide()
            if tangent:self.tangent_guide()
            if self.existing:self.hidden.append((self.existing,self.existing.Visibility));self.existing.Visibility=False
            self.status.setText(tr('この平面を選択して「スケッチを作成」で作図できます。','Select the finished plane and use Create Sketch to draw on it.'))
            if path:
                length,distance=self.path_guide();self.status.setText(tr('経路長: %.3f mm\n始点からの距離: %.3f mm\n確定後、平面を選んでスケッチを作成できます。','Path length: %.3f mm\nDistance from start: %.3f mm\nConfirm, then select the plane to create a sketch.')%(length,distance))
            self.status.setStyleSheet('color:#3c6f62;');self.valid=True;self.accept_button.setEnabled(not self.picking)
        except Exception as error:self.status.setText(str(error));self.status.setStyleSheet('color:#ac3830;')
        if points:self.point_guide()
        if self.picking:
            self.status.setText(tr('画面上の辺、またはブラウザーの経路スケッチを選択してください。','Click an edge in the view or select a path sketch in the browser.') if path else
                               tr('画面上の円柱または円すいの側面をクリックしてください。','Click a cylindrical or conical side face in the view.') if tangent else
                               tr('点%d：画面上の頂点またはスケッチの端点をクリックしてください。','Point %d: click a vertex or sketch endpoint in the view.')%(('reference_a','reference_b','reference_c').index(self.picking)+1) if points else
                               tr('画面上の直線辺をクリックしてください。','Click a straight edge in the view.') if self.picking=='axis_reference' else
                                tr('画面上の平らな面をクリックしてください。','Click a planar face in the view.'))
            self.status.setStyleSheet('color:#247c9c;')
        try:self.last_signature=self.signature()
        except (ReferenceError,RuntimeError):self.last_signature=None

    def detach(self):
        self.ticket+=1;self.picking=None
        if self.observing:Gui.Selection.removeObserver(self);self.observing=False

    def cancel(self):
        self.detach();super().cancel()

    def accept(self):
        if not self.active or self.picking:return
        for field in self.spins:field.interpretText()
        self.update_preview()
        if not self.valid:return
        try:
            self.clear_preview();result=planes.create(self.doc,self.kind,existing=self.existing,**self.parameters())
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
