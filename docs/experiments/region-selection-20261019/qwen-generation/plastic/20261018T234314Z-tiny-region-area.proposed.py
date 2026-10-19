def format_region_area(area):
    value = float(area)
    if not math.isfinite(value) or value < 0:
        raise ValueError('Invalid region area')
    if 0 < value < 0.01:
        return format(value, '.6g')
    return format(value, '.2f')
