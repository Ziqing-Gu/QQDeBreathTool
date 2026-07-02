from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget


class MeterWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.level_db = -80.0
        self.clip = False
        self.setFixedSize(104, 20)
        self.setToolTip("监听电平表；爆音时显示 CLIP")

    def set_level(self, level_db, clip=False):
        self.level_db = max(-80.0, min(12.0, float(level_db)))
        self.clip = bool(clip)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(17, 22, 29))
        painter.setPen(QPen(QColor(49, 58, 70), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        norm = max(0.0, min(1.0, (self.level_db + 60.0) / 60.0))
        width = int(norm * (self.width() - 2))
        if self.clip:
            color = QColor(239, 68, 68)
        elif self.level_db > -6.0:
            color = QColor(245, 158, 11)
        else:
            color = QColor(34, 197, 94)
        painter.fillRect(1, 1, width, self.height() - 2, color)

        painter.setPen(QPen(QColor(226, 232, 240), 1))
        text = "CLIP" if self.clip else f"{self.level_db:.1f} dB"
        painter.drawText(self.rect(), Qt.AlignCenter, text)

