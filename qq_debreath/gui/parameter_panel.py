from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QLabel


class DragValueLabel(QLabel):
    valueChanged = pyqtSignal(float)

    def __init__(
        self,
        prefix,
        value=5.0,
        minimum=0.0,
        maximum=500.0,
        suffix="ms",
        decimals=1,
        default=None,
        step=1.0,
        fine_step=0.2,
    ):
        super().__init__()
        self.prefix = prefix
        self.suffix = suffix
        self.decimals = int(decimals)
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.value = max(self.minimum, min(self.maximum, float(value)))
        self.default = max(self.minimum, min(self.maximum, float(value if default is None else default)))
        self.step = float(step)
        self.fine_step = float(fine_step)
        self.dragging = False
        self.drag_y = 0
        self.drag_value = self.value
        self.setCursor(Qt.SizeVerCursor)
        self.setMinimumWidth(86)
        self.setMinimumHeight(26)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "QLabel { padding: 3px 8px; border: 1px solid #3E4756; "
            "border-radius: 4px; background: #151A22; color: #F8FAFC; "
            "font-weight: 650; } "
            "QLabel:hover { border-color: #64748B; background: #1B2230; }"
        )
        self.refresh()

    def refresh(self):
        self.setText(f"{self.prefix} {self.value:.{self.decimals}f} {self.suffix}")

    def setValue(self, value, emit=False):
        new_value = max(self.minimum, min(self.maximum, float(value)))
        if abs(new_value - self.value) < 1e-9:
            return
        self.value = new_value
        self.refresh()
        if emit:
            self.valueChanged.emit(self.value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.AltModifier:
                self.setValue(self.default, emit=True)
                return
            self.dragging = True
            self.drag_y = event.globalY()
            self.drag_value = self.value
            self.grabMouse()

    def mouseMoveEvent(self, event):
        if not self.dragging:
            return
        delta = self.drag_y - event.globalY()
        step = self.fine_step if event.modifiers() & Qt.ShiftModifier else self.step
        self.setValue(self.drag_value + delta * step, emit=True)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            self.releaseMouse()

    def mouseDoubleClickEvent(self, event):
        from PyQt5.QtWidgets import QInputDialog

        value, ok = QInputDialog.getDouble(self, self.prefix, self.suffix, self.value, self.minimum, self.maximum, self.decimals)
        if ok:
            self.setValue(value, emit=True)
