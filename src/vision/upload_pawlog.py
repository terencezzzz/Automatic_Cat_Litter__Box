"""Send completed camera visits and AI observations to PawLog History."""
import argparse
import base64
import json
import re
import sys
from pathlib import Path
from time import sleep, time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.webapp.groq_tools import observe_stool

VISITS = ROOT / "outputs" / "vision"
KEY = VISITS / ".pawlog-upload-key"
ENDPOINT = "https://pawlog-workshop-demo.shangkeytchong.chatgpt.site/api/vision-visits"
IMAGES = ("cat.jpg", "waste-original.png", "detection.jpg")
VISIT_ID = re.compile(r"auto-\d{8}-\d{6}-\d{6}")
AI_RETRY_SECONDS = 300


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        return None


def send(opener, key, url, record, visit_id, expected_status):
    request = Request(
        url, data=json.dumps(record).encode("utf-8"), method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "PawLog-Monitor/1.0",
        },
    )
    with opener.open(request, timeout=12) as response:
        if response.status not in expected_status or json.load(response).get("id") != visit_id:
            raise ValueError("Unexpected PawLog response")


def sync_observation(opener, key, folder):
    marker = folder / ".pawlog-health-observation-uploaded"
    if marker.exists():
        return
    cached = folder / ".pawlog-health-observation.json"
    attempted = folder / ".pawlog-health-observation-attempt"
    url = f"{ENDPOINT}/{folder.name}/observation"
    if not cached.is_file():
        if attempted.exists() and time() - attempted.stat().st_mtime < AI_RETRY_SECONDS:
            return
        attempted.touch()
        try:
            observation = observe_stool(folder / "waste-original.png")
        except (OSError, ValueError):
            send(opener, key, url, {"status": "failed"}, folder.name, (200,))
            print(f"PawLog AI analysis will retry: {folder.name}", flush=True)
            return
        pending = cached.with_suffix(".tmp")
        pending.write_text(json.dumps(observation), encoding="utf-8")
        pending.replace(cached)
    observation = json.loads(cached.read_text(encoding="utf-8"))
    send(opener, key, url, {"status": "complete", "observation": observation}, folder.name, (200,))
    marker.touch()
    print(f"PawLog AI observation uploaded: {folder.name}", flush=True)


def sync_visits():
    key = KEY.read_text(encoding="utf-8").strip()
    if not key:
        raise ValueError("PawLog upload key is empty")
    opener = build_opener(NoRedirect())
    failures = 0
    for folder in sorted(VISITS.glob("auto-*")):
        report_file = folder / "result.json"
        marker = folder / ".pawlog-uploaded"
        if not VISIT_ID.fullmatch(folder.name) or not report_file.is_file():
            continue
        try:
            report = json.loads(report_file.read_text(encoding="utf-8"))
            if not marker.exists():
                record = {
                    "id": folder.name,
                    "capturedAt": report["waste_photo_at"],
                    "wasteDetected": report["waste_detected"],
                    "images": {name: base64.b64encode((folder / name).read_bytes()).decode("ascii") for name in IMAGES},
                }
                send(opener, key, ENDPOINT, record, folder.name, (200, 201))
                marker.touch()
                print(f"PawLog uploaded: {folder.name}", flush=True)
            if report["waste_detected"] is True:
                sync_observation(opener, key, folder)
        except (OSError, ValueError, KeyError, AttributeError) as error:
            failures += 1
            reason = f"HTTP {error.code}" if isinstance(error, HTTPError) else type(error).__name__
            print(f"PawLog sync pending: {folder.name} ({reason})", flush=True)
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        failures = sync_visits()
        if args.once:
            return int(failures > 0)
        sleep(15)


if __name__ == "__main__":
    raise SystemExit(main())
