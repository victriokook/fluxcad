"""Scene-only blue motion copies; original bodies remain fixed and untouched."""
import math
import FreeCAD as App
import FreeCADGui as Gui
from pivy import coin
from i18n import tr
import model,animation_tools,render_tools
import json,tempfile
from pathlib import Path
from datetime import datetime
from PySide import QtCore,QtWidgets as W

def source_visible(source):
    try:
        seen = set()
        while source is not None:
            if source.Name in seen or not source.ViewObject.isVisible():
                return False
            seen.add(source.Name)
            source = source.getParentGeoFeatureGroup()
        return True
    except (RuntimeError, ReferenceError, AttributeError):
        return False

class MotionPreview:
    def __init__(self, ws, source):
        if not source or source.Document != App.ActiveDocument or not hasattr(source,'Shape') or not source_visible(source) or not source.Shape.Solids or not source.Shape.isValid() or getattr(source,'FluxCADInternal',False) or source.TypeId=='Sketcher::SketchObject':
            raise ValueError(tr('表示中のソリッドボディを選択してください。','Select a visible solid body.'))
        self.ws = ws
        self.doc = source.Document
        self.name = source.Name
        self.source = source
        self.shape = source.Shape
        self.pose = list(source.getGlobalPlacement().toMatrix().A)
        self.view = Gui.activeDocument().activeView()
        self.graph = self.view.getSceneGraph()
        self.closed = False
        self.last = (0, 2, 'Z', 0, 0, 0, 0)
        world = model.world_shape(source)
        self.pivot = world.BoundBox.Center
        self.radius = world.BoundBox.DiagonalLength / 2
        vertices, facets = world.tessellate(max(0.05, world.BoundBox.DiagonalLength / 250))
        if not vertices or not facets or len(vertices) > 200000 or len(facets) > 300000:
            raise ValueError(tr('表示コピーの形状が大きすぎます。','Preview geometry exceeds limits.'))
        self.switch = coin.SoSwitch()
        self.switch.whichChild = coin.SO_SWITCH_NONE
        branch = coin.SoSeparator()
        self.transform = coin.SoTransform()
        branch.addChild(self.transform)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        branch.addChild(pick)
        material = coin.SoMaterial()
        material.diffuseColor = (.15, .65, 1.0)
        material.transparency = .25
        branch.addChild(material)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(vertices), [tuple(v) for v in vertices])
        branch.addChild(coords)
        faces = coin.SoIndexedFaceSet()
        indices = [number for tri in facets for number in (*tri, -1)]
        faces.coordIndex.setValues(0, len(indices), indices)
        branch.addChild(faces)
        self.switch.addChild(branch)
        self.graph.addChild(self.switch)

    def check(self):
        if self.closed or App.ActiveDocument != self.doc or self.doc.getObject(self.name) != self.source or Gui.activeDocument().activeView() != self.view:
            raise ValueError(tr('対象文書またはボディが変更されました。','The document or body changed.'))
        if not self.source.Shape.isSame(self.shape) or max(abs(a - b) for a, b in zip(self.source.getGlobalPlacement().toMatrix().A, self.pose)) > 1e-7 or not source_visible(self.source):
            raise ValueError(tr('元形状または配置が変更されました。','The source geometry or placement changed.'))
        return None

    def update(self, frame, frames, axis, degrees, dx, dy, dz):
        self.check()
        degrees = animation_tools.validate_motion(frames, 30, axis, degrees)
        if isinstance(frame,bool) or not isinstance(frame, int) or frame < 0 or frame >= frames:
            raise ValueError(tr('フレーム番号が無効です。','Invalid frame number.'))
        for val in (dx, dy, dz):
            if isinstance(val,bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or abs(val) > 10000:
                raise ValueError(tr('移動量は有限の±10000 mm以内にしてください。','Translation must be finite and within +/-10000 mm.'))
        u = frame / (frames - 1)
        axes_dict = {'X':App.Vector(1,0,0),'Y':App.Vector(0,1,0),'Z':App.Vector(0,0,1)}
        rotation = App.Rotation(axes_dict[axis], degrees * u)
        self.transform.center.setValue(*tuple(self.pivot))
        self.transform.rotation.setValue(*rotation.Q)
        self.transform.translation.setValue(dx * u, dy * u, dz * u)
        unchanged = abs(math.sin(math.radians(degrees * u) / 2)) < 1e-9 and max(abs(dx * u), abs(dy * u), abs(dz * u)) < 1e-9
        self.switch.whichChild = coin.SO_SWITCH_NONE if unchanged else coin.SO_SWITCH_ALL
        self.last = (frame, frames, axis, degrees, dx, dy, dz)
        self.view.redraw()

    def close(self):
        if self.closed:
            return
        try:
            index = self.graph.findChild(self.switch)
            if index >= 0:
                self.graph.removeChild(index)
        except (RuntimeError, ReferenceError):
            pass
        finally:
            self.closed = True

    def fit(self, ws, dx, dy, dz):
        self.check()
        radius=self.radius
        for val in (dx, dy, dz):
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or abs(val) > 10000:
                raise ValueError(tr('移動量が無効です。','Invalid translation.'))
        pivot = tuple(self.pivot)
        low = [min(p, p + d) - radius for p, d in zip(pivot, (dx, dy, dz))]
        high = [max(p, p + d) + radius for p, d in zip(pivot, (dx, dy, dz))]
        center = [(low[i] + high[i]) / 2.0 for i in range(3)]
        widths = [max(.001,high[i] - low[i]) for i in range(3)]
        group = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        group.addChild(pick)
        style = coin.SoDrawStyle()
        style.style = coin.SoDrawStyle.INVISIBLE
        group.addChild(style)
        transform = coin.SoTransform()
        transform.translation.setValue(*center)
        group.addChild(transform)
        cube = coin.SoCube()
        cube.width = widths[0]
        cube.height = widths[1]
        cube.depth = widths[2]
        group.addChild(cube)
        self.graph.addChild(group)
        animation = self.view.isAnimationEnabled()
        self.view.setAnimationEnabled(False)
        try:
            ws.fit()
        finally:
            self.graph.removeChild(group)
            self.view.setAnimationEnabled(animation)

def write_motion_sequence(session, frames, fps, axis, degrees, dx, dy, dz, width, height, background, folder, cancel=None, progress=None):
    session.check()
    degrees = animation_tools.validate_motion(frames, fps, axis, degrees)
    for val in (dx, dy, dz):
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or abs(val) > 10000:
            raise ValueError(tr('移動量が無効です。', 'Invalid translation.'))
    render_tools.validate_capture(session.ws, session.doc, width, height, background, 'current')
    destination = Path(folder)
    if not destination.is_dir():
        raise ValueError(tr('保存先フォルダがありません。', 'Output folder does not exist.'))
    saved = session.view.getCamera()
    animation = session.view.isAnimationEnabled()
    last = session.last
    target = destination / ('FluxCAD-motion-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    try:
        with tempfile.TemporaryDirectory(prefix='.fluxcad-motion-', dir=str(destination)) as temporary:
            stage = Path(temporary) / 'frames'
            stage.mkdir()
            names = []
            for index in range(frames):
                if cancel and cancel():
                    return None
                session.update(index, frames, axis, degrees, dx, dy, dz)
                Gui.updateGui()
                session.check()
                if cancel and cancel():
                    return None
                image = render_tools.capture(session.ws, session.doc, width, height, background, 'current', False)
                name = 'frame-%04d.png' % index
                if not image.save(str(stage / name), 'PNG'):
                    raise RuntimeError(tr('画像を保存できません。', 'Cannot save image.'))
                names.append(name)
                if progress:
                    progress(index + 1, frames)
            if cancel and cancel():
                return None
            manifest = dict(version=1, kind='display-copy-motion', source=session.name, original_visible=True, pivot=list(session.pivot), translation=[dx, dy, dz], axis=axis, degrees=degrees, frames=names, fps=fps, width=width, height=height, background=background, duration_seconds=frames / fps)
            (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            if target.exists():
                raise FileExistsError(str(target))
            stage.rename(target)
            return target
    finally:
        if not session.closed:
            try:
                session.update(*last)
            except (ValueError, RuntimeError, ReferenceError):
                session.close()
        if any(doc is session.doc for doc in App.listDocuments().values()):
            try:
                session.view.setCamera(saved)
                session.view.setAnimationEnabled(animation)
                session.view.redraw()
            except (RuntimeError, ReferenceError):
                pass


class MotionAnimationDialog(animation_tools.AnimationDialog):
    def __init__(self,ws):
        self.motion=None
        self.mode=None
        super().__init__(ws)
        self.context_timer=QtCore.QTimer(self)
        self.context_timer.setInterval(200)
        self.context_timer.timeout.connect(self.check_context)
        self.base_note=self.layout().itemAt(0).widget()
        self.camera_note=self.base_note.text()
        self.mode=W.QComboBox()
        self.mode.addItem(tr('カメラ回転','Camera Orbit'),'camera')
        self.mode.addItem(tr('部品の移動・回転（表示コピー）','Part Motion (Display Copy)'),'part')
        self.layout().insertWidget(0,self.mode)
        self.part_box=W.QGroupBox(tr('表示コピーの設定','Display Copy Settings'))
        form=W.QFormLayout(self.part_box)
        self.source=W.QComboBox()
        for obj in source_candidates(self.doc):
            if hasattr(obj,'Shape') and obj.Shape.Solids and source_visible(obj) and not getattr(obj,'FluxCADInternal',False):
                self.source.addItem(obj.Label+' ['+obj.Name+']',obj.Name)
        selected=Gui.Selection.getSelection()
        if len(selected)==1:
            index=self.source.findData(selected_source_name(self.doc, selected))
            if index>=0:
                self.source.setCurrentIndex(index)
        form.addRow(tr('対象ボディ','Target Body'),self.source)
        for name,label,value in [('dx','X',30),('dy','Y',0),('dz','Z',0)]:
            field=W.QDoubleSpinBox()
            field.setRange(-10000,10000)
            field.setDecimals(3)
            field.setSuffix(' mm')
            field.setValue(value)
            field.setKeyboardTracking(False)
            setattr(self,name,field)
            form.addRow(tr('移動量 ','Translation ')+label,field)
            field.valueChanged.connect(self.settings_changed)
        self.fit_button=W.QPushButton(tr('動き全体を表示','Fit Entire Motion'))
        self.fit_button.clicked.connect(self.fit_motion)
        form.addRow(self.fit_button)
        self.layout().insertWidget(2,self.part_box)
        self.part_box.hide()
        self.source.currentIndexChanged.connect(self.settings_changed)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        import animation_preset_ui
        animation_preset_ui.install(self)

    def restore(self):
        watcher=getattr(self,'context_timer',None)
        if watcher:
            watcher.stop()
        if self.motion is not None:
            self.motion.close()
            self.motion = None
        super().restore()

    def seek(self, value):
        if self.exporting:
            return
        if self.mode is None or self.mode.currentData() != 'part':
            if self.motion is not None:
                self.motion.close()
                self.motion = None
            super().seek(value)
            return
        try:
            render_tools.validate_capture(self.ws, self.doc, 64, 64, 'White', 'current')
            source = self.doc.getObject(self.source.currentData() or '')
            if self.motion is None or self.motion.closed or self.motion.name != (source.Name if source else None):
                if self.motion is not None:
                    self.motion.close()
                self.motion = MotionPreview(self.ws, source)
            self.motion.update(value, self.frames.value(), self.axis.currentData(), self.degrees.value(), self.dx.value(), self.dy.value(), self.dz.value())
            self.position_label.setText('%d / %d' % (value + 1, self.frames.value()))
            if not self.context_timer.isActive():
                self.context_timer.start()
            self.status.clear()
        except Exception as error:
            self.restore()
            self.status.setText(str(error))

    def settings_changed(self, *args):
        super().settings_changed(*args)
        if self.mode is not None and self.mode.currentData() == 'part':
            self.fit_motion()

    def mode_changed(self, *args):
        if self.exporting:
            return
        self.stop()
        part = self.mode.currentData() == 'part'
        self.part_box.setVisible(part)
        self.base_note.setText(tr('元の形状は比較用に残ります。青い表示コピーだけが移動・回転します。実部品・ジョイント・履歴は変更しません。', 'The original stays as a reference. Only a blue display copy moves and rotates. Actual parts, joints and history remain unchanged.') if part else self.camera_note)
        if part:
            self.seek(0)
            self.fit_motion()
        self.adjustSize()
        available = self.screen().availableGeometry()
        parent = self.ws.main.frameGeometry()
        x = max(available.left(), min(parent.right() - self.width() - 16, available.right() - self.width() - 16))
        y = max(available.top() + 16, min(parent.top() + 150, available.bottom() - self.height() - 40))
        self.move(x, y)

    def fit_motion(self, *args):
        if self.exporting or self.mode is None or self.mode.currentData() != 'part':
            return
        self.pause()
        self.seek(self.slider.value())
        if self.motion is None:
            return
        try:
            self.motion.fit(self.ws, self.dx.value(), self.dy.value(), self.dz.value())
            Gui.updateGui()
            self.motion.check()
        except Exception as error:
            self.restore()
            self.status.setText(str(error))

    def export_frames(self):
        if self.mode.currentData() != 'part':
            super().export_frames()
            return
        if self.exporting:
            return
        self.pause()
        self.seek(self.slider.value())
        if self.motion is None:
            return
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
            path = write_motion_sequence(self.motion, self.frames.value(), self.fps.value(), self.axis.currentData(), self.degrees.value(), self.dx.value(), self.dy.value(), self.dz.value(), self.width_spin.value(), self.height_spin.value(), self.background.currentData(), folder, cancel=progress.wasCanceled, progress=update)
            self.status.setText(tr('書き出しを取り消しました。', 'Export cancelled.') if path is None else tr('保存しました：', 'Saved: ') + str(path))
        except Exception as error:
            self.status.setText(str(error))
        finally:
            progress.close()
            self.exporting = False

    def check_context(self):
        if self.exporting or not self.isVisible() or self.motion is None:
            return
        try:
            self.motion.check()
        except (ValueError, RuntimeError, ReferenceError) as error:
            self.restore()
            self.status.setText(str(error))

def source_candidates(doc):
    import export_tools
    return [obj for obj in export_tools.visible_objects(doc) if hasattr(obj, 'Shape') and obj.Shape.Solids and not getattr(obj, 'FluxCADInternal', False)]

def selected_source_name(doc, objects):
    if len(objects) != 1 or objects[0].Document != doc:
        return ''
    from browser import body_owner
    return body_owner(objects[0]).Name
