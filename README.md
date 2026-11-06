# Automatic Cat Litter Box

Workshop II prototype. For the presentation, the ESP32-CAM provides snapshots over the local network. A Windows PC runs cat and waste detection. The hardware teammate owns the Arduino, sensors, motor control, and prototype integration.

## Repository layout

| Folder | Contents |
| --- | --- |
| [src/vision/](src/vision/) | Windows detection scripts and launchers |
| [src/firmware/camera/](src/firmware/camera/) | ESP32-CAM firmware and [Wi-Fi setup](src/firmware/camera/CameraWebServer/WIFI_SETUP.md) |
| [src/firmware/diagnostics/](src/firmware/diagnostics/) | Arduino sensor, safety-gate, and ESP32 Wi-Fi diagnostic sketches |
| `data/raw/` | Original local sample photos |
| [models/](models/README.md) | Local YOLO weights and setup notes |

Python dependencies are listed in `requirements.txt` at the project root.

## Presentation setup

1. Install Python 3.10 on the demo PC and follow the [AI setup guide](src/vision/README.md). Copy the two model files into [models/](models/README.md) before the presentation.
2. Connect the PC and ESP32-CAM to the same reachable network. Check that `http://<camera-ip>/capture` opens a snapshot.
3. Run `src/vision/start-camera-monitor.cmd` and enter the ESP32-CAM IP. The monitor watches for a cat visit and runs waste detection after a confirmed cat-free interval. Event images and JSON go to `outputs/vision/`.

The PC reports vision results. Arduino-side independent sensors must govern motor safety. Unknown vision results must prevent cleaning. Hardware integration and the full presentation flow still need a test with the assembled prototype.

Local build output, camera results, source images, coursework files, backups, and model binaries are kept outside the Git upload through `.gitignore`.
