"""Own webcam capture, YOLO inference, annotated frames, and live status."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from ..config import MODEL, ROOT, RUNS, prepare_environment
from .adaptive_inference import AdaptiveInference


class LiveInferenceService:
    """Run one camera inference loop and expose its newest JPEG frame."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: Any = None
        self._jpeg: bytes | None = None
        self._status: dict[str, Any] = {
            "running": False,
            "camera": None,
            "model": None,
            "device": None,
            "fps": 0.0,
            "frames": 0,
            "error": None,
        }

    @staticmethod
    def available_weights() -> list[dict[str, str]]:
        trained = RUNS / "coco8_train" / "weights" / "best.pt"
        choices = []
        if trained.is_file():
            choices.append({"path": str(trained.relative_to(ROOT)), "label": "COCO8 演示训练 · best.pt"})
        if MODEL.is_file():
            choices.append({"path": str(MODEL.relative_to(ROOT)), "label": "YOLO11n 预训练权重"})
        return choices

    @staticmethod
    def _resolve_weight(relative_path: str) -> Path:
        candidate = (ROOT / relative_path).resolve()
        allowed = { (ROOT / item["path"]).resolve() for item in LiveInferenceService.available_weights() }
        if candidate not in allowed or not candidate.is_file():
            raise ValueError("模型权重无效，请从界面提供的模型列表中选择。")
        return candidate

    def start(self, camera: int, weight_path: str, confidence: float) -> None:
        self.stop()
        prepare_environment()
        weight = self._resolve_weight(weight_path)

        import cv2

        capture = cv2.VideoCapture(camera, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(camera)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"无法打开摄像头 {camera}。请检查相机权限，或尝试另一个摄像头编号。")

        try:
            engine = AdaptiveInference(weight)
        except Exception:
            capture.release()
            raise

        with self._lock:
            stop_event = threading.Event()
            self._stop_event = stop_event
            self._capture = capture
            self._jpeg = None
            self._status = {
                "running": True,
                "camera": camera,
                "model": weight.name,
                "weight_path": str(weight.relative_to(ROOT)),
                **engine.status(),
                "fps": 0.0,
                "frames": 0,
                "error": None,
            }
            self._thread = threading.Thread(
                target=self._run, args=(capture, engine, confidence, stop_event),
                name="aiu-yolo-webcam", daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
            capture = self._capture
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=30.0)
            if thread.is_alive():
                raise RuntimeError("推理仍在结束中，请稍后再试。")
        if capture is not None:
            capture.release()
        with self._lock:
            self._thread = None
            self._capture = None
            self._status["running"] = False

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def latest_frame(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def _run(self, capture: Any, engine: AdaptiveInference, confidence: float, stop_event: threading.Event) -> None:
        import cv2

        last_time = time.perf_counter()
        try:
            while not stop_event.is_set():
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("摄像头读取失败，请检查连接或占用情况。")
                results = engine.predict(frame, confidence)
                annotated = results[0].plot()
                del results
                encoded, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if not encoded:
                    continue
                now = time.perf_counter()
                instantaneous_fps = 1.0 / max(now - last_time, 1e-6)
                last_time = now
                with self._lock:
                    self._jpeg = buffer.tobytes()
                    self._status.update(engine.status())
                    self._status["frames"] += 1
                    previous = self._status["fps"]
                    self._status["fps"] = instantaneous_fps if previous == 0 else previous * 0.8 + instantaneous_fps * 0.2
        except Exception as exc:
            with self._lock:
                self._status["error"] = str(exc)
        finally:
            engine.close()
            capture.release()
            with self._lock:
                if self._capture is capture:
                    self._status["running"] = False
                    self._capture = None
                    self._thread = None
