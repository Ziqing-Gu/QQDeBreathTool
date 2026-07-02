from __future__ import annotations

from pathlib import Path

from .legacy import app, to_legacy_regions


def build_stem_gains(audio_length, sample_rate, regions, fade_in_ms=5.0, fade_out_ms=5.0):
    return app().build_stem_gains(audio_length, sample_rate, to_legacy_regions(list(regions)), fade_in_ms, fade_out_ms)


def normalize_breath_blocks(data, audio, regions, sample_rate, target_db=-6.0):
    return app().normalize_breath_blocks(data, audio, to_legacy_regions(list(regions)), sample_rate, target_db)


def apply_breath_gain(data, gain_db=0.0):
    return app().apply_breath_gain(data, gain_db)


def export_stems(
    path: str | Path,
    audio,
    sample_rate,
    subtype,
    regions,
    fade_in_ms=5.0,
    fade_out_ms=5.0,
    normalize_breath=False,
    breath_target_db=-6.0,
    breath_gain_db=0.0,
):
    return app().export_stems(
        path,
        audio,
        sample_rate,
        subtype,
        to_legacy_regions(list(regions)),
        fade_in_ms,
        fade_out_ms,
        normalize_breath,
        breath_target_db,
        breath_gain_db,
    )


def export_stems_legacy_defaults(path: str | Path, audio, sample_rate, subtype, regions):
    return app().export_stems(path, audio, sample_rate, subtype, to_legacy_regions(list(regions)))
