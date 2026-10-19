"""Named dimensions in a native VarSet, with atomic expression updates."""
import math
import re
import FreeCAD as App
import model
from i18n import tr

GROUP = 'FluxCAD Parameters'
TYPES = {'length': 'App::PropertyDistance', 'angle': 'App::PropertyAngle', 'number': 'App::PropertyFloat'}
UNITS = {'length': 'mm', 'angle': 'deg', 'number': ''}
KEEP = '__keep_expression__'


def container(doc):
    matches = [o for o in doc.Objects if getattr(o, 'FluxParameters', False)]
    if len(matches) > 1:
        raise ValueError(tr('この文書には複数のパラメータ一覧があります。標準ツリーで整理してください。',
                            'This document has multiple parameter sets. Resolve them in the native tree.'))
    return matches[0] if matches else None


def expression(obj, path):
    if path == 'V' and 'FluxPositionV' in obj.PropertiesList: path = 'FluxPositionV'
    paths = {path.lstrip('.')}
    match = re.fullmatch(r'Constraints\[(\d+)\]', path)
    if match:
        name = obj.Constraints[int(match[1])].Name
        if name: paths.update(('Constraints.' + name, 'Constraints.<<' + name + '>>'))
    return next((v for k, v in obj.ExpressionEngine if k.lstrip('.') in paths), '')


def value(obj, path):
    if path == 'V' and 'FluxPositionV' in obj.PropertiesList: path = 'FluxPositionV'
    match = re.fullmatch(r'Constraints\[(\d+)\]', path)
    return obj.getDatum(int(match[1])) if match else getattr(obj, path)


def formatted(number, kind):
    raw = number.Value if hasattr(number, 'Value') else float(number)
    return ('%.12g' % raw) + (' ' + UNITS[kind] if UNITS[kind] else '')


def rows(doc):
    obj = container(doc)
    if not obj: return []
    result = []
    for name in obj.PropertiesList:
        if obj.getGroupOfProperty(name) != GROUP: continue
        kind = next((k for k, t in TYPES.items() if t == obj.getTypeIdOfProperty(name)), None)
        if kind:
            result.append(dict(name=name, kind=kind, formula=expression(obj, name) or formatted(getattr(obj, name), kind),
                               result=formatted(getattr(obj, name), kind)))
    return result


def add_plastic_dimensions(obj, add):
    from model_plastic import FIELDS
    from plastic_panel import LABELS
    for key in FIELDS[obj.FluxPlastic]:
        if key=='Draft' and key not in obj.PropertiesList:
            continue
        add(obj,obj,key,'angle' if key in ('Angle','Draft') else 'length',tr(*LABELS[key]))

def dimensions(doc):
    """Only active scalar dimensions with known modeling semantics."""
    result = []; seen = set()
    def add(owner, obj, path, kind, label):
        key = (obj.Name, path)
        if key in seen: return
        seen.add(key)
        result.append(dict(owner=owner.Name, owner_label=owner.Label, object=obj.Name, path=path,
                           kind=kind, label=label, value=formatted(value(obj, path), kind),
                           expression=expression(obj, path)))
    for obj in doc.Objects:
        if obj.TypeId == 'Sketcher::SketchObject':
            for i, c in enumerate(obj.Constraints):
                if c.Type not in ('Distance', 'DistanceX', 'DistanceY', 'Radius', 'Diameter', 'Angle', 'AngleViaPoint'): continue
                if obj.getDriving(i):
                    add(obj, obj, 'Constraints[%d]' % i, 'angle' if c.Type.startswith('Angle') else 'length',
                        c.Name or '%s %d' % (c.Type, i + 1))
        elif getattr(obj,'FluxPrimitive','')=='dome':
            import model_dome
            model_dome.add_dimensions(obj,add)
        elif getattr(obj, 'FluxHole', False):
            tool = obj.Tool; kind = str(getattr(tool, 'HoleType', 'simple'))
            fields = [('U', tr('穴位置 U', 'Hole Position U')), ('V', tr('穴位置 V', 'Hole Position V'))]
            if kind != 'threaded': fields.append(('Diameter', tr('直径', 'Diameter')))
            if not tool.Through: fields.append(('Depth', tr('深さ', 'Depth')))
            if kind in ('counterbore', 'countersink'): fields.append(('HeadDiameter', tr('入口の直径', 'Entrance Diameter')))
            if kind == 'counterbore': fields.append(('HeadDepth', tr('ザグリ深さ', 'Counterbore Depth')))
            for prop, label in fields: add(obj, tool, prop, 'length', label)
            if kind == 'countersink': add(obj, tool, 'SinkAngle', 'angle', tr('皿角度', 'Countersink Angle'))
        elif getattr(obj, 'FluxExtent', False):
            import model_extents
            tool = model_extents.tool(obj)
            fields = [('StartOffset', 'length', tr('開始オフセット', 'Start Offset'))]
            if str(tool.Extent) == 'distance':
                fields.append(('Distance', 'length', tr('押し出し距離', 'Extrusion Distance')))
                if str(tool.Direction) == 'two': fields.append(('Second', 'length', tr('反対側の距離', 'Reverse Distance')))
            if str(tool.Extent) == 'face': fields.append(('EndOffset', 'length', tr('終点オフセット', 'End Offset')))
            fields.append(('TaperAngle', 'angle', tr('勾配角', 'Taper Angle')))
            if str(tool.Direction) == 'two': fields.append(('TaperAngleRev', 'angle', tr('反対側の勾配角', 'Reverse Taper')))
            for prop, kind, label in fields:
                if prop in tool.PropertiesList: add(obj, tool, prop, kind, label)
        elif getattr(obj, 'FluxPlastic', ''):
            add_plastic_dimensions(obj,add)
        elif getattr(obj, 'FluxDimensionScale', False):
            for axis in ('X', 'Y', 'Z'):
                add(obj, obj, 'Delta' + axis, 'length',
                    tr('%s方向の増減量', '%s Dimension Change') % axis)
        elif obj.TypeId == 'Part::Extrusion' and obj.Solid:
            add(obj, obj, 'LengthFwd', 'length', tr('押し出し距離', 'Extrusion Distance'))
            if obj.LengthRev.Value > 0: add(obj, obj, 'LengthRev', 'length', tr('反対側の距離', 'Reverse Distance'))
    return result


