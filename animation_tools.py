"""Camera turntable playback and transactional PNG sequence export."""
from pathlib import Path
import math,datetime,json,tempfile
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore,QtWidgets as W
from i18n import tr
import render_tools

def validate_motion(frames, fps, axis, degrees):
    if isinstance(frames, bool) or not isinstance(frames, int) or not (2 <= frames <= 240):
        raise ValueError(tr('アニメーション設定が無効です。','Invalid animation settings.'))
    if isinstance(fps, bool) or not isinstance(fps, int) or not (1 <= fps <= 60):
        raise ValueError(tr('アニメーション設定が無効です。','Invalid animation settings.'))
    if axis not in ['X', 'Y', 'Z']:
        raise ValueError(tr('アニメーション設定が無効です。','Invalid animation settings.'))
    if isinstance(degrees, bool) or not math.isfinite(degrees) or abs(degrees) > 3600:
        raise ValueError(tr('アニメーション設定が無効です。','Invalid animation settings.'))
    return float(degrees)

def frame_camera(view, camera, frame, frames, axis, degrees):
    deg = validate_motion(frames, 30, axis, degrees)
    if isinstance(frame, bool) or not isinstance(frame, int) or not (0 <= frame < frames):
        raise ValueError(tr('フレーム番号が無効です。','Invalid frame number.'))
    view.setAnimationEnabled(False)
    view.setCamera(camera)
    node = view.getCameraNode()
    position = App.Vector(*node.position.getValue().getValue())
    rotation = App.Rotation(*node.orientation.getValue().getValue())
    distance = node.focalDistance.getValue()
    center = position + rotation.multVec(App.Vector(0, 0, -distance))
    axes = {'X': App.Vector(1, 0, 0), 'Y': App.Vector(0, 1, 0), 'Z': App.Vector(0, 0, 1)}
    delta = App.Rotation(axes[axis], deg * frame / (frames - 1))
    point = center + delta.multVec(position - center)
    node.position.setValue(point.x, point.y, point.z)
    node.orientation.setValue(*delta.multiply(rotation).Q)
    view.redraw()

