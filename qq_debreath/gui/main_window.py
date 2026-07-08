from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

from PyQt5.QtCore import Qt, QEvent, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollBar,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from qq_debreath.gui.analyze_thread import AnalyzeThread
from qq_debreath.gui.dialogs import AboutDialog
from qq_debreath.gui.meter import MeterWidget
from qq_debreath.gui.parameter_panel import DragValueLabel
from qq_debreath.gui.theme import APP_STYLESHEET
from qq_debreath.gui.waveform_view import WaveformWidget


def _legacy():
    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "ensure_numpy") and hasattr(main, "Region"):
        return main
    mod = sys.modules.get("debreath_tool_app")
    if mod is not None and hasattr(mod, "ensure_numpy") and hasattr(mod, "Region"):
        return mod
    return importlib.import_module("debreath_tool_app")


np = None


def ensure_numpy():
    global np
    np = _legacy().ensure_numpy()
    return np


def app_icon_path(*args, **kwargs):
    return _legacy().app_icon_path(*args, **kwargs)


def load_settings(*args, **kwargs):
    return _legacy().load_settings(*args, **kwargs)


def save_settings(*args, **kwargs):
    return _legacy().save_settings(*args, **kwargs)


def load_model(*args, **kwargs):
    return _legacy().load_model(*args, **kwargs)


def ensure_soundfile(*args, **kwargs):
    return _legacy().ensure_soundfile(*args, **kwargs)


def safe_wav_subtype(*args, **kwargs):
    return _legacy().safe_wav_subtype(*args, **kwargs)


def ensure_sounddevice(*args, **kwargs):
    return _legacy().ensure_sounddevice(*args, **kwargs)


def sanitize_audio_array(*args, **kwargs):
    return _legacy().sanitize_audio_array(*args, **kwargs)


def clean_audio_array(*args, **kwargs):
    return _legacy().clean_audio_array(*args, **kwargs)


def normalize_regions(*args, **kwargs):
    return _legacy().normalize_regions(*args, **kwargs)


def normalize_breath_blocks(*args, **kwargs):
    return _legacy().normalize_breath_blocks(*args, **kwargs)


def apply_breath_gain(*args, **kwargs):
    return _legacy().apply_breath_gain(*args, **kwargs)


def build_stem_gains(*args, **kwargs):
    return _legacy().build_stem_gains(*args, **kwargs)


def insert_region_with_boundaries(*args, **kwargs):
    return _legacy().insert_region_with_boundaries(*args, **kwargs)


def region_public_dict(*args, **kwargs):
    return _legacy().region_public_dict(*args, **kwargs)


def core_regions_to_gui_regions(*args, **kwargs):
    return _legacy().core_regions_to_gui_regions(*args, **kwargs)


def finite_float(*args, **kwargs):
    return _legacy().finite_float(*args, **kwargs)


def log_startup(*args, **kwargs):
    return _legacy().log_startup(*args, **kwargs)


def log_exception(*args, **kwargs):
    return _legacy().log_exception(*args, **kwargs)


def Region(*args, **kwargs):
    return _legacy().Region(*args, **kwargs)


DEFAULT_FADE_SECONDS = _legacy().DEFAULT_FADE_SECONDS
DEFAULT_BREATH_TARGET_DB = _legacy().DEFAULT_BREATH_TARGET_DB
EDITABLE_CLASSES = _legacy().EDITABLE_CLASSES
CLASSES = _legacy().CLASSES


def normalize_class_name(cls):
    return _legacy().normalize_class_name(cls)


def class_display_name(cls):
    return _legacy().class_display_name(cls)


class CopyableLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.copy_status_callback = None
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_copy_menu)
        self.setToolTip("双击或右键复制")

    def copy_text(self):
        text = self.text().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        if self.copy_status_callback is not None:
            self.copy_status_callback(f"已复制时码：{text}")

    def show_copy_menu(self, pos):
        menu = QMenu(self)
        action = menu.addAction("复制时码")
        if menu.exec_(self.mapToGlobal(pos)) == action:
            self.copy_text()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.copy_text()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("去呼吸 / 呼吸与噪音分离工具 1.11")
        self.setStyleSheet(APP_STYLESHEET)
        icon = app_icon_path()
        if icon:
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1180, 560)
        self.setAcceptDrops(True)
        self.audio = None
        self.sr = 48000
        self.subtype = "PCM_24"
        self.path = None
        self.model = None
        self.is_playing = False
        self.play_start_time = 0.0
        self.play_start_pos = 0.0
        self.playback_audio_length = 0
        self.playback_audio = None
        self.playback_device_sr = self.sr
        self.playback_end_timer = None
        self.updating_class_combo = False
        self.settings = load_settings()
        self.undo_stack = []
        self.redo_stack = []
        self.drag_snapshot = None
        self.analysis_thread = None
        self.analysis_progress = None
        self.analysis_model = None

        self.wave = WaveformWidget()

        open_btn = QPushButton("打开/拖入音频")
        self.undo_btn = QPushButton("Undo")
        self.redo_btn = QPushButton("Redo")
        self.play_btn = QPushButton("播放")
        self.play_follow = QCheckBox("跟随")
        self.play_follow.setChecked(bool(self.settings.get("play_follow", True)))
        self.play_follow.setToolTip("播放时自动翻动波形视图")
        self.return_to_play_start = QCheckBox("回起点")
        self.return_to_play_start.setChecked(bool(self.settings.get("return_to_play_start", False)))
        self.return_to_play_start.setToolTip("播放自然结束后，播放指针回到本次播放起点")
        stop_btn = QPushButton("停止")
        self.analyze_btn = QPushButton("分析")
        self.analyze_btn.setObjectName("primaryButton")
        self.analyze_btn.setMinimumWidth(82)
        self.export_btn = QPushButton("导出三轨")
        self.export_btn.setObjectName("exportButton")
        self.export_btn.setMinimumWidth(96)
        fit_btn = QPushButton("全览")
        delete_btn = QPushButton("删除区块")
        type_label = QLabel("类型:")
        self.class_combo = QComboBox()
        for cls in EDITABLE_CLASSES:
            self.class_combo.addItem(class_display_name(cls), cls)
        monitor_label = QLabel("Monitor:")
        monitor_label.setMinimumWidth(64)
        monitor_label.setToolTip("勾选要监听的分轨")
        self.monitor_voice = QCheckBox("Voice")
        self.monitor_voice.setChecked(bool(self.settings.get("monitor_voice", True)))
        self.monitor_breath = QCheckBox("Breath")
        self.monitor_breath.setChecked(bool(self.settings.get("monitor_breath", True)))
        self.monitor_noize = QCheckBox("Noise")
        self.monitor_noize.setChecked(bool(self.settings.get("monitor_noize", True)))
        self.display_gain = DragValueLabel("显示", 1.0, 0.1, 64.0, "x", 1)
        self.monitor_gain_db = DragValueLabel(
            "监听",
            float(self.settings.get("monitor_gain_db", 0.0)),
            -20.0,
            20.0,
            "dB",
            1,
            default=0.0,
        )
        self.monitor_gain_db.setToolTip("监听音量；只影响播放监听，不影响导出")
        self.monitor_meter = MeterWidget()
        about_btn = QPushButton("关于")
        self.enable_fade = QCheckBox("Fade")
        self.enable_fade.setChecked(bool(self.settings.get("enable_fade", True)))
        self.fade_in_ms = DragValueLabel("In", float(self.settings.get("fade_in_ms", DEFAULT_FADE_SECONDS * 1000.0)), default=DEFAULT_FADE_SECONDS * 1000.0)
        self.fade_out_ms = DragValueLabel("Out", float(self.settings.get("fade_out_ms", DEFAULT_FADE_SECONDS * 1000.0)), default=DEFAULT_FADE_SECONDS * 1000.0)
        self.normalize_breath = QCheckBox("呼吸标准化")
        self.normalize_breath.setChecked(bool(self.settings.get("normalize_breath", False)))
        self.breath_target_db = DragValueLabel(
            "目标",
            float(self.settings.get("breath_target_db", DEFAULT_BREATH_TARGET_DB)),
            -60.0,
            0.0,
            "dB",
            default=DEFAULT_BREATH_TARGET_DB,
        )
        self.breath_gain_db = DragValueLabel(
            "呼吸音量",
            float(self.settings.get("breath_gain_db", 0.0)),
            -30.0,
            30.0,
            "dB",
            1,
            default=0.0,
            step=0.1,
            fine_step=0.1,
        )
        self.region_info = QLabel("未选中区块")
        self.region_info.setObjectName("hintLabel")
        self.region_time_info = CopyableLabel("--:--.--- - --:--.---")
        self.region_time_info.setObjectName("timeLabel")
        self.region_time_info.setMinimumWidth(172)
        self.region_time_info.setToolTip("选中区块的时码范围；双击或右键复制")
        self.position_info = CopyableLabel("00:00.000")
        self.position_info.setObjectName("timeLabel")
        self.status = QLabel("拖入一个音频文件开始。")
        self.status.setObjectName("statusLabel")
        self.region_time_info.copy_status_callback = self.status.setText
        self.position_info.copy_status_callback = self.status.setText
        self.view_scroll = QScrollBar(Qt.Horizontal)
        self.view_scroll.setEnabled(False)

        open_btn.clicked.connect(self.open_file_dialog)
        self.undo_btn.clicked.connect(self.undo)
        self.redo_btn.clicked.connect(self.redo)
        self.play_btn.clicked.connect(self.toggle_playback)
        stop_btn.clicked.connect(lambda: self.stop_playback(return_to_start=True))
        self.analyze_btn.clicked.connect(self.analyze)
        self.export_btn.clicked.connect(self.export)
        about_btn.clicked.connect(self.show_about)
        fit_btn.clicked.connect(self.fit_view)
        delete_btn.clicked.connect(self.delete_region)
        self.class_combo.currentIndexChanged.connect(self.class_combo_changed)
        self.display_gain.valueChanged.connect(self.wave.set_display_gain)
        self.enable_fade.stateChanged.connect(self.global_fade_changed)
        self.fade_in_ms.valueChanged.connect(self.global_fade_changed)
        self.fade_out_ms.valueChanged.connect(self.global_fade_changed)
        self.normalize_breath.stateChanged.connect(self.monitor_settings_changed)
        self.breath_target_db.valueChanged.connect(self.monitor_settings_changed)
        self.breath_gain_db.valueChanged.connect(self.monitor_settings_changed)
        self.play_follow.stateChanged.connect(self.save_user_settings)
        self.return_to_play_start.stateChanged.connect(self.save_user_settings)
        self.monitor_voice.stateChanged.connect(self.monitor_settings_changed)
        self.monitor_breath.stateChanged.connect(self.monitor_settings_changed)
        self.monitor_noize.stateChanged.connect(self.monitor_settings_changed)
        self.monitor_gain_db.valueChanged.connect(self.monitor_gain_changed)
        self.wave.selectedChanged.connect(self.selection_changed)
        self.wave.regionsChanged.connect(self.regions_changed)
        self.wave.playheadChanged.connect(self.playhead_changed)
        self.wave.editStarted.connect(self.begin_region_edit)
        self.wave.editFinished.connect(self.finish_region_edit)
        self.wave.viewChanged.connect(self.sync_view_scrollbar)
        self.wave.regionTypeToggleRequested.connect(self.toggle_region_type_from_wave)
        self.view_scroll.valueChanged.connect(self.scrollbar_moved)

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.update_playhead_from_audio)
        self.playback_end_timer = QTimer(self)
        self.playback_end_timer.setSingleShot(True)
        self.playback_end_timer.timeout.connect(self.finish_playback_at_end)
        self.global_fade_changed()
        self.update_wave_display_processing()
        self.update_history_buttons()
        QTimer.singleShot(0, self.restore_last_session)

        top = QHBoxLayout()
        top.setContentsMargins(10, 8, 10, 6)
        top.setSpacing(7)
        for w in [
            open_btn,
            self.undo_btn,
            self.redo_btn,
            self.analyze_btn,
            type_label,
            self.class_combo,
            delete_btn,
        ]:
            top.addWidget(w)
        top.addStretch(1)
        for w in [
            self.enable_fade,
            self.fade_in_ms,
            self.fade_out_ms,
            self.normalize_breath,
            self.breath_target_db,
            self.breath_gain_db,
        ]:
            top.addWidget(w)
        top.addWidget(self.export_btn)

        transport = QHBoxLayout()
        transport.setContentsMargins(10, 6, 10, 4)
        transport.setSpacing(7)
        for w in [
            self.play_btn,
            self.play_follow,
            self.return_to_play_start,
            stop_btn,
            monitor_label,
            self.monitor_voice,
            self.monitor_breath,
            self.monitor_noize,
            fit_btn,
            self.display_gain,
            about_btn,
        ]:
            transport.addWidget(w)
        transport.addStretch(1)
        transport.addWidget(self.monitor_gain_db)
        transport.addWidget(self.monitor_meter)

        info = QHBoxLayout()
        info.setContentsMargins(10, 2, 10, 2)
        info.setSpacing(8)
        info.addWidget(self.region_info)
        info.addStretch(1)
        info.addWidget(QLabel("区块:"))
        info.addWidget(self.region_time_info)
        info.addWidget(QLabel("当前位置:"))
        info.addWidget(self.position_info)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(top)
        layout.addWidget(self.wave, 4)
        layout.addWidget(self.view_scroll)
        layout.addLayout(transport)
        layout.addLayout(info)
        layout.addWidget(self.status)
        root = QWidget()
        root.setObjectName("appRoot")
        root.setLayout(layout)
        self.setCentralWidget(root)
        QApplication.instance().installEventFilter(self)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.load_file(Path(urls[0].toLocalFile()))

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择音频文件", "", "Audio Files (*.wav *.aif *.aiff *.flac *.ogg *.mp3);;All Files (*.*)")
        if path:
            self.load_file(Path(path))

    def load_file(self, path, save_session_now=True):
        try:
            reader = ensure_soundfile()
            info = reader.info(str(path))
            audio, sr = reader.read(str(path), always_2d=True, dtype="float64")
            audio, audio_report = sanitize_audio_array(audio)
        except Exception as exc:
            QMessageBox.critical(self, "读取失败", str(exc))
            return
        self.audio = audio
        self.sr = sr
        self.subtype = safe_wav_subtype(info.subtype)
        self.path = Path(path)
        self.wave.set_audio(audio, sr)
        self.wave.set_regions([])
        self.sync_view_scrollbar(self.wave.view_start, self.wave.view_end)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_history_buttons()
        self.selection_changed(-1)
        self.playhead_changed(0.0)
        log_startup(
            f"loaded file={path} sr={sr} channels={audio.shape[1]} duration={len(audio) / sr:.3f} "
            f"peak={audio_report['peak']:.8f} p99={audio_report['p99']:.8f} "
            f"invalid={audio_report['invalid_count']} invalid_ratio={audio_report['invalid_ratio']:.6f}"
        )
        self.status.setText(f"已加载：{path} | {sr} Hz | {audio.shape[1]} ch | {len(audio) / sr:.3f} s")
        self.status.setText(self.status.text() + f" | peak {audio_report['peak']:.6f} | p99 {audio_report['p99']:.6f}")
        if save_session_now:
            self.save_session()

    def ensure_model(self):
        if self.model is None:
            self.model = load_model()
        return self.model

    def analyze(self):
        if self.audio is None:
            return
        try:
            model = self.ensure_model()
        except Exception as exc:
            QMessageBox.critical(self, "分析失败", str(exc))
            return

        if self.analysis_thread is not None and self.analysis_thread.isRunning():
            return

        self.stop_playback()
        self.analyze_btn.setEnabled(False)
        self.status.setText("正在分析 Breath，请稍候...")
        self.analysis_progress = QProgressDialog("正在分析 Breath... 0%", "", 0, 100, self)
        self.analysis_progress.setWindowTitle("分析中")
        self.analysis_progress.setWindowFlags(self.analysis_progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.analysis_progress.setWindowModality(Qt.WindowModal)
        self.analysis_progress.setMinimumDuration(0)
        self.analysis_progress.setCancelButton(None)
        self.analysis_progress.setValue(0)
        self.analysis_progress.show()

        if sys.platform == "darwin":
            self.analysis_model = model
            QTimer.singleShot(0, self.run_analysis_on_main_thread)
            return

        self.analysis_thread = AnalyzeThread(self.audio, self.sr, model, self.path)
        self.analysis_thread.progress.connect(self.analysis_progress_changed)
        self.analysis_thread.completed.connect(self.analysis_finished)
        self.analysis_thread.failed.connect(self.analysis_failed)
        self.analysis_thread.finished.connect(self.analysis_cleanup)
        self.analysis_thread.start()

    def run_analysis_on_main_thread(self):
        try:
            QApplication.processEvents()
            from qq_debreath.core import AnalysisParams, analyze_audio

            result = analyze_audio(
                self.audio,
                self.sr,
                self.analysis_model,
                AnalysisParams(detect_noize=False),
                source_path=self.path,
                progress_callback=self.analysis_progress_changed,
            )
            regions = core_regions_to_gui_regions(result.regions)
        except Exception as exc:
            log_exception("mac main-thread analysis failed")
            self.analysis_failed(str(exc))
        else:
            self.analysis_finished(regions)
        finally:
            self.analysis_model = None
            self.analysis_cleanup()

    def analysis_progress_changed(self, value):
        if self.analysis_progress is None:
            return
        value = max(0, min(100, int(value)))
        self.analysis_progress.setValue(value)
        self.analysis_progress.setLabelText(f"正在分析 Breath... {value}%")
        QApplication.processEvents()

    def analysis_finished(self, regions):
        regions = core_regions_to_gui_regions(regions)
        self.push_undo("Analyze")
        self.wave.set_regions(regions)
        self.redo_stack.clear()
        self.selection_changed(self.wave.selected)
        self.save_session()
        breath_count = sum(1 for r in regions if r.cls == "Breath")
        if breath_count:
            self.status.setText(f"分析完成：{breath_count} 个 Breath。Noise 已留给手动标记。")
        else:
            self.status.setText("分析完成：没有检测到 Breath。可用 Shift 手动画区块。")

    def analysis_failed(self, message):
        QMessageBox.critical(self, "分析失败", message)
        self.status.setText("分析失败。")

    def analysis_cleanup(self):
        if self.analysis_progress is not None:
            self.analysis_progress.close()
            self.analysis_progress = None
        self.analyze_btn.setEnabled(True)
        if self.analysis_thread is not None:
            self.analysis_thread.deleteLater()
            self.analysis_thread = None

    def format_time(self, seconds):
        seconds = max(0.0, float(seconds))
        minutes = int(seconds // 60)
        rem = seconds - minutes * 60
        return f"{minutes:02d}:{rem:06.3f}"

    def snapshot_regions(self):
        return {
            "regions": [region_public_dict(r) for r in self.wave.regions],
            "selected": self.wave.selected,
        }

    def restore_snapshot(self, snapshot):
        self.wave.regions = [
            Region(float(r["start"]), float(r["end"]), normalize_class_name(r["cls"]), finite_float(r.get("confidence", 1.0), 1.0))
            for r in snapshot.get("regions", [])
        ]
        self.wave.selected = int(snapshot.get("selected", -1))
        self.wave.regions = normalize_regions(self.wave.regions, self.wave.duration)
        if self.wave.selected >= len(self.wave.regions):
            self.wave.selected = -1
        self.selection_changed(self.wave.selected)
        self.wave.update()
        self.update_history_buttons()
        self.save_session()

    def snapshots_equal(self, a, b):
        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

    def push_undo(self, label="Edit"):
        snap = self.snapshot_regions()
        if self.undo_stack and self.snapshots_equal(self.undo_stack[-1], snap):
            return
        self.undo_stack.append(snap)
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)
        self.update_history_buttons()

    def begin_region_edit(self):
        self.drag_snapshot = self.snapshot_regions()

    def finish_region_edit(self):
        if self.drag_snapshot is None:
            return
        current = self.snapshot_regions()
        if not self.snapshots_equal(self.drag_snapshot, current):
            self.undo_stack.append(self.drag_snapshot)
            if len(self.undo_stack) > 100:
                self.undo_stack.pop(0)
            self.redo_stack.clear()
        self.drag_snapshot = None
        self.update_history_buttons()

    def undo(self):
        if not self.undo_stack:
            return
        current = self.snapshot_regions()
        snap = self.undo_stack.pop()
        self.redo_stack.append(current)
        self.restore_snapshot(snap)

    def redo(self):
        if not self.redo_stack:
            return
        current = self.snapshot_regions()
        snap = self.redo_stack.pop()
        self.undo_stack.append(current)
        self.restore_snapshot(snap)

    def update_history_buttons(self):
        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(bool(self.undo_stack))
            self.redo_btn.setEnabled(bool(self.redo_stack))

    def selection_changed(self, idx):
        self.updating_class_combo = True
        if idx >= 0 and idx < len(self.wave.regions):
            r = self.wave.regions[idx]
            combo_index = self.class_combo.findData(r.cls)
            if combo_index >= 0:
                self.class_combo.setCurrentIndex(combo_index)
            time_range = f"{self.format_time(r.start)} - {self.format_time(r.end)}"
            self.region_info.setText(f"已选：{class_display_name(r.cls)} | {time_range}")
            self.region_time_info.setText(time_range)
        else:
            self.region_info.setText("Shift+拖动新增区块；右键区块切换 Breath/Noise；Shift+滚轮左右移动；数值拖动时 Shift 微调，Alt+左键恢复默认；B/N 改类型，Delete 删除。")
            self.region_time_info.setText("--:--.--- - --:--.---")
        self.updating_class_combo = False

    def regions_changed(self):
        selected_region = None
        if 0 <= self.wave.selected < len(self.wave.regions):
            selected_region = self.wave.regions[self.wave.selected].copy()
        self.wave.regions = normalize_regions(self.wave.regions, self.wave.duration)
        if selected_region is not None:
            self.wave.selected = self.find_matching_region_index(selected_region)
        if self.wave.selected >= len(self.wave.regions):
            self.wave.selected = -1
        self.wave.invalidate_waveform_cache()
        self.selection_changed(self.wave.selected)
        self.wave.update()
        self.save_session()

    def find_matching_region_index(self, target):
        best = -1
        best_score = 1e9
        for i, r in enumerate(self.wave.regions):
            if r.cls != target.cls:
                continue
            score = abs(r.start - target.start) + abs(r.end - target.end)
            if score < best_score:
                best = i
                best_score = score
        if best_score <= 0.05:
            return best
        return -1

    def class_combo_changed(self, *args):
        cls = self.class_combo.currentData()
        if cls is None:
            cls = normalize_class_name(self.class_combo.currentText())
        self.wave.set_new_class(cls)
        if self.updating_class_combo:
            return
        idx = self.wave.selected
        if idx < 0 or idx >= len(self.wave.regions):
            return
        if self.wave.regions[idx].cls == cls:
            return
        self.push_undo("Change Type")
        self.wave.regions[idx].cls = cls
        self.redo_stack.clear()
        self.regions_changed()

    def set_selected_region_type(self, cls):
        cls = normalize_class_name(cls)
        if cls not in EDITABLE_CLASSES:
            return
        combo_index = self.class_combo.findData(cls)
        if combo_index >= 0:
            was_blocked = self.class_combo.blockSignals(True)
            self.class_combo.setCurrentIndex(combo_index)
            self.class_combo.blockSignals(was_blocked)
        self.wave.set_new_class(cls)
        idx = self.wave.selected
        if idx < 0 or idx >= len(self.wave.regions):
            return
        if self.wave.regions[idx].cls == cls:
            return
        self.push_undo("Change Type")
        self.wave.regions[idx].cls = cls
        self.redo_stack.clear()
        self.regions_changed()
        self.status.setText(f"已设为 {class_display_name(cls)}。")

    def toggle_region_type_from_wave(self, idx):
        if idx < 0 or idx >= len(self.wave.regions):
            return
        current = self.wave.regions[idx].cls
        next_cls = "Noize" if current == "Breath" else "Breath"
        self.set_selected_region_type(next_cls)

    def monitor_visible_classes(self):
        visible = set()
        if self.monitor_voice.isChecked():
            visible.add("Vocal Only")
        if self.monitor_breath.isChecked():
            visible.add("Breath")
        if self.monitor_noize.isChecked():
            visible.add("Noize")
        return visible

    def update_wave_display_processing(self):
        self.wave.set_display_processing(
            self.normalize_breath.isChecked(),
            self.breath_target_db.value,
            self.breath_gain_db.value,
            self.monitor_visible_classes(),
        )

    def global_fade_changed(self, *args):
        if self.enable_fade.isChecked():
            self.wave.set_global_fades(self.fade_in_ms.value, self.fade_out_ms.value)
        else:
            self.wave.set_global_fades(0.0, 0.0)
        self.save_user_settings()
        self.update_wave_display_processing()
        if self.is_playing:
            self.start_playback()

    def save_user_settings(self, *args):
        self.settings["normalize_breath"] = bool(self.normalize_breath.isChecked())
        self.settings["breath_target_db"] = float(self.breath_target_db.value)
        self.settings["breath_gain_db"] = float(self.breath_gain_db.value)
        self.settings["enable_fade"] = bool(self.enable_fade.isChecked())
        self.settings["fade_in_ms"] = float(self.fade_in_ms.value)
        self.settings["fade_out_ms"] = float(self.fade_out_ms.value)
        self.settings["play_follow"] = bool(self.play_follow.isChecked())
        self.settings["return_to_play_start"] = bool(self.return_to_play_start.isChecked())
        self.settings["monitor_voice"] = bool(self.monitor_voice.isChecked())
        self.settings["monitor_breath"] = bool(self.monitor_breath.isChecked())
        self.settings["monitor_noize"] = bool(self.monitor_noize.isChecked())
        self.settings["monitor_gain_db"] = float(self.monitor_gain_db.value)
        save_settings(self.settings)

    def save_session(self):
        # Standalone/exe only: remember the last local WAV and edited regions.
        # Future ARA/VST3 builds must not restore this global local-file state;
        # ARA follows the current DAW Audio Event/Source, and VST3 follows the
        # current plugin instance recorded buffer.
        if self.path is None:
            return
        self.settings["last_file"] = str(self.path)
        self.settings["last_regions"] = [region_public_dict(r) for r in self.wave.regions]
        save_settings(self.settings)

    def restore_last_session(self):
        # Standalone/exe only. Do not copy this behavior into ARA/VST3 plugins.
        last_file = self.settings.get("last_file")
        if not last_file:
            return
        path = Path(last_file)
        if not path.exists():
            QMessageBox.warning(self, "找不到上次的音频文件", f"上次打开的文件不存在：\n{path}")
            self.settings["last_file"] = ""
            self.settings["last_regions"] = []
            save_settings(self.settings)
            return
        saved_regions = list(self.settings.get("last_regions", []))
        self.load_file(path, save_session_now=False)
        regions = []
        for item in saved_regions:
            try:
                regions.append(
                    Region(
                        float(item["start"]),
                        float(item["end"]),
                        normalize_class_name(item["cls"]),
                        finite_float(item.get("confidence", 1.0), 1.0),
                    )
                )
            except Exception:
                pass
        self.wave.set_regions(normalize_regions(regions, self.wave.duration))
        self.selection_changed(-1)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_history_buttons()
        self.status.setText(f"已恢复上次会话：{path}")
        self.save_session()

    def playhead_changed(self, pos):
        self.position_info.setText(self.format_time(pos))
        if self.is_playing and abs(pos - (self.play_start_pos + (time.monotonic() - self.play_start_time))) > 0.12:
            self.start_playback()

    def delete_region(self):
        idx = self.wave.selected
        if idx >= 0 and idx < len(self.wave.regions):
            self.push_undo("Delete Region")
            self.wave.regions.pop(idx)
            self.wave.selected = -1
            self.redo_stack.clear()
            self.regions_changed()
            self.status.setText("已删除选中区块。")

    def fit_view(self):
        if self.audio is not None:
            self.wave.set_view(0.0, self.wave.duration)

    def sync_view_scrollbar(self, start, end):
        duration = max(0.0, float(self.wave.duration))
        span = max(0.0, float(end) - float(start))
        scale = 1000
        max_value = max(0, int(round((duration - span) * scale)))
        page_step = max(1, int(round(span * scale)))
        value = max(0, min(max_value, int(round(float(start) * scale))))
        self.view_scroll.blockSignals(True)
        self.view_scroll.setRange(0, max_value)
        self.view_scroll.setPageStep(page_step)
        self.view_scroll.setSingleStep(max(1, int(round(0.05 * scale))))
        self.view_scroll.setValue(value)
        self.view_scroll.setEnabled(max_value > 0)
        self.view_scroll.blockSignals(False)

    def scrollbar_moved(self, value):
        if self.audio is None:
            return
        scale = 1000
        span = self.wave.view_end - self.wave.view_start
        start = float(value) / scale
        self.wave.set_view(start, start + span, emit=False)

    def export(self):
        if self.audio is None or self.path is None:
            return
        folder = QFileDialog.getExistingDirectory(self, "选择导出文件夹", str(self.path.parent))
        if not folder:
            return
        temp_path = Path(folder) / self.path.name
        try:
            fade_in = self.fade_in_ms.value if self.enable_fade.isChecked() else 0.0
            fade_out = self.fade_out_ms.value if self.enable_fade.isChecked() else 0.0
            from qq_debreath.core import AnalysisParams
            from qq_debreath.core.facade import render_stems

            out = render_stems(
                self.audio,
                self.sr,
                self.wave.regions,
                AnalysisParams(
                    detect_noize=False,
                    fade_seconds=DEFAULT_FADE_SECONDS,
                    breath_target_db=self.breath_target_db.value,
                    breath_gain_db=self.breath_gain_db.value,
                    normalize_breath=self.normalize_breath.isChecked(),
                ),
                folder,
                source_path=temp_path,
                subtype=self.subtype,
                fade_in_ms=fade_in,
                fade_out_ms=fade_out,
            )
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "导出完成", "\n".join(out.values()))

    def toggle_playback(self):
        if self.is_playing:
            self.stop_playback(return_to_start=True)
        else:
            self.start_playback()

    def monitor_settings_changed(self, *args):
        self.save_user_settings()
        self.update_wave_display_processing()
        if self.is_playing:
            self.start_playback()

    def monitor_gain_changed(self, value):
        self.save_user_settings()
        if self.is_playing:
            self.start_playback()

    def show_about(self):
        AboutDialog(self).exec_()

    def follow_playhead_if_needed(self, pos):
        if not self.play_follow.isChecked() or self.audio is None:
            return
        start = self.wave.view_start
        end = self.wave.view_end
        span = max(0.5, end - start)
        if span >= self.wave.duration - 1e-6:
            return
        if pos < start or pos >= end:
            new_start = max(0.0, min(self.wave.duration - span, pos))
            self.wave.set_view(new_start, new_start + span)

    def start_playback(self):
        if self.audio is None:
            return
        self.stop_playback(reset_button=False)
        start_sample = int(round(self.wave.playhead * self.sr))
        start_sample = max(0, min(len(self.audio) - 1, start_sample))
        self.follow_playhead_if_needed(start_sample / self.sr)
        playback_audio = self.make_playback_audio()
        self.playback_audio = playback_audio
        self.playback_audio_length = len(playback_audio)
        self.playback_device_sr = self.sr
        try:
            player = ensure_sounddevice()
            player.play(playback_audio[start_sample:], self.sr, blocking=False)
        except Exception as exc:
            QMessageBox.critical(self, "播放失败", str(exc))
            return
        self.is_playing = True
        self.play_start_time = time.monotonic()
        self.play_start_pos = start_sample / self.sr
        self.play_btn.setText("暂停")
        self.timer.start()
        remaining_ms = max(1, int(round((len(playback_audio) - start_sample) / self.sr * 1000.0)) - 3)
        self.playback_end_timer.start(remaining_ms)

    def apply_monitor_gain(self, data):
        gain = 10 ** (self.monitor_gain_db.value / 20.0)
        return data * gain

    def make_playback_audio(self):
        ensure_numpy()
        if not any(
            [
                self.monitor_voice.isChecked(),
                self.monitor_breath.isChecked(),
                self.monitor_noize.isChecked(),
            ]
        ):
            return np.zeros_like(self.audio)
        fade_in = self.fade_in_ms.value if self.enable_fade.isChecked() else 0.0
        fade_out = self.fade_out_ms.value if self.enable_fade.isChecked() else 0.0
        gains, class_id = build_stem_gains(
            len(self.audio),
            self.sr,
            self.wave.regions,
            fade_in,
            fade_out,
        )
        data = np.zeros_like(self.audio)
        if self.monitor_voice.isChecked():
            data += self.audio * gains[:, class_id["Vocal Only"]][:, None]
        if self.monitor_breath.isChecked():
            breath = self.audio * gains[:, class_id["Breath"]][:, None]
            if self.normalize_breath.isChecked():
                breath = normalize_breath_blocks(
                    breath.copy(),
                    self.audio,
                    self.wave.regions,
                    self.sr,
                    self.breath_target_db.value,
                )
            breath = apply_breath_gain(breath, self.breath_gain_db.value)
            data += breath
        if self.monitor_noize.isChecked():
            data += self.audio * gains[:, class_id["Noize"]][:, None]
        return self.apply_monitor_gain(data)

    def stop_playback(self, reset_button=True, return_to_start=False):
        was_playing = self.is_playing
        return_pos = self.play_start_pos
        if self.is_playing:
            try:
                ensure_sounddevice().stop()
            except Exception:
                log_exception("stop_playback failed")
        if self.playback_end_timer is not None:
            self.playback_end_timer.stop()
        self.is_playing = False
        self.playback_audio_length = 0
        self.playback_audio = None
        self.playback_device_sr = self.sr
        self.timer.stop()
        self.monitor_meter.set_level(-80.0, False)
        if reset_button:
            self.play_btn.setText("播放")
        if was_playing and return_to_start and self.return_to_play_start.isChecked() and self.audio is not None:
            self.wave.set_playhead(return_pos)
            self.follow_playhead_if_needed(return_pos)

    def finish_playback_at_end(self):
        if not self.is_playing or self.audio is None:
            return
        if self.return_to_play_start.isChecked():
            self.stop_playback(return_to_start=True)
            return
        duration = (self.playback_audio_length or len(self.audio)) / self.sr
        self.wave.set_playhead(duration)
        self.follow_playhead_if_needed(duration)
        self.update_monitor_meter(duration)
        self.stop_playback()

    def update_monitor_meter(self, pos):
        if self.audio is None:
            self.monitor_meter.set_level(-80.0, False)
            return
        start = max(0, int(round(pos * self.sr)))
        window = max(1, int(round(0.08 * self.sr)))
        end = min(len(self.audio), start + window)
        if end <= start:
            self.monitor_meter.set_level(-80.0, False)
            return
        source = self.playback_audio
        if source is None:
            source = self.make_playback_audio()
        chunk = source[start:end]
        peak = float(np.max(np.abs(chunk))) if chunk.size else 0.0
        db = 20.0 * np.log10(max(peak, 1e-12))
        self.monitor_meter.set_level(db, peak >= 1.0)

    def update_playhead_from_audio(self):
        if not self.is_playing or self.audio is None:
            return
        pos = self.play_start_pos + (time.monotonic() - self.play_start_time)
        playback_duration = (self.playback_audio_length or len(self.audio)) / self.sr
        if pos >= playback_duration:
            pos = playback_duration
            if self.return_to_play_start.isChecked():
                self.stop_playback(return_to_start=True)
                return
            self.stop_playback()
        self.wave.set_playhead(pos)
        self.follow_playhead_if_needed(pos)
        self.update_monitor_meter(pos)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier and not event.isAutoRepeat():
                if event.modifiers() & Qt.ShiftModifier:
                    self.redo()
                else:
                    self.undo()
                return True
            if event.key() == Qt.Key_Space and not event.isAutoRepeat():
                self.toggle_playback()
                return True
            if event.key() == Qt.Key_Delete and not event.isAutoRepeat():
                self.delete_region()
                return True
            if event.key() == Qt.Key_B and not event.isAutoRepeat():
                self.set_selected_region_type("Breath")
                return True
            if event.key() == Qt.Key_N and not event.isAutoRepeat():
                self.set_selected_region_type("Noise")
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier and not event.isAutoRepeat():
            if event.modifiers() & Qt.ShiftModifier:
                self.redo()
            else:
                self.undo()
            event.accept()
            return
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self.toggle_playback()
            event.accept()
            return
        if event.key() == Qt.Key_Delete and not event.isAutoRepeat():
            self.delete_region()
            event.accept()
            return
        if event.key() == Qt.Key_B and not event.isAutoRepeat():
            self.set_selected_region_type("Breath")
            event.accept()
            return
        if event.key() == Qt.Key_N and not event.isAutoRepeat():
            self.set_selected_region_type("Noise")
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.stop_playback()
        super().closeEvent(event)
