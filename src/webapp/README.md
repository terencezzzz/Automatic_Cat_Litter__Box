# PawLog UI preview

English, cat-themed frontend based on the approved Canva concept. The local History page shows completed camera visits saved by the monitoring script. Other demo screens retain their sample data.

## Open locally

From the project root, double-click `preview-webapp.cmd`, or run:

```powershell
python -m src.webapp.preview
```

Open **http://127.0.0.1:8080** on this computer. Keep the server running while viewing. If that port is in use, run `python -m src.webapp.preview --port 8081` and open the matching address. Python 3.10+ is sufficient; no pip/npm install is needed for the preview.

The preview server listens on loopback so real photos stay on this computer.

## Automatic camera history

Leave the PawLog preview running. In another PowerShell window at the project root, start the monitor once:

```powershell
.\.venv\Scripts\python.exe src/vision/monitor_camera.py "http://pawlog-cam.local/capture"
```

Open `http://127.0.0.1:8080/#history`. The monitor saves each completed visit under `outputs/vision/auto-*/`. History checks for completed visits every five seconds and displays the cat photo, post-visit photo and annotated detection. The hosted [PawLog History](https://pawlog-workshop-demo.shangkeytchong.chatgpt.site/#history) also receives completed visits when the monitor runs on the PC configured with the PawLog upload credential. Hosted History, visit photos and AI observations are publicly viewable. The upload credential is required to write records. The monitor retries pending visits every 15 seconds. After a positive waste detection, Groq receives only the post-visit photo and the monitor uploads its structured observation to the same History record. If analysis fails, the photos remain available and the monitor retries analysis after five minutes. Previously saved visits can be synced with `python src/vision/upload_pawlog.py --once`.

## Files and assets

`templates/index.html` is a static app shell; `static/app.js` contains view templates and sample state; `static/app.css` contains the responsive design system. The standard-library `preview.py` serves the HTML, assets and local vision records without importing the earlier backend scaffold.

The litter-box scene is an AI-generated illustrative asset, labeled on every full-size display. Cat portraits are copied from the project's existing local sample photos; they are fictional profiles, not verified cat identities. Assets are local so there are no third-party image requests.

Earlier backend scaffold files (`app.py`, `runtime.py`, `store.py`, `analysis.py`, `vision.py`) are **paused, unfinished integration work** from before the UI-only scope was selected. They are not used or validated by this preview. Do not run them as a production service. The active monitor and hosted Worker provide camera-visit ingestion, Groq observations and online History. Arduino integration remains unfinished.
