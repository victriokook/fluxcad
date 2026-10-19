def crossing_nested_regions(sketch, regions):
    if not regions:
        return regions
    material = regions[0]['face']
    if len(regions) > 1:
        material = material.multiFuse([r['face'] for r in regions[1:]])
    missing = []
    for cell in _cells(_geometry(sketch)):
        cell = cell.copy()
        cell.Placement = sketch.Placement.multiply(cell.Placement)
        tolerance = max(1e-9, cell.Area * 1e-8)
        overlap = cell.common(material).Area
        if overlap <= tolerance:
            missing.append(cell)
        elif abs(overlap - cell.Area) > tolerance:
            raise _reference_error()
    missing.sort(key=lambda c: (c.CenterOfMass.x, c.CenterOfMass.y, c.CenterOfMass.z, c.Area))
    result = list(regions)
    for index, face in enumerate(missing):
        result.append(dict(face=face, edges=[], inputs=[], network=True, nested_cell=True,
                           key=('CrossingNestedRegion%d' % (index + 1),)))
    return result
