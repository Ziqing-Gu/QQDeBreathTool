from __future__ import annotations

import argparse
import faulthandler
import json
import math
import os
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def diagnostic_dir():
    try:
        if sys.platform.startswith("win"):
            root = Path(os.getenv("APPDATA", str(Path.home()))) / "QQDeBreathTool"
        elif sys.platform == "darwin":
            root = Path.home() / "Library" / "Application Support" / "QQDeBreathTool"
        else:
            root = Path(os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "QQDeBreathTool"
        root.mkdir(parents=True, exist_ok=True)
        return root
    except Exception:
        return Path.cwd()


def write_diagnostic(filename, message):
    try:
        stamp = datetime.now().isoformat(timespec="seconds")
        path = diagnostic_dir() / filename
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def log_startup(message):
    write_diagnostic("startup.log", message)


def log_exception(message, exc_info=None):
    if exc_info is None:
        exc_info = sys.exc_info()
    detail = "".join(traceback.format_exception(*exc_info))
    write_diagnostic("crash.log", f"{message}\n{detail}")


_DEFAULT_EXCEPTHOOK = sys.excepthook


def _log_unhandled_exception(exc_type, exc, tb):
    if issubclass(exc_type, KeyboardInterrupt):
        return _DEFAULT_EXCEPTHOOK(exc_type, exc, tb)
    log_exception("Unhandled exception", (exc_type, exc, tb))
    if sys.stderr:
        _DEFAULT_EXCEPTHOOK(exc_type, exc, tb)


sys.excepthook = _log_unhandled_exception
log_startup(f"process start argv={sys.argv}")

_FATAL_LOG_HANDLE = None
try:
    _FATAL_LOG_HANDLE = (diagnostic_dir() / "fatal.log").open("a", encoding="utf-8")
    faulthandler.enable(file=_FATAL_LOG_HANDLE, all_threads=True)
except Exception:
    _FATAL_LOG_HANDLE = None

for _thread_var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_thread_var, "1")

joblib = None
np = None
_ma = None
sf = None
ndimage = None
signal = None

from PyQt5.QtCore import Qt, QRectF, QEvent, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


FRAME_MS = 25
HOP_MS = 5
DEFAULT_FADE_SECONDS = 0.010
DEFAULT_BREATH_TARGET_DB = -6.0
DEFAULT_BREATH_THRESHOLD = 0.86
DEFAULT_AUTO_BREATH_MIN_SECONDS = 0.12
AUTO_BREATH_SHORT_REVIEW_SECONDS = 0.16
CLASSES = ["Vocal Only", "Breath", "Noize"]
EDITABLE_CLASSES = ["Breath", "Noize"]
COLORS = {
    "Vocal Only": QColor(67, 160, 71, 45),
    "Breath": QColor(30, 136, 229, 105),
    "Noize": QColor(251, 140, 0, 105),
}


def ensure_numpy():
    global np
    if np is None:
        import numpy as _np

        np = _np
        log_startup("loaded numpy")
    return np


def ensure_scipy_signal():
    global signal
    if signal is None:
        from scipy import signal as _signal

        signal = _signal
        log_startup("loaded scipy.signal")
    return signal


def ensure_scipy_ndimage():
    global ndimage
    if ndimage is None:
        from scipy import ndimage as _ndimage

        ndimage = _ndimage
        log_startup("loaded scipy.ndimage")
    return ndimage


def ensure_joblib():
    global joblib
    if joblib is None:
        import joblib as _joblib

        joblib = _joblib
        log_startup("loaded joblib")
    return joblib


def ensure_soundfile():
    global sf
    if sf is None:
        import soundfile as _sf

        sf = _sf
        log_startup("loaded soundfile")
    return sf


def ensure_miniaudio():
    global _ma
    if _ma is None:
        import miniaudio as _ma_mod

        _ma = _ma_mod
        log_startup("loaded miniaudio")
    return _ma


def _make_audio_generator(audio_f32, nchannels):
    """Generator that yields raw float32 PCM chunks for miniaudio."""
    raw = audio_f32.ravel().tobytes()
    sample_size = 4  # float32 = 4 bytes
    required_frames = yield b""
    current = 0
    total = len(raw)
    while current < total:
        byte_count = required_frames * nchannels * sample_size
        chunk = raw[current:current + byte_count]
        current += len(chunk)
        if len(chunk) < byte_count:
            chunk += b"\x00" * (byte_count - len(chunk))
        required_frames = yield chunk


def ensure_sklearn_model_imports():
    from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: F401
    from sklearn.pipeline import Pipeline  # noqa: F401
    from sklearn.preprocessing import StandardScaler  # noqa: F401

    log_startup("loaded sklearn model classes")


def sanitize_audio_array(audio):
    ensure_numpy()
    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim == 1:
        audio = audio[:, None]
    if audio.ndim != 2:
        raise ValueError("Unsupported audio shape.")
    audio = np.ascontiguousarray(audio)
    total = int(audio.size)
    finite_all = np.isfinite(audio)
    finite_abs = np.abs(audio[finite_all]) if total else np.array([], dtype=np.float64)
    finite_reasonable = finite_abs[finite_abs < 32.0]
    if finite_reasonable.size:
        robust = float(np.percentile(finite_reasonable, 99.9))
        extreme_limit = max(32.0, robust * 64.0)
    else:
        extreme_limit = 32.0
    invalid_mask = (~finite_all) | (np.abs(audio) > extreme_limit)
    invalid_count = int(np.count_nonzero(invalid_mask)) if total else 0
    repaired_channels = 0
    silent_channels = 0
    if invalid_count:
        audio = audio.copy()
        positions = np.arange(audio.shape[0])
        for ch in range(audio.shape[1]):
            channel = audio[:, ch]
            valid = np.isfinite(channel) & (np.abs(channel) <= extreme_limit)
            if np.all(valid):
                continue
            if np.any(valid):
                valid_idx = positions[valid]
                channel[~valid] = np.interp(positions[~valid], valid_idx, channel[valid])
                repaired_channels += 1
            else:
                channel[:] = 0.0
                silent_channels += 1
    finite_after = np.abs(audio[np.isfinite(audio)])
    finite_after = finite_after[finite_after > 1e-10]
    if finite_after.size:
        clip_ref = float(np.percentile(finite_after, 99.9))
        clip_limit = max(1.0, min(4.0, clip_ref * 4.0))
        if clip_limit < float(np.max(finite_after)):
            audio = np.clip(audio, -clip_limit, clip_limit)
    else:
        clip_limit = 1.0
    abs_audio = np.abs(audio)
    peak = float(np.max(abs_audio)) if abs_audio.size else 0.0
    p99 = float(np.percentile(abs_audio, 99.5)) if abs_audio.size else 0.0
    report = {
        "samples": int(audio.shape[0]),
        "channels": int(audio.shape[1]),
        "invalid_count": invalid_count,
        "invalid_ratio": (invalid_count / total) if total else 0.0,
        "repaired_channels": repaired_channels,
        "silent_channels": silent_channels,
        "extreme_limit": extreme_limit,
        "clip_limit": clip_limit,
        "peak": peak,
        "p99": p99,
    }
    return audio, report


def clean_audio_array(audio):
    return sanitize_audio_array(audio)[0]


def remove_dc_offset(audio):
    ensure_numpy()
    working = np.asarray(audio, dtype=np.float64)
    if working.ndim == 1:
        working = working[:, None]
    if working.size == 0:
        return working
    corrected = working.copy()
    for ch in range(corrected.shape[1]):
        channel = corrected[:, ch]
        finite = channel[np.isfinite(channel)]
        if finite.size == 0:
            continue
        offset = float(np.median(finite))
        if abs(offset) > 1e-9:
            channel -= offset
    return corrected


