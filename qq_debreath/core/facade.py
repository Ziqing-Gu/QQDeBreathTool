from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import audio_io, detection, model_loader, rendering, report
from .legacy import to_core_region
from .types import AnalysisParams, AnalysisResult, Region


def load_model(path: str | Path | None = None):
    return model_loader.load_model(path)


def analyze_audio(
    audio,
    sample_rate: int,
    model_bundle,
    params: AnalysisParams | None = None,
    source_path: str | Path | None = None,
    progress_callback=None,
) -> AnalysisResult:
    threshold = params.threshold if params is not None else None
    detect_noize = params.detect_noize if params is not None else False
    regions = detection.analyze_regions(
        audio,
        sample_rate,
        model_bundle,
        threshold=threshold,
        detect_noize=detect_noize,
        source_path=source_path,
        progress_callback=progress_callback,
    )
    num_samples = int(len(audio))
    return AnalysisResult(
        sample_rate=int(sample_rate),
        num_samples=num_samples,
        duration=num_samples / float(sample_rate),
        regions=[to_core_region(region) for region in regions],
    )


def render_stems(
    audio,
    sample_rate: int,
    regions: list[Any],
    params: AnalysisParams | None,
    out_dir: str | Path,
    *,
    source_path: str | Path | None = None,
    subtype: str = "PCM_24",
    fade_in_ms: float | None = None,
    fade_out_ms: float | None = None,
) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if source_path is None:
        stem_input = out_dir / "audio.wav"
    else:
        stem_input = out_dir / Path(source_path).name
    if params is None:
        return rendering.export_stems_legacy_defaults(
            stem_input,
            audio,
            int(sample_rate),
            subtype,
            regions,
        )
    fade_ms = float(params.fade_seconds) * 1000.0
    fade_in = fade_ms if fade_in_ms is None else float(fade_in_ms)
    fade_out = fade_ms if fade_out_ms is None else float(fade_out_ms)
    return rendering.export_stems(
        stem_input,
        audio,
        int(sample_rate),
        subtype,
        regions,
        fade_in,
        fade_out,
        bool(params.normalize_breath),
        float(params.breath_target_db),
        float(params.breath_gain_db),
    )


def analyze_file_to_directory(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    model_path: str | Path | None = None,
    params: AnalysisParams | None = None,
) -> dict[str, Any]:
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    audio, sample_rate, info = audio_io.read_audio(input_path)
    model_bundle = load_model(model_path)
    result = analyze_audio(audio, sample_rate, model_bundle, params, source_path=input_path)
    exports = render_stems(
        audio,
        sample_rate,
        result.regions,
        params,
        out_dir,
        source_path=input_path,
        subtype=info.subtype or "PCM_24",
    )
    data = report.analysis_report(input_path, result.regions, exports)
    report_path = out_dir / f"{input_path.stem}_analysis_report.json"
    report.write_analysis_report(report_path, data)
    return {"regions": len(result.regions), "report": str(report_path), "exports": exports}
