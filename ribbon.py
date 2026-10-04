"""Fusion-inspired command ribbon, using original icons and FreeCAD commands."""
from i18n import tr
import os
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets as W

STYLE = '''
QToolBar#FluxCADToolbar {background:#f5f5f5;border:0;border-bottom:1px solid #d6d6d6;padding:0;spacing:0;}
QWidget#FluxRibbon {background:#f5f5f5;color:#333;font-family:"Yu Gothic UI";font-size:12px;}
QFrame#FluxTop {background:#e9e9e9;border-bottom:1px solid #d6d6d6;}
QToolButton {padding:1px 4px;border:1px solid transparent;border-radius:2px;}
QWidget#FluxRibbon QToolButton:hover {background:#dcebf7;border:1px solid #9bc4e5;}
QWidget#FluxRibbon QToolButton:pressed {background:#c4e0f5;}
QTabBar::tab {background:transparent;padding:3px 15px;color:#555;border:0;border-bottom:2px solid transparent;}
QTabBar::tab:selected {color:#303030;border-bottom:2px solid #444;font-weight:bold;}
QTabBar::tab:disabled {color:#a6aaae;}
QFrame#FluxGroup {border-right:1px solid #d3d3d3;}
QToolButton#FluxGroupLabel {padding:0px 8px;font-size:11px;color:#4c5259;}
QToolButton#FluxWorkspace {border:1px solid #c4c4c4;border-radius:4px;background:#f9f9f9;font-size:13px;}
QLabel#FluxDocTitle {color:#636971;font-size:12px;}
QMenu {background:#fff;color:#303740;border:1px solid #c1c7ce;padding:5px;}
QMenu::item {padding:6px 30px 6px 12px;}
QMenu::item:selected {background:#dcebf7;}
QMenu::separator {height:1px;background:#e2e5e7;margin:4px 10px;}
'''


