from __future__ import annotations

from .legacy import app, to_legacy_region, to_legacy_regions


def normalize_regions(regions, duration):
    return app().normalize_regions(to_legacy_regions(list(regions)), duration)


def insert_region_with_boundaries(regions, new_region, duration, min_duration=0.005):
    return app().insert_region_with_boundaries(
        to_legacy_regions(list(regions)),
        to_legacy_region(new_region),
        duration,
        min_duration,
    )


def subtract_regions(base, cuts, min_gap):
    return app().subtract_regions(base, cuts, min_gap)


def region_public_dict(region):
    return app().region_public_dict(to_legacy_region(region))

