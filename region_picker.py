"""Pick filled sketch profiles without adding selectable document objects."""
from i18n import tr
import math
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets as W
from pivy import coin
import model


class RegionPicker(QtCore.QObject):
    def __init__(self,workspace):
        super().__init__(workspace.main)
        self.ws = workspace
        self.enabled = True
        self.cache = {}
        self.selected = None
        self.selections = []
        self.overlay = None
        self.press = None
        self.ticket = 0

    def clear(self):
        if self.overlay:
            graph,node = self.overlay
            if graph.findChild(node)>=0:
                graph.removeChild(node)
        self.overlay = None
        self.selected = None
        self.selections = []

    def close(self):
        self.enabled = False
        self.ticket += 1
        self.clear()
        self.cache.clear()

    @staticmethod
    def signature(obj):
        return (obj.Shape.hashCode(),str(obj.getGlobalPlacement()))

    def refresh(self):
        if not self.selected:
            return
        docname,name,edges,signature = self.selected
        doc = App.ActiveDocument
        sels = Gui.Selection.getSelectionEx()
        obj = doc.getObject(name) if doc and doc.Name==docname else None
        if (self.ws.current_sketch() or not obj or not obj.Visibility or
            len(sels)!=1 or sels[0].Object!=obj or sels[0].SubElementNames or
            self.signature(obj)!=signature):
            self.clear()

    def chosen(self,obj,regions):
        indices = self.chosen_many(obj,regions)
        if len(indices)>1:
            raise ValueError(tr('この操作では領域を1つ選択してください。複数領域の選択は押し出しで使用できます。'))
        return indices[0] if indices else None

    def chosen_many(self,obj,regions):
        self.refresh()
        if self.selected and self.selected[:2]==(obj.Document.Name,obj.Name):
            return [model.profile_for_key(regions,entry[2]) for entry in self.selections]
        return []

    @staticmethod
    def ray(view,widget,point):
        node=view.getCameraNode()
        rotation=view.getCameraOrientation()
        position=App.Vector(*node.position.getValue().getValue())
        distance=node.focalDistance.getValue()
        height=node.height.getValue() if hasattr(node,'height') else 2*distance*math.tan(node.heightAngle.getValue()/2)
        scale=height/max(1,widget.height())
        x=(point.x()-widget.width()/2)*scale
        y=(widget.height()/2-point.y())*scale
        if hasattr(node,'height'):
            origin=position+rotation.multVec(App.Vector(x,y,0))
            direction=rotation.multVec(App.Vector(0,0,-1))
        else:
            origin=position
            direction=rotation.multVec(App.Vector(x,y,-distance))
            direction.normalize()
        return origin,direction

    def hit(self,widget,point):
        doc=App.ActiveDocument
        if not doc or self.ws.current_sketch():
            return None
        view=Gui.activeDocument().activeView()
        if not hasattr(view,'getCameraNode'):
            return None
        origin,direction=self.ray(view,widget,point)
        hits=[]
        live=set()
        for obj in doc.Objects:
            if obj.TypeId!='Sketcher::SketchObject' or not obj.Visibility:
                continue
            key=(doc.Name,obj.Name)
            live.add(key)
            signature=self.signature(obj)
            cached=self.cache.get(key)
            if not cached or cached[0]!=signature:
                try:
                    regions=model.profiles(obj)
                except (ValueError,PartError):
                    continue
                # Shape coordinates include the sketch's local Placement; apply parent containers too.
                delta=obj.getGlobalPlacement().multiply(obj.Placement.inverse())
                faces=[]
                for region in regions:
                    face=region['face'].copy()
                    face.Placement=delta.multiply(face.Placement)
                    faces.append((face,model.profile_key(region)))
                cached=(signature,faces)
                self.cache[key]=cached
            for face,edges in cached[1]:
                normal=face.normalAt(0,0)
                denominator=direction.dot(normal)
                if abs(denominator)<1e-9:
                    continue
                t=(face.CenterOfMass-origin).dot(normal)/denominator
                if t<0:
                    continue
                point3=origin+direction*t
                if face.isInside(point3,1e-6,True):
                    hits.append((t,obj,edges,signature,face))
        self.cache={k:v for k,v in self.cache.items() if k in live}
        if not hits:
            return None
        hit=min(hits,key=lambda h:h[0])
        # Respect visible solids in front of the sketch. Grid/highlight nodes are unpickable.
        action=coin.SoRayPickAction(coin.SbViewportRegion(widget.width(),widget.height()))
        action.setRay(coin.SbVec3f(*origin),coin.SbVec3f(*direction))
        action.setRadius(0)
        action.apply(view.getSceneGraph())
        picked=action.getPickedPoint()
        if picked:
            p=App.Vector(*picked.getPoint().getValue())
            if (p-origin).dot(direction)<hit[0]-1e-4:
                return None
        return hit

    def select(self,hit,add=False):
        t,obj,edges,signature,face=hit
        if not App.ActiveDocument or obj.Document!=App.ActiveDocument or self.signature(obj)!=signature:
            return
        entries = list(self.selections) if add else []
        key = (obj.Document.Name,obj.Name)
        if entries and entries[0][:2]!=key:
            self.ws.main.statusBar().showMessage(tr('複数領域は同じスケッチ内で選択してください。'),7000)
            return
        entry = (*key,edges,signature,face)
        if any(old[:3]==entry[:3] for old in entries):
            entries = [old for old in entries if old[:3]!=entry[:3]]
        else:
            entries.append(entry)
        self.restore(entries)

    def restore(self,entries):
        self.clear()
        Gui.Selection.clearSelection()
        if not entries:
            return
        doc=App.ActiveDocument
        docname,name,edges,signature,_=entries[0]
        obj=doc.getObject(name) if doc and doc.Name==docname else None
        if not obj or not obj.Visibility or self.signature(obj)!=signature:
            return
        Gui.Selection.addSelection(obj)
        self.selections=list(entries)
        self.selected=entries[0][:4]
        node=coin.SoSeparator()
        transparency=coin.SoTransparencyType()
        transparency.value=coin.SoTransparencyType.SORTED_OBJECT_BLEND
        node.addChild(transparency)
        pick=coin.SoPickStyle()
        pick.style=coin.SoPickStyle.UNPICKABLE
        node.addChild(pick)
        light=coin.SoLightModel()
        light.model=coin.SoLightModel.BASE_COLOR
        node.addChild(light)
        mat=coin.SoMaterial()
        mat.diffuseColor=(0.15,0.58,0.92)
        mat.transparency=0.60
        node.addChild(mat)
        for *_,face in entries:
            vertices,triangles=face.tessellate(0.1)
            coords=coin.SoCoordinate3()
            coords.point.setValues(0,len(vertices),[(v.x,v.y,v.z) for v in vertices])
            node.addChild(coords)
            mesh=coin.SoIndexedFaceSet()
            indices=[i for triangle in triangles for i in (*triangle,-1)]
            mesh.coordIndex.setValues(0,len(indices),indices)
            node.addChild(mesh)
        graph=Gui.activeDocument().activeView().getSceneGraph()
        graph.addChild(node)
        self.overlay=(graph,node)
        self.ws.main.statusBar().showMessage(tr('%d 領域を選択：合計 %.2f mm² — Ctrlで追加・解除 / 押し出し E') %
                                           (len(entries),sum(e[4].Area for e in entries)),7000)

    def eventFilter(self,widget,event):
        if getattr(getattr(self.ws,'cube',None),'forwarding',False):
            return False
        if Gui.Control.activeDialog() and not self.ws.current_sketch():
            self.press=None
            return False  # Native surface/measurement tasks own edge selection.
        if self.ws.hole_panel.active or self.ws.edge_panel.active or self.ws.split_panel.active or self.ws.combine_panel.active or self.ws.component_panel.active or self.ws.joint_panel.active or self.ws.primitive_panel.active or self.ws.path_pattern_panel.active or self.ws.construction_panel.active or self.ws.construction_axis_panel.active:
            return False
        if not self.enabled or self.ws.drag_move.active or self.ws.extrusion.active or self.ws.features.active or self.ws.transform.active or self.ws.alignment.active or self.ws.mesh_edit.active or self.ws.mesh_ops.active:
            return False
        kind=event.type()
        if kind==QtCore.QEvent.MouseButtonPress:
            self.ticket+=1
            if event.button()==QtCore.Qt.LeftButton and event.modifiers() in (QtCore.Qt.NoModifier,QtCore.Qt.ControlModifier) and not self.ws.current_sketch():
                point=event.position() if hasattr(event,'position') else event.pos()
                additive=event.modifiers()==QtCore.Qt.ControlModifier
                hit=self.hit(widget,point) if additive else None
                self.press=(widget,point,additive,hit)
                if hit:
                    # Native Ctrl selection would toggle the entire sketch off.
                    # Own only interior clicks; solid/edge Ctrl selection stays native.
                    return True
            else:
                self.press=None
        elif kind==QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.LeftButton:
            press=self.press
            self.press=None
            if press and press[0]==widget and event.modifiers() in (QtCore.Qt.NoModifier,QtCore.Qt.ControlModifier):
                point=event.position() if hasattr(event,'position') else event.pos()
                if press[3]:
                    if (point-press[1]).manhattanLength()<W.QApplication.startDragDistance():
                        self.select(press[3],add=True)
                    return True
                if press[2]:
                    return False
                if (point-press[1]).manhattanLength()<W.QApplication.startDragDistance():
                    ticket=self.ticket
                    # Let FreeCAD finish its ordinary click before applying profile selection.
                    def apply():
                        if (self.enabled and ticket==self.ticket and not self.ws.drag_move.active and not self.ws.extrusion.active and not self.ws.features.active
                                and not self.ws.transform.active and not self.ws.alignment.active and not self.ws.mesh_edit.active and not self.ws.mesh_ops.active and not self.ws.hole_panel.active and not self.ws.edge_panel.active and not self.ws.split_panel.active and not self.ws.combine_panel.active and not self.ws.component_panel.active and not self.ws.joint_panel.active and not self.ws.primitive_panel.active and not self.ws.path_pattern_panel.active and not self.ws.construction_panel.active and not self.ws.construction_axis_panel.active and not self.ws.current_sketch()):
                            self.ws.safe(pick)
                    def pick():
                        hit=self.hit(widget,point)
                        if hit: self.select(hit)
                        else: self.clear()
                    QtCore.QTimer.singleShot(0,apply)
        return False


# OCC errors inherit RuntimeError in supported FreeCAD builds.
PartError = RuntimeError
