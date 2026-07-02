"""Shared stylesheet for the standalone Qt GUI."""


APP_STYLESHEET = """
QMainWindow {
    background: #101318;
    color: #E6EAF0;
}

QWidget#appRoot {
    background: #101318;
    color: #E6EAF0;
}

QPushButton {
    min-height: 26px;
    padding: 4px 10px;
    border: 1px solid #343B46;
    border-radius: 4px;
    background: #202631;
    color: #E8ECF3;
    font-weight: 600;
}

QPushButton:hover {
    background: #2A3240;
    border-color: #4B5565;
}

QPushButton:pressed {
    background: #171C24;
}

QPushButton:disabled {
    background: #20242B;
    color: #6F7887;
    border-color: #2B3038;
}

QPushButton#primaryButton {
    background: #2563EB;
    border-color: #3B82F6;
    color: white;
}

QPushButton#primaryButton:hover {
    background: #2F6FF4;
}

QPushButton#exportButton {
    background: #059669;
    border-color: #10B981;
    color: white;
}

QPushButton#exportButton:hover {
    background: #0AA875;
}

QLabel {
    color: #CDD5E1;
}

QLabel#timeLabel {
    color: #F8FAFC;
    font-family: Consolas, "Cascadia Mono", monospace;
    font-weight: 700;
    padding: 2px 8px;
    background: #171C24;
    border: 1px solid #2E3540;
    border-radius: 4px;
}

QLabel#statusLabel {
    color: #AAB4C3;
    padding: 5px 8px;
    background: #141922;
    border-top: 1px solid #252C36;
}

QLabel#hintLabel {
    color: #AAB4C3;
}

QCheckBox {
    color: #E6EAF0;
    spacing: 6px;
    min-height: 26px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid #586273;
    background: #151A22;
}

QCheckBox::indicator:checked {
    background: #38BDF8;
    border-color: #7DD3FC;
}

QComboBox {
    min-height: 26px;
    padding: 3px 24px 3px 8px;
    border: 1px solid #343B46;
    border-radius: 4px;
    background: #171C24;
    color: #F1F5F9;
}

QComboBox:hover {
    border-color: #4B5565;
}

QComboBox QAbstractItemView {
    background: #171C24;
    color: #F1F5F9;
    selection-background-color: #2563EB;
    border: 1px solid #343B46;
}

QScrollBar:horizontal {
    height: 12px;
    background: #11161D;
    border: 1px solid #252C36;
    border-radius: 4px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #3E4756;
    min-width: 32px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #566173;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
    height: 0;
}
"""