def build(ws):
    root = W.QWidget()
    root.setObjectName('FluxRibbon')
    layout = W.QVBoxLayout(root)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(0)
    ws.ribbon = root
    ws.ribbon_actions = {}
    ws.ribbon_menus = {}
    ws.solid_action_keys = ['extrude','revolve','loft','sweep','box','cylinder','hole','fillet','chamfer','shell','move','move_numeric','move_copy','align','join','cut','split_body','linear_pattern','circular_pattern','mirror','offset_plane','rectangle','mesh_scale','mesh_rotate']

    def action(key, text, icon, callback, shortcut=None):
        path = os.path.join(os.path.dirname(__file__),'icons',icon+'.svg')
        ico = QtGui.QIcon(path if os.path.exists(path) else ':/icons/'+icon+'.svg')
        a = QtGui.QAction(ico,text,root)
        a.triggered.connect(lambda checked=False: ws.safe(callback))
        a.setToolTip(text + ('  ['+shortcut+']' if shortcut else ''))
        ws.actions.append((a,shortcut,callback))
        ws.ribbon_actions[key] = a
        return a

    def command(name):
        return lambda: Gui.runCommand(name)

    action('new',tr('新規デザイン'),'document-new',command('Std_New'))
    action('open',tr('開く…'),'document-open',command('Std_Open'))
    action('save',tr('保存'),'document-save',command('Std_Save'))
    action('undo',tr('元に戻す'),'edit-undo',command('Std_Undo'))
    action('redo',tr('やり直す'),'edit-redo',command('Std_Redo'))
    import drawing, drawing_detail
    for key,ja,en,icon,callback in [
        ('drawing_new','新規図面','New Drawing','drawing-page',lambda:drawing.new_page(ws)),
        ('drawing_open','図面を開く','Open Drawing','drawing-page',lambda:drawing.open_page(ws)),
        ('drawing_sheet','用紙設定','Sheet Settings','drawing-page',lambda:drawing.sheet_settings(ws)),
        ('drawing_view','ベースビュー','Base View','drawing-view',lambda:drawing.insert_view(ws)),
        ('drawing_projection','三面図','Projected Views','drawing-projection',lambda:drawing.insert_view(ws,group=True)),
        ('drawing_edit','選択項目を編集','Edit Selection','drawing-view',lambda:drawing.edit_selected(ws)),
        ('drawing_note','注記','Note','drawing-note',lambda:drawing.annotation(ws)),
        ('drawing_frames','図の枠を表示 / 非表示','Toggle View Frames','drawing-view',lambda:drawing.toggle_frames(ws)),
        ('drawing_display','図の配置と表示','View Placement and Display','drawing-view',lambda:drawing_detail.view_settings(ws)),
        ('drawing_pdf','PDF出力…','Export PDF…','drawing-export',lambda:drawing.export_page(ws,'pdf')),
        ('drawing_svg','SVG出力…','Export SVG…','drawing-export',lambda:drawing.export_page(ws,'svg')),
        ('drawing_design','デザインに戻る','Return to Design','Part_Box',lambda:drawing.switch(ws,False))]:
        action(key,tr(ja,en),icon,callback);ws.solid_action_keys.append(key)
    for key,ja,en in [('length','長さ寸法','Length Dimension'),('horizontal','水平寸法','Horizontal Dimension'),
                      ('vertical','垂直寸法','Vertical Dimension'),('radius','半径寸法','Radius Dimension'),
                      ('diameter','直径寸法','Diameter Dimension'),('angle','角度寸法','Angle Dimension')]:
        action('drawing_'+key,tr(ja,en),'drawing-dimension',lambda k=key:drawing.dimension(ws,k))
        ws.solid_action_keys.append('drawing_'+key)
    for key,ja,en,icon,tipja,tipen in [
        ('section','断面図','Section View','drawing-section','元の投影図を選び、切断方向と位置を設定します。','Select a base view, then set the cut direction and position.'),
        ('detail','詳細図','Detail View','drawing-detail','元の投影図を選び、拡大する範囲と倍率を設定します。','Select a base view, then set the detail region and magnification.'),
        ('hatch','ハッチング','Hatch','drawing-hatch','図面の面を選び、パターン・尺度・角度を設定します。','Select drawing faces and set the pattern, scale and angle.'),
        ('circle_center','中心マーク','Center Marks','drawing-center','図面の円・円弧を選び、中心線を追加します。','Select drawing circles or arcs to add centerlines.'),
        ('edge_center','2辺間の中心線','Centerline Between Edges','drawing-center','同じ投影図の2辺をCtrlで選択します。','Ctrl-select two edges in the same drawing view.'),
        ('face_center','面の中心線','Face Centerline','drawing-center','図面の面内部を選び、中心線を配置します。','Select drawing faces to position a centerline.'),
        ('erase','補助線を削除','Remove Cosmetic Geometry','drawing-center','図面の中心線・補助線を選択して削除します。','Select cosmetic edges or centerlines in the drawing to remove them.')]:
        a=action('drawing_'+key,tr(ja,en),icon,lambda k=key:drawing_detail.start(ws,k))
        a.setToolTip(tr(tipja,tipen));ws.solid_action_keys.append('drawing_'+key)
    action('sketch',tr('スケッチを作成'),'Sketcher_NewSketch',ws.sketch)
    action('rectangle',tr('長方形スケッチ'),'Sketcher_CreateRectangle',ws.rectangle)
    action('extrude',tr('押し出し'),'extrude',ws.extrude,'E')
    action('revolve',tr('回転'),'revolve',ws.revolve)
    action('loft',tr('ロフト'),'loft',lambda:ws.section_feature('loft'))
    action('sweep',tr('スイープ'),'sweep',lambda:ws.section_feature('sweep'))
    action('linear_pattern',tr('矩形状パターン','Rectangular Pattern'),'linear-pattern',lambda:ws.pattern('linear'))
    action('circular_pattern',tr('円形状パターン'),'circular-pattern',lambda:ws.pattern('circular'))
    action('path_pattern',tr('パスに沿ったパターン','Pattern on Path'),'path-pattern',lambda:ws.path_pattern_panel.start())
    ws.solid_action_keys.append('path_pattern')
    action('mirror',tr('ミラー'),'mirror',ws.mirror)
    action('box',tr('直方体'),'Part_Box',ws.box)
    action('cylinder',tr('円柱'),'Part_Cylinder',ws.cylinder)
    for key,label,en in [('sphere','球','Sphere'),('torus','トーラス','Torus'),('coil','コイル','Coil'),('pipe','パイプ','Pipe')]:
        action(key,tr(label,en),key,lambda kind=key:ws.primitive_panel.start(kind))
        ws.solid_action_keys.append(key)
    action('hole',tr('穴'),'hole',ws.hole,'H')
    action('fillet',tr('フィレット'),'Part_Fillet',ws.fillet,'F')
    action('chamfer',tr('面取り'),'chamfer',ws.chamfer)
    action('split_body',tr('ボディを分割','Split Body'),'split-body',ws.split_body)
    action('shell',tr('シェル（中空化）'),'shell',ws.shell)
    action('offset_plane',tr('オフセット平面'),'offset-plane',ws.offset_plane)
    action('midplane',tr('中間平面','Midplane'),'midplane',lambda:ws.construction_panel.start('midplane'))
    action('angled_plane',tr('角度付き平面','Plane at Angle'),'angled-plane',lambda:ws.construction_panel.start('angle'))
    action('three_point_plane',tr('3点を通る平面','Plane Through Three Points'),'three-point-plane',lambda:ws.construction_panel.start('three_points'))
    action('tangent_plane',tr('接平面','Tangent Plane'),'tangent-plane',lambda:ws.construction_panel.start('tangent'))
    action('path_plane',tr('パスに沿った平面','Plane Along Path'),'path-plane',lambda:ws.construction_panel.start('along_path'))
    ws.solid_action_keys.extend(['midplane','angled_plane','three_point_plane','tangent_plane','path_plane'])
    action('center_axis',tr('円柱・円すいの中心軸','Axis Through Cylinder / Cone'),'center-axis',lambda:ws.construction_axis_panel.start('center'))
    action('two_point_axis',tr('2点を通る軸','Axis Through Two Points'),'construction-axis',lambda:ws.construction_axis_panel.start('two_points'))
    ws.solid_action_keys.extend(['center_axis','two_point_axis'])
    action('move',tr('移動（ドラッグ）'),'move',ws.start_move,'M').setCheckable(True)
    action('move_numeric',tr('数値で移動…'),'move',ws.move)
    action('move_copy',tr('移動 / コピー（回転）…'),'body-rotate',ws.move_copy)
    action('mesh_scale',tr('メッシュのサイズ変更…','Resize Mesh…'),'mesh-scale',lambda:ws.edit_mesh('scale'))
    action('mesh_rotate',tr('メッシュの回転…','Rotate Mesh…'),'body-rotate',lambda:ws.edit_mesh('rotate'))
    action('mesh_separate',tr('部品を分離…','Separate Parts…'),'mesh-separate',lambda:ws.edit_mesh('separate'))
    action('mesh_cut',tr('平面で切断…','Plane Cut…'),'mesh-cut',lambda:ws.edit_mesh('cut'))
    ws.solid_action_keys.extend(['mesh_separate','mesh_cut'])
    action('align',tr('位置合わせ…'),'align',ws.align)
    action('join',tr('結合'),'Part_Fuse',lambda: ws.boolean(False))
    action('cut',tr('切り取り'),'Part_Cut',lambda: ws.boolean(True))
    action('intersect',tr('交差部分を残す','Intersect'),'Part_Common',lambda:ws.boolean('intersect'))
    ws.solid_action_keys.append('intersect')
    action('component',tr('コンポーネントを作成…','Create Components…'),'component',ws.create_component)
    action('duplicate_component',tr('コンポーネントを複製','Duplicate Component'),'component',ws.duplicate_component)
    action('ground_component',tr('接地 / 接地を解除','Ground / Unground'),'rigid-joint',ws.ground_component)
    action('rigid_joint',tr('固定ジョイント…','Rigid Joint…'),'rigid-joint',lambda:ws.start_joint('rigid'))
    action('revolute_joint',tr('回転ジョイント…','Revolute Joint…'),'revolute-joint',lambda:ws.start_joint('revolute'))
    action('slider_joint',tr('スライダージョイント…','Slider Joint…'),'slider-joint',lambda:ws.start_joint('slider'))
    action('release_joint',tr('ジョイントを解除','Release Joint'),'rigid-joint',ws.release_joint)
    ws.solid_action_keys.extend(['component','duplicate_component','ground_component','rigid_joint','revolute_joint','slider_joint','release_joint'])
    action('export',tr('エクスポート…'),'document-export',ws.export)
    action('insert',tr('挿入…'),'insert',command('Std_Import'))
    action('search',tr('コマンドを検索'),'search',ws.command_search,'S')
    action('select',tr('選択'),'select',ws.select_mode)
    action('box_select',tr('窓選択'),'select',command('Std_BoxSelection'))
    action('select_all',tr('すべて選択'),'select',command('Std_SelectAll'))
    action('fit',tr('全体表示'),'zoom-fit-best',ws.fit)
    tabs_action = action('bottom_tabs',tr('下段タブを表示'),'eye',ws.toggle_bottom_tabs)
    tabs_action.setCheckable(True)
    tabs_action.setChecked(ws.bottom_tabs_visible)
    tabs_action.setToolTip(tr('下段のドキュメントタブと加工履歴をまとめて表示 / 非表示'))
    action('native',tr('FreeCAD 標準UIに戻す'),'preferences-system',ws.restore)
    ws.sketch_action_keys = []
    sketch_commands = [
        ('line',tr('線分'),'line','Sketcher_CreateLine'),
        ('polyline',tr('ポリライン'),'polyline','Sketcher_CreatePolyline'),
        ('draw_rectangle',tr('2点指定の長方形'),'Sketcher_CreateRectangle','Sketcher_CreateRectangle'),
        ('center_rectangle',tr('中心の長方形'),'center-rectangle','Sketcher_CreateRectangle_Center'),
        ('rounded_rectangle',tr('角丸長方形','Rounded Rectangle'),'sketch-fillet','Sketcher_CreateOblong'),
        ('circle',tr('中心と半径の円'),'circle','Sketcher_CreateCircle'),
        ('circle3',tr('3点指定の円'),'circle3','Sketcher_Create3PointCircle'),
        ('arc',tr('中心指定の円弧'),'arc','Sketcher_CreateArc'),
        ('arc3',tr('3点指定の円弧'),'arc3','Sketcher_Create3PointArc'),
        ('spline',tr('フィット点スプライン'),'spline','Sketcher_CreateBSplineByInterpolation'),
        ('control_spline',tr('制御点スプライン'),'spline','Sketcher_CreateBSpline'),
        ('ellipse',tr('楕円'),'ellipse','Sketcher_CreateEllipseByCenter'),
        ('polygon',tr('ポリゴン'),'polygon','Sketcher_CreateRegularPolygon'),
        ('slot',tr('スロット'),'slot','Sketcher_CreateSlot'),
        ('arc_slot',tr('円弧スロット','Arc Slot'),'slot','Sketcher_CreateArcSlot'),
        ('point',tr('点'),'point','Sketcher_CreatePoint'),
        ('sketch_mirror',tr('ミラー'),'mirror','Sketcher_Symmetry'),
        ('sketch_rectangular_pattern',tr('矩形状パターン','Rectangular Pattern'),'linear-pattern','Sketcher_RectangularArray'),
        ('sketch_rotate',tr('回転 / 円形状パターン','Rotate / Circular Pattern'),'circular-pattern','Sketcher_Rotate'),
        ('sketch_move',tr('移動 / 配列','Move / Array'),'move','Sketcher_Translate'),
        ('sketch_copy',tr('コピー','Copy'),'document-copy','Sketcher_Copy'),
        ('sketch_scale',tr('尺度','Scale'),'mesh-scale','Sketcher_Scale'),
        ('project',tr('投影','Project'),'sketch-project','Sketcher_Projection'),
        ('sketch_intersection',tr('交差','Intersect'),'sketch-intersection','Sketcher_Intersection'),
        ('trim',tr('トリム'),'trim','Sketcher_Trimming'),
        ('extend',tr('延長'),'extend','Sketcher_Extend'),
        ('sketch_split',tr('分割','Split Edge'),'trim','Sketcher_Split'),
        ('sketch_offset',tr('オフセット'),'offset','Sketcher_Offset'),
        ('sketch_fillet',tr('フィレット'),'sketch-fillet','Sketcher_CreateFillet'),
        ('sketch_chamfer',tr('面取り'),'chamfer','Sketcher_CreateChamfer'),
        ('construction',tr('補助線に切替'),'construction','Sketcher_ToggleConstruction'),
        ('coincident',tr('一致'),'coincident','Sketcher_ConstrainCoincident'),
        ('point_on_object',tr('点を線上に拘束','Point on Object'),'point-on-object','Sketcher_ConstrainPointOnObject'),
        ('horizontal',tr('水平'),'horizontal','Sketcher_ConstrainHorizontal'),
        ('vertical',tr('垂直'),'vertical','Sketcher_ConstrainVertical'),
        ('parallel',tr('平行'),'parallel','Sketcher_ConstrainParallel'),
        ('perpendicular',tr('直角'),'perpendicular','Sketcher_ConstrainPerpendicular'),
        ('equal',tr('等しい'),'equal','Sketcher_ConstrainEqual'),
        ('tangent',tr('接線'),'tangent','Sketcher_ConstrainTangent'),
        ('symmetric',tr('対称'),'symmetric','Sketcher_ConstrainSymmetric'),
        ('fix',tr('固定'),'fix','Sketcher_ConstrainBlock'),
        ('dimension',tr('寸法'),'dimension','Sketcher_Dimension'),
        ('dimension_length',tr('長さ・距離','Length / Distance'),'dimension','Sketcher_ConstrainDistance'),
        ('dimension_horizontal',tr('水平距離','Horizontal Distance'),'dimension','Sketcher_ConstrainDistanceX'),
        ('dimension_vertical',tr('垂直距離','Vertical Distance'),'dimension-vertical','Sketcher_ConstrainDistanceY'),
        ('dimension_radius',tr('半径','Radius'),'dimension-radius','Sketcher_ConstrainRadius'),
        ('dimension_diameter',tr('直径','Diameter'),'dimension-diameter','Sketcher_ConstrainDiameter'),
        ('dimension_angle',tr('角度','Angle'),'dimension-angle','Sketcher_ConstrainAngle'),
        ('reference_dimension',tr('駆動寸法 / 参照寸法に切替','Toggle Driving / Reference Dimension'),'dimension-reference','Sketcher_ToggleDrivingConstraint')]
    ws.sketch_commands={key:cmd for key,title,icon,cmd in sketch_commands}
    for key,title,icon,cmd in sketch_commands:
        action(key,title,icon,lambda c=cmd: ws.sketch_command(c))
        ws.sketch_action_keys.append(key)
    for key, tip in {
        'project': tr('別のスケッチやボディの辺・頂点を編集中の平面へ投影します。元の形状の変更に追従します。',
                      'Project edges or vertices from another sketch or body onto the sketch plane. References follow source changes.'),
        'sketch_intersection': tr('ボディの面・辺とスケッチ平面の交差を取り込みます。投影とは異なり、平面を横切る形状を選びます。',
                                  'Include intersections of faces or edges with the sketch plane. Select geometry crossing the plane.'),
        'dimension': tr('線・円・円弧などの選択に応じて寸法を付けます。Mキーで寸法の種類を切り替えます。',
                        'Dimension selected lines, circles or arcs contextually. Press M to cycle dimension types.'),
        'point_on_object': tr('点と線・円弧などをCtrlで選択して、点をその曲線上に拘束します。投影した辺も参照できます。',
                              'Ctrl-select a point and a line or curve to constrain the point onto it. Projected edges can be used.'),
        'reference_dimension': tr('選択した寸法を、形状を決める駆動寸法と測定用の参照寸法の間で切り替えます。',
                                  'Switch selected dimensions between driving the geometry and measuring it as a reference.'),
        'sketch_mirror': tr('スケッチの線・円などを選択し、鏡映の基準となる軸を指定して複製します。',
                            'Select sketch geometry, then choose the reflection axis to create a mirrored copy.'),
        'sketch_rectangular_pattern': tr('選択したスケッチ図形を行・列に複製します。個数や寸法はFreeCAD標準の設定画面で指定します。',
                                         'Repeat selected sketch geometry in rows and columns using the native FreeCAD settings.'),
        'sketch_rotate': tr('スケッチ図形を選択して回転します。複製数を増やすと円形状パターンを作成できます。',
                            'Rotate selected sketch geometry. Increase the copy count to create a circular pattern.'),
        'sketch_move': tr('スケッチ図形を選択し、基準点と移動先をクリックします。操作パネルで複製数と行数を指定できます。',
                          'Select sketch geometry, then click a base point and destination. Set copy and row counts in the task controls.'),
        'sketch_copy': tr('選択したスケッチ図形をコピーします。基準点を最後に選択し、コピー先をクリックします。',
                          'Copy selected sketch geometry. Select the reference point last, then click the destination.'),
        'sketch_scale': tr('選択したスケッチ図形を、基準点と倍率を指定して拡大・縮小します。',
                           'Scale selected sketch geometry using a reference point and scale factor.'),
    }.items():
        ws.ribbon_actions[key].setToolTip(tip)
    action('edit_sketch',tr('スケッチを編集'),'Sketcher_NewSketch',ws.edit_sketch)
    action('select_sketch',tr('選択（作図を終了）'),'select',ws.select_sketch_geometry)
    ws.sketch_action_keys.append('select_sketch')
    action('finish_sketch',tr('スケッチを終了'),'finish',ws.finish_sketch)
    ws.sketch_action_keys.append('finish_sketch')

    def measure():
        import model_mesh
        selected=Gui.Selection.getSelection()
        if len(selected)==1 and model_mesh.is_mesh(selected[0]):
            obj=selected[0];mesh=model_mesh.world_mesh(obj);b=mesh.BoundBox
            W.QMessageBox.information(ws.main,tr('検査 — ')+obj.Label,
                tr('外形寸法 X / Y / Z\n%.3f / %.3f / %.3f mm\n\n三角形数：%d',
                   'Bounding size X / Y / Z\n%.3f / %.3f / %.3f mm\n\nTriangles: %d')%(b.XLength,b.YLength,b.ZLength,mesh.CountFacets))
            return
        obj = ws.selection()[0]
        b = obj.Shape.BoundBox
        W.QMessageBox.information(ws.main,tr('検査 — ')+obj.Label,
            tr('外形寸法 X / Y / Z\n%.3f / %.3f / %.3f mm\n\n体積  %.3f mm³\n表面積  %.3f mm²') %
            (b.XLength,b.YLength,b.ZLength,obj.Shape.Volume,obj.Shape.Area))
    action('measure',tr('計測（寸法・体積）'),'measure',measure)
    import native_tools
    for key,label,english,icon,tip,tip_en in [
        ('native_measure','計測','Measure','measure',
         '辺・面・点を選択して計測します。Ctrlで2つ選択すると距離や角度を測れます。',
         'Measure selected edges, faces or points. Ctrl-select two elements for distance or angle.'),
        ('check_geometry','形状を検査','Check Geometry','check-geometry',
         '選択した形状をFreeCAD標準の検査ツールで検証します。',
         'Validate selected shapes with the native FreeCAD geometry checker.'),
        ('solid_scale','尺度','Scale','mesh-scale',
         '選択した形状を原点基準で拡大・縮小します。均一倍率またはXYZ別の倍率を指定できます。',
         'Scale selected shapes about the origin, uniformly or with separate X/Y/Z factors.'),
        ('appearance','外観','Appearance','appearance',
         '選択したボディ・メッシュの色、透明度、表示方法を設定します。',
         'Set color, transparency and display style for selected bodies or meshes.')]:
        action(key,tr(label,english),icon,lambda k=key:native_tools.start(ws,k)).setToolTip(tr(tip,tip_en))
        ws.solid_action_keys.append(key)
    for key,label,english,icon,tip,tip_en in [
        ('surface_patch','パッチ','Patch','surface-patch',
         '閉じた境界の辺を選び、面を張ります。閉じたスケッチ全体の事前選択も使えます。',
         'Fill a closed boundary with a surface. Preselect its edges or an entire closed sketch.'),
        ('surface_boundary','境界サーフェス','Boundary Surface','surface-boundary',
         '2〜4本の境界曲線から面を作成します。張り方を標準タスクで指定します。',
         'Create a surface from 2 to 4 boundary curves. Choose the filling style in the native task.'),
        ('surface_sections','断面曲線から面','Surface from Sections','loft',
         '複数の辺を順番に選択し、それらを通る面を作成します。1断面につき1本の辺を使います。',
         'Create a surface through selected edges in order, using one edge per section.'),
        ('cross_sections','断面線を作成','Create Cross Sections','cross-sections',
         '選択形状からXY・XZ・YZ方向の断面線を作成します。複数断面の間隔も指定できます。',
         'Create XY, XZ or YZ section curves from selected shapes, with optional repeated spacing.'),
        ('section_analysis','断面解析（クリッピング）','Section Analysis (Clipping)','section-analysis',
         '形状を変更せず、切断位置より手前を非表示にして内部を確認します。',
         'Inspect the interior with view clipping, without modifying the shape.')]:
        action(key,tr(label,english),icon,lambda k=key:native_tools.start(ws,k)).setToolTip(tr(tip,tip_en))
        ws.solid_action_keys.append(key)

    import surface_ops
    for key,label,english,icon,tip,tip_en in [
        ('surface_extrude','押し出し','Extrude','extrude',
         'スケッチや輪郭線を押し出して面を作成します。両端はふさぎません。',
         'Extrude sketches or curves into surfaces without end caps.'),
        ('surface_revolve','回転','Revolve','revolve',
         '輪郭線を指定軸のまわりに回転させ、面を作成します。',
         'Revolve a profile about an axis to create a surface.'),
        ('surface_loft','ロフト','Loft','loft',
         '複数の開いた／閉じた輪郭を順番につなぎ、面を作成します。',
         'Create a surface through ordered open or closed profiles.'),
        ('surface_sweep','スイープ','Sweep','sweep',
         '断面を選び、タスク内の「スイープ経路」で経路を指定します。',
         'Choose a profile, then use Sweep Path in the task to select the path.'),
        ('surface_extend','面を延長','Extend Face','surface-extend',
         '面を1つ選び、U・V方向の延長率を指定します。プレビュー・再編集ができます。',
         'Select one face and enter U/V extension percentages, with preview and later editing.')]:
        action(key,tr(label,english),icon,lambda k=key:surface_ops.start(ws,k)).setToolTip(tr(tip,tip_en))
        ws.solid_action_keys.append(key)

    import surface_finish
    action('surface_offset',tr('オフセット面','Offset Surface'),'surface-offset',lambda:surface_finish.offset(ws)).setToolTip(
        tr('サーフェス、またはボディの選択面を法線方向に一定距離ずらします。',
           'Offset a surface or selected body faces by a signed normal distance.'))
    action('surface_thicken',tr('厚み付け','Thicken'),'surface-thicken',lambda:surface_finish.offset(ws,fill=True)).setToolTip(
        tr('サーフェスに厚みを付け、新しいボディを作成します。正負の距離で方向を指定します。',
           'Thicken a surface into a new body. Signed distance controls the direction.'))
    action('refine_shape',tr('形状を簡略化','Refine Shape'),'refine-shape',lambda:surface_finish.refine(ws)).setToolTip(
        tr('同じ面上の不要な分割線などを除きます。元形状への参照を保持します。',
           'Remove redundant splits such as coplanar edges, keeping a link to the source.'))
    ws.solid_action_keys.extend(['surface_offset','surface_thicken','refine_shape'])

    def axes():
        if Gui.activeDocument():
            v = Gui.activeDocument().activeView()
            v.setAxisCross(not v.hasAxisCross())
    action('axes',tr('原点軸を表示 / 非表示'),'Part_Box',axes)
    grid_action = action('grid',tr('グリッド'),'grid',ws.toggle_grid)
    grid_action.setCheckable(True)
    grid_action.setChecked(ws.grid.enabled)
    grid_action.setToolTip(tr('作図面のグリッドを表示 / 非表示。細かさや固定間隔は「グリッド設定」で変更できます。'))
    action('grid_settings',tr('グリッド設定…'),'grid',ws.grid_settings)
    for key,text,method in [('top',tr('上面'),'viewTop'),('front',tr('正面'),'viewFront'),('right',tr('右側面'),'viewRight')]:
        action(key,text,'Part_Box',lambda m=method: getattr(Gui.activeDocument().activeView(),m)() if Gui.activeDocument() else None)

    def button(parent_layout, a, large=False, compact=False):
        b = W.QToolButton()
        b.setDefaultAction(a)
        b.setIconSize(QtCore.QSize(26,26) if large else QtCore.QSize(16,16))
        b.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        if large:
            b.setFixedSize(40,34)
        if compact:
            b.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
            b.setFixedSize(40,34)
        b.setObjectName('FluxIcon_'+a.text())
        parent_layout.addWidget(b)
        return b

    top = W.QFrame()
    top.setObjectName('FluxTop')
    row = W.QHBoxLayout(top)
    row.setContentsMargins(10,0,10,0)
    row.setSpacing(4)
    brand = W.QLabel('FLUX<span style="color:#1689bf">CAD</span>')
    brand.setStyleSheet('font-size:16px;font-weight:700;margin-right:16px;')
    row.addWidget(brand)
    file_button = W.QToolButton()
    file_button.setText(tr('ファイル'))
    file_menu = W.QMenu(file_button)
    file_menu.setObjectName('FluxFileMenu')
    for key in ['new','open','save','export']:
        file_menu.addAction(ws.ribbon_actions[key])
    file_button.setMenu(file_menu)
    file_button.setPopupMode(W.QToolButton.InstantPopup)
    row.addWidget(file_button)
    for key in ['save','undo','redo']:
        button(row,ws.ribbon_actions[key])
    row.addStretch()
    ws.doc_title = W.QLabel(tr('無題のデザイン'))
    ws.doc_title.setObjectName('FluxDocTitle')
    row.addWidget(ws.doc_title)
    row.addStretch()
    options = W.QToolButton()
    options.setText(tr('設定 ▾'))
    menu = W.QMenu(options)
    menu.setObjectName('FluxSettingsMenu')
    import i18n
    language_menu=W.QMenu(tr('表示言語 / Language','Language'),menu)
    language_menu.setObjectName('FluxSettingsLanguage');menu.addMenu(language_menu)
    ws.ribbon_menus['language']=language_menu
    ws.language_action_group=QtGui.QActionGroup(language_menu)
    ws.language_action_group.setExclusive(True);ws.language_actions={}
    for code,title in [('ja','日本語'),('en','English')]:
        entry=language_menu.addAction(title);entry.setCheckable(True)
        entry.setChecked(i18n.pending_language()==code);entry.setData(code)
        ws.language_action_group.addAction(entry);ws.language_actions[code]=entry
        entry.triggered.connect(lambda checked=False,c=code:ws.change_language(c))
    view_menu=W.QMenu(tr('表示'),menu);view_menu.setObjectName('FluxSettingsView');menu.addMenu(view_menu)
    ws.ribbon_menus['設定.表示']=view_menu
    for key in ['fit','grid','grid_settings','axes','bottom_tabs','top','front','right']:view_menu.addAction(ws.ribbon_actions[key])
    menu.addAction(ws.ribbon_actions['bottom_tabs'])
    native_menu = menu.addAction(tr('FreeCAD メニューバーを表示 / 非表示'))
    native_menu.triggered.connect(lambda: ws.main.menuBar().setVisible(not ws.main.menuBar().isVisible()))
    nav_menu = W.QMenu(tr('マウス操作'),menu);nav_menu.setObjectName('FluxSettingsMouse');menu.addMenu(nav_menu)
    ws.ribbon_menus['設定.マウス操作']=nav_menu
    for title,key,value in [(tr('自由回転'),'FreeOrbit',ws.mouse.free_orbit),(tr('ズーム方向を反転'),'ReverseZoom',ws.mouse.reverse_zoom)]:
        option = nav_menu.addAction(title)
        option.setCheckable(True)
        option.setChecked(value)
        option.toggled.connect(lambda enabled,k=key: ws.mouse.preference(k,enabled))
    menu.addAction(ws.ribbon_actions['native'])
    options.setMenu(menu)
    options.setPopupMode(W.QToolButton.InstantPopup)
    row.addWidget(options)
    layout.addWidget(top)
    top.setFixedHeight(26)

    body=W.QHBoxLayout();body.setContentsMargins(10,0,4,0);body.setSpacing(10)
    workspace=W.QToolButton();workspace.setObjectName('FluxWorkspace');workspace.setText(tr('デザイン'))
    ws.workspace_button=workspace;ws.drawing_mode=False
    workspace.setFixedSize(94,62)
    workspace_menu=W.QMenu(workspace)
    workspace_menu.setObjectName('FluxWorkspaceMenu')
    for title in [tr('デザイン'),tr('レンダリング'),tr('アニメーション'),tr('シミュレーション'),tr('製造'),tr('図面')]:
        option=workspace_menu.addAction(title);option.setEnabled(title in (tr('デザイン'),tr('図面')))
        if title in (tr('デザイン'),tr('図面')):
            option.triggered.connect(lambda checked=False,draw=title==tr('図面'):ws.safe(lambda:drawing.switch(ws,draw)))
    workspace.setMenu(workspace_menu);workspace.setPopupMode(W.QToolButton.InstantPopup)
    body.addWidget(workspace)
    right=W.QVBoxLayout();right.setContentsMargins(0,0,0,0);right.setSpacing(0)
    tabrow = W.QHBoxLayout();tabrow.setContentsMargins(0,0,0,0)
    ws.ribbon_tabs = W.QTabBar()
    ws.ribbon_tabs.setFixedHeight(26)
    ws.ribbon_tabs.setExpanding(False);ws.ribbon_tabs.setDrawBase(False)
    ws.tab_indices={'solid':0,'surface':1,'mesh':2,'sheet':3,'plastic':4,'manage':5,'utilities':6,'sketch':7,'drawing':8}
    for name in [tr('ソリッド'),tr('サーフェス'),tr('メッシュ'),tr('シートメタル'),tr('プラスチック'),tr('管理'),tr('ユーティリティ'),tr('スケッチ'),tr('図面','Drawing')]:
        ws.ribbon_tabs.addTab(name)
    for index in [3,4,5]:
        ws.ribbon_tabs.setTabEnabled(index,False)
        ws.ribbon_tabs.setTabToolTip(index,tr('このワークスペースは未実装です。'))
    ws.ribbon_tabs.setTabVisible(ws.tab_indices['sketch'],False)
    ws.ribbon_tabs.setTabVisible(ws.tab_indices['drawing'],False)
    ws.ribbon_tabs.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Fixed)
    tabrow.addWidget(ws.ribbon_tabs,1)
    button(tabrow,ws.ribbon_actions['search'])
    right.addLayout(tabrow)
    ws.ribbon_stack = W.QStackedWidget()
    ws.ribbon_stack.setFixedHeight(54)
    ws.ribbon_stack.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
    right.addWidget(ws.ribbon_stack);body.addLayout(right,1);layout.addLayout(body)

    def populate(menu,keys,path):
        # Keep Python wrappers alive across native workbench switches (PySide 6).
        ws.ribbon_menus[path]=menu
        menu.setObjectName('FluxMenu_'+path)
        for key in keys:
            if key is None:menu.addSeparator()
            elif isinstance(key,tuple):
                title,children=key
                submenu=W.QMenu(title,menu);menu.addMenu(submenu)
                populate(submenu,children,path+' > '+title)
            else:
                a=ws.ribbon_actions[key];menu.addAction(a)
                if not a.property('FluxMenuPath'):a.setProperty('FluxMenuPath',path)

    def page(name,groups, compact=False):
        page = W.QWidget()
        row = W.QHBoxLayout(page)
        row.setContentsMargins(0,0,0,0)
        row.setSpacing(5)
        for title, keys, featured in groups:
            frame = W.QFrame()
            frame.setObjectName('FluxGroup')
            group = W.QVBoxLayout(frame)
            group.setContentsMargins(2,0,7,0)
            group.setSpacing(0)
            icons = W.QHBoxLayout()
            icons.setSpacing(1)
            for key in featured:
                button(icons,ws.ribbon_actions[key],True,compact)
            group.addLayout(icons)
            label = W.QToolButton()
            label.setObjectName('FluxGroupLabel')
            label.setFixedHeight(18)
            label.setText(title)
            dropdown = W.QMenu(label)
            populate(dropdown,keys,name+' > '+title)
            ws.ribbon_menus[name+'.'+title]=dropdown
            label.setMenu(dropdown)
            label.setPopupMode(W.QToolButton.InstantPopup)
            group.addWidget(label,0,QtCore.Qt.AlignHCenter)
            row.addWidget(frame)
        row.addStretch()
        ws.ribbon_stack.addWidget(page)
    page(tr('ソリッド'),[
        (tr('スケッチ'),['sketch','rectangle'],['sketch']),
        (tr('作成'),['sketch',None,'extrude','revolve','sweep','loft','hole',None,'box','cylinder','sphere','torus','coil','pipe',None,(tr('パターン'),['linear_pattern','circular_pattern','path_pattern']),'mirror'],['extrude','revolve','sweep','loft']),
        (tr('修正'),['fillet','chamfer','shell',None,'join','cut','intersect','split_body','refine_shape',None,'move_copy','align','move','move_numeric','solid_scale',None,'appearance'],['fillet','chamfer','shell','join','move_copy']),
        (tr('構築'),['offset_plane','midplane','angled_plane','tangent_plane','three_point_plane','path_plane',None,'center_axis','two_point_axis'],['offset_plane']),
        (tr('検査'),['native_measure','measure','section_analysis','cross_sections','check_geometry'],['native_measure']),
        (tr('挿入'),['insert'],['insert']),
        (tr('アセンブリ','Assemble'),['component','duplicate_component','ground_component',None,'rigid_joint','revolute_joint','slider_joint','release_joint'],['component']),
        (tr('選択'),['select','box_select','select_all',None,'edit_sketch'],['select'])])
    page(tr('スケッチ'),[
          (tr('作成'),['line','polyline',(tr('長方形'),['draw_rectangle','center_rectangle','rounded_rectangle']),(tr('円'),['circle','circle3']),(tr('円弧'),['arc3','arc']),(tr('スプライン'),['spline','control_spline']),'polygon','ellipse',(tr('スロット'),['slot','arc_slot']),'point',None,
                      'sketch_mirror',(tr('パターン'),['sketch_rectangular_pattern','sketch_rotate']),None,
                      (tr('投影 / 含める','Project / Include'),['project','sketch_intersection']),None,'dimension',
                      (tr('寸法の種類','Dimension Types'),['dimension_length','dimension_horizontal','dimension_vertical','dimension_radius','dimension_diameter','dimension_angle',None,'reference_dimension'])],['line','draw_rectangle','spline','polygon','dimension','arc3']),
          (tr('修正'),['sketch_fillet','sketch_chamfer','trim','extend','sketch_split','sketch_offset',None,'sketch_move','sketch_copy','sketch_rotate','sketch_scale',None,'construction'],['sketch_fillet','trim','sketch_offset']),
          (tr('拘束'),['horizontal','vertical','coincident','point_on_object','tangent','equal','parallel','perpendicular','fix','symmetric',None,'reference_dimension'],
           ['horizontal','vertical','tangent','equal','parallel','perpendicular','fix','symmetric']),
          (tr('検査'),['measure'],['measure']),
          (tr('選択'),['select_sketch'],['select_sketch']),
          (tr('スケッチを終了'),['finish_sketch'],['finish_sketch'])],compact=True)
    page(tr('ユーティリティ'),[(tr('ナビゲーション'),['fit','top','front','right'],['fit','top','front','right']),
          (tr('表示設定'),['grid','grid_settings','axes','bottom_tabs','appearance'],['grid','axes']),(tr('検査'),['native_measure','measure','section_analysis','cross_sections','check_geometry'],['native_measure'])])
    page(tr('メッシュ'),[(tr('挿入'),['insert'],['insert']),
         (tr('修正'),['move','move_numeric','mesh_rotate','mesh_scale',None,'mesh_separate','mesh_cut',None,'appearance'],['move','mesh_rotate','mesh_scale','mesh_separate','mesh_cut']),
         (tr('検査'),['measure'],['measure']),
         (tr('出力','Export'),['export'],['export']),
         (tr('選択'),['select','box_select','select_all'],['select'])])
    page(tr('サーフェス'),[
        (tr('スケッチ'),['sketch','rectangle'],['sketch']),
        (tr('作成'),['surface_extrude','surface_revolve','surface_sweep','surface_loft',None,'surface_patch','surface_boundary','surface_sections'],['surface_extrude','surface_revolve','surface_sweep','surface_loft','surface_patch']),
        (tr('修正'),['surface_offset','surface_thicken','surface_extend','refine_shape',None,'solid_scale','appearance'],['surface_offset','surface_thicken','surface_extend']),
        (tr('構築'),['offset_plane','midplane','angled_plane','tangent_plane','three_point_plane','path_plane'],['offset_plane']),
        (tr('検査'),['native_measure','measure','section_analysis','cross_sections','check_geometry'],['native_measure','section_analysis']),
        (tr('挿入'),['insert','export'],['insert']),
        (tr('選択'),['select','box_select','select_all'],['select'])])
    page(tr('図面','Drawing'),[
        (tr('用紙','Sheet'),['drawing_new','drawing_open','drawing_sheet'],['drawing_new']),
        (tr('作成','Create'),['drawing_view','drawing_projection','drawing_section','drawing_detail'],['drawing_view','drawing_projection','drawing_section','drawing_detail']),
        (tr('寸法','Dimensions'),['drawing_length','drawing_horizontal','drawing_vertical','drawing_radius','drawing_diameter','drawing_angle'],['drawing_length','drawing_diameter','drawing_angle']),
        (tr('注記','Annotations'),['drawing_note',None,'drawing_circle_center','drawing_edge_center','drawing_face_center','drawing_hatch'],['drawing_note','drawing_circle_center']),
        (tr('修正','Modify'),['drawing_edit','drawing_display','drawing_frames','drawing_erase'],['drawing_edit']),
        (tr('出力','Export'),['drawing_pdf','drawing_svg'],['drawing_pdf']),
        (tr('デザイン','Design'),['drawing_design'],['drawing_design'])])
    ws.ribbon_tabs.currentChanged.connect(lambda i: ws.ribbon_stack.setCurrentIndex({0:0,ws.tab_indices['sketch']:1,ws.tab_indices['utilities']:2,ws.tab_indices['mesh']:3,ws.tab_indices['surface']:4,ws.tab_indices['drawing']:5}.get(i,0)))
    root.setStyleSheet(STYLE)
    root.setSizePolicy(W.QSizePolicy.Ignored,W.QSizePolicy.Fixed)
    ws.toolbar.addWidget(root)
    ws.toolbar.setStyleSheet('QToolBar#FluxCADToolbar {padding:0;margin:0;spacing:0;border:0;border-bottom:1px solid #c9cccf;}')
