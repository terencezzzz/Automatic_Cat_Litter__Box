"""Observe litter box visits and record a waste check. No motor control."""
import argparse
import json
from datetime import datetime
from threading import Thread
from time import monotonic, sleep

from upload_pawlog import KEY as PAWLOG_KEY, sync_visits

from detect import ROOT, YOLO, cv2, predict_waste, read_photo
from detect_cat import predict_cat

INTERVAL = 2.0
MIN_VISIT_TIME = 6.0
CLEAR_TIME = 10.0
MAX_FRAME_GAP = 4.0


class Visit:
    def __init__(self):
        self.seen_cat = False
        self.present_since = None
        self.last_present = None
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
            if self.last_present is None or captured_at - self.last_present > MAX_FRAME_GAP:
                self.present_since = captured_at
                if not self.seen_cat:
                    self.first_seen_at = None
            self.last_present = captured_at
            if captured_at - self.present_since >= MIN_VISIT_TIME:
                self.seen_cat = True
        else:
            self.present_since = self.last_present = None
        if cat_present is not False:
            self.clear_since = self.last_clear = None
            return False
        if not self.seen_cat:
            return False
        if self.last_clear is None or captured_at - self.last_clear > MAX_FRAME_GAP:
            self.clear_since = captured_at
        self.last_clear = captured_at
        return captured_at - self.clear_since >= CLEAR_TIME


def check_camera(source, model, confidence=0.35, fetch=None):
    # Timestamp before requesting the frame, so slow requests cannot make old
    # observations count as an uninterrupted clear window.
    captured_at = monotonic()
    photo_time = datetime.now().astimezone()
    photo = fetch(source) if fetch else read_photo(source)
    _, cats = predict_cat(model, photo, confidence)
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
    pending_report = output / "result.json.tmp"
    pending_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    pending_report.replace(output / "result.json")
    print(f"Waste detected: {report['waste_detected']} | Saved: {output}", flush=True)
    return report['waste_detected']


def sync_pawlog_in_background():
    while True:
        try:
            sync_visits()
        except (OSError, ValueError) as error:
            print(f"PawLog sync unavailable: {type(error).__name__}", flush=True)
        sleep(15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="ESP32-CAM IP or full HTTP /capture URL")
    parser.add_argument("--cat-conf", type=float, default=0.35,
                        help="Cat confidence threshold (default: 0.35)")
    args = parser.parse_args()
    if not 0 < args.cat_conf < 1:
        parser.error("--cat-conf must be between 0 and 1")
    source = args.source.strip()
    if not source.startswith(("http://", "https://")):
        source = "http://" + source
    source = source.rstrip("/")
    if not source.endswith("/capture"):
        source += "/capture"

    monitor(source, args.cat_conf, sync=True)


def monitor(source, confidence=.35, *, cleaning=None, automatic=False, timed_motor=None, stop=None, sync=False, fetch=None):
    print(f"Loading models. Camera: {source}", flush=True)
    cat_model = YOLO(str(ROOT / "models" / "yolo26n.pt"))
    waste_model = YOLO(str(ROOT / "models" / "weights.pt"))
    if sync:
        if not PAWLOG_KEY.is_file():
            print('PawLog upload key missing. Visits are saved locally and upload will retry.', flush=True)
        Thread(target=sync_pawlog_in_background, daemon=True).start()
    visit = Visit()
    confirm_next_frame = False
    print(f"Monitoring. Cat threshold: {confidence:.2f}. Press Ctrl+C to stop.", flush=True)

    pending_clean = None
    while stop is None or not stop.is_set():
        started = monotonic()
        try:
            captured_at, photo_time, photo, cat_count = check_camera(source, cat_model, confidence, fetch)
            if stop is not None and stop.is_set():
                return
            cat_present = cat_count > 0
            if timed_motor:
                timed_motor.observe(cat_present, captured_at)
                if pending_clean is not None:
                    if not cat_present and captured_at - pending_clean <= 2.5:
                        print('MotorTest start requested' if timed_motor.start(captured_at) else 'MotorTest start blocked', flush=True)
                    pending_clean = None
            if cleaning:
                cleaning.observe(cat_present, captured_at)
                if pending_clean is not None:
                    if not cat_present and captured_at - pending_clean <= MAX_FRAME_GAP:
                        print('Automatic start queued' if cleaning.run_once() else 'Automatic start blocked', flush=True)
                    pending_clean = None
            ready = visit.observe(cat_present, captured_at)
            if cat_present:
                visit.record_cat(photo, photo_time, cat_count)
                presence = captured_at - visit.present_since
                status = "Visit confirmed" if visit.seen_cat else f"Waiting for {MIN_VISIT_TIME:g}s"
                print(f"CAT DETECTED | Present: {presence:.1f}s | {status}", flush=True)
            elif not visit.seen_cat:
                print("Waiting for a cat visit", flush=True)
            elif ready and confirm_next_frame:
                if timed_motor:
                    try:
                        save_waste_check(waste_model, photo, photo_time, visit)
                    except Exception as error:
                        print(f"Waste check failed: {error}", flush=True)
                    pending_clean = captured_at
                else:
                    waste = save_waste_check(waste_model, photo, photo_time, visit)
                    if automatic and waste:
                        pending_clean = captured_at
                visit = Visit()
                ready = False
            elif ready:
                print("Clear window reached | Checking the next fresh frame", flush=True)
            else:
                print(f"Cat not detected | Clear window: {captured_at - visit.clear_since:.1f}s", flush=True)
            confirm_next_frame = ready
        except Exception as error:
            if timed_motor and timed_motor.running:
                timed_motor.blocked = True
                try:
                    timed_motor.stop()
                except OSError:
                    pass  # The Uno camera watchdog also stops the timed cycle.
            if cleaning:
                cleaning.observe(None, started)
            pending_clean = None
            visit.observe(None, monotonic())
            confirm_next_frame = False
            print(f"UNKNOWN | Clear timer reset: {error}", flush=True)
        interval = .25 if timed_motor and timed_motor.running else INTERVAL
        delay = max(0.0, interval - (monotonic() - started))
        stop.wait(delay) if stop is not None else sleep(delay)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
