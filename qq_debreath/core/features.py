from __future__ import annotations

from .legacy import app


def features_for_audio(audio, sample_rate):
    return app().features_for_audio(audio, sample_rate)


def frame_features(audio, sample_rate):
    return features_for_audio(audio, sample_rate)
