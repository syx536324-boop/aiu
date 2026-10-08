"""Parse experiment options and invoke the benchmark feature."""

import argparse

from .experiment import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare YOLO11n inference backends on identical tensors")
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--warmups", type=int, default=12)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.iterations < 20 or args.warmups < 1 or not 1 <= args.threads <= 24:
        parser.error("Use at least 20 iterations, one warmup, and 1-24 CPU threads")
    run_experiment(args.iterations, args.warmups, args.threads)


if __name__ == "__main__":
    main()
