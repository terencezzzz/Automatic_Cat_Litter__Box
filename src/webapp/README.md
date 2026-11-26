# PawLog dashboard

Overview, History, My Cats and Notifications use completed camera visits. Open a full record to assign a cat below the visit photo. Cat profiles and assignments are saved in the browser for the current site address.

## Open locally

From the project root, double-click `preview-webapp.cmd`, or run:

```powershell
python -m src.webapp.preview
```

Open **http://127.0.0.1:8080** on this computer. Keep the server running while viewing. If that port is in use, run `python -m src.webapp.preview --port 8081` and open the matching address. Python 3.10+ is sufficient; no pip/npm install is needed for the preview.

The preview server listens on loopback so real photos stay on this computer.

## Camera, USB motor and automatic cleaning

For wiring, hardware startup, and photo-only tests, see the [PawLog controller guide](../firmware/controller/PawLogController/README.md).

To run the dashboard and camera monitor together without connecting a motor, replace `CAMERA_IP` with the address printed by the ESP32-CAM:

```powershell
.\.venv\Scripts\python.exe -m src.webapp.preview --camera CAMERA_IP
```

Open `http://127.0.0.1:8080/#history`. The monitor saves each completed visit under `outputs/vision/auto-*/`. History checks for completed visits every five seconds. Use the same camera address under **Settings → Live camera** if you want to view its stream.

Camera monitoring uploads completed visits by default using the existing PawLog upload credential. Use `--no-sync` for a local-only session. Hosted [PawLog History](https://pawlog-workshop-demo.shangkeytchong.chatgpt.site/#history), photos and AI observations are publicly viewable. The monitor retries pending uploads every 15 seconds and sends a positive waste photo to Groq for an observation. Previously saved visits can also be synced with `python src/vision/upload_pawlog.py --once`.

## Files and assets

`templates/index.html` is a static app shell; `static/app.js` contains view templates and sample state; `static/app.css` contains the responsive design system. The standard-library `preview.py` serves the HTML, assets and local vision records without importing the earlier backend scaffold.

The litter-box scene is an AI-generated illustrative asset, labeled on every full-size display. Cat portraits are copied from the project's existing local sample photos; they are fictional profiles, not verified cat identities. Assets are local so there are no third-party image requests.

Use `preview.py` as the dashboard entry point. With hardware arguments it uses `vision.py` for bounded LAN snapshots, `monitor_camera.py` for visit detection and `cleaning.py` for USB control. The earlier `app.py` server scaffold is a separate entry point.
