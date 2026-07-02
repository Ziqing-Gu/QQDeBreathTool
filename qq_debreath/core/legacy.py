from __future__ import annotations

from importlib import import_module
from typing import Any


def app():
    return import_module("debreath_tool_app")


def to_core_region(region: Any):
    from .types import Region

    return Region(
        start=float(region.start),
        end=float(region.end),
        cls=str(region.cls),
        confidence=getattr(region, "confidence", None),
    )


def to_legacy_region(region: Any):
    legacy_app = app()
    if isinstance(region, legacy_app.Region):
        return region
    confidence = getattr(region, "confidence", None)
    if confidence is None:
        confidence = 1.0
    return legacy_app.Region(float(region.start), float(region.end), str(region.cls), float(confidence))


def to_legacy_regions(regions: list[Any]):
    return [to_legacy_region(region) for region in regions]

