def remember(fields):
    for field in fields.values():
        if hasattr(field, 'value'):
            field._flux_primitive_start_value = field.value()


def values(existing, fields, result):
    import model_primitives
    answer = dict(result)
    if existing is None:
        return answer
    original = model_primitives.settings(existing)
    for key, value in original.items():
        field = fields.get(key)
        if key in answer and hasattr(field, 'value') and answer[key] == getattr(field, '_flux_primitive_start_value', None):
            answer[key] = value
    return answer


def position(existing, fields, result):
    if existing is None:
        return tuple(result)
    original = tuple(existing.Placement.Base)
    return tuple(original[i] if result[i] == getattr(fields[key], '_flux_primitive_start_value', None) else result[i]
                 for i, key in enumerate(('x', 'y', 'z')))


def unchanged(existing, result, pose):
    import model_primitives
    if existing is None:
        return False
    return (result == model_primitives.settings(existing)
            and tuple(pose.toMatrix().A) == tuple(existing.Placement.toMatrix().A))


def lock_dimensions(existing, kind, fields):
    import parameters
    from i18n import tr
    mapping = {
        'sphere': {'diameter': 'Radius'},
        'torus': {'diameter': 'Radius1', 'section': 'Radius2'},
        'coil': {'diameter': 'Diameter', 'section': 'Section', 'pitch': 'Pitch', 'turns': 'Turns', 'left': 'LeftHanded'},
        'pipe': {'diameter': 'Diameter', 'wall': 'Wall', 'length': 'Length'},
    }.get(kind, {})
    for key in ('diameter', 'section', 'pitch', 'turns', 'left', 'wall', 'length'):
        field = fields[key]
        if not hasattr(field, '_flux_primitive_unlinked_tooltip'):
            field._flux_primitive_unlinked_tooltip = field.toolTip()
        prop = mapping.get(key)
        expression = parameters.expression(existing, prop) if existing is not None and prop else ''
        field.setEnabled(not bool(expression))
        field.setToolTip(tr('式: %s\n参照元の寸法を編集してください。', 'Expression: %s\nEdit the referenced dimension.') % expression
                         if expression else field._flux_primitive_unlinked_tooltip)


def check_placement(existing, pose):
    from i18n import tr
    if existing is None:
        return
    controlled = any(path.lstrip('.') == 'Placement' or path.lstrip('.').startswith('Placement.')
                     for path, expression in existing.ExpressionEngine)
    if controlled and tuple(pose.toMatrix().A) != tuple(existing.Placement.toMatrix().A):
        raise ValueError(tr('配置は式で制御されています。参照元の寸法を編集してください。',
                            'Placement is controlled by an expression. Edit the referenced dimension.'))


def lock_position(existing, fields):
    from i18n import tr
    expressions = [(path, value) for path, value in existing.ExpressionEngine
                   if path.lstrip('.') == 'Placement' or path.lstrip('.').startswith('Placement.')] if existing is not None else []
    details = '; '.join('%s = %s' % item for item in expressions)
    original = tuple(existing.Placement.Base) if expressions else None
    for index, key in enumerate(('x', 'y', 'z')):
        field = fields[key]
        if not hasattr(field, '_flux_position_unlinked_tooltip'):
            field._flux_position_unlinked_tooltip = field.toolTip()
        field.setEnabled(not bool(expressions))
        field.setToolTip(tr('配置の式: %s\n参照元の寸法を編集してください。', 'Placement expression: %s\nEdit the referenced dimension.') % details
                         if expressions else field._flux_position_unlinked_tooltip)
        if expressions:
            blocked = field.blockSignals(True)
            try:
                field.setValue(original[index])
            finally:
                field.blockSignals(blocked)
            field._flux_primitive_start_value = field.value()
            field._flux_dome_start_value = field.value()

def unchanged_dome(existing, result, pose):
    return (existing is not None and getattr(existing, 'FluxPrimitive', '') == 'dome'
            and 'WallThickness' in existing.PropertiesList and unchanged(existing, result, pose))
