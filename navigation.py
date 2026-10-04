"""Fusion-style viewport navigation, shared by solid and sketch editing."""
import math
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from pivy import coin


class FusionMouse(QtCore.QObject):
    def __init__(self,parent,workspace=None):
        super().__init__(parent)
        self.workspace = workspace
        self.enabled = True
        self.last = None
        self.owner = None
        self.pivot = None
        self.mode = None
        self.params = App.ParamGet('User parameter:BaseApp/Preferences/FluxCAD/Navigation')
        self.reverse_zoom = self.params.GetBool('ReverseZoom',False)
        self.free_orbit = self.params.GetBool('FreeOrbit',True)

    def preference(self,name,value):
        if name == 'ReverseZoom':
            self.reverse_zoom = value
        else:
            self.free_orbit = value
        self.params.SetBool(name,value)

    def cancel(self):
        self.last = self.owner = self.pivot = self.mode = None

    @staticmethod
    def position(event):
        return event.position() if hasattr(event,'position') else event.pos()

    @staticmethod
    def camera_height(node):
        if hasattr(node,'height'):
            return node.height.getValue()
        return 2*node.focalDistance.getValue()*math.tan(node.heightAngle.getValue()/2)

    @staticmethod
    def center(view):
        import model_mesh
        bounds = App.BoundBox()
        selected = Gui.Selection.getSelectionEx()
        shapes = [sub for selection in selected for sub in selection.SubObjects if hasattr(sub,'BoundBox')]
        if not shapes:
            objects = Gui.Selection.getSelection() or [o for o in App.ActiveDocument.Objects if (hasattr(o,'Shape') or model_mesh.is_mesh(o)) and o.Visibility]
            for obj in objects:
                if model_mesh.is_mesh(obj):bounds.add(model_mesh.world_mesh(obj).BoundBox)
            shapes = [o.Shape for o in objects if hasattr(o,'Shape')]
        for shape in shapes:
            if not shape.isNull():
                bounds.add(shape.BoundBox)
        if bounds.isValid():
            return bounds.Center
        node = view.getCameraNode()
        p = App.Vector(*node.position.getValue().getValue())
        return p + view.getCameraOrientation().multVec(App.Vector(0,0,-node.focalDistance.getValue()))

    def zoom(self,view,widget,pos,factor):
        node = view.getCameraNode()
        camera = view.getCameraOrientation()
        height = self.camera_height(node)
        new_height = max(0.001,min(1e8,height*factor))
        factor = new_height / max(height,1e-12)
        p = App.Vector(*node.position.getValue().getValue())
        distance = node.focalDistance.getValue()
        scale = height/max(1,widget.height())
        offset = camera.multVec(App.Vector((pos.x()-widget.width()/2)*scale,
                                          (widget.height()/2-pos.y())*scale,0))
        if hasattr(node,'height'):
            p += offset*(1-factor)
            node.height = new_height
        else:
            anchor = p + camera.multVec(App.Vector(0,0,-distance)) + offset
            p = anchor + (p-anchor)*factor
            node.focalDistance = distance*factor
        node.position.setValue(p.x,p.y,p.z)

    def orbit(self, view, pivot, dx, dy):
        node = view.getCameraNode()
        rotation = view.getCameraOrientation()
        p = App.Vector(*node.position.getValue().getValue())
        up = rotation.multVec(App.Vector(0,1,0)) if self.free_orbit else App.Vector(0,0,1)
        right = rotation.multVec(App.Vector(1,0,0))
        delta = App.Rotation(up,-dx*.4).multiply(App.Rotation(right,-dy*.4))
        p = pivot + delta.multVec(p-pivot)
        node.orientation.setValue(*delta.multiply(rotation).Q)
        node.position.setValue(p.x,p.y,p.z)

    def eventFilter(self,widget,event):
        kind = event.type()
        if kind in (QtCore.QEvent.WindowDeactivate,QtCore.QEvent.Hide,QtCore.QEvent.UngrabMouse):
            if widget == self.owner:
                self.cancel()
            return False
        if not self.enabled or not Gui.activeDocument():
            self.cancel()
            return False
        view = Gui.activeDocument().activeView()
        if not hasattr(view,'getCameraNode'):
            return False
        if kind == QtCore.QEvent.KeyPress and event.key()==QtCore.Qt.Key_Escape and self.last is not None:
            self.cancel()
            return True
        if kind == QtCore.QEvent.MouseButtonDblClick and event.button()==QtCore.Qt.MiddleButton:
            self.cancel()
            if self.workspace:
                self.workspace.fit()
            return True
        if kind == QtCore.QEvent.Wheel:
            delta = event.angleDelta().y()
            if not delta:
                delta = event.pixelDelta().y()*3
            if delta:
                factor = math.exp(max(-2,min(2,delta*(-1 if not self.reverse_zoom else 1)*0.0015)))
                self.zoom(view,widget,self.position(event),factor)
                if self.workspace:
                    self.workspace.grid.update()
            return True
        if kind == QtCore.QEvent.MouseButtonPress and event.button()==QtCore.Qt.MiddleButton:
            self.last = self.position(event)
            self.owner = widget
            self.pivot = self.center(view)
            self.mode = None
            return True
        if kind == QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.MiddleButton:
            self.cancel()
            return True
        if kind != QtCore.QEvent.MouseMove or self.last is None:
            return False
        if widget != self.owner:
            return False
        if not event.buttons() & QtCore.Qt.MiddleButton:
            self.cancel()
            return False
        pos = self.position(event)
        dx,dy = pos.x()-self.last.x(),pos.y()-self.last.y()
        self.last = pos
        mods = event.modifiers()
        mode = 'zoom' if mods & QtCore.Qt.ShiftModifier and mods & QtCore.Qt.ControlModifier else ('orbit' if mods & QtCore.Qt.ShiftModifier else 'pan')
        if mode=='orbit' and self.mode!='orbit':
            self.pivot=self.center(view)
        self.mode=mode
        node=view.getCameraNode()
        rotation=view.getCameraOrientation()
        p=App.Vector(*node.position.getValue().getValue())
        if mode=='zoom':
            factor=math.exp(max(-2,min(2,dy*0.01*(-1 if self.reverse_zoom else 1))))
            self.zoom(view,widget,pos,factor)
        elif mode=='orbit':
            self.orbit(view,self.pivot,dx,dy)
        else:
            scale=self.camera_height(node)/max(1,widget.height())
            p+=rotation.multVec(App.Vector(-dx*scale,dy*scale,0))
            node.position.setValue(p.x,p.y,p.z)
        if self.workspace:
            self.workspace.grid.update()
        return True
