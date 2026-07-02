from __future__ import annotations

import importlib
import math
import sys

from PyQt5.QtCore import Qt, QRectF, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QWidget


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


def clean_audio_array(*args, **kwargs):
    return _legacy().clean_audio_array(*args, **kwargs)


def normalize_breath_blocks(*args, **kwargs):
    return _legacy().normalize_breath_blocks(*args, **kwargs)


def apply_breath_gain(*args, **kwargs):
    return _legacy().apply_breath_gain(*args, **kwargs)


def build_stem_gains(*args, **kwargs):
    return _legacy().build_stem_gains(*args, **kwargs)


def normalize_regions(*args, **kwargs):
    return _legacy().normalize_regions(*args, **kwargs)


def insert_region_with_boundaries(*args, **kwargs):
    return _legacy().insert_region_with_boundaries(*args, **kwargs)


def finite_float(*args, **kwargs):
    return _legacy().finite_float(*args, **kwargs)


def Region(*args, **kwargs):
    return _legacy().Region(*args, **kwargs)


DEFAULT_FADE_SECONDS = _legacy().DEFAULT_FADE_SECONDS
DEFAULT_BREATH_TARGET_DB = _legacy().DEFAULT_BREATH_TARGET_DB
CLASSES = _legacy().CLASSES
COLORS = _legacy().COLORS


