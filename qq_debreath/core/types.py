from __future__ import annotations

from dataclasses import dataclass

from .constants import DEFAULT_BREATH_GAIN_DB, DEFAULT_BREATH_TARGET_DB, DEFAULT_BREATH_THRESHOLD, DEFAULT_FADE_SECONDS


@dataclass
class Region:
    start: float
    end: float
    cls: str
    confidence: float | None = None


@dataclass
class AnalysisParams:
    threshold: float = DEFAULT_BREATH_THRESHOLD
    detect_noize: bool = False
    fade_seconds: float = DEFAULT_FADE_SECONDS
    breath_target_db: float = DEFAULT_BREATH_TARGET_DB
    breath_gain_db: float = DEFAULT_BREATH_GAIN_DB
    normalize_breath: bool = False


@dataclass
class AnalysisResult:
    sample_rate: int
    num_samples: int
    duration: float
    regions: list[Region]