def fingerprint(doc):
    obj = container(doc)
    return repr((obj.Name if obj else None, rows(doc), dimensions(doc)))


def assigned(doc, item):
    obj = container(doc)
    if obj:
        for row in rows(doc):
            if item['expression'] == obj.Name + '.' + row['name']: return row['name']
    return KEEP if item['expression'] else None


def _formula(text, kind):
    text = text.strip().removeprefix('=').strip()
    if not text: raise ValueError(tr('値または式を入力してください。', 'Enter a value or expression.'))
    if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', text) and UNITS[kind]:
        text += ' ' + UNITS[kind]
    return text


def _validate_unit(obj, text, kind, name):
    actual = obj.evalExpression(text)
    if not hasattr(actual, 'Unit'): actual = App.Units.Quantity(float(actual))
    expected = App.Units.Quantity('1 ' + UNITS[kind] if UNITS[kind] else '1')
    if actual.Unit != expected.Unit or not math.isfinite(actual.Value):
        raise ValueError(tr('%s：単位が一致しないか、有限の数値ではありません。',
                            '%s: incompatible units or a non-finite value.') % name)


def _referenced(doc, obj, name):
    token = r'(?<!\w)' + re.escape(name) + r'(?!\w)'
    prefixes = (obj.Name + '.', '<<' + obj.Label + '>>.')
    for other in doc.Objects:
        for path, text in other.ExpressionEngine:
            if other == obj and path.lstrip('.') == name: continue
            if re.search(token, text) and (other == obj or any(p in text for p in prefixes)): return True
    return False


