"""Project paths and local cache settings for the YOLO demo."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
DATASETS = ROOT / "datasets"
RUNS = ROOT / "runs"
CONFIG = ROOT / ".config"
TEMP = ROOT / ".tmp"
MODEL = MODELS / "yolo11n.pt"


def prepare_environment() -> None:
    """Keep downloads, Ultralytics settings, and temporary data on drive D."""
    for path in (MODELS, DATASETS, RUNS, CONFIG, TEMP):
        path.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(CONFIG)
    os.environ["TORCH_HOME"] = str(MODELS)
    os.environ["TEMP"] = str(TEMP)
    os.environ["TMP"] = str(TEMP)
