import FreeCAD as App
import FreeCADGui as Gui
from i18n import tr
from pathlib import Path
import sys
import importlib
__doc__ = 'FluxCAD SheetMetal Bridge: delegates to upstream SheetMetal addon for base, flange, and unfold operations. Supports only closed sketches for sheet_base.'
COMMANDS = {'sheet_base': 'SheetMetal_AddBase', 'sheet_flange': 'SheetMetal_AddWall', 'sheet_unfold': 'SheetMetal_Unfold'}
_ADDON_ROOT = Path(__file__).resolve().parent / 'addons' / 'SheetMetal'
_LANG_PATH = _ADDON_ROOT / 'Resources' / 'translations'
_ICON_PATH = _ADDON_ROOT / 'Resources' / 'icons'
_loaded = False

def load():
    global _loaded
    if _loaded:
        return dict(COMMANDS)
    addon_root = _ADDON_ROOT
    base_cmd_file = addon_root / 'SheetMetalBaseCmd.py'
    if not base_cmd_file.is_file():
        raise RuntimeError(tr('シートメタルアドオンが見つかりません', 'SheetMetal addon not found'))
    dependencies = addon_root.parent / 'python-deps'
    for path in (addon_root, dependencies):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    try:
        importlib.import_module('SheetMetalBaseCmd')
        importlib.import_module('SheetMetalCmd')
        importlib.import_module('SheetMetalUnfoldCmd')
    except Exception as e:
        raise RuntimeError(tr('アドオンモジュールの読み込みに失敗しました', 'Failed to load addon modules')) from e
    Gui.addLanguagePath(str(_LANG_PATH))
    Gui.addIconPath(str(_ICON_PATH))
    Gui.updateLocale()
    for cmd_name in COMMANDS.values():
        if cmd_name not in Gui.listCommands():
            raise RuntimeError(tr(f'コマンド {cmd_name} が登録されていません', f'Command {cmd_name} is not registered'))
    _loaded = True
    return dict(COMMANDS)

def start(ws, key):
    if key not in COMMANDS:
        raise ValueError(tr('無効なコマンドキーです', 'Invalid command key'))
    load()
    cmd = COMMANDS[key]
    if App.ActiveDocument is None:
        raise RuntimeError(tr('アクティブドキュメントがありません', 'No active document'))
    if ws.current_sketch():
        raise ValueError(tr('スケッチが選択されています', 'A sketch is selected'))
    if Gui.Control.activeDialog():
        raise ValueError(tr('対話ボックスが開いています', 'A dialog is open'))
    selection = Gui.Selection.getSelectionEx()
    if len(selection) != 1:
        raise ValueError(tr('選択がありません', 'No selection'))
    entry = selection[0]
    obj = entry.Object
    doc = App.ActiveDocument
    if obj.Document != doc:
        raise ValueError(tr('選択はアクティブドキュメントに属していません', 'Selection does not belong to active document'))
    if key == 'sheet_base':
        if obj.TypeId != 'Sketcher::SketchObject':
            raise ValueError(tr('スケッチオブジェクトが選択されていません', 'No Sketcher::SketchObject selected'))
        wires = [w for w in obj.Shape.Wires if len(w.Edges) > 0]
        if not wires:
            raise ValueError(tr('ベースワイヤーが空です', 'Base wire is empty'))
        if not all((w.isClosed() for w in wires)):
            raise ValueError(tr('閉じたプロファイルのみサポートされています', 'Only closed profiles are supported'))
    elif key == 'sheet_flange':
        if not hasattr(obj, 'Shape') or not obj.Shape.Solids:
            raise ValueError(tr('板金ボディの辺を1つ選択してください。', 'Select one edge of a sheet metal solid.'))
        if len(entry.SubElementNames) != 1 or not entry.SubElementNames[0].startswith('Edge'):
            raise ValueError(tr('曲げる直線の辺を1つ選択してください。', 'Select one straight edge to bend.'))
        import Part
        edge = obj.Shape.getElement(entry.SubElementNames[0])
        if not isinstance(edge, Part.Edge) or not isinstance(edge.Curve, Part.Line):
            raise ValueError(tr('直線の辺を選択してください。', 'Select a straight edge.'))
    elif key == 'sheet_unfold':
        if not hasattr(obj, 'Shape') or not obj.Shape.Solids:
            raise ValueError(tr('ソリッドの平面を1つ選択してください。', 'Select one planar face on a solid.'))
        if len(entry.SubElementNames) != 1:
            raise ValueError(tr('単一のサブ要素が必要です', 'Single subelement required'))
        name = entry.SubElementNames[0]
        if not name.startswith('Face'):
            raise ValueError(tr('Face で始まるサブ要素が必要です', 'Subelement must start with Face'))
        face = obj.Shape.getElement(name)
        from Part import Plane
        if not isinstance(face.Surface, Plane):
            raise ValueError(tr('平面な面が必要です', 'Planar face required'))
        if len(obj.Shape.Solids) == 0:
            raise ValueError(tr('ソリッドが必要です', 'Solid required'))
    if not Gui.Command.get(cmd).isActive():
        raise ValueError(tr('コマンドがアクティブではありません', 'Command is not active'))
    ws.region_picker.ticket += 1
    ws.region_picker.clear()
    ws.region_picker.press = None
    Gui.runCommand(cmd)
    ws.native_task_opened = True
    ws.compact()
    ws.ribbon_tabs.setCurrentIndex(ws.tab_indices['sheet'])
