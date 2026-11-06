# Local Vision Detection on Windows

Run these commands from the project root to create the Python environment and install the dependencies.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy both weights into `models/` as described in the [model setup guide](../../models/README.md). The `.ultralytics/` directory stores local Ultralytics settings. Detection outputs go to `outputs/vision/`.

## Windows launchers

| Launcher | How to use it |
| --- | --- |
| `start-camera-monitor.cmd` | Double-click and enter the ESP32-CAM IP. After detecting a cat visit, the monitor waits for about 10 seconds without a cat detection, checks a fresh frame, and runs one waste check. Events go to `outputs/vision/auto-*/`. |
| `test-cat-camera.cmd` | Double-click and enter the camera IP shown after `Camera Ready!` in the camera serial output. |
| `test-cat-photo.cmd` | Drop a local photo onto the launcher to check for a cat. |
| `test-poop-photo.cmd` | Drop a local photo onto the launcher to check for waste. |

## Check a single ESP32-CAM snapshot

Run from the project root and replace `<camera-ip>` with the actual camera IP. The PC must be able to reach the camera on the local network. Use the `/capture` snapshot endpoint.

```powershell
.\.venv\Scripts\python.exe src/vision/detect_cat.py "http://<camera-ip>/capture"
.\.venv\Scripts\python.exe src/vision/detect.py "http://<camera-ip>/capture"
```

## Read the results

- **Cat detection** uses the COCO-pretrained `models/yolo26n.pt` and filters for the `cat` class. It saves an image and JSON under `outputs/vision/cat-*/`. A failed capture or inference returns `status: unknown`, `cat_detected: null`, and exit code 1. A `false` result means the model found no cat in the frame. Poor lighting or occlusion can cause missed detections.
- **Waste detection** uses `models/weights.pt`. It saves `detection.jpg` with bounding boxes on a 640 × 640 image and `result.json` with labels, confidence, coordinates, and inference time. `waste_detected` recognizes the labels `waste`, `poop`, `urine`, and `cat urine` when present in the loaded model. `poop_detected` is retained for compatibility. A failed capture or inference exits with code 1.
- **Waste model options** include `--conf 0.5` to change the default confidence threshold of 0.32 and `--model models/other-model.pt` to compare another set of weights. The `model_classes` field shows which classes the loaded model supports.

The vision scripts report observations. The single-frame cat detector always sets `cleaning_allowed` to `false`. Motor safety depends on the Arduino-side sensors, and unknown vision results must prevent cleaning. The assembled prototype still needs end-to-end testing.
