"""Run the project's trained model locally on a photo (or ESP32 snapshot URL)."""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".ultralytics"))

import cv2
import numpy as np
import requests
from ultralytics import YOLO

def read_photo(source):
    if source.startswith(("http://", "https://")):
        response = requests.get(source, timeout=15)
        response.raise_for_status()
        data = np.frombuffer(response.content, dtype=np.uint8)
    else:
        data = np.frombuffer(Path(source).read_bytes(), dtype=np.uint8)
    photo = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if photo is None:
        raise ValueError("Source is not a readable photo; use the camera snapshot URL, not its web page.")
    return photo


def predict_waste(model, photo, confidence):
    # Roboflow training used a 640 x 640 stretch; preserve that preprocessing.
    photo = cv2.resize(photo, (640, 640))
    result = model.predict(photo, imgsz=640, conf=confidence, device="cpu", verbose=False)[0]
    detections = [dict(label=result.names[int(b.cls.item())], confidence=round(float(b.conf.item()), 4), xyxy=b.xyxy[0].tolist()) for b in result.boxes]
    # Support both the original model and the merged waste-class model.
    waste_labels = {"waste", "poop", "urine", "cat urine"}
    report = dict(status="ok", waste_detected=any(d["label"].strip().lower() in waste_labels for d in detections), poop_detected=any(d["label"] == "poop" for d in detections), model_classes=model.names, threshold=confidence, detections=detections, inference_ms=result.speed.get("inference"))
    return result, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", help="Photo path or HTTP snapshot URL")
    parser.add_argument("--conf", type=float, default=0.32)
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "weights.pt", help="Local model weights to evaluate without replacing the current model")
    args = parser.parse_args()
    if not 0 < args.conf < 1:
        parser.error("--conf must be between 0 and 1")
    source = args.source
    if not source:
        import tkinter as tk
        from tkinter import filedialog
        window = tk.Tk()
        window.withdraw()
        source = filedialog.askopenfilename(title="Select a cat litter photo", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")])
        window.destroy()
        if not source:
            print("Cancelled. No detection performed.")
            return
    photo = read_photo(source)
    model = YOLO(str(args.model))
    result, report = predict_waste(model, photo, args.conf)
    output = ROOT / "outputs" / "vision" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output.mkdir(parents=True)
    cv2.imencode(".jpg", result.plot())[1].tofile(str(output / "detection.jpg"))
    (output / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Saved to: {output}")
    print("Detection only. No motor command is sent.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"DETECTION FAILED (unknown result): {error}")
        raise SystemExit(1)
