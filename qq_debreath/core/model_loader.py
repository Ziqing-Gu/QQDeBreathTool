from __future__ import annotations

from pathlib import Path

from .legacy import app


def candidate_model_paths():
    return app().candidate_model_paths()


def load_model(path: str | Path | None = None):
    return app().load_model(path)

