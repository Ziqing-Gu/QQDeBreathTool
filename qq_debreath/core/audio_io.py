from __future__ import annotations

from pathlib import Path

from .legacy import app


def read_audio(path: str | Path):
    reader = app().ensure_soundfile()
    info = reader.info(str(path))
    audio, sample_rate = reader.read(str(path), always_2d=True, dtype="float64")
    return app().clean_audio_array(audio), int(sample_rate), info


def clean_audio_array(audio):
    return app().clean_audio_array(audio)


def sanitize_audio_array(audio):
    return app().sanitize_audio_array(audio)

