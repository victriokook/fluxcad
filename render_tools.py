"""Native image rendering with transient camera/grid changes and atomic PNG output."""
from pathlib import Path
import tempfile, os
import FreeCAD as App
import FreeCADGui as Gui
from FreeCADGui import Control
from PySide import QtCore, QtGui, QtWidgets as W
from i18n import tr

def validate_capture(ws, doc, width, height, background, camera):
    if doc is None or App.ActiveDocument != doc:
        raise ValueError(tr('対象文書が変更されました。', 'The active document changed.'))
    if ws.current_sketch() or Control.activeDialog():
        raise ValueError(tr('編集中の操作を終了してください。', 'Finish the active edit first.'))
    view = Gui.activeDocument().activeView()
    if not hasattr(view, 'getCamera'):
        raise ValueError(tr('3Dビューを開いてください。', 'Open a 3D view.'))
    for dimension in (width, height):
        if isinstance(dimension, bool) or not isinstance(dimension, int) or not 64 <= dimension <= 2048:
            raise ValueError(tr('画像サイズは64〜2048ピクセルです。', 'Image dimensions must be 64 to 2048 pixels.'))
    if background not in ('White', 'Transparent', 'Current') or camera not in ('current', 'iso', 'front', 'top', 'right'):
        raise ValueError(tr('背景または視点が無効です。', 'Invalid background or camera.'))
    visible = False
    for obj in doc.Objects:
        if obj.ViewObject.isVisible() and ((hasattr(obj, 'Shape') and not obj.Shape.isNull()) or (hasattr(obj, 'Mesh') and obj.Mesh.CountFacets > 0)):
            visible = True
            break
    if not visible:
        raise ValueError(tr('表示中の形状がありません。', 'No geometry is visible.'))
    return view

def capture(ws,doc,width,height,background='White',camera='current',smooth=True):
    view=validate_capture(ws,doc,width,height,background,camera)
    saved=view.getCamera()
    animation=view.isAnimationEnabled()
    view.setAnimationEnabled(False)
    selection=Gui.Selection.getSelectionEx()
    factor=2 if smooth else 1
    try:
        Gui.Selection.clearSelection()
        with ws.grid.excluded():
            with tempfile.TemporaryDirectory() as folder:
                if camera != 'current':
                    methods = {'iso': view.viewAxonometric, 'front': view.viewFront, 'top': view.viewTop, 'right': view.viewRight}
                    methods[camera]()
                    view.fitAll()
                view.redraw()
                path=Path(folder)/'render.png'
                view.saveImage(str(path),width*factor,height*factor,background)
                image=QtGui.QImage(str(path))
                if image.isNull() or image.width()!=width*factor or image.height()!=height*factor:
                    raise RuntimeError(tr('画像の生成に失敗しました。','Image generation failed.'))
                if factor==2:
                    image=image.scaled(width,height,QtCore.Qt.IgnoreAspectRatio,QtCore.Qt.SmoothTransformation)
                return image.copy()
    finally:
        view.setCamera(saved)
        view.setAnimationEnabled(animation)
        view.redraw()
        Gui.Selection.clearSelection()
        for selected in selection:
            if selected.SubElementNames:
                for name in selected.SubElementNames:
                    Gui.Selection.addSelection(selected.Object,name)
            else:
                Gui.Selection.addSelection(selected.Object)

