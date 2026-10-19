import os
import FreeCAD as App
import FreeCADGui as Gui
from i18n import tr

def canonical(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))

def recent_paths(preferences):
    mru = []
    for i in range(10):
        p = preferences.GetString(f'MRU{i}', '')
        if p:
            mru.append(p)
    seen = set()
    unique = []
    for p in mru:
        c = canonical(p)
        if c not in seen and c:
            seen.add(c)
            unique.append(p)
    return unique

def action_label(index, path):
    label = f"{index + 1}. " + os.path.basename(path).replace("&", "&&")
    return label

def install(ws, file_menu):
    from PySide import QtGui
    submenu = file_menu.addMenu(tr('最近開いたファイル', 'Recent Files'))
    submenu.setObjectName('FluxRecentFilesMenu')
    submenu.aboutToShow.connect(lambda: _refresh_menu(submenu, ws))
    file_menu.insertMenu(ws.ribbon_actions["save"], submenu)

def _refresh_menu(submenu, ws):
    submenu.clear()
    prefs = App.ParamGet('User parameter:BaseApp/Preferences/RecentFiles')
    paths = recent_paths(prefs)
    if not paths:
        act = submenu.addAction(tr('履歴はありません', 'No Recent Files'))
        act.setEnabled(False)
        return
    for i, p in enumerate(paths):
        label = action_label(i, p)
        act = submenu.addAction(label)
        act.setToolTip(p)
        if not os.path.isfile(p):
            act.setEnabled(False)
        else:
            act.triggered.connect(lambda checked=False, path=p: ws.safe(lambda: open_recent(path)))

def open_recent(path):
    canonical_path = canonical(path)
    if not os.path.isfile(path):
        raise ValueError(tr('ファイルがありません。', 'File not found.'))
    for doc in App.listDocuments().values():
        if canonical(doc.FileName) == canonical_path:
            App.setActiveDocument(doc.Name)
            remember(path)
            return
    if os.path.splitext(path)[1].lower() == '.fcstd':
        App.openDocument(path)
    else:
        Gui.open(path)
    remember(path)

def remember(path):
    if not os.path.isfile(path):
        raise ValueError(tr('ファイルがありません。', 'File not found.'))
    path = os.path.abspath(path)
    key = canonical(path)
    prefs = App.ParamGet('User parameter:BaseApp/Preferences/RecentFiles')
    paths = [path] + [p for p in recent_paths(prefs) if canonical(p) != key]
    for index in range(10):
        prefs.SetString('MRU%d' % index, paths[index] if index < len(paths) else '')
