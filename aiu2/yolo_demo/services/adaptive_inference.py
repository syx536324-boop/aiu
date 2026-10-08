"""Move one YOLO model between GPU and CPU and recover from CUDA failures."""

import gc

from .device_policy import AutoDevicePolicy


class AdaptiveInference:
    def __init__(self, weight):
        import torch
        from ultralytics import YOLO

        self.torch = torch
        torch.set_num_threads(4)
        self.model = YOLO(str(weight))
        self.policy = AutoDevicePolicy(torch.cuda.is_available())
        self.device = 'cpu'
        self.gpu_label = torch.cuda.get_device_name(0) if self.policy.cuda_available else 'GPU'

    def _move(self, device):
        self.model.predictor = None
        self.model.to(device)
        self.device = device
        gc.collect()
        if self.policy.cuda_available:
            self.torch.cuda.empty_cache()

    def predict(self, frame, confidence):
        target = self.policy.decide()
        try:
            if target != self.device:
                self._move(target)
            return self.model.predict(frame, conf=confidence, imgsz=640, device=self.device, verbose=False)
        except RuntimeError as exc:
            message = str(exc).lower()
            if target == 'cpu' or not any(word in message for word in ('cuda', 'cudnn', 'cublas', 'out of memory')):
                raise
            self.policy.gpu_failed()
        # Retry outside the exception scope so GPU tensor traceback references are released.
        self._move('cpu')
        return self.model.predict(frame, conf=confidence, imgsz=640, device='cpu', verbose=False)

    def status(self):
        return {**self.policy.status(), 'device': self.gpu_label if self.device == 'cuda:0' else 'CPU'}

    def close(self):
        self.model = None
        gc.collect()
        if self.policy.cuda_available:
            self.torch.cuda.empty_cache()
