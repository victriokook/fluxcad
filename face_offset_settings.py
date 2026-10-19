import json

def save_settings(obj, filepath):
    import os
    import tempfile
    from pathlib import Path
    data = {"source": obj.Source.Name, "faces": list(obj.FaceNames), "distance": float(obj.Distance)}
    target = Path(filepath)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent, prefix='.fluxcad-offset-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
