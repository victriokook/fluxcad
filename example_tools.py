from pathlib import Path
import shutil
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets as W
from i18n import tr

CATALOG = (
    ('case', 'plastic/Parametric-enclosure.FCStd', '寸法連動の樹脂ケース', 'Parametric plastic enclosure'),
    ('draft', 'plastic/Drafted-enclosure.FCStd', '抜き勾配付きケース', 'Drafted enclosure'),
    ('instances', 'plastic/Instanced-enclosures.FCStd', '複数配置の樹脂ケース', 'Instanced enclosures'),
    ('rib', 'plastic/Tapered-rib-demo.FCStd', '抜き勾配リブ', 'Tapered rib'),
    ('gusset', 'plastic/Gusset-enclosure.FCStd', '三角リブのケース', 'Gusset enclosure'),
    ('snap', 'plastic/Snap-hook.FCStd', 'スナップ爪', 'Snap hook'),
    ('dome', 'dome/Hollow-dome-demo.FCStd', '中空ドーム', 'Hollow dome'),
    ('ellipse', 'ellipse/Positioned-ellipses-demo.FCStd', '位置付き数値楕円', 'Positioned numeric ellipses'),
)

def source_path(key):
    item = next((item for item in CATALOG if item[0] == key), None)
    if item is None:
        raise ValueError(tr('使用例を選び直してください。', 'Select an example again.'))
    source = Path(__file__).resolve().parent / 'examples' / item[1]
    if not source.is_file():
        raise ValueError(tr('使用例ファイルがありません。', 'Example file is missing.'))
    return source

def copy_example(key, destination):
    source = source_path(key)
    target = Path(destination).expanduser().absolute()
    examples = (Path(__file__).resolve().parent / 'examples').resolve()
    if target.suffix.lower() != '.fcstd' or target.resolve().is_relative_to(examples):
        raise ValueError(tr('使用例フォルダーの外に、新しいFCStdファイル名を指定してください。', 'Choose a new FCStd filename outside the examples folder.'))
    created = False
    try:
        with source.open('rb') as incoming:
            with target.open('xb') as outgoing:
                created = True
                shutil.copyfileobj(incoming, outgoing)
    except FileExistsError:
        raise ValueError(tr('同名ファイルがあります。別の名前を指定してください。', 'File exists. Choose another name.')) from None
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise
    return target

def show(ws):
    if ws.current_sketch() or Gui.Control.activeDialog():
        raise ValueError(tr('編集中の操作を終了してください。', 'Finish the active edit first.'))
    labels = [tr(item[2], item[3]) for item in CATALOG]
    label, accepted = W.QInputDialog.getItem(ws.main, tr('使用例を作業コピーで開く', 'Open Example Working Copy'), tr('使用例', 'Example'), labels, 0, False)
    if not accepted:
        return
    item = CATALOG[labels.index(label)]
    suggested = Path(item[1]).stem + '-copy.FCStd'
    path, _ = W.QFileDialog.getSaveFileName(ws.main, tr('作業コピーの保存先', 'Save Working Copy'), suggested, 'FreeCAD (*.FCStd)', options=W.QFileDialog.DontConfirmOverwrite)
    if not path:
        return
    if ws.current_sketch() or Gui.Control.activeDialog():
        raise ValueError(tr('編集中の操作を終了してください。', 'Finish the active edit first.'))
    target = copy_example(item[0], path)
    doc = App.openDocument(str(target))
    import recent_files
    recent_files.remember(str(target))
    ws.refresh()
    view = Gui.activeDocument().activeView()
    view.viewAxonometric()
    view.fitAll()
    return doc