def write_sequence(ws,doc,view,camera,frames,fps,axis,degrees,width,height,background,folder,cancel=None,progress=None):
    degrees = validate_motion(frames,fps,axis,degrees)
    render_tools.validate_capture(ws,doc,width,height,background,'current')
    if Gui.activeDocument().activeView() != view:
        raise ValueError(tr('3Dビューが変更されました。','The 3D view changed.'))
    destination = Path(folder)
    if not destination.is_dir():
        raise ValueError(tr('保存先フォルダがありません。','Output folder does not exist.'))
    saved = view.getCamera()
    animation = view.isAnimationEnabled()
    target = destination / ('FluxCAD-animation-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    if target.exists():
        raise FileExistsError(str(target))
    try:
        with tempfile.TemporaryDirectory(prefix='.fluxcad-animation-',dir=str(destination)) as temporary:
            stage = Path(temporary) / 'frames'
            stage.mkdir()
            names = []
            for index in range(frames):
                if cancel and cancel():
                    return None
                if App.ActiveDocument != doc or Gui.activeDocument().activeView() != view:
                    raise ValueError(tr('対象文書またはビューが変更されました。','The document or view changed.'))
                frame_camera(view,camera,index,frames,axis,degrees)
                Gui.updateGui()
                if cancel and cancel():
                    return None
                image = render_tools.capture(ws,doc,width,height,background,'current',False)
                name = 'frame-%04d.png' % index
                if not image.save(str(stage/name),'PNG'):
                    raise RuntimeError(tr('画像を保存できません。','Cannot save image.'))
                names.append(name)
                if progress:
                    progress(index+1,frames)
            if cancel and cancel():
                return None
            manifest = dict(version=1,frames=names,fps=fps,axis=axis,degrees=degrees,width=width,height=height,background=background,kind='camera-orbit',duration_seconds=frames/fps)
            (stage/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
            if target.exists():
                raise FileExistsError(str(target))
            stage.rename(target)
            return target
    finally:
        if any(candidate is doc for candidate in App.listDocuments().values()):
            try:
                view.setCamera(saved)
                view.setAnimationEnabled(animation)
                view.redraw()
            except (RuntimeError,ReferenceError):
                pass

class AnimationDialog(W.QDialog):
    def __init__(self,ws):
        super().__init__(ws.main)
        self.ws=ws
        self.doc=App.ActiveDocument
        self.view=Gui.activeDocument().activeView()
        self.camera=self.view.getCamera()
        self.animation=self.view.isAnimationEnabled()
        self.exporting=False
        self.timer=QtCore.QTimer(self)
        self.timer.timeout.connect(self.step)
        self.setWindowTitle(tr('アニメーション','Animation'))
        self.setModal(True)
        self.resize(380,460)
        layout=W.QVBoxLayout(self)
        note=W.QLabel(tr('モデルの周囲をカメラが回転します。部品やジョイントは動かしません。','Orbit the camera around the model. Parts and joints remain fixed.'))
        note.setWordWrap(True)
        layout.addWidget(note)
        form=W.QFormLayout()
        self.axis=W.QComboBox()
        for key in ('X','Y','Z'):
            self.axis.addItem(key,key)
        self.axis.setCurrentIndex(2)
        form.addRow(tr('回転軸','Axis'),self.axis)
        self.degrees=W.QDoubleSpinBox()
        self.degrees.setRange(-3600,3600)
        self.degrees.setDecimals(1)
        self.degrees.setValue(360)
        self.degrees.setSuffix(' °')
        form.addRow(tr('回転角度','Rotation Angle'),self.degrees)
        for name,ja,en,low,high,value in [('frames','フレーム数','Frames',2,240,120),('fps','再生速度 (fps)','Playback (fps)',1,60,30),('width_spin','画像の幅 (px)','Image Width (px)',64,2048,640),('height_spin','画像の高さ (px)','Image Height (px)',64,2048,480)]:
            widget=W.QSpinBox()
            widget.setRange(low,high)
            widget.setValue(value)
            setattr(self,name,widget)
            form.addRow(tr(ja,en),widget)
        self.background=W.QComboBox()
        for ja,en,key in [('白','White','White'),('透明','Transparent','Transparent'),('現在の背景','Current','Current')]:
            self.background.addItem(tr(ja,en),key)
        form.addRow(tr('書き出し背景','Export Background'),self.background)
        layout.addLayout(form)
        self.slider=W.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0,119)
        self.slider.valueChanged.connect(self.seek)
        self.position_label=W.QLabel('1 / 120')
        self.status=W.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.slider)
        layout.addWidget(self.position_label)
        layout.addWidget(self.status)
        row=W.QHBoxLayout()
        for name,ja,en,callback in [('play_button','再生','Play',self.play),('pause_button','一時停止','Pause',self.pause),('stop_button','最初に戻す','Reset',self.stop)]:
            button=W.QPushButton(tr(ja,en))
            button.clicked.connect(callback)
            setattr(self,name,button)
            row.addWidget(button)
        layout.addLayout(row)
        self.export_button=W.QPushButton(tr('PNG連番を書き出し…','Export PNG Sequence…'))
        self.export_button.clicked.connect(self.export_frames)
        self.close_button=W.QPushButton(tr('閉じる','Close'))
        self.close_button.clicked.connect(self.reject)
        layout.addWidget(self.export_button)
        layout.addWidget(self.close_button)
        self.frames.valueChanged.connect(self.settings_changed)
        self.axis.currentIndexChanged.connect(self.settings_changed)
        self.degrees.valueChanged.connect(self.settings_changed)
        self.fps.valueChanged.connect(self.settings_changed)

    def restore(self):
        self.timer.stop()
        if not any(candidate is self.doc for candidate in App.listDocuments().values()):
            return
        try:
            self.view.setCamera(self.camera)
            self.view.setAnimationEnabled(self.animation)
            self.view.redraw()
        except (RuntimeError,ReferenceError):
            pass

    def seek(self, value):
        if self.exporting:
            return
        try:
            render_tools.validate_capture(self.ws, self.doc, 64, 64, 'White', 'current')
            if Gui.activeDocument().activeView() != self.view:
                raise ValueError(tr('3Dビューが変更されました。','The 3D view changed.'))
            frame_camera(self.view, self.camera, value, self.frames.value(), self.axis.currentData(), self.degrees.value())
            self.position_label.setText('%d / %d' % (value + 1, self.frames.value()))
            self.status.clear()
        except Exception as error:
            self.restore()
            self.status.setText(str(error))

    def play(self):
        if self.exporting:
            return
        self.seek(self.slider.value())
        if self.status.text():
            return
        if self.slider.value() == self.slider.maximum():
            self.slider.setValue(0)
        self.timer.start(max(1, round(1000 / self.fps.value())))
        self.status.setText(tr('再生中','Playing'))

    def pause(self):
        self.timer.stop()

    def stop(self):
        if self.exporting:
            return
        self.restore()
        self.slider.blockSignals(True)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.position_label.setText('1 / %d' % self.frames.value())
        self.status.setText(tr('最初の視点に戻しました。','Restored the starting view.'))

    def step(self):
        if self.slider.value() >= self.slider.maximum():
            self.pause()
            self.status.setText(tr('再生が終了しました。','Playback complete.'))
            return
        self.slider.setValue(self.slider.value() + 1)

    def settings_changed(self, *args):
        if self.exporting:
            return
        self.pause()
        self.slider.blockSignals(True)
        self.slider.setRange(0, self.frames.value() - 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.seek(0)

    def reject(self):
        if self.exporting:
            return
        self.restore()
        W.QDialog.reject(self)

    def closeEvent(self, event):
        if self.exporting:
            event.ignore()
            return
        self.restore()
        event.accept()

    def export_frames(self):
        if self.exporting:
            return
        self.pause()
        folder = W.QFileDialog.getExistingDirectory(self, tr('PNG 連番の保存先', 'PNG Sequence Destination'))
        if not folder:
            return
        self.exporting = True
        progress = W.QProgressDialog(tr('画像を書き出しています…', 'Exporting frames…'), tr('キャンセル', 'Cancel'), 0, self.frames.value(), self)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        def update(done, total):
            progress.setValue(done)
            W.QApplication.processEvents()

        try:
            path = write_sequence(self.ws, self.doc, self.view, self.camera, self.frames.value(), self.fps.value(), self.axis.currentData(), self.degrees.value(), self.width_spin.value(), self.height_spin.value(), self.background.currentData(), folder, cancel=progress.wasCanceled, progress=update)
            if path is None:
                self.status.setText(tr('書き出しを取り消しました。', 'Export cancelled.'))
            else:
                self.status.setText(tr('保存しました：', 'Saved: ') + str(path))
        except Exception as error:
            self.status.setText(str(error))
        finally:
            progress.close()
            self.exporting = False

def show(ws):
    render_tools.validate_capture(ws, App.ActiveDocument, 64, 64, 'White', 'current')
    prior = getattr(ws, 'animation_dialog', None)
    if prior and prior.isVisible():
        prior.raise_()
        prior.activateWindow()
        return prior
    from motion_tools import MotionAnimationDialog
    dialog = MotionAnimationDialog(ws)
    ws.animation_dialog = dialog
    available = dialog.screen().availableGeometry()
    parent = ws.main.frameGeometry()
    x = max(available.left(), min(parent.right() - dialog.width() - 16, available.right() - dialog.width() - 16))
    y = max(available.top() + 16, min(parent.top() + 150, available.bottom() - dialog.height() - 40))
    dialog.move(x, y)
    dialog.show()
    return dialog
