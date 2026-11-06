"""Detect cats in a photo or ESP32-CAM snapshot. Never controls motors."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from detect import ROOT, YOLO, cv2, read_photo


def predict_cat(model, photo, confidence):
    cat_classes = [key for key, name in model.names.items() if name.strip().lower() == "cat"]
    if not cat_classes:
        raise ValueError("Model has no 'cat' class. Use the cat model, not waste weights.")
    result = model.predict(photo, classes=cat_classes, conf=confidence, imgsz=640, device="cpu", verbose=False)[0]
    detections = [dict(label="cat", confidence=round(float(box.conf.item()), 4), xyxy=box.xyxy[0].tolist()) for box in result.boxes]
    return result, detections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", help="Photo path or HTTP /capture URL")
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "yolo26n.pt")
    args = parser.parse_args()
    if not 0 < args.conf < 1:
        parser.error("--conf must be between 0 and 1")
    source = args.source
    if not source:
        import tkinter as tk
        from tkinter import filedialog
        window = tk.Tk()
        window.withdraw()
        source = filedialog.askopenfilename(title="Select a cat photo", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp")])
        window.destroy()
        if not source:
            print("Cancelled. No detection performed.")
            return
    output = ROOT / "outputs" / "vision" / ("cat-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    output.mkdir(parents=True)
    report = dict(status="unknown", cat_detected=None, cleaning_allowed=False)
    try:
        photo = read_photo(source)
        model = YOLO(str(args.model))
        result, detections = predict_cat(model, photo, args.conf)
        image_path = output / "detection.jpg"
        success, encoded = cv2.imencode(".jpg", result.plot())
        if not success:
            raise ValueError("Could not encode detection image")
        encoded.tofile(str(image_path))
        report.update(status="ok", cat_detected=bool(detections), observation="cat_present" if detections else "cat_not_detected", detections=detections, threshold=args.conf, model=str(args.model), inference_ms=result.speed.get("inference"))
    except Exception as error:
        report["error"] = str(error)
    (output / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Saved to: {output}")
    print("Detection only. No motor command is sent. No detection does not prove absence.")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
