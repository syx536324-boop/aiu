"""Parse local YOLO commands and compose the selected feature entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .tasks import predict_image, train_demo


def main() -> None:
    parser = argparse.ArgumentParser(description="AIU2 YOLO11n demo and local inference app")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("train", help="Fine-tune YOLO11n on COCO8 for three epochs")
    predict = subcommands.add_parser("predict", help="Run detection on one image")
    predict.add_argument("--source", type=Path, help="Image path; defaults to a COCO8 validation image")
    web = subcommands.add_parser("web", help="Start the local webcam inference website")
    web.add_argument("--host", default="127.0.0.1", help="Bind address; defaults to localhost only")
    web.add_argument("--port", type=int, default=8765, help="Local web port")
    args = parser.parse_args()

    if args.command == "train":
        train_demo()
    elif args.command == "predict":
        predict_image(args.source)
    else:
        from .web.server import serve_web

        serve_web(args.host, args.port)


if __name__ == "__main__":
    main()