class WaveformWidget(QWidget):
    selectedChanged = pyqtSignal(int)
    regionsChanged = pyqtSignal()
    playheadChanged = pyqtSignal(float)
    editStarted = pyqtSignal()
    editFinished = pyqtSignal()
    viewChanged = pyqtSignal(float, float)
    regionTypeToggleRequested = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.audio = None
        self.sr = 48000
        self.duration = 1.0
        self.regions = []
        self.selected = -1
        self.view_start = 0.0
        self.view_end = 1.0
        self.drag_mode = None
        self.drag_region = -1
        self.create_start = None
        self.temp_end = None
        self.new_class = "Breath"
        self.playhead = 0.0
        self.display_gain = 1.0
        self.global_fade_in = DEFAULT_FADE_SECONDS
        self.global_fade_out = DEFAULT_FADE_SECONDS
        self.normalize_breath_display = False
        self.breath_target_db = DEFAULT_BREATH_TARGET_DB
        self.breath_gain_db = 0.0
        self.monitor_visible_classes = set(CLASSES)
        self.hover_region = -1
        self.hover_edge = None
        self.setMinimumHeight(260)
        self.setMouseTracking(True)

    def set_audio(self, audio, sr):
        ensure_numpy()
        audio = clean_audio_array(audio)
        self.audio = np.nan_to_num(np.mean(audio, axis=1), nan=0.0, posinf=0.0, neginf=0.0)
        self.sr = int(sr) if sr else 48000
        self.duration = len(self.audio) / sr
        self.view_start = 0.0
        self.view_end = self.duration
        self.selected = -1
        self.playhead = 0.0
        self.update()
        self.viewChanged.emit(self.view_start, self.view_end)

    def set_regions(self, regions):
        self.regions = regions
        self.update()

    def set_new_class(self, cls):
        self.new_class = cls

    def set_playhead(self, t):
        self.playhead = max(0.0, min(self.duration, float(t)))
        self.playheadChanged.emit(self.playhead)
        self.update()

    def set_display_gain(self, gain):
        self.display_gain = max(0.1, min(64.0, finite_float(gain, 1.0)))
        self.update()

    def waveform_display_amp(self, samples):
        if samples.size == 0:
            return 1e-6
        abs_samples = np.abs(samples)
        finite = abs_samples[np.isfinite(abs_samples)]
        if finite.size == 0:
            return 1e-6
        nonzero = finite[finite > 1e-10]
        source = nonzero if nonzero.size else finite
        amp = max(
            finite_float(np.percentile(source, 99.0), 0.0),
            finite_float(np.percentile(source, 95.0), 0.0) * 1.8,
            finite_float(np.max(source), 0.0) * 0.18,
        )
        return max(amp, 1e-6)

    def waveform_column_bounds(self, samples, cols):
        if samples.size == 0 or cols <= 0:
            return np.zeros(0), np.zeros(0), 1e-6
        lo = np.zeros(cols, dtype=np.float64)
        hi = np.zeros(cols, dtype=np.float64)
        peaks = np.zeros(cols, dtype=np.float64)
        length = len(samples)
        for x in range(cols):
            start = int(x * length / cols)
            end = int((x + 1) * length / cols)
            if end <= start:
                end = min(length, start + 1)
            chunk = samples[start:end]
            if chunk.size == 0:
                continue
            lo[x] = finite_float(np.min(chunk), 0.0)
            hi[x] = finite_float(np.max(chunk), 0.0)
            peaks[x] = max(abs(lo[x]), abs(hi[x]))
        active = peaks[np.isfinite(peaks) & (peaks > 1e-10)]
        if active.size:
            amp = max(
                finite_float(np.percentile(active, 92.0), 0.0),
                finite_float(np.percentile(active, 75.0), 0.0) * 1.8,
                finite_float(np.median(active), 0.0) * 3.0,
                finite_float(np.max(active), 0.0) * 0.035,
            )
        else:
            amp = self.waveform_display_amp(samples)
        return lo, hi, max(amp, 1e-6)

    def set_view(self, start, end, emit=True):
        if self.audio is None:
            return
        span = max(0.01, float(end) - float(start))
        span = min(span, self.duration)
        start = max(0.0, min(self.duration - span, float(start)))
        end = start + span
        changed = abs(start - self.view_start) > 1e-9 or abs(end - self.view_end) > 1e-9
        self.view_start = start
        self.view_end = end
        self.update()
        if emit and changed:
            self.viewChanged.emit(self.view_start, self.view_end)

    def set_global_fades(self, fade_in_ms, fade_out_ms):
        self.global_fade_in = max(0.0, float(fade_in_ms)) / 1000.0
        self.global_fade_out = max(0.0, float(fade_out_ms)) / 1000.0
        self.update()

    def set_display_processing(
        self,
        normalize_breath=False,
        breath_target_db=DEFAULT_BREATH_TARGET_DB,
        breath_gain_db=0.0,
        visible_classes=None,
    ):
        self.normalize_breath_display = bool(normalize_breath)
        self.breath_target_db = finite_float(breath_target_db, DEFAULT_BREATH_TARGET_DB)
        self.breath_gain_db = max(-30.0, min(30.0, finite_float(breath_gain_db, 0.0)))
        self.monitor_visible_classes = set(visible_classes or CLASSES)
        self.update()

    def time_to_x(self, t):
        w = max(1, self.width())
        return int((t - self.view_start) / max(1e-9, self.view_end - self.view_start) * w)

    def x_to_time(self, x):
        return self.view_start + x / max(1, self.width()) * (self.view_end - self.view_start)

    def regions_touch(self, left, right):
        if left.cls == right.cls:
            return False
        return abs(float(right.start) - float(left.end)) <= max(2.0 / max(1, self.sr), 0.002)

    def draw_fade_x(self, painter, x1, x2, top, bottom):
        if x2 <= x1:
            return
        painter.drawLine(x1, bottom, x2, top)
        painter.drawLine(x1, top, x2, bottom)

    def class_at_time(self, t):
        for r in reversed(self.regions):
            if r.start <= t <= r.end:
                return r.cls
        return "Vocal Only"

    def view_samples_for_display(self, start_sample, end_sample):
        samples = np.asarray(self.audio[start_sample:end_sample], dtype=np.float64).copy()
        if samples.size:
            samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
        if samples.size == 0:
            return samples
        target_peak = 10.0 ** (self.breath_target_db / 20.0)
        breath_gain = 10.0 ** (self.breath_gain_db / 20.0)
        for r in self.regions:
            if r.cls != "Breath":
                continue
            region_start = max(0, min(len(self.audio), int(round(r.start * self.sr))))
            region_end = max(region_start, min(len(self.audio), int(round(r.end * self.sr))))
            if region_end <= start_sample or region_start >= end_sample:
                continue
            a = max(region_start, start_sample) - start_sample
            b = min(region_end, end_sample) - start_sample
            if self.normalize_breath_display and target_peak > 0:
                source = self.audio[region_start:region_end]
                peak = float(np.max(np.abs(source))) if source.size else 0.0
                if peak > 1e-9:
                    samples[a:b] *= target_peak / peak
            samples[a:b] *= breath_gain
        return samples

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(12, 16, 22))
        painter.fillRect(self.rect(), COLORS["Vocal Only"])
        mid = self.height() // 2
        painter.setPen(QPen(QColor(48, 56, 68), 1))
        painter.drawLine(0, mid, self.width(), mid)

        for i, r in enumerate(self.regions):
            x1 = self.time_to_x(r.start)
            x2 = self.time_to_x(r.end)
            if x2 < 0 or x1 > self.width():
                continue
            top = 24
            bottom = self.height() - 4
            painter.fillRect(QRectF(x1, 24, max(1, x2 - x1), self.height() - 28), COLORS[r.cls])
            fade_pen = QPen(QColor(226, 232, 240, 150), 1)
            painter.setPen(fade_pen)
            fade_in = min(self.global_fade_in, (r.end - r.start) * 0.5)
            fade_out = min(self.global_fade_out, (r.end - r.start) * 0.5)
            touches_left = i > 0 and self.regions_touch(self.regions[i - 1], r)
            touches_right = i + 1 < len(self.regions) and self.regions_touch(r, self.regions[i + 1])
            if fade_in > 0 and not touches_left:
                fx = self.time_to_x(min(r.end, r.start + fade_in))
                self.draw_fade_x(painter, x1, fx, top, bottom)
                painter.drawLine(fx, top, fx, bottom)
            if fade_out > 0 and not touches_right:
                fx = self.time_to_x(max(r.start, r.end - fade_out))
                self.draw_fade_x(painter, fx, x2, top, bottom)
                painter.drawLine(fx, top, fx, bottom)
            if touches_right:
                next_region = self.regions[i + 1]
                boundary = (r.end + next_region.start) * 0.5
                left_fade = min(self.global_fade_out, (r.end - r.start) * 0.5)
                right_fade = min(self.global_fade_in, (next_region.end - next_region.start) * 0.5)
                xa = self.time_to_x(max(r.start, boundary - left_fade))
                xb = self.time_to_x(min(next_region.end, boundary + right_fade))
                self.draw_fade_x(painter, xa, xb, top, bottom)
                painter.drawLine(self.time_to_x(boundary), top, self.time_to_x(boundary), bottom)
            painter.setBrush(Qt.NoBrush)
            if i == self.hover_region and self.hover_edge in {"left", "right"}:
                hx = x1 if self.hover_edge == "left" else x2
                painter.setPen(QPen(QColor(250, 204, 21), 4))
                painter.drawLine(hx, 22, hx, self.height())
            if i == self.selected:
                painter.setPen(QPen(QColor(248, 250, 252), 2))
                painter.drawRect(QRectF(x1, 24, max(1, x2 - x1), self.height() - 28))

        if self.drag_mode == "create" and self.create_start is not None and self.temp_end is not None:
            x1 = self.time_to_x(min(self.create_start, self.temp_end))
            x2 = self.time_to_x(max(self.create_start, self.temp_end))
            painter.fillRect(QRectF(x1, 24, max(1, x2 - x1), self.height() - 28), COLORS[self.new_class])
            painter.setPen(QPen(QColor(248, 250, 252), 1))
            painter.drawRect(QRectF(x1, 24, max(1, x2 - x1), self.height() - 28))

        if self.audio is not None and len(self.audio) > 0:
            ensure_numpy()
            a = int(self.view_start * self.sr)
            b = int(self.view_end * self.sr)
            a = max(0, min(len(self.audio) - 1, a))
            b = max(a + 1, min(len(self.audio), b))
            raw_samples = np.asarray(self.audio[a:b], dtype=np.float64).copy()
            if raw_samples.size:
                raw_samples = np.nan_to_num(raw_samples, nan=0.0, posinf=0.0, neginf=0.0)
            samples = self.view_samples_for_display(a, b)
            cols = max(1, self.width())
            col_lo, col_hi, _ = self.waveform_column_bounds(samples, cols)
            _, _, amp = self.waveform_column_bounds(raw_samples, cols)
            display_gain = finite_float(self.display_gain, 1.0)
            for x in range(cols):
                if x >= len(col_lo):
                    continue
                t = self.x_to_time(x)
                cls = self.class_at_time(t)
                if cls in self.monitor_visible_classes:
                    painter.setPen(QPen(QColor(226, 232, 240), 1))
                else:
                    painter.setPen(QPen(QColor(92, 104, 121), 1))
                lo = col_lo[x] / amp * display_gain
                hi = col_hi[x] / amp * display_gain
                if not math.isfinite(lo) or not math.isfinite(hi):
                    continue
                y1 = mid - int(np.clip(hi, -1, 1) * (self.height() * 0.42))
                y2 = mid - int(np.clip(lo, -1, 1) * (self.height() * 0.42))
                painter.drawLine(x, y1, x, y2)

        if self.view_start <= self.playhead <= self.view_end:
            x = self.time_to_x(self.playhead)
            painter.setPen(QPen(QColor(250, 204, 21), 2))
            painter.drawLine(x, 22, x, self.height())

    def hit_region(self, x):
        t = self.x_to_time(x)
        best = -1
        for i, r in enumerate(self.regions):
            if r.start <= t <= r.end:
                best = i
        return best

    def hit_edge(self, idx, t):
        if idx < 0 or idx >= len(self.regions):
            return None
        r = self.regions[idx]
        near = max(0.01, 0.006 * (self.view_end - self.view_start))
        if abs(t - r.start) <= near:
            return "left"
        if abs(t - r.end) <= near:
            return "right"
        return None

    def update_hover(self, x):
        idx = self.hit_region(x)
        edge = self.hit_edge(idx, self.x_to_time(x))
        changed = idx != self.hover_region or edge != self.hover_edge
        self.hover_region = idx
        self.hover_edge = edge
        if edge in {"left", "right"}:
            self.setCursor(Qt.SizeHorCursor)
        elif idx >= 0:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.unsetCursor()
        if changed:
            self.update()

    def mousePressEvent(self, event):
        t = self.x_to_time(event.x())
        if event.button() == Qt.RightButton:
            idx = self.hit_region(event.x())
            if idx >= 0:
                self.selected = idx
                self.selectedChanged.emit(idx)
                self.regionTypeToggleRequested.emit(idx)
                self.update()
                event.accept()
                return
            event.accept()
            return
        if event.button() != Qt.LeftButton:
            return
        self.set_playhead(t)
        if event.modifiers() & Qt.ShiftModifier:
            self.editStarted.emit()
            self.create_start = t
            self.temp_end = t
            self.drag_mode = "create"
            return
        idx = self.hit_region(event.x())
        self.selected = idx
        self.selectedChanged.emit(idx)
        if idx >= 0:
            r = self.regions[idx]
            edge = self.hit_edge(idx, t)
            if edge == "left":
                self.drag_mode = "left"
            elif edge == "right":
                self.drag_mode = "right"
            else:
                self.drag_mode = "move"
            self.drag_region = idx
            self.drag_anchor = t
            self.orig = r.copy()
            self.editStarted.emit()
        self.update()

    def mouseMoveEvent(self, event):
        if self.drag_mode is None:
            self.update_hover(event.x())
            return
        t = max(0.0, min(self.duration, self.x_to_time(event.x())))
        if self.drag_mode == "create":
            self.temp_end = t
            self.update()
            return
        if self.drag_region < 0:
            return
        r = self.regions[self.drag_region]
        if self.drag_mode == "left":
            r.start = min(t, r.end - 0.005)
        elif self.drag_mode == "right":
            r.end = max(t, r.start + 0.005)
        elif self.drag_mode == "move":
            delta = t - self.drag_anchor
            dur = self.orig.end - self.orig.start
            r.start = max(0.0, min(self.duration - dur, self.orig.start + delta))
            r.end = r.start + dur
        self.regionsChanged.emit()
        self.update()

    def mouseReleaseEvent(self, event):
        if self.drag_mode == "create" and self.create_start is not None:
            end = self.x_to_time(event.x())
            a, b = sorted([self.create_start, end])
            if b - a >= 0.02:
                self.regions, self.selected = insert_region_with_boundaries(
                    self.regions,
                    Region(a, b, self.new_class),
                    self.duration,
                )
                self.regionsChanged.emit()
                self.selectedChanged.emit(self.selected)
        self.drag_mode = None
        self.drag_region = -1
        self.create_start = None
        self.temp_end = None
        self.editFinished.emit()
        self.update_hover(event.x())
        self.update()

    def wheelEvent(self, event):
        if self.audio is None:
            return
        span = self.view_end - self.view_start
        angle_delta = event.angleDelta()
        if abs(angle_delta.x()) > 0 or abs(angle_delta.y()) > 0:
            dx = float(angle_delta.x())
            dy = float(angle_delta.y())
            uses_physical_wheel = True
        else:
            pixel_delta = event.pixelDelta()
            dx = float(pixel_delta.x())
            dy = float(pixel_delta.y())
            uses_physical_wheel = False
        if (not uses_physical_wheel) and event.inverted():
            dx = -dx
            dy = -dy
        if event.modifiers() & Qt.ShiftModifier:
            primary_delta = dy if abs(dy) > 1e-9 else dx
            if abs(primary_delta) < 1e-9:
                event.accept()
                return
            direction = -1.0 if primary_delta > 0 else 1.0
            step = span * 0.18 * direction
            start = self.view_start + step
            self.set_view(start, start + span)
            event.accept()
            return
        center = self.x_to_time(event.x())
        primary_delta = dy if abs(dy) >= abs(dx) else dx
        if abs(primary_delta) < 1e-9:
            event.accept()
            return
        factor = 0.8 if primary_delta > 0 else 1.25
        new_span = max(0.5, min(self.duration, span * factor))
        ratio = (center - self.view_start) / max(1e-9, span)
        view_start = max(0.0, min(self.duration - new_span, center - ratio * new_span))
        self.set_view(view_start, view_start + new_span)
        event.accept()
