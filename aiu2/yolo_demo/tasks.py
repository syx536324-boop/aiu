"""Run a small CUDA training pass and image detection with YOLO11n."""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

from .config import DATASETS, MODEL, RUNS, TEMP, prepare_environment

COCO8_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco8.zip"


def _runtime():
    prepare_environment()
    import torch
    from ultralytics import YOLO, settings

    settings.update({"datasets_dir": str(DATASETS), "runs_dir": str(RUNS)})
    return torch, YOLO


def _prepare_coco8() -> Path:
    """Place the official sample dataset and its local config inside this project."""
    from ultralytics import __file__ as ultralytics_file
    from ultralytics.utils import YAML

    dataset_root = DATASETS / "coco8"
    if not (dataset_root / "images" / "train").is_dir() or not (dataset_root / "images" / "val").is_dir():
        archive_path = TEMP / "coco8.zip"
        with urlopen(COCO8_URL, timeout=60) as response, archive_path.open("wb") as target:
            shutil.copyfileobj(response, target)
        with ZipFile(archive_path) as archive:
            root = DATASETS.resolve()
            for item in archive.infolist():
                if not (root / item.filename).resolve().is_relative_to(root):
                    raise ValueError(f"Unsafe dataset archive entry: {item.filename}")
            archive.extractall(DATASETS)

    official = Path(ultralytics_file).parent / "cfg" / "datasets" / "coco8.yaml"
    dataset_config = YAML.load(official)
    dataset_config["path"] = str(dataset_root)
    dataset_config.pop("download", None)
    local_yaml = DATASETS / "coco8-local.yaml"
    YAML.save(local_yaml, dataset_config)
    return local_yaml


def train_demo() -> Path:
    """Fine-tune YOLO11n on the official COCO8 sample and return best weights."""
    torch, yolo_class = _runtime()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; training was not started.")
    print(f"CUDA device: {torch.cuda.get_device_name(0)}", flush=True)
    data_yaml = _prepare_coco8()
    model = yolo_class(str(MODEL))
    model.train(
        data=str(data_yaml),
        epochs=3,
        imgsz=640,
        batch=2,
        device=0,
        workers=0,
        cache=False,
        amp=True,
        plots=False,
        project=str(RUNS),
        name="coco8_train",
        exist_ok=True,
    )
    best = RUNS / "coco8_train" / "weights" / "best.pt"
    if not best.is_file():
        raise RuntimeError(f"Training finished without a best checkpoint: {best}")
    print(f"Saved trained weights: {best}", flush=True)
    return best


def predict_image(source: Path | None = None) -> Path:
    """Detect objects in one image and save the annotated result."""
    torch, yolo_class = _runtime()
    if source is None:
        candidates = sorted((DATASETS / "coco8" / "images" / "val").glob("*.*"))
        if not candidates:
            raise FileNotFoundError("No COCO8 validation image found; run train first or pass --source.")
        source = candidates[0]
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    trained = RUNS / "coco8_train" / "weights" / "best.pt"
    weights = trained if trained.is_file() else MODEL
    model = yolo_class(str(weights))
    results = model.predict(
        source=str(source),
        imgsz=640,
        device=0 if torch.cuda.is_available() else "cpu",
        save=True,
        project=str(RUNS),
        name="predict",
        exist_ok=True,
    )
    if not results:
        raise RuntimeError("No prediction result was returned.")
    output = RUNS / "predict" / source.name
    if not output.is_file():
        raise RuntimeError(f"Prediction output was not saved: {output}")
    print(f"Saved annotated image: {output}", flush=True)
    return output
