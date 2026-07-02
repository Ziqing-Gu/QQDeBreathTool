from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from qq_debreath.core import AnalysisParams
from qq_debreath.core import audio_io, model_loader
from qq_debreath.core.facade import analyze_audio, render_stems


APP_NAME = "QQDeBreathTool"
SCHEMA_VERSION = 1
ALGORITHM_VERSION = "python_v1"

ERROR_EXIT_CODE = 1
INPUT_ERROR_EXIT_CODE = 2
MODEL_ERROR_EXIT_CODE = 3
ANALYSIS_ERROR_EXIT_CODE = 4


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_model_path(model_path: str | Path | None = None) -> Path:
    if model_path:
        path = Path(model_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"Model not found: {path}")

    for candidate in model_loader.candidate_model_paths():
        if candidate.exists():
            return Path(candidate)
    raise FileNotFoundError("breath_frame_model.joblib was not found.")


def bool_from_int(value: str) -> bool:
    if value not in {"0", "1"}:
        raise argparse.ArgumentTypeError("must be 0 or 1")
    return value == "1"


def breath_gain_db_value(value: str) -> float:
    parsed = float(value)
    if parsed < -30.0 or parsed > 30.0:
        raise argparse.ArgumentTypeError("must be between -30.0 and +30.0 dB")
    return parsed


def file_key(label: str) -> str:
    return {
        "Vocal Only": "vocal_only",
        "Breath": "breath",
        "Noize": "noize",
    }[label]


def region_to_plugin_json(region, idx: int, sample_rate: int) -> dict[str, Any]:
    start_sample = int(round(float(region.start) * sample_rate))
    end_sample = int(round(float(region.end) * sample_rate))
    return {
        "id": idx,
        "type": region.cls,
        "start_time": float(region.start),
        "end_time": float(region.end),
        "start_sample": start_sample,
        "end_sample": end_sample,
        "confidence": region.confidence,
    }


def ok_payload(
    *,
    input_path: Path,
    input_sha256: str,
    model_path: Path,
    model_sha256: str,
    params: AnalysisParams,
    fade_ms: float,
    audio,
    sample_rate: int,
    info,
    regions,
    exports: dict[str, str],
) -> dict[str, Any]:
    return {
        "app": APP_NAME,
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "status": "ok",
        "input": {
            "path": str(input_path),
            "sample_rate": int(sample_rate),
            "channels": int(info.channels),
            "num_samples": int(len(audio)),
            "duration": float(len(audio) / sample_rate),
            "sha256": input_sha256,
        },
        "model": {
            "path": str(model_path),
            "sha256": model_sha256,
        },
        "params": {
            "threshold": float(params.threshold),
            "fade_ms": float(fade_ms),
            "breath_target_db": float(params.breath_target_db),
            "breath_gain_db": float(params.breath_gain_db),
            "detect_noize": bool(params.detect_noize),
        },
        "regions": [region_to_plugin_json(region, idx, sample_rate) for idx, region in enumerate(regions, start=1)],
        "files": {file_key(label): path for label, path in exports.items()},
    }


def error_payload(code: str, message: str, detail: str | None = None) -> dict[str, Any]:
    payload = {
        "app": APP_NAME,
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
    }
    if detail:
        payload["error"]["detail"] = detail
    return payload


def write_json(path: Path, payload: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze audio for the QQDeBreathTool plugin bridge.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--threshold", type=float, default=0.86)
    parser.add_argument("--fade-ms", type=float, default=10.0)
    parser.add_argument("--breath-target-db", type=float, default=-6.0)
    parser.add_argument("--breath-gain-db", type=breath_gain_db_value, default=0.0)
    parser.add_argument("--detect-noize", type=bool_from_int, default=False)
    return parser


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    input_path = args.input
    if not input_path.exists():
        return INPUT_ERROR_EXIT_CODE, error_payload("INPUT_NOT_FOUND", f"Input file not found: {input_path}")

    try:
        model_path = resolve_model_path(args.model)
    except Exception as exc:
        return MODEL_ERROR_EXIT_CODE, error_payload("MODEL_NOT_FOUND", str(exc))

    params = AnalysisParams(
        threshold=float(args.threshold),
        detect_noize=bool(args.detect_noize),
        fade_seconds=float(args.fade_ms) / 1000.0,
        breath_target_db=float(args.breath_target_db),
        breath_gain_db=float(args.breath_gain_db),
        normalize_breath=False,
    )

    try:
        input_sha256 = sha256_file(input_path)
        model_sha256 = sha256_file(model_path)
        audio, sample_rate, info = audio_io.read_audio(input_path)
        model_bundle = model_loader.load_model(model_path)
        result = analyze_audio(audio, sample_rate, model_bundle, params, source_path=input_path)
        exports = render_stems(
            audio,
            sample_rate,
            result.regions,
            params,
            args.out_dir,
            source_path=input_path,
            subtype=info.subtype or "PCM_24",
        )
        return 0, ok_payload(
            input_path=input_path,
            input_sha256=input_sha256,
            model_path=model_path,
            model_sha256=model_sha256,
            params=params,
            fade_ms=float(args.fade_ms),
            audio=audio,
            sample_rate=sample_rate,
            info=info,
            regions=result.regions,
            exports=exports,
        )
    except Exception as exc:
        return ANALYSIS_ERROR_EXIT_CODE, error_payload("ANALYSIS_FAILED", str(exc), traceback.format_exc())


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    exit_code, payload = run(args)
    write_json(args.output_json, payload)
    status = payload.get("status", "unknown")
    region_count = len(payload.get("regions", [])) if isinstance(payload.get("regions"), list) else 0
    print(f"status={status} regions={region_count} output_json={args.output_json}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
