"""Observe litter box visits and record a waste check. No motor control."""
import argparse
import json
from datetime import datetime
from time import monotonic, sleep

from detect import ROOT, YOLO, cv2, predict_waste, read_photo
from detect_cat import predict_cat

INTERVAL = 2.0
CLEAR_TIME = 10.0
MAX_FRAME_GAP = 4.0


class Visit:
    def __init__(self):
        self.seen_cat = False
        self.clear_since = None
        self.last_clear = None
        self.first_seen_at = None
        self.last_seen_at = None
        self.cat_photo = None
        self.cats_in_photo = None

    def record_cat(self, photo, photo_time, cat_count):
        if self.first_seen_at is None:
            self.first_seen_at = photo_time
            self.cat_photo = photo
            self.cats_in_photo = cat_count
        self.last_seen_at = photo_time

    def observe(self, cat_present, captured_at):
        if cat_present is True:
            self.seen_cat = True
        if cat_present is not False:
            self.clear_since = self.last_clear = None
            return False
        if not self.seen_cat:
            return False
        if self.last_clear is None or captured_at - self.last_clear > MAX_FRAME_GAP:
            self.clear_since = captured_at
        self.last_clear = captured_at
        return captured_at - self.clear_since >= CLEAR_TIME


def check_camera(source, model):
    # Timestamp before requesting the frame, so slow requests cannot make old
    # observations count as an uninterrupted clear window.
    captured_at = monotonic()
    photo_time = datetime.now().astimezone()
    photo = read_photo(source)
    _, cats = predict_cat(model, photo, 0.35)
    if monotonic() - captured_at > MAX_FRAME_GAP:
        raise RuntimeError("Camera observation took too long")
    return captured_at, photo_time, photo, len(cats)


def save_waste_check(model, photo, photo_time, visit):
    result, report = predict_waste(model, photo, 0.32)
    output = ROOT / "outputs" / "vision" / datetime.now().strftime("auto-%Y%m%d-%H%M%S-%f")
    images = {
        "cat.jpg": visit.cat_photo,
        "waste-original.png": photo,
        "detection.jpg": result.plot(),
    }
    encoded_images = {}
    for name, image in images.items():
        success, encoded = cv2.imencode("." + name.rsplit(".", 1)[1], image)
        if not success:
            raise ValueError(f"Could not encode {name}")
        encoded_images[name] = encoded
    output.mkdir(parents=True)
    for name, encoded in encoded_images.items():
        encoded.tofile(str(output / name))
    report.update(
        cat_detected=False,
        cleaning_allowed=False,
        cat_id=None,
        cat_photo="cat.jpg",
        cats_detected_in_cat_photo=visit.cats_in_photo,
        cat_first_seen_at=visit.first_seen_at.isoformat(),
        cat_last_seen_at=visit.last_seen_at.isoformat(),
        observed_presence_seconds=round(
            (visit.last_seen_at - visit.first_seen_at).total_seconds(), 1
        ),
        waste_photo="waste-original.png",
        waste_photo_at=photo_time.isoformat(),
    )
    (output / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Waste detected: {report['waste_detected']} | Saved: {output}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="ESP32-CAM IP or full HTTP /capture URL")
    source = parser.parse_args().source.strip()
    if not source.startswith(("http://", "https://")):
        source = "http://" + source
    source = source.rstrip("/")
    if not source.endswith("/capture"):
        source += "/capture"

    print(f"Loading models. Camera: {source}", flush=True)
    cat_model = YOLO(str(ROOT / "models" / "yolo26n.pt"))
    waste_model = YOLO(str(ROOT / "models" / "weights.pt"))
    visit = Visit()
    confirm_next_frame = False
    print("Monitoring. Press Ctrl+C to stop.", flush=True)

    while True:
        started = monotonic()
        try:
            captured_at, photo_time, photo, cat_count = check_camera(source, cat_model)
            cat_present = cat_count > 0
            ready = visit.observe(cat_present, captured_at)
            if cat_present:
                visit.record_cat(photo, photo_time, cat_count)
                print("CAT DETECTED | Clear timer reset", flush=True)
            elif not visit.seen_cat:
                print("Waiting for a cat visit", flush=True)
            elif ready and confirm_next_frame:
                save_waste_check(waste_model, photo, photo_time, visit)
                visit = Visit()
                ready = False
            elif ready:
                print("Clear window reached | Checking the next fresh frame", flush=True)
            else:
                print(f"Cat not detected | Clear window: {captured_at - visit.clear_since:.1f}s", flush=True)
            confirm_next_frame = ready
        except Exception as error:
            visit.observe(None, monotonic())
            confirm_next_frame = False
            print(f"UNKNOWN | Clear timer reset: {error}", flush=True)
        sleep(max(0.0, INTERVAL - (monotonic() - started)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
