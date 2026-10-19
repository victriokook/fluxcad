import json,os,math,tempfile
from pathlib import Path
from i18n import tr

def _error():
    return ValueError(tr('アニメーション設定ファイルの形式または値が無効です。','Invalid animation settings file format or values.'))

def _number(v,low,high,digits):
    if isinstance(v,bool) or not isinstance(v,(int,float)):raise _error()
    if not low<=v<=high or not math.isfinite(v) or round(v,digits)!=v:raise _error()
    return float(v)

def validate(p):
    keys={'format','version','mode','axis','degrees','frames','fps','width','height','background','translation'}
    if not isinstance(p,dict) or set(p)!=keys:raise _error()
    if p['format']!='FluxCAD-animation' or type(p['version']) is not int or p['version']!=1:raise _error()
    if p['mode'] not in ('camera','part') or p['axis'] not in ('X','Y','Z') or p['background'] not in ('White','Transparent','Current'):raise _error()
    for key,low,high in (('frames',2,240),('fps',1,60),('width',64,2048),('height',64,2048)):
        if type(p[key]) is not int or not low<=p[key]<=high:raise _error()
    degrees=_number(p['degrees'],-3600,3600,1)
    if not isinstance(p['translation'],list) or len(p['translation'])!=3:raise _error()
    translation=[_number(v,-10000,10000,3) for v in p['translation']]
    return dict(format='FluxCAD-animation',version=1,mode=p['mode'],axis=p['axis'],degrees=degrees,frames=p['frames'],fps=p['fps'],width=p['width'],height=p['height'],background=p['background'],translation=translation)

def _pairs(items):
    result={}
    for key,value in items:
        if key in result:raise _error()
        result[key]=value
    return result

def read(path):
    with Path(path).open('rb') as handle:raw=handle.read(32769)
    if len(raw)>32768:raise _error()
    try:data=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=_pairs)
    except (json.JSONDecodeError,UnicodeDecodeError):raise _error() from None
    return validate(data)

def write(path,payload):
    raw=(json.dumps(validate(payload),ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
    target=Path(path);temporary=None
    try:
        with tempfile.NamedTemporaryFile(delete=False,dir=str(target.parent),prefix='.fluxcad-preset-',suffix='.tmp') as handle:
            temporary=Path(handle.name);handle.write(raw);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,target)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return target