def apply(doc, entries, bindings=(), expected=None):
    if not doc or App.getDocument(doc.Name) != doc:
        raise ValueError(tr('対象文書が閉じられました。', 'The document was closed.'))
    if expected is not None and fingerprint(doc) != expected:
        raise ValueError(tr('文書の寸法が変更されています。一覧を閉じて開き直してください。',
                            'Document dimensions changed. Close and reopen this dialog.'))
    prior = {r['name']: r for r in rows(doc)}; current = container(doc)
    definitions = {}; reserved = set(current.PropertiesList if current else ['Label','Label2','Visibility','ExpressionEngine','FluxParameters']) - set(prior)
    for row in entries:
        name = row['name'].strip(); kind = row['kind']
        if not name.isidentifier() or name.startswith('_') or name in reserved or name in definitions:
            raise ValueError(tr('%s：名前が重複しているか使用できません。空白・記号・先頭の数字は使えません。',
                                '%s: duplicate or invalid name. Spaces, punctuation and leading digits are not allowed.') % name)
        if kind not in TYPES: raise ValueError(tr('単位の種類を選んでください。', 'Choose a unit type.'))
        if name in prior and kind != prior[name]['kind']:
            raise ValueError(tr('既存のパラメータの単位は変更できません。', 'The unit type of an existing parameter cannot be changed.'))
        definitions[name] = (kind, _formula(row['formula'], kind))
    available = {(d['object'], d['path']): d for d in dimensions(doc)}
    for binding in bindings:
        key = (binding['object'], binding['path']); name = binding['parameter']
        if key not in available: raise ValueError(tr('割り当て先が変更されています。開き直してください。', 'A target dimension changed. Reopen the dialog.'))
        if name not in (None, KEEP) and (name not in definitions or definitions[name][0] != available[key]['kind']):
            raise ValueError(tr('割り当てるパラメータの名前と単位を確認してください。', 'Check the parameter name and unit for this assignment.'))
    same_definitions = definitions == {name:(r['kind'],r['formula']) for name,r in prior.items()}
    same_bindings = all(b['parameter']==KEEP or
                        available[(b['object'],b['path'])]['expression']==
                        (current.Name+'.'+b['parameter'] if current and b['parameter'] else '') for b in bindings)
    if same_definitions and same_bindings:return current
    healthy = {o.Name: bool(o.Shape.Solids) for o in doc.Objects if hasattr(o,'Shape') and not o.Shape.isNull() and o.Shape.isValid()}
    with model.transaction(doc, tr('パラメータを変更', 'Change Parameters')):
        obj = current
        if obj is None:
            obj = doc.addObject('App::VarSet', 'Parameters'); obj.Label = tr('パラメータ', 'Parameters')
            obj.addProperty('App::PropertyBool','FluxParameters','FluxCAD'); obj.FluxParameters = True
            obj.setEditorMode('FluxParameters',2)
        for name in prior: obj.setExpression(name, None)
        for name, (kind, formula) in definitions.items():
            if name not in prior:
                obj.addProperty(TYPES[kind], name, GROUP)
                if name not in obj.PropertiesList: raise ValueError(tr('この名前は使用できません。', 'This name is not supported.'))
        for name, (kind, formula) in definitions.items():
            try: obj.setExpression(name, formula)
            except Exception as error: raise ValueError('%s: %s' % (name, error)) from None
        obj.recompute()
        for name, (kind, formula) in definitions.items(): _validate_unit(obj, formula, kind, name)
        for binding in bindings:
            name = binding['parameter']
            if name != KEEP:
                target = doc.getObject(binding['object']); path = binding['path']
                desired = None if name is None else obj.Name + '.' + name
                if expression(target,path) == (desired or ''):continue
                # FreeCAD 1.1 parses the legacy hole property V as the volt unit.
                # Use a native scalar alias; HoleTool keeps the legacy value in sync.
                if path == 'V' and (name is not None or 'FluxPositionV' in target.PropertiesList):
                    if 'FluxPositionV' not in target.PropertiesList:
                        target.addProperty('App::PropertyDistance','FluxPositionV','Hole')
                        target.FluxPositionV = target.V
                        target.setEditorMode('FluxPositionV',2)
                    path = 'FluxPositionV'
                try:target.setExpression(path, desired)
                except Exception as error:raise ValueError('%s.%s: %s' % (binding['object'],binding['path'],error)) from None
        for name in set(prior) - set(definitions):
            if _referenced(doc, obj, name):
                raise ValueError(tr('%s は式で使用中のため削除できません。先に割り当て・参照式を解除してください。',
                                    '%s is used by an expression. Remove its assignments and references first.') % name)
            obj.removeProperty(name)
        doc.recompute()
        for name, (kind, formula) in definitions.items(): _validate_unit(obj, formula, kind, name)
        for other in [obj] + list(obj.InListRecursive):
            if 'Invalid' in other.State or 'Error' in other.State:
                raise ValueError(tr('%s を再計算できません。変更は取り消しました。',
                                    'Cannot recompute %s. The changes were rolled back.') % other.Label)
        for name, solid in healthy.items():
            other = doc.getObject(name)
            if other and (other.Shape.isNull() or not other.Shape.isValid() or (solid and not other.Shape.Solids)):
                raise ValueError(tr('%s の形状が成立しません。変更は取り消しました。',
                                    '%s would have an invalid shape. The changes were rolled back.') % other.Label)
    return obj


def lock_fields(obj, mapping):
    """Existing feature editors preserve links instead of replacing dimensions."""
    for prop, widget in mapping.items():
        if not hasattr(widget, '_flux_unlinked_tooltip'): widget._flux_unlinked_tooltip = widget.toolTip()
        expr = expression(obj, prop) if obj and prop in obj.PropertiesList else ''
        widget.setEnabled(not bool(expr))
        widget.setToolTip(tr('式: %s\n「修正 → パラメータを変更」で編集できます。',
                             'Expression: %s\nEdit it using Modify → Change Parameters.') % expr if expr else widget._flux_unlinked_tooltip)
