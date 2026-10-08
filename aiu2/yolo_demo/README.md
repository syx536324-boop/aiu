# YOLO demo module

This module owns the local model training and image prediction behavior.
Run it from the project root with .venv\Scripts\python.exe -m yolo_demo train
or .venv\Scripts\python.exe -m yolo_demo predict. The __main__ module only
parses commands; tasks.py runs the model; config.py keeps paths on drive D.
