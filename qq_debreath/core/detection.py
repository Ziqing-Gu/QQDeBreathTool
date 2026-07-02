from __future__ import annotations

from .legacy import app


def analyze_regions(
    audio,
    sample_rate,
    model_bundle,
    threshold=None,
    detect_noize=False,
    source_path=None,
    progress_callback=None,
):
    return app().analyze_regions(
        audio,
        sample_rate,
        model_bundle,
        threshold=threshold,
        detect_noize=detect_noize,
        source_path=source_path,
        progress_callback=progress_callback,
    )

