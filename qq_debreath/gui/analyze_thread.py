from __future__ import annotations

from PyQt5.QtCore import QThread, pyqtSignal

from qq_debreath.core import AnalysisParams, analyze_audio


class AnalyzeThread(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, audio, sample_rate, model_bundle, source_path=None):
        super().__init__()
        self.audio = audio
        self.sample_rate = sample_rate
        self.model_bundle = model_bundle
        self.source_path = source_path

    def run(self):
        try:
            result = analyze_audio(
                self.audio,
                self.sample_rate,
                self.model_bundle,
                AnalysisParams(detect_noize=False),
                source_path=self.source_path,
                progress_callback=self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(result.regions)