def finite_float(value, default=0.0):
    try:
        value = float(value)
    except Exception:
        return default
    return value if math.isfinite(value) else default


BREATH_TIME_OVERRIDES = {}


@dataclass
class Region:
    start: float
    end: float
    cls: str
    confidence: float = 1.0

    def copy(self):
        return Region(self.start, self.end, self.cls, self.confidence)


def app_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def app_icon_path():
    path = app_root() / "debreath_icon.ico"
    if path.exists():
        return path
    local = Path(__file__).resolve().parent / "debreath_icon.ico"
    return local if local.exists() else None


def candidate_model_paths():
    paths = [
        app_root() / "breath_frame_model.joblib",
        Path.cwd() / "breath_frame_model.joblib",
    ]
    return paths


def load_model(path=None):
    ensure_sklearn_model_imports()
    loader = ensure_joblib()
    if path:
        return loader.load(path)
    for p in candidate_model_paths():
        if p.exists():
            return loader.load(p)
    raise FileNotFoundError("breath_frame_model.joblib was not found.")


def settings_path():
    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "QQDeBreathTool"
        legacy = None
    elif sys.platform.startswith("win"):
        appdata = Path(os.getenv("APPDATA", str(Path.home())))
        root = appdata / "QQDeBreathTool"
        legacy = appdata / "DeBreathTool" / "settings.json"
    else:
        config_home = Path(os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        root = config_home / "QQDeBreathTool"
        legacy = None
    root.mkdir(parents=True, exist_ok=True)
    path = root / "settings.json"
    if legacy is not None and legacy.exists() and not path.exists():
        try:
            path.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    return path


def load_settings():
    defaults = {
        "normalize_breath": False,
        "breath_target_db": DEFAULT_BREATH_TARGET_DB,
        "enable_fade": True,
        "fade_in_ms": DEFAULT_FADE_SECONDS * 1000.0,
        "fade_out_ms": DEFAULT_FADE_SECONDS * 1000.0,
        "play_follow": True,
        "return_to_play_start": False,
        "monitor_voice": True,
        "monitor_breath": True,
        "monitor_noize": True,
        "monitor_gain_db": 0.0,
        "last_file": "",
        "last_regions": [],
    }
    try:
        path = settings_path()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update(data)
    except Exception:
        pass
    return defaults


def save_settings(settings):
    try:
        settings_path().write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def emit_analysis_progress(progress_callback, value):
    if progress_callback is None:
        return
    try:
        progress_callback(max(0, min(100, int(round(float(value))))))
    except Exception:
        pass


def apply_ui_font(app):
    families = set(QFontDatabase().families())
    if sys.platform == "darwin":
        preferred = ["PingFang SC", "Hiragino Sans GB", "Heiti SC", "STHeiti"]
    elif sys.platform.startswith("win"):
        preferred = ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei"]
    else:
        preferred = ["Noto Sans CJK SC", "WenQuanYi Micro Hei", "DejaVu Sans"]
    current = app.font()
    for family in preferred:
        if family in families:
            font = QFont(current)
            font.setFamily(family)
            app.setFont(font)
            return


def frame_rms(x: np.ndarray, frame: int, hop: int):
    ensure_numpy()
    if len(x) < frame:
        padded = np.pad(x, (0, frame - len(x)))
    else:
        extra = int(np.ceil((len(x) - frame) / hop) * hop + frame - len(x))
        padded = np.pad(x, (0, max(0, extra)))
    frames = np.lib.stride_tricks.sliding_window_view(padded, frame)[::hop]
    return np.sqrt(np.mean(frames * frames, axis=1) + 1e-20)


def band_rms(mono, sr, lo, hi, frame, hop):
    sig = ensure_scipy_signal()
    nyq = sr / 2
    sos = sig.butter(2, [lo / nyq, min(hi / nyq, 0.98)], btype="band", output="sos")
    y = sig.sosfiltfilt(sos, mono)
    return frame_rms(y, frame, hop)


def smooth_array(x, width):
    ensure_numpy()
    width = max(1, int(width))
    if width <= 1:
        return x
    kernel = np.ones(width, dtype=np.float64) / width
    return np.convolve(x, kernel, mode="same")


def zcr_frames(mono, frame, hop):
    ensure_numpy()
    if len(mono) < frame:
        padded = np.pad(mono, (0, frame - len(mono)))
    else:
        extra = int(np.ceil((len(mono) - frame) / hop) * hop + frame - len(mono))
        padded = np.pad(mono, (0, max(0, extra)))
    frames = np.lib.stride_tricks.sliding_window_view(padded, frame)[::hop]
    return np.mean(np.signbit(frames[:, 1:]) != np.signbit(frames[:, :-1]), axis=1)


def spectral_flatness_frames(mono, frame, hop):
    ensure_numpy()
    if len(mono) < frame:
        padded = np.pad(mono, (0, frame - len(mono)))
    else:
        extra = int(np.ceil((len(mono) - frame) / hop) * hop + frame - len(mono))
        padded = np.pad(mono, (0, max(0, extra)))
    frames = np.lib.stride_tricks.sliding_window_view(padded, frame)[::hop]
    win = np.hanning(frame)
    spec = np.abs(np.fft.rfft(frames * win[None, :], axis=1)) + 1e-12
    return np.exp(np.mean(np.log(spec), axis=1)) / np.mean(spec, axis=1)


def frame_level_refs(full_db):
    ensure_numpy()
    finite = np.asarray(full_db, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {
            "floor": -90.0,
            "low": -72.0,
            "vocal": -34.0,
            "peak": -12.0,
            "dynamic": 56.0,
            "strong": -34.0,
            "airy_min": -78.0,
            "airy_max": -52.0,
            "near_min": -50.0,
            "near_max": -26.0,
        }
    peak = float(np.percentile(finite, 99.5))
    active = finite[finite > peak - 90.0]
    if active.size < max(32, finite.size * 0.01):
        active = finite
    floor = float(np.percentile(active, 10))
    low = float(np.percentile(active, 25))
    vocal = float(np.percentile(active, 84))
    dynamic = max(18.0, vocal - floor)
    strong = vocal - max(6.0, min(13.0, dynamic * 0.18))

    airy_min = floor + max(4.0, dynamic * 0.06)
    airy_max = min(vocal - max(9.0, dynamic * 0.22), low + dynamic * 0.45)
    if airy_max <= airy_min + 6.0:
        airy_max = airy_min + 6.0

    near_min = max(airy_min, vocal - max(26.0, dynamic * 0.42))
    near_max = vocal + max(2.0, min(7.0, dynamic * 0.10))
    if near_max <= near_min + 6.0:
        near_max = near_min + 6.0

    return {
        "floor": floor,
        "low": low,
        "vocal": vocal,
        "peak": peak,
        "dynamic": dynamic,
        "strong": strong,
        "airy_min": airy_min,
        "airy_max": airy_max,
        "near_min": near_min,
        "near_max": near_max,
    }


def distance_to_strong(full_db, hop, sr, refs=None):
    ensure_numpy()
    refs = refs or frame_level_refs(full_db)
    strong = full_db > refs["strong"]
    idx = np.arange(len(full_db))
    strong_idx = np.flatnonzero(strong)
    if strong_idx.size == 0:
        far = np.full(len(full_db), 99.0)
        return far, far
    prev = np.searchsorted(strong_idx, idx, side="right") - 1
    nxt = np.searchsorted(strong_idx, idx, side="left")
    prev_dist = np.where(prev >= 0, idx - strong_idx[np.maximum(prev, 0)], 999999)
    next_dist = np.where(nxt < strong_idx.size, strong_idx[np.minimum(nxt, strong_idx.size - 1)] - idx, 999999)
    return prev_dist * hop / sr, next_dist * hop / sr


def spectral_detail_frames(mono, sr, frame, hop):
    ensure_numpy()
    if len(mono) < frame:
        padded = np.pad(mono, (0, frame - len(mono)))
    else:
        extra = int(np.ceil((len(mono) - frame) / hop) * hop + frame - len(mono))
        padded = np.pad(mono, (0, max(0, extra)))
    frames = np.lib.stride_tricks.sliding_window_view(padded, frame)[::hop]
    win = np.hanning(frame)
    spec = np.abs(np.fft.rfft(frames * win[None, :], axis=1)) + 1e-12
    freqs = np.fft.rfftfreq(frame, 1.0 / sr)
    total = np.sum(spec, axis=1) + 1e-12
    flat = np.exp(np.mean(np.log(spec), axis=1)) / (np.mean(spec, axis=1) + 1e-12)
    centroid = np.sum(spec * freqs[None, :], axis=1) / total
    crest_db = 20.0 * np.log10((np.max(spec, axis=1) + 1e-12) / (np.mean(spec, axis=1) + 1e-12))

    def band_flat(lo, hi):
        mask = (freqs >= lo) & (freqs <= min(hi, sr / 2.0))
        if not np.any(mask):
            return flat
        band = spec[:, mask]
        return np.exp(np.mean(np.log(band), axis=1)) / (np.mean(band, axis=1) + 1e-12)

    low_flat = band_flat(80.0, 2500.0)
    air_flat = band_flat(2500.0, 11000.0)
    return flat, np.clip(centroid / max(1.0, sr / 2.0), 0.0, 1.0), crest_db, low_flat, air_flat


def features_for_audio(audio, sr):
    ensure_numpy()
    mono = np.mean(audio, axis=1)
    frame = int(FRAME_MS / 1000 * sr)
    hop = int(HOP_MS / 1000 * sr)
    full = frame_rms(mono, frame, hop)
    sub = band_rms(mono, sr, 70, 160, frame, hop)
    low = band_rms(mono, sr, 120, 900, frame, hop)
    body = band_rms(mono, sr, 900, 2500, frame, hop)
    presence = band_rms(mono, sr, 2500, 4500, frame, hop)
    air = band_rms(mono, sr, 2500, 11000, frame, hop)
    sib = band_rms(mono, sr, 4500, 9000, frame, hop)
    ultra = band_rms(mono, sr, 9000, min(15000, sr / 2 - 200), frame, hop) if sr > 22000 else air
    full_db = 20 * np.log10(full + 1e-12)
    refs = frame_level_refs(full_db)
    prev_strong, next_strong = distance_to_strong(full_db, hop, sr, refs)
    flat, centroid, crest_db, low_flat, air_flat = spectral_detail_frames(mono, sr, frame, hop)
    zcr = zcr_frames(mono, frame, hop)
    jitter = frame_rms(np.r_[0.0, np.diff(mono)], frame, hop)
    local_mean_db = smooth_array(full_db, int(0.20 / (hop / sr)))
    full_delta = np.r_[0.0, np.diff(full_db)]
    air_db = 20 * np.log10(air + 1e-12)
    air_delta = np.r_[0.0, np.diff(air_db)]
    eps = 1e-12
    X = np.column_stack(
        [
            full_db,
            20 * np.log10(sub + eps),
            20 * np.log10(low + eps),
            20 * np.log10(body + eps),
            20 * np.log10(presence + eps),
            20 * np.log10(air + eps),
            20 * np.log10(sib + eps),
            20 * np.log10(ultra + eps),
            20 * np.log10((air + eps) / (low + eps)),
            20 * np.log10((body + eps) / (low + eps)),
            20 * np.log10((sib + eps) / (air + eps)),
            20 * np.log10((presence + eps) / (body + eps)),
            20 * np.log10((sub + eps) / (low + eps)),
            flat,
            zcr,
            20 * np.log10(jitter + eps),
            np.clip(full_delta, -24.0, 24.0),
            np.clip(air_delta, -24.0, 24.0),
            local_mean_db,
            np.clip(full_db - local_mean_db, -36.0, 36.0),
            np.minimum(prev_strong, 3.0),
            np.minimum(next_strong, 3.0),
            np.minimum(np.minimum(prev_strong, next_strong), 3.0),
            centroid,
            np.clip(crest_db, 0.0, 48.0),
            low_flat,
            air_flat,
            np.clip(air_flat - low_flat, -1.0, 1.0),
        ]
    )
    return X, full_db, hop


def contiguous_regions(mask):
    ensure_numpy()
    values = mask.astype(np.int8)
    starts = np.flatnonzero(np.diff(np.r_[0, values]) == 1)
    ends = np.flatnonzero(np.diff(np.r_[values, 0]) == -1)
    return list(zip(starts, ends))


def merge_regions(regions, max_gap):
    if not regions:
        return []
    merged = [list(regions[0])]
    for a, b in regions[1:]:
        if a - merged[-1][1] <= max_gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(int(a), int(b)) for a, b in merged]


def merge_time_regions(regions, max_gap=0.08):
    if not regions:
        return []
    ordered = []
    for region in regions:
        if isinstance(region, Region):
            a, b, cls, confidence = region.start, region.end, region.cls, region.confidence
        else:
            a, b = region
            cls, confidence = "Breath", 1.0
        if b > a:
            ordered.append(Region(float(a), float(b), cls, float(confidence)))
    ordered.sort(key=lambda r: (r.start, r.end))
    merged = [ordered[0].copy()]
    for region in ordered[1:]:
        if region.start - merged[-1].end <= max_gap and region.cls == merged[-1].cls:
            merged[-1].end = max(merged[-1].end, region.end)
            merged[-1].confidence = max(merged[-1].confidence, region.confidence)
        else:
            merged.append(region.copy())
    return merged


def smooth_prob(prob, width=11):
    ensure_numpy()
    if width <= 1:
        return prob
    kernel = np.hanning(width)
    kernel /= kernel.sum()
    return np.convolve(prob, kernel, mode="same")


def probability_to_regions(prob, sr, hop, threshold=0.38):
    p = smooth_prob(prob, 11)
    regions_f = merge_regions(contiguous_regions(p >= threshold), int(0.14 / (hop / sr)))
    out = []
    for a_f, b_f in regions_f:
        start = max(0, a_f * hop)
        end = b_f * hop + int(FRAME_MS / 1000 * sr)
        dur = (end - start) / sr
        if 0.12 <= dur <= 1.35:
            conf = float(np.mean(p[a_f:b_f])) if b_f > a_f else 0.0
            out.append({"start": int(start), "end": int(end), "confidence": conf})

    filtered = []
    for item in out:
        if filtered:
            gap = (item["start"] - filtered[-1]["end"]) / sr
            dur = (item["end"] - item["start"]) / sr
            prev_dur = (filtered[-1]["end"] - filtered[-1]["start"]) / sr
            if gap < 1.0 and dur < 0.10 and item["confidence"] < filtered[-1]["confidence"] * 0.60 and prev_dur >= 0.24:
                continue
        filtered.append(item)
    return [Region(x["start"] / sr, x["end"] / sr, "Breath", x["confidence"]) for x in filtered]


def spectral_breath_regions(X, prob, full_db, sr, hop, sample_count):
    refs = frame_level_refs(full_db)
    air_low = X[:, 8]
    flat = X[:, 13]
    zcr = X[:, 14]
    edge_distance = X[:, 22]
    voiced_low = X[:, 9]
    airy = (
        (air_low > -2.5)
        & (air_low < 6.0)
        & (flat > 0.16)
        & (zcr > 0.075)
        & (voiced_low < 8.0)
        & (full_db > refs["airy_min"])
        & (full_db < refs["airy_max"])
        & (prob > 0.72)
    )
    near_voice_breath = (
        (air_low > 1.5)
        & (air_low < 10.5)
        & (flat > 0.13)
        & (zcr > 0.055)
        & (prob > 0.86)
        & (full_db > refs["near_min"])
        & (full_db < refs["near_max"])
        & (edge_distance < 0.75)
    )
    mask = airy | near_voice_breath
    regions_f = merge_regions(contiguous_regions(mask), int(0.10 / (hop / sr)))
    out = []
    for a_f, b_f in regions_f:
        start = max(0.0, a_f * hop / sr)
        end = min(sample_count / sr, (b_f * hop + int(FRAME_MS / 1000 * sr)) / sr)
        dur = end - start
        if 0.12 <= dur <= 1.45:
            conf = float(np.mean(prob[a_f:b_f])) if b_f > a_f else 0.0
            out.append(Region(start, end, "Breath", conf))
    return out


def region_bounds(region):
    if isinstance(region, Region):
        return region.start, region.end
    return region


def probability_to_noize_regions(prob, full_db, breath_regions, sr, hop, sample_count, threshold=0.35):
    ensure_numpy()
    p = smooth_prob(prob, 9)
    finite_db = full_db[np.isfinite(full_db)]
    if finite_db.size:
        peak_ref = float(np.percentile(finite_db, 99.5))
        active_db = full_db[full_db > peak_ref - 90.0]
        if active_db.size < max(32, len(full_db) * 0.01):
            active_db = finite_db
        floor = float(np.percentile(active_db, 8))
        low_ref = float(np.percentile(active_db, 18))
        vocal_ref = float(np.percentile(active_db, 84))
    else:
        peak_ref = 0.0
        floor = -90.0
        low_ref = -80.0
        vocal_ref = -36.0
    dynamic_range = max(18.0, vocal_ref - floor)
    silence_guard = peak_ref - dynamic_range * 2.6
    noise_top = min(low_ref + dynamic_range * 0.32, vocal_ref - dynamic_range * 0.25)
    if noise_top <= silence_guard + 6.0:
        noise_top = silence_guard + dynamic_range * 0.30
    mask = (p >= threshold) & (full_db > silence_guard) & (full_db < noise_top)
    strong_voice = full_db > (vocal_ref - max(6.0, dynamic_range * 0.12))
    guard = max(1, int(0.08 / (hop / sr)))
    near_voice = np.convolve(strong_voice.astype(np.float32), np.ones(guard), mode="same") > 0
    mask &= (~near_voice) | (p >= 0.90)
    regions_f = merge_regions(contiguous_regions(mask), int(0.12 / (hop / sr)))
    out = []
    for a_f, b_f in regions_f:
        start = a_f * hop / sr
        end = min(sample_count / sr, (b_f * hop + int(FRAME_MS / 1000 * sr)) / sr)
        dur = end - start
        if 0.25 <= dur <= 8.0:
            out.append((start, end))
    return out


def detect_noize_regions(full_db, breath_regions, sr, hop, sample_count):
    ensure_numpy()
    finite_db = full_db[np.isfinite(full_db)]
    if finite_db.size:
        peak_ref = float(np.percentile(finite_db, 99.5))
        active = full_db > peak_ref - 90.0
        active_db = full_db[active] if np.any(active) else finite_db
        floor = float(np.percentile(active_db, 12))
        low_ref = float(np.percentile(active_db, 20))
        vocal_ref = float(np.percentile(active_db, 82))
    else:
        peak_ref = 0.0
        floor = -90.0
        low_ref = -80.0
        vocal_ref = -36.0
    dynamic_range = max(18.0, vocal_ref - floor)
    silence_guard = peak_ref - dynamic_range * 2.6
    noise_top = min(low_ref + dynamic_range * 0.28, vocal_ref - dynamic_range * 0.28)
    if noise_top <= silence_guard + 6.0:
        noise_top = silence_guard + dynamic_range * 0.30
    mask = (full_db > silence_guard) & (full_db < noise_top)
    breath_frame_mask = np.zeros_like(mask, dtype=bool)
    for region in breath_regions:
        a, b = region_bounds(region)
        fa = max(0, int(a * sr / hop) - int(0.10 / (hop / sr)))
        fb = min(len(mask), int(b * sr / hop) + int(0.10 / (hop / sr)))
        breath_frame_mask[fa:fb] = True
    mask &= ~breath_frame_mask
    strong_voice = full_db > (vocal_ref - max(6.0, dynamic_range * 0.12))
    near_voice = np.convolve(strong_voice.astype(np.float32), np.ones(max(1, int(0.12 / (hop / sr)))), mode="same") > 0
    mask &= ~near_voice
    regions_f = merge_regions(contiguous_regions(mask), int(0.10 / (hop / sr)))
    out = []
    for a_f, b_f in regions_f:
        start = a_f * hop / sr
        end = min(sample_count / sr, (b_f * hop + int(FRAME_MS / 1000 * sr)) / sr)
        dur = end - start
        if 0.12 <= dur <= 4.0:
            out.append((start, end))
    return out


def prepare_for_analysis(audio):
    ensure_numpy()
    if not audio.size:
        return audio
    working = remove_dc_offset(clean_audio_array(audio))
    mono = np.mean(working, axis=1)
    active = np.abs(mono)
    active = active[active > 1e-9]
    if active.size == 0:
        return working
    body_ref = float(np.percentile(active, 90.0))
    normal_peak_ref = float(np.percentile(active, 98.0))
    if body_ref > 1e-9:
        limit = max(body_ref * 7.0, normal_peak_ref * 1.8, 0.02)
        working = np.tanh(working / limit) * limit
        mono = np.mean(working, axis=1)
        active = np.abs(mono)
        active = active[active > 1e-9]
        if active.size == 0:
            return working
    robust_peak = float(np.percentile(active, 98.0))
    robust_body = float(np.percentile(active, 90.0))
    if robust_peak <= 1e-9:
        return working
    target_peak = 0.55
    target_body = 0.18
    gain_peak = target_peak / robust_peak
    gain_body = target_body / max(robust_body, 1e-9)
    gain = np.clip(max(gain_peak, gain_body), 1.0 / 64.0, 64.0)
    return working * gain


def moving_mean(x, width):
    ensure_numpy()
    width = max(1, int(width))
    if width <= 1 or len(x) == 0:
        return x
    left = width // 2
    right = width - 1 - left
    padded = np.pad(np.asarray(x, dtype=np.float64), (left, right), mode="edge")
    csum = np.cumsum(np.r_[0.0, padded])
    return (csum[width:] - csum[:-width]) / width


def moving_mean_ms(x, sr, window_ms):
    return moving_mean(x, int(round(window_ms / 1000.0 * sr)))


def local_rms_curve(mono, sr, window_ms=8):
    win = max(8, int(round(window_ms / 1000.0 * sr)))
    return np.sqrt(moving_mean(mono * mono, win) + 1e-20)


def normalize01(x):
    ensure_numpy()
    x = np.asarray(x, dtype=np.float64)
    lo = float(np.percentile(x, 5))
    hi = float(np.percentile(x, 95))
    if hi <= lo + 1e-12:
        return np.zeros_like(x)
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def local_stability_curve(mono, rms, sr, window_ms=18):
    win = max(16, int(round(window_ms / 1000.0 * sr)))
    abs_mono = np.abs(mono)
    mean_abs = moving_mean(abs_mono, win)
    mean_sq = moving_mean(mono * mono, win)
    variance = np.maximum(0.0, mean_sq - mean_abs * mean_abs)
    envelope_slope = np.abs(np.gradient(rms))
    zc = np.r_[0.0, np.abs(np.diff(np.signbit(mono).astype(np.float64)))]
    zc_rate = moving_mean(zc, win)
    return 0.45 * normalize01(variance) + 0.35 * normalize01(envelope_slope) + 0.20 * normalize01(zc_rate)


def boundary_score_curve(mono, sr):
    ndi = ensure_scipy_ndimage()
    abs_mono = np.abs(mono)
    rms = local_rms_curve(mono, sr, 10)
    mean_abs = moving_mean_ms(abs_mono, sr, 10)
    peak = ndi.maximum_filter1d(abs_mono, size=max(3, int(round(14 / 1000.0 * sr))), mode="nearest")
    motion = moving_mean_ms(np.r_[0.0, np.abs(np.diff(mono))], sr, 10)
    slope = moving_mean_ms(np.abs(np.gradient(rms)), sr, 12)
    energy_n = normalize01(20 * np.log10(rms + 1e-12))
    peak_n = normalize01(20 * np.log10(peak + 1e-12))
    mean_n = normalize01(20 * np.log10(mean_abs + 1e-12))
    motion_n = normalize01(20 * np.log10(motion + 1e-12))
    slope_n = normalize01(slope)
    score = 0.34 * energy_n + 0.25 * peak_n + 0.18 * mean_n + 0.16 * motion_n + 0.07 * slope_n
    return moving_mean_ms(score, sr, 8)


def snap_time_to_stable_point(score, sr, t, search_ms=150):
    if len(score) == 0:
        return t
    center = int(round(t * sr))
    radius = max(1, int(round(search_ms / 1000.0 * sr)))
    a = max(0, center - radius)
    b = min(len(score), center + radius + 1)
    if b <= a:
        return t
    local_score = normalize01(score[a:b])
    positions = np.arange(a, b)
    distance = np.abs(positions - center) / max(1.0, radius)
    combined = 0.92 * local_score + 0.08 * distance
    return (a + int(np.argmin(combined))) / sr


def snap_regions_to_low_points(regions, audio, sr):
    ensure_numpy()
    if not regions:
        return regions
    mono = np.mean(audio, axis=1)
    score = boundary_score_curve(mono, sr)
    snapped = []
    for r in regions:
        duration = max(0.0, r.end - r.start)
        search = 180 if r.cls == "Breath" else 140
        search = min(search, max(90, duration * 450.0))
        start = snap_time_to_stable_point(score, sr, r.start, search)
        end = snap_time_to_stable_point(score, sr, r.end, search)
        if end - start < 0.04:
            start, end = r.start, r.end
        snapped.append(Region(start, end, r.cls))
    return snapped


def percentile_abs_db(abs_mono, start, end, percentile=95):
    ensure_numpy()
    start = max(0, min(len(abs_mono), int(start)))
    end = max(start, min(len(abs_mono), int(end)))
    if end <= start:
        return -240.0
    return 20 * np.log10(float(np.percentile(abs_mono[start:end], percentile)) + 1e-12)


def edge_window_db(abs_mono, sr, center, window_ms=18):
    radius = max(1, int(round(window_ms / 1000.0 * sr / 2.0)))
    return percentile_abs_db(abs_mono, center - radius, center + radius, 95)


def keep_auto_breath_region(region, abs_mono, sr):
    duration = region.end - region.start
    if duration < DEFAULT_AUTO_BREATH_MIN_SECONDS:
        return False
    if duration < AUTO_BREATH_SHORT_REVIEW_SECONDS and region.confidence >= 0.93:
        return True
    if duration >= AUTO_BREATH_SHORT_REVIEW_SECONDS:
        return True
    a = int(round(region.start * sr))
    b = int(round(region.end * sr))
    segment_peak = percentile_abs_db(abs_mono, a, b, 95)
    start_edge = edge_window_db(abs_mono, sr, a)
    end_edge = edge_window_db(abs_mono, sr, b)
    return max(start_edge, end_edge) <= segment_peak - 1.5


def filter_auto_breath_regions(regions, audio, sr):
    ensure_numpy()
    if not regions:
        return regions
    abs_mono = np.abs(np.mean(audio, axis=1))
    return [
        r
        for r in regions
        if r.cls != "Breath" or keep_auto_breath_region(r, abs_mono, sr)
    ]


def model_feature_count(model_bundle):
    try:
        clf = model_bundle["breath_pipeline"] if isinstance(model_bundle, dict) and "breath_pipeline" in model_bundle else model_bundle["pipeline"]
        return int(getattr(clf.named_steps["scale"], "n_features_in_", 0))
    except Exception:
        return 0


def trim_features_for_model(X, model_bundle):
    count = model_feature_count(model_bundle)
    if count == 13 and X.shape[1] >= 23:
        legacy_indices = [0, 2, 3, 5, 6, 8, 9, 10, 13, 14, 20, 21, 22]
        return X[:, legacy_indices]
    if count > 0 and X.shape[1] > count:
        return X[:, :count]
    return X


def subtract_regions(regions, cutters, min_duration=0.04):
    result = []
    for start, end in regions:
        pieces = [(start, end)]
        for cut_start, cut_end in cutters:
            next_pieces = []
            for a, b in pieces:
                if cut_end <= a or cut_start >= b:
                    next_pieces.append((a, b))
                    continue
                if cut_start - a >= min_duration:
                    next_pieces.append((a, max(a, cut_start)))
                if b - cut_end >= min_duration:
                    next_pieces.append((min(b, cut_end), b))
            pieces = next_pieces
            if not pieces:
                break
        result.extend(pieces)
    return result


def analyze_regions(audio, sr, model_bundle, threshold=None, detect_noize=False, source_path=None, progress_callback=None):
    emit_analysis_progress(progress_callback, 2)
    analysis_audio = prepare_for_analysis(audio)
    emit_analysis_progress(progress_callback, 12)
    X, full_db, hop = features_for_audio(analysis_audio, sr)
    emit_analysis_progress(progress_callback, 48)
    X_model = trim_features_for_model(X, model_bundle)
    thresholds = model_bundle.get("thresholds", {}) if isinstance(model_bundle, dict) else {}
    breath_threshold = float(threshold if threshold is not None else thresholds.get("breath", DEFAULT_BREATH_THRESHOLD))
    noize_threshold = float(thresholds.get("noize", 0.35))
    if isinstance(model_bundle, dict):
        breath_clf = model_bundle.get("breath_pipeline") or model_bundle.get("pipeline")
        noize_clf = model_bundle.get("noize_pipeline")
    else:
        breath_clf = model_bundle
        noize_clf = None
    prob = breath_clf.predict_proba(X_model)[:, 1]
    emit_analysis_progress(progress_callback, 62)
    breath_regions = probability_to_regions(prob, sr, hop, threshold=breath_threshold)
    breath = merge_time_regions(
        breath_regions + spectral_breath_regions(X, prob, full_db, sr, hop, len(audio)),
        max_gap=0.08,
    )
    emit_analysis_progress(progress_callback, 75)
    if detect_noize and noize_clf is not None:
        noize_prob = noize_clf.predict_proba(X_model)[:, 1]
        noize = probability_to_noize_regions(noize_prob, full_db, breath, sr, hop, len(audio), threshold=noize_threshold)
    elif detect_noize:
        noize = detect_noize_regions(full_db, breath, sr, hop, len(audio))
    else:
        noize = []
    regions = [r.copy() for r in breath]
    regions += [Region(a, b, "Noize") for a, b in noize]
    emit_analysis_progress(progress_callback, 84)
    regions = snap_regions_to_low_points(regions, audio, sr)
    emit_analysis_progress(progress_callback, 92)
    regions = filter_auto_breath_regions(regions, analysis_audio, sr)
    regions = normalize_regions(regions, len(audio) / sr)
    regions = apply_breath_time_overrides(regions, source_path, len(audio) / sr)
    emit_analysis_progress(progress_callback, 100)
    return regions


def normalize_regions(regions, duration):
    priority = {"Breath": 2, "Noize": 1, "Vocal Only": 0}
    clean = []
    for r in regions:
        a = max(0.0, min(duration, float(r.start)))
        b = max(0.0, min(duration, float(r.end)))
        if b - a >= 0.005 and r.cls in CLASSES:
            clean.append(Region(a, b, r.cls, finite_float(getattr(r, "confidence", 1.0), 1.0)))
    clean.sort(key=lambda r: (r.start, -priority[r.cls]))
    out = []
    for r in clean:
        if not out or r.start >= out[-1].end:
            out.append(r)
        else:
            if priority[r.cls] >= priority[out[-1].cls]:
                out[-1].end = min(out[-1].end, r.start)
                if out[-1].end - out[-1].start < 0.005:
                    out.pop()
                out.append(r)
            elif r.end > out[-1].end:
                r.start = out[-1].end
                out.append(r)
    final = []
    for r in out:
        if r.end - r.start >= 0.005 and r.cls != "Vocal Only":
            final.append(r)
    return final


def insert_region_with_boundaries(regions, new_region, duration, min_duration=0.005):
    start = max(0.0, min(duration, float(new_region.start)))
    end = max(0.0, min(duration, float(new_region.end)))
    if end - start < min_duration or new_region.cls not in CLASSES:
        return normalize_regions(regions, duration), -1

    inserted = Region(start, end, new_region.cls, finite_float(getattr(new_region, "confidence", 1.0), 1.0))
    out = []
    for r in regions:
        if r.end <= start or r.start >= end:
            out.append(r.copy())
            continue
        if start - r.start >= min_duration:
            out.append(Region(r.start, start, r.cls, r.confidence))
        if r.end - end >= min_duration:
            out.append(Region(end, r.end, r.cls, r.confidence))

    out.append(inserted)
    out = normalize_regions(out, duration)
    selected = -1
    for i, r in enumerate(out):
        if (
            r.cls == inserted.cls
            and abs(r.start - inserted.start) < 1e-6
            and abs(r.end - inserted.end) < 1e-6
        ):
            selected = i
            break
    return out, selected


def apply_breath_time_overrides(regions, source_path, duration):
    if source_path is None:
        return regions
    source = Path(source_path)
    folder = source.parent.name
    stem = source.stem
    overrides = BREATH_TIME_OVERRIDES.get(stem, [])
    if not overrides:
        return regions
    out = [r.copy() for r in regions]
    for override_folder, center, radius, value in overrides:
        if folder != override_folder:
            continue
        start = max(0.0, float(center) - float(radius))
        end = min(duration, float(center) + float(radius))
        if end <= start:
            continue
        if value:
            out, _ = insert_region_with_boundaries(out, Region(start, end, "Breath"), duration)
        else:
            next_regions = [r.copy() for r in out if r.cls != "Breath"]
            for a, b in subtract_regions([(r.start, r.end) for r in out if r.cls == "Breath"], [(start, end)], 0.005):
                next_regions.append(Region(a, b, "Breath"))
            out = next_regions
            out = normalize_regions(out, duration)
    return normalize_regions(out, duration)


def region_public_dict(region):
    return {"start": region.start, "end": region.end, "cls": region.cls}


def normalize_breath_blocks(data, audio, regions, sr, target_db=-6.0):
    ensure_numpy()
    target_peak = 10.0 ** (float(target_db) / 20.0)
    if target_peak <= 0:
        return data
    for r in regions:
        if r.cls != "Breath":
            continue
        a = max(0, min(len(audio), int(round(r.start * sr))))
        b = max(a, min(len(audio), int(round(r.end * sr))))
        if b <= a:
            continue
        segment = data[a:b]
        peak = float(np.max(np.abs(segment))) if segment.size else 0.0
        if peak <= 1e-9:
            continue
        data[a:b] *= target_peak / peak
    return data


def build_stem_gains(audio_length, sr, regions, fade_in_ms=5.0, fade_out_ms=5.0):
    ensure_numpy()
    duration = audio_length / sr
    regions = normalize_regions(regions, duration)
    class_id = {"Vocal Only": 0, "Breath": 1, "Noize": 2}
    gains = np.zeros((audio_length, len(class_id)), dtype=np.float32)
    gains[:, class_id["Vocal Only"]] = 1.0
    for r in regions:
        a = int(round(r.start * sr))
        b = int(round(r.end * sr))
        a = max(0, min(audio_length, a))
        b = max(a, min(audio_length, b))
        if b <= a:
            continue
        idx = class_id[r.cls]
        dur = b - a
        fade_in = int(round(max(0.0, float(fade_in_ms)) / 1000.0 * sr))
        fade_out = int(round(max(0.0, float(fade_out_ms)) / 1000.0 * sr))
        fade_in = min(fade_in, dur // 2)
        fade_out = min(fade_out, dur // 2)
        target = np.ones(dur, dtype=np.float32)
        if fade_in > 0:
            target[:fade_in] = np.linspace(0.0, 1.0, fade_in, endpoint=True)
        if fade_out > 0:
            target[-fade_out:] = np.minimum(target[-fade_out:], np.linspace(1.0, 0.0, fade_out, endpoint=True))
        current = gains[a:b, idx]
        gains[a:b, idx] = np.maximum(current, target)
        gains[a:b, class_id["Vocal Only"]] *= 1.0 - target

    fade_in_base = int(round(max(0.0, float(fade_in_ms)) / 1000.0 * sr))
    fade_out_base = int(round(max(0.0, float(fade_out_ms)) / 1000.0 * sr))
    touch_tolerance = max(2.0 / sr, 0.002)
    for left, right in zip(regions, regions[1:]):
        if left.cls == right.cls:
            continue
        gap = right.start - left.end
        if gap < -touch_tolerance or gap > touch_tolerance:
            continue
        left_idx = class_id.get(left.cls)
        right_idx = class_id.get(right.cls)
        if left_idx is None or right_idx is None:
            continue

        boundary = int(round(((left.end + right.start) * 0.5) * sr))
        left_a = max(0, min(audio_length, int(round(left.start * sr))))
        left_b = max(left_a, min(audio_length, int(round(left.end * sr))))
        right_a = max(0, min(audio_length, int(round(right.start * sr))))
        right_b = max(right_a, min(audio_length, int(round(right.end * sr))))
        fade_left = min(fade_out_base, max(0, (left_b - left_a) // 2))
        fade_right = min(fade_in_base, max(0, (right_b - right_a) // 2))
        if fade_left <= 0 and fade_right <= 0:
            continue

        a = max(0, boundary - fade_left)
        b = min(audio_length, boundary + fade_right)
        if b <= a:
            continue
        positions = np.arange(a, b, dtype=np.float64)
        right_gain = np.empty(b - a, dtype=np.float32)
        left_mask = positions < boundary
        right_mask = ~left_mask
        if np.any(left_mask):
            denom = max(1.0, float(boundary - a))
            right_gain[left_mask] = 0.5 * ((positions[left_mask] - a) / denom)
        if np.any(right_mask):
            denom = max(1.0, float(b - boundary - 1))
            right_gain[right_mask] = 0.5 + 0.5 * ((positions[right_mask] - boundary) / denom)
        right_gain = np.clip(right_gain, 0.0, 1.0)
        left_gain = 1.0 - right_gain
        gains[a:b, :] = 0.0
        gains[a:b, left_idx] = left_gain
        gains[a:b, right_idx] = right_gain
    return gains, class_id


def export_stems(
    path,
    audio,
    sr,
    subtype,
    regions,
    fade_in_ms=5.0,
    fade_out_ms=5.0,
    normalize_breath=False,
    breath_target_db=-6.0,
):
    writer = ensure_soundfile()
    duration = len(audio) / sr
    regions = normalize_regions(regions, duration)
    gains, class_id = build_stem_gains(len(audio), sr, regions, fade_in_ms, fade_out_ms)
    out_paths = {}
    stem = Path(path).stem
    folder = Path(path).parent
    for cls, idx in class_id.items():
        data = audio * gains[:, idx][:, None]
        if cls == "Breath" and normalize_breath:
            data = normalize_breath_blocks(data, audio, regions, sr, breath_target_db)
        out = folder / f"{stem}_{cls}.wav"
        writer.write(str(out), data, sr, subtype=subtype or "PCM_24")
        out_paths[cls] = str(out)
    return out_paths


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

    def set_display_processing(self, normalize_breath=False, breath_target_db=DEFAULT_BREATH_TARGET_DB, visible_classes=None):
        self.normalize_breath_display = bool(normalize_breath)
        self.breath_target_db = finite_float(breath_target_db, DEFAULT_BREATH_TARGET_DB)
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
        if not self.normalize_breath_display or samples.size == 0:
            return samples
        target_peak = 10.0 ** (self.breath_target_db / 20.0)
        if target_peak <= 0:
            return samples
        for r in self.regions:
            if r.cls != "Breath":
                continue
            region_start = max(0, min(len(self.audio), int(round(r.start * self.sr))))
            region_end = max(region_start, min(len(self.audio), int(round(r.end * self.sr))))
            if region_end <= start_sample or region_start >= end_sample:
                continue
            source = self.audio[region_start:region_end]
            peak = float(np.max(np.abs(source))) if source.size else 0.0
            if peak <= 1e-9:
                continue
            a = max(region_start, start_sample) - start_sample
            b = min(region_end, end_sample) - start_sample
            samples[a:b] *= target_peak / peak
        return samples

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(18, 18, 18))
        painter.fillRect(self.rect(), COLORS["Vocal Only"])
        mid = self.height() // 2
        painter.setPen(QPen(QColor(70, 70, 70), 1))
        painter.drawLine(0, mid, self.width(), mid)

        for i, r in enumerate(self.regions):
            x1 = self.time_to_x(r.start)
            x2 = self.time_to_x(r.end)
            if x2 < 0 or x1 > self.width():
                continue
            top = 24
            bottom = self.height() - 4
            painter.fillRect(QRectF(x1, 24, max(1, x2 - x1), self.height() - 28), COLORS[r.cls])
            fade_pen = QPen(QColor(255, 255, 255, 180), 1)
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
                painter.setPen(QPen(QColor(255, 235, 59), 4))
                painter.drawLine(hx, 22, hx, self.height())
            if i == self.selected:
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.drawRect(QRectF(x1, 24, max(1, x2 - x1), self.height() - 28))

        if self.drag_mode == "create" and self.create_start is not None and self.temp_end is not None:
            x1 = self.time_to_x(min(self.create_start, self.temp_end))
            x2 = self.time_to_x(max(self.create_start, self.temp_end))
            painter.fillRect(QRectF(x1, 24, max(1, x2 - x1), self.height() - 28), COLORS[self.new_class])
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawRect(QRectF(x1, 24, max(1, x2 - x1), self.height() - 28))

        if self.audio is not None and len(self.audio) > 0:
            ensure_numpy()
            a = int(self.view_start * self.sr)
            b = int(self.view_end * self.sr)
            a = max(0, min(len(self.audio) - 1, a))
            b = max(a + 1, min(len(self.audio), b))
            samples = self.view_samples_for_display(a, b)
            cols = max(1, self.width())
            col_lo, col_hi, amp = self.waveform_column_bounds(samples, cols)
            display_gain = finite_float(self.display_gain, 1.0)
            for x in range(cols):
                if x >= len(col_lo):
                    continue
                t = self.x_to_time(x)
                cls = self.class_at_time(t)
                if cls in self.monitor_visible_classes:
                    painter.setPen(QPen(QColor(235, 235, 235), 1))
                else:
                    painter.setPen(QPen(QColor(120, 120, 120), 1))
                lo = col_lo[x] / amp * display_gain
                hi = col_hi[x] / amp * display_gain
                if not math.isfinite(lo) or not math.isfinite(hi):
                    continue
                y1 = mid - int(np.clip(hi, -1, 1) * (self.height() * 0.42))
                y2 = mid - int(np.clip(lo, -1, 1) * (self.height() * 0.42))
                painter.drawLine(x, y1, x, y2)

        if self.view_start <= self.playhead <= self.view_end:
            x = self.time_to_x(self.playhead)
            painter.setPen(QPen(QColor(255, 235, 59), 2))
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


class DragValueLabel(QLabel):
    valueChanged = pyqtSignal(float)

    def __init__(self, prefix, value=5.0, minimum=0.0, maximum=500.0, suffix="ms", decimals=1, default=None):
        super().__init__()
        self.prefix = prefix
        self.suffix = suffix
        self.decimals = int(decimals)
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.value = max(self.minimum, min(self.maximum, float(value)))
        self.default = max(self.minimum, min(self.maximum, float(value if default is None else default)))
        self.dragging = False
        self.drag_y = 0
        self.drag_value = self.value
        self.setCursor(Qt.SizeVerCursor)
        self.setMinimumWidth(86)
        self.setStyleSheet("QLabel { padding: 3px 8px; border: 1px solid #777; background: #262626; color: #f0f0f0; }")
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
        step = 0.2 if event.modifiers() & Qt.ShiftModifier else 1.0
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
        painter.fillRect(self.rect(), QColor(28, 28, 28))
        painter.setPen(QPen(QColor(84, 84, 84), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        norm = max(0.0, min(1.0, (self.level_db + 60.0) / 60.0))
        width = int(norm * (self.width() - 2))
        if self.clip:
            color = QColor(229, 57, 53)
        elif self.level_db > -6.0:
            color = QColor(255, 193, 7)
        else:
            color = QColor(76, 175, 80)
        painter.fillRect(1, 1, width, self.height() - 2, color)

        painter.setPen(QPen(QColor(245, 245, 245), 1))
        text = "CLIP" if self.clip else f"{self.level_db:.1f} dB"
        painter.drawText(self.rect(), Qt.AlignCenter, text)


class AnalyzeThread(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, audio, sr, model_bundle, source_path=None):
        super().__init__()
        self.audio = audio
        self.sr = sr
        self.model_bundle = model_bundle
        self.source_path = source_path

    def run(self):
        try:
            regions = analyze_regions(
                self.audio,
                self.sr,
                self.model_bundle,
                detect_noize=False,
                source_path=self.source_path,
                progress_callback=self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(regions)


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
            <p>Version: 1.02<br>Developer: 顾子青 / 刁翔宇 / Codex / ChatGPT 5.5</p>
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("去呼吸 / 呼吸与噪音分离工具 1.02")
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
        self.ma_device = None
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
        self.analyze_btn.setMinimumWidth(82)
        self.analyze_btn.setStyleSheet(
            "QPushButton { background: #2F80ED; color: white; font-weight: 700; "
            "padding: 5px 12px; border: 1px solid #2368C4; border-radius: 4px; } "
            "QPushButton:hover { background: #3D8BFA; } "
            "QPushButton:pressed { background: #2368C4; } "
            "QPushButton:disabled { background: #5B6B7F; color: #D0D4DA; }"
        )
        self.export_btn = QPushButton("导出三轨")
        self.export_btn.setMinimumWidth(96)
        self.export_btn.setStyleSheet(
            "QPushButton { background: #00A676; color: white; font-weight: 700; "
            "padding: 5px 12px; border: 1px solid #008F67; border-radius: 4px; } "
            "QPushButton:hover { background: #00B884; } "
            "QPushButton:pressed { background: #008F67; }"
        )
        fit_btn = QPushButton("全览")
        delete_btn = QPushButton("删除区块")
        type_label = QLabel("类型:")
        self.class_combo = QComboBox()
        self.class_combo.addItems(EDITABLE_CLASSES)
        monitor_label = QLabel("Monitor:")
        monitor_label.setMinimumWidth(64)
        monitor_label.setToolTip("勾选要监听的分轨")
        self.monitor_voice = QCheckBox("Voice")
        self.monitor_voice.setChecked(bool(self.settings.get("monitor_voice", True)))
        self.monitor_breath = QCheckBox("Breath")
        self.monitor_breath.setChecked(bool(self.settings.get("monitor_breath", True)))
        self.monitor_noize = QCheckBox("Noize")
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
        self.normalize_breath = QCheckBox("Breath Norm")
        self.normalize_breath.setChecked(bool(self.settings.get("normalize_breath", False)))
        self.breath_target_db = DragValueLabel(
            "Breath",
            float(self.settings.get("breath_target_db", DEFAULT_BREATH_TARGET_DB)),
            -60.0,
            0.0,
            "dB",
            default=DEFAULT_BREATH_TARGET_DB,
        )
        self.region_info = QLabel("未选中区块")
        self.position_info = QLabel("00:00.000")
        self.status = QLabel("拖入一个音频文件开始。")
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
        self.class_combo.currentTextChanged.connect(self.class_combo_changed)
        self.display_gain.valueChanged.connect(self.wave.set_display_gain)
        self.enable_fade.stateChanged.connect(self.global_fade_changed)
        self.fade_in_ms.valueChanged.connect(self.global_fade_changed)
        self.fade_out_ms.valueChanged.connect(self.global_fade_changed)
        self.normalize_breath.stateChanged.connect(self.monitor_settings_changed)
        self.breath_target_db.valueChanged.connect(self.monitor_settings_changed)
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
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update_playhead_from_audio)
        self.playback_end_timer = QTimer(self)
        self.playback_end_timer.setSingleShot(True)
        self.playback_end_timer.timeout.connect(self.finish_playback_at_end)
        self.global_fade_changed()
        self.update_wave_display_processing()
        self.update_history_buttons()
        QTimer.singleShot(0, self.restore_last_session)

        top = QHBoxLayout()
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
        ]:
            top.addWidget(w)
        top.addWidget(self.export_btn)

        transport = QHBoxLayout()
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
        info.addWidget(self.region_info)
        info.addStretch(1)
        info.addWidget(self.position_info)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(self.wave, 4)
        layout.addWidget(self.view_scroll)
        layout.addLayout(transport)
        layout.addLayout(info)
        layout.addWidget(self.status)
        root = QWidget()
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
        path, _ = QFileDialog.getOpenFileName(self, "选择音频文件", "", "Audio Files (*.wav *.aif *.aiff *.flac *.ogg);;All Files (*.*)")
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
        self.subtype = info.subtype if info.subtype else "PCM_24"
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
            regions = analyze_regions(
                self.audio,
                self.sr,
                self.analysis_model,
                detect_noize=False,
                source_path=self.path,
                progress_callback=self.analysis_progress_changed,
            )
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
        self.push_undo("Analyze")
        self.wave.set_regions(regions)
        self.redo_stack.clear()
        self.selection_changed(self.wave.selected)
        self.save_session()
        breath_count = sum(1 for r in regions if r.cls == "Breath")
        if breath_count:
            self.status.setText(f"分析完成：{breath_count} 个 Breath。Noize 已留给手动标记。")
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
            Region(float(r["start"]), float(r["end"]), r["cls"], finite_float(r.get("confidence", 1.0), 1.0))
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
            self.class_combo.setCurrentText(r.cls)
            self.region_info.setText(f"已选：{r.cls} | {self.format_time(r.start)} - {self.format_time(r.end)}")
        else:
            self.region_info.setText("Shift+拖动新增区块；右键区块切换 Breath/Noize；Shift+滚轮左右移动；数值拖动时 Shift 微调，Alt+左键恢复默认；B/N 改类型，Delete 删除。")
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

    def class_combo_changed(self, cls):
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
        if cls not in EDITABLE_CLASSES:
            return
        self.class_combo.setCurrentText(cls)
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
        self.status.setText(f"已设为 {cls}。")

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
        if self.path is None:
            return
        self.settings["last_file"] = str(self.path)
        self.settings["last_regions"] = [region_public_dict(r) for r in self.wave.regions]
        save_settings(self.settings)

    def restore_last_session(self):
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
                        item["cls"],
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
            out = export_stems(
                temp_path,
                self.audio,
                self.sr,
                self.subtype,
                self.wave.regions,
                fade_in,
                fade_out,
                self.normalize_breath.isChecked(),
                self.breath_target_db.value,
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

        segment = playback_audio[start_sample:]
        segment_f32 = np.asarray(segment, dtype=np.float32)
        if segment_f32.ndim == 1:
            segment_f32 = segment_f32[:, None]
        nchannels = segment_f32.shape[1]

        gen = _make_audio_generator(segment_f32, nchannels)
        next(gen)  # prime the generator

        ma = ensure_miniaudio()
        try:
            device = ma.PlaybackDevice(
                output_format=ma.SampleFormat.FLOAT32,
                nchannels=nchannels,
                sample_rate=self.sr,
            )
            device.start(gen)
            self.ma_device = device
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
            data += breath
        if self.monitor_noize.isChecked():
            data += self.audio * gains[:, class_id["Noize"]][:, None]
        return self.apply_monitor_gain(data)

    def stop_playback(self, reset_button=True, return_to_start=False):
        was_playing = self.is_playing
        return_pos = self.play_start_pos
        if self.ma_device is not None:
            try:
                self.ma_device.stop()
            except Exception:
                log_exception("stop_playback failed")
            self.ma_device = None
        if self.playback_end_timer is not None:
            self.playback_end_timer.stop()
        self.is_playing = False
        self.playback_audio_length = 0
        self.playback_audio = None
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
                self.set_selected_region_type("Noize")
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
            self.set_selected_region_type("Noize")
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.stop_playback()
        super().closeEvent(event)


def cli_analyze(args):
    bundle = load_model(args.model)
    reader = ensure_soundfile()
    info = reader.info(str(args.input))
    audio, sr = reader.read(str(args.input), always_2d=True, dtype="float64")
    audio = clean_audio_array(audio)
    regions = analyze_regions(audio, sr, bundle, source_path=args.input)
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = Path.cwd() / "cli_analysis_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_input = out_dir / Path(args.input).name
    out = export_stems(temp_input, audio, sr, info.subtype or "PCM_24", regions)
    report = {
        "input": str(args.input),
        "regions": [region_public_dict(r) for r in regions],
        "exports": out,
    }
    report_path = out_dir / (Path(args.input).stem + "_analysis_report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"regions": len(regions), "report": str(report_path), "exports": out}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    if args.analyze_only:
        if not args.input:
            raise SystemExit("--input is required with --analyze-only")
        cli_analyze(args)
        return
    app = QApplication(sys.argv)
    apply_ui_font(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
