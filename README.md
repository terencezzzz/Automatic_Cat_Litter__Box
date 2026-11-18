# Automatic Cat Litter Box / PawLog

ESP32-CAM supplies live video and photos over Wi-Fi. A Windows PC detects cat visits and waste, obtains Groq observations and automatically uploads records to https://pawlog-workshop-demo.shangkeytchong.chatgpt.site/#history.

## Start monitoring

1. Install dependencies from requirements.txt in .venv and supply both weights as described in models/README.md.
2. Copy .env.example to .env and configure Groq locally.
3. Connect the camera and PC to the same network. Verify http://pawlog-cam.local/capture.
4. Double-click src/vision/start-camera-monitor.cmd and press Enter for the default camera name.

The PC must stay running. Six seconds of continuous cat detection confirms a visit. Ten seconds without detection plus a fresh-frame check triggers waste detection. Photos and JSON are saved under outputs/vision/auto-*/. Pending uploads retry every 15 seconds; failed AI analysis retries after five minutes.

## PawLog and credentials

Hosted History, photographs and AI observations are public by owner choice. Camera live video requires the viewer to reach the camera locally. Online History can be viewed remotely after upload.

The configured PC stores the upload credential in ignored outputs/vision/.pawlog-upload-key. Transfer this privately to a fresh PC. Hosted PAWLOG_UPLOAD_KEY must match. Groq credentials are read locally from .env. Runtime photos, credentials and model binaries must stay excluded from Git.

AI describes stool appearance and possible abnormalities with care guidance. AI can make mistakes. Consult a licensed veterinarian about concerns. A photo cannot establish overall cat health.

## Firmware

CameraWebServer uses 115200 baud and advertises pawlog-cam.local. See src/firmware/camera/CameraWebServer/WIFI_SETUP.md for upload settings and src/firmware/WIRING_GUIDE.md for UNO and IBT-2 connections.

The chosen motor configuration omits limit switches. MotorTest.ino currently supports a manual one-second pulse and stop command. Automatic tray motion, accurate return-to-home and occupied-tray protection remain unimplemented or unverified. HC-SR04 is optional for separate diagnostics; camera monitoring does not require it.

## Source layout

- src/vision contains detection, monitoring and upload scripts.
- src/webapp contains the local viewer, Groq client and earlier backend drafts.
- deploy/pawlog contains the hosted Worker, frontend and Sites manifest. Run node build.mjs there to create dist/server/index.js. Hosting uses the BUCKET R2 binding.
- src/firmware contains ESP32-CAM firmware and UNO diagnostic sketches.

Double-click preview-webapp.cmd for an optional local History viewer. The published website receives records directly from the configured monitoring PC.
