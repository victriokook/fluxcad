"""Japanese / English UI text; language changes take effect on restart."""
import FreeCAD as App
from translations_en import EN

PREFERENCES='User parameter:BaseApp/Preferences/FluxCAD'
_language=App.ParamGet(PREFERENCES).GetString('Language','ja')
if _language not in ('ja','en'):_language='ja'


def language():
    return _language


def tr(source, english=None):
    """Translate a display string, with an optional contextual English form."""
    if _language=='en':return english if english is not None else EN.get(source,source)
    return source


def pending_language():
    result=App.ParamGet(PREFERENCES).GetString('Language',_language)
    return result if result in ('ja','en') else _language


def save_language(code):
    if code not in ('ja','en'):raise ValueError('Unsupported language: '+str(code))
    App.ParamGet(PREFERENCES).SetString('Language',code)
    # FreeCAD reads this preference on its next launch, including its native
    # Sketcher tasks. Never rebuild the workspace while a document is edited.
    App.ParamGet('User parameter:BaseApp/Preferences/General').SetString('Language',{'ja':'Japanese','en':'English'}[code])
    App.saveParameter()
