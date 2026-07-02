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
sd = None
sf = None
ndimage = None
signal = None

from PyQt5.QtCore import Qt, QRectF, QEvent, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollBar,
    QVBoxLayout,
    QWidget,
)


FRAME_MS = 25
HOP_MS = 5
DEFAULT_FADE_SECONDS = 0.010
DEFAULT_BREATH_TARGET_DB = -6.0
DEFAULT_BREATH_THRESHOLD = 0.86
DEFAULT_WAV_OUTPUT_SUBTYPE = "PCM_24"
SAFE_WAV_OUTPUT_SUBTYPES = {
    "PCM_S8",
    "PCM_16",
    "PCM_24",
    "PCM_32",
    "FLOAT",
    "DOUBLE",
    "ULAW",
    "ALAW",
}
DEFAULT_AUTO_BREATH_MIN_SECONDS = 0.12
AUTO_BREATH_SHORT_REVIEW_SECONDS = 0.16
CLASSES = ["Vocal Only", "Breath", "Noize"]
EDITABLE_CLASSES = ["Breath", "Noize"]
COLORS = {
    "Vocal Only": QColor(22, 101, 52, 34),
    "Breath": QColor(56, 189, 248, 118),
    "Noize": QColor(245, 158, 11, 122),
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


def safe_wav_subtype(subtype):
    """Return a subtype that libsndfile can write into a WAV container."""
    requested = str(subtype or "").strip()
    if not requested or requested.upper() in {"UNKNOWN", "N/A", "NOTYPE"}:
        return DEFAULT_WAV_OUTPUT_SUBTYPE
    if requested.upper() not in SAFE_WAV_OUTPUT_SUBTYPES:
        return DEFAULT_WAV_OUTPUT_SUBTYPE

    try:
        writer = ensure_soundfile()
        available = writer.available_subtypes("WAV")
        if requested in available:
            return requested
        requested_upper = requested.upper()
        for candidate in available:
            if candidate.upper() == requested_upper:
                return candidate
    except Exception:
        log_exception("checking WAV subtypes failed")

    return DEFAULT_WAV_OUTPUT_SUBTYPE


def ensure_sounddevice():
    global sd
    if sd is None:
        import sounddevice as _sd

        sd = _sd
        log_startup("loaded sounddevice")
    return sd


def default_output_samplerate(fallback_sr):
    try:
        sd_mod = ensure_sounddevice()
        devices = sd_mod.query_devices()
        default_device = devices[sd_mod.default.device[1]]
        if default_device and default_device.get("default_samplerate"):
            return int(default_device["default_samplerate"])
    except Exception:
        log_exception("default_output_samplerate failed")
    return fallback_sr


def resample_for_playback(audio, src_sr, dst_sr):
    if src_sr == dst_sr:
        return audio.copy()
    ensure_numpy()
    ensure_scipy_signal()
    num_samples = int(audio.shape[0] * dst_sr / src_sr)
    return signal.resample(audio, num_samples, axis=0)


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


def core_regions_to_gui_regions(regions):
    return [
        Region(
            float(region.start),
            float(region.end),
            str(region.cls),
            finite_float(getattr(region, "confidence", 1.0), 1.0),
        )
        for region in regions
    ]


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
        Path.home() / "Desktop" / "去呼吸" / "breath_frame_model.joblib",
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
        "breath_gain_db": 0.0,
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


def apply_breath_gain(data, gain_db=0.0):
    gain_db = finite_float(gain_db, 0.0)
    if abs(gain_db) < 1e-12:
        return data
    gain_db = max(-30.0, min(30.0, gain_db))
    return data * (10.0 ** (gain_db / 20.0))


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
    breath_gain_db=0.0,
):
    writer = ensure_soundfile()
    duration = len(audio) / sr
    regions = normalize_regions(regions, duration)
    gains, class_id = build_stem_gains(len(audio), sr, regions, fade_in_ms, fade_out_ms)
    out_paths = {}
    stem = Path(path).stem
    folder = Path(path).parent
    output_subtype = safe_wav_subtype(subtype)
    for cls, idx in class_id.items():
        data = audio * gains[:, idx][:, None]
        if cls == "Breath" and normalize_breath:
            data = normalize_breath_blocks(data, audio, regions, sr, breath_target_db)
        if cls == "Breath":
            data = apply_breath_gain(data, breath_gain_db)
        out = folder / f"{stem}_{cls}.wav"
        writer.write(str(out), data, sr, format="WAV", subtype=output_subtype)
        out_paths[cls] = str(out)
    return out_paths




from qq_debreath.gui.main_window import MainWindow

def cli_analyze(args):
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = Path.cwd() / "cli_analysis_outputs"
    from qq_debreath.core.facade import analyze_file_to_directory

    result = analyze_file_to_directory(args.input, out_dir, model_path=args.model, params=None)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "analyze-for-plugin":
        from qq_debreath.cli.analyze_for_plugin import main as plugin_cli_main

        raise SystemExit(plugin_cli_main(sys.argv[2:]))

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
