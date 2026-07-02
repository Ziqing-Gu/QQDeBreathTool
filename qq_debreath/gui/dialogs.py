from __future__ import annotations

from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 QQDeBreathTool")
        self.resize(620, 520)

        title = QLabel("QQDeBreathTool")
        title.setStyleSheet("QLabel { font-size: 22px; font-weight: 700; }")

        warning = QLabel("禁止商用，加 Q 群 692973169 交流")
        warning.setStyleSheet("QLabel { color: #D32F2F; font-size: 17px; font-weight: 800; padding: 4px 0; }")

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(
            """
            <p>QQDeBreathTool 是由混音师顾子青用 Codex 加载 ChatGPT 5.5 制作出来的分离齿音 / 噪音的软件，由程序员刁翔宇帮助编译修正。</p>
            <p>QQDeBreathTool 是一个面向人声后期处理的呼吸声分离工具，用于辅助将人声素材中的 Breath、Vocal Only 与 Noize 区块进行标记、试听和导出。</p>
            <p>软件会基于波形能量、频谱特征和区块边界稳定性自动分析呼吸声候选区域，并在分析时显示百分比进度。用户可以手动调整区块边界、修改区块类型，也可以直接右键区块在 Breath 与 Noize 之间快速切换。</p>
            <p>监听区支持 Voice、Breath、Noize 三路复选监听。未勾选的类型会在波形中以灰色显示，便于判断当前实际听到的内容。Fade 与 Breath Norm 可同步作用于监听；打开 Breath Norm 后，Breath 区块波形也会显示为标准化后的大小。</p>
            <p>导出时，软件会保持原始音频的时间长度和位置关系，生成可直接重新导入 DAW 工程的分轨文件，方便继续进行音量、EQ、压缩、混响或其他混音处理。</p>
            <p><b>主要功能：</b></p>
            <ul>
              <li>拖入 WAV 等音频文件并显示波形</li>
              <li>自动分析 Breath 区块</li>
              <li>手动拖动区块边界与修改类型</li>
              <li>支持 Breath / Noize 快捷键标记与右键切换</li>
              <li>支持 Voice、Breath、Noize 复选监听</li>
              <li>支持监听音量调整与电平 Meter，监听增益不会影响导出文件</li>
              <li>支持 Shift + 鼠标滚轮左右移动波形视图</li>
              <li>支持 Shift 拖动数值微调，Alt + 左键恢复默认数值</li>
              <li>支持全局 Fade In / Fade Out，并可选择是否作用于监听与导出</li>
              <li>支持 Breath 分段标准化，并可同步显示与监听</li>
              <li>支持恢复上次打开的音频和已编辑区块</li>
              <li>导出 Vocal Only、Breath、Noize 三条对齐音频</li>
            </ul>
            <p><b>建议用途：</b></p>
            <p>适合在人声混音前期或精修阶段，用来快速拆分呼吸声、清理非演唱内容，并保留完整时间线，方便在 Cubase、Nuendo、Pro Tools、Logic Pro 等 DAW 中继续处理。</p>
            <p>Version: 1.04<br>Developer: 顾子青 / 刁翔宇 / Codex / ChatGPT 5.5</p>
            """
        )

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close_btn)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(warning)
        layout.addWidget(text, 1)
        layout.addLayout(buttons)
        self.setLayout(layout)

