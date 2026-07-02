from __future__ import annotations

import json
from pathlib import Path

from .regions import region_public_dict


def analysis_report(input_path: str | Path, regions, exports: dict[str, str]):
    return {
        "input": str(input_path),
        "regions": [region_public_dict(region) for region in regions],
        "exports": exports,
    }


def write_analysis_report(path: str | Path, report: dict):
    path = Path(path)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