class RenderDialog(W.QDialog):
    def __init__(self, ws):
        super().__init__(ws.main)
        self.ws = ws
        self.doc = App.ActiveDocument
        self.image = None
        self.signature = None
        self.setWindowTitle(tr('レンダリング','Rendering'))
        self.resize(600, 620)
        self.setModal(True)
        
        layout = W.QVBoxLayout()
        
        note = W.QLabel(tr('表示中のモデルをPNG画像にします。反射・影の物理計算は行いません。','Create a PNG of visible models. Physically based reflections and shadows are not calculated.'))
        note.setWordWrap(True)
        layout.addWidget(note)
        
        form_layout = W.QFormLayout()
        
        self.width_spin = W.QSpinBox()
        self.width_spin.setRange(64, 2048)
        self.width_spin.setValue(1280)
        form_layout.addRow(tr('幅 (px)','Width (px)'), self.width_spin)
        
        self.height_spin = W.QSpinBox()
        self.height_spin.setRange(64, 2048)
        self.height_spin.setValue(720)
        form_layout.addRow(tr('高さ (px)','Height (px)'), self.height_spin)
        
        self.background = W.QComboBox()
        self.background.addItem(tr('白','White'), 'White')
        self.background.addItem(tr('透明','Transparent'), 'Transparent')
        self.background.addItem(tr('現在の背景','Current'), 'Current')
        form_layout.addRow(tr('背景','Background'), self.background)
        
        self.camera = W.QComboBox()
        self.camera.addItem(tr('現在の視点','Current View'), 'current')
        self.camera.addItem(tr('等角投影','Isometric'), 'iso')
        self.camera.addItem(tr('正面','Front'), 'front')
        self.camera.addItem(tr('上面','Top'), 'top')
        self.camera.addItem(tr('右側面','Right'), 'right')
        form_layout.addRow(tr('視点','Camera'), self.camera)
        
        self.smooth = W.QCheckBox(tr('輪郭を滑らかにする','Smooth Edges'))
        self.smooth.setChecked(True)
        form_layout.addRow(self.smooth)
        
        layout.addLayout(form_layout)
        
        self.preview = W.QLabel()
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.preview.setMinimumHeight(240)
        self.preview.setScaledContents(False)
        layout.addWidget(self.preview)
        
        self.status = W.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        
        button_layout = W.QHBoxLayout()
        
        self.preview_button = W.QPushButton(tr('プレビュー','Preview'))
        self.preview_button.clicked.connect(self.render_preview)
        button_layout.addWidget(self.preview_button)
        
        self.save_button = W.QPushButton(tr('PNG画像を保存…','Save PNG…'))
        self.save_button.clicked.connect(self.save_image)
        button_layout.addWidget(self.save_button)
        
        self.close_button = W.QPushButton(tr('閉じる','Close'))
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

    def settings(self):
        return (self.width_spin.value(), self.height_spin.value(), self.background.currentData(), self.camera.currentData(), self.smooth.isChecked())

    def render_preview(self):
        try:
            image = capture(self.ws, self.doc, *self.settings())
            self.image = image
            self.signature = self.settings()
            pixmap = QtGui.QPixmap.fromImage(image).scaled(520, 280, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.preview.setPixmap(pixmap)
            status_text = f"{self.width_spin.value()}x{self.height_spin.value()} px"
            self.status.setText(status_text)
            return True
        except Exception as e:
            self.image = None
            self.signature = None
            self.preview.clear()
            self.status.setText(str(e))
            return False


    def save_image(self):
        try:
            if self.doc != App.ActiveDocument:
                raise ValueError(tr('対象文書が変更されました。','The active document changed.'))
            if not self.render_preview():
                return
            file_path, _ = W.QFileDialog.getSaveFileName(self, tr('PNG画像を保存','Save PNG'), '', 'PNG (*.png)')
            if not file_path:
                return
            original = file_path
            if not file_path.lower().endswith('.png'):
                file_path += '.png'
            if file_path != original and os.path.exists(file_path):
                answer = W.QMessageBox.question(self, tr('上書き確認','Confirm Overwrite'), tr('既存の画像を上書きしますか？','Overwrite the existing image?'), W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
                if answer != W.QMessageBox.Yes:
                    return
            save_file = QtCore.QSaveFile(file_path)
            if not save_file.open(QtCore.QIODevice.WriteOnly):
                raise RuntimeError(save_file.errorString())
            try:
                if not self.image.save(save_file, 'PNG'):
                    raise RuntimeError(tr('PNG画像を保存できません。','Cannot save PNG image.'))
                if not save_file.commit():
                    raise RuntimeError(save_file.errorString())
            except Exception:
                save_file.cancelWriting()
                raise
            self.status.setText(tr('保存しました：','Saved: ') + file_path)
        except Exception as error:
            self.status.setText(str(error))

def show(ws):
    if App.ActiveDocument is None:
        raise ValueError(tr('文書が開いていません。','No document open.'))
    doc = App.ActiveDocument
    if ws.current_sketch() or Gui.Control.activeDialog():
        raise ValueError(tr('編集を完了させてください。','Finish editing first.'))
    if not hasattr(Gui.activeDocument().activeView(), 'getCamera'):
        raise ValueError(tr('3Dビューを開いてください。','Open a 3D view.'))
    prior = getattr(ws, 'render_dialog', None)
    if prior and prior.isVisible():
        prior.raise_()
        prior.activateWindow()
        return prior
    dialog = RenderDialog(ws)
    ws.render_dialog = dialog
    dialog.show()
    return dialog
