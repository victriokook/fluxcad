"""Grid spacing entry that survives live palette refreshes."""
from PySide import QtCore, QtWidgets as W
from i18n import tr


class GridSpacingBox(W.QDoubleSpinBox):
    chosen = QtCore.Signal(float)

    def __init__(self):
        super().__init__()
        self.editing = False
        self.draft_valid = False
        self.setDecimals(3)
        self.setRange(0.001, 10000)
        self.setSingleStep(0.1)
        self.setSuffix(' mm')
        # Do not apply intermediate entries such as the zero in "0.5".
        self.setKeyboardTracking(False)
        self.setToolTip(tr('数値を入力してEnterで確定すると、その間隔に固定します。',
                           'Enter a value and press Enter to use a fixed grid spacing.'))
        self.lineEdit().textEdited.connect(self._text_edited)
        self.valueChanged.connect(self._value_changed)
        self.editingFinished.connect(self._finish)

    def _text_edited(self, text):
        self.editing = True
        self.draft_valid = self.hasAcceptableInput()

    def _value_changed(self, value):
        self.editing = False
        self.chosen.emit(value)

    def _finish(self):
        # Entering the same number must also switch automatic spacing to fixed.
        pending = self.editing and self.draft_valid
        self.editing = False
        if pending:
            self.chosen.emit(self.value())

    def sync(self, value, force=False):
        if not force and (self.editing or self.hasFocus() or self.lineEdit().hasFocus()):
            return
        if force:
            self.editing = False
        previous = self.blockSignals(True)
        try:
            # Avoid resetting the caret/selection when the value is unchanged.
            if force or abs(self.value() - value) > 1e-9:
                self.setValue(value)
        finally:
            self.blockSignals(previous)

    def choose(self, value):
        """Presets are explicit choices, including the currently displayed value."""
        self.sync(value, force=True)
        self.chosen.emit(self.value())
