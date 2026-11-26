# PawLog controller and local dashboard

The ESP32-CAM serves snapshots over Wi-Fi. The Windows PC runs both YOLO
models and the local PawLog dashboard. The Arduino Uno connects to the PC
by USB and controls the motor through the IBT-2.

## Uno connections

| Component | Uno |
| --- | --- |
| HOME SPDT switch | COM to GND, NC to D2, NO to D4 |
| TILT SPDT switch | COM to GND, NC to D3, NO to D8 |
| IBT-2 | RPWM to D5, LPWM to D6, R_EN and L_EN to D7 |
| HC-SR04 | Trig to D9, Echo to D10, VCC to 5V, GND to GND |

Keep the driver and Uno grounds common and use the existing 10 kΩ
pulldown from D7 to GND. Use a physical motor-power cutoff within reach.
The old TILT-only diagnostic uses a timed return. This firmware requires
both switches and reads both contacts on each switch.

Measure the empty-box distance with the assembled tray at HOME and TILT
and through the full motion. Choose a narrow range that includes repeatable
empty readings and excludes occupied readings. Check sensor coverage using
objects with motor power disconnected. The controller treats no echo and
out-of-range readings as blocked. PWM starts at 100/255. The sketch assumes
RPWM moves toward TILT and LPWM moves toward HOME.

## Start on Windows

1. Open **PawLogController.ino** in Arduino IDE, choose **Arduino Uno**
   and its USB COM port, upload the sketch, then close Serial Monitor.
2. From the repository root, run `.venv\Scripts\python.exe -m pip install -r requirements.txt`
   if the environment is missing a dependency.
3. Copy the ESP32-CAM IP from its serial output after `Camera Ready!`.
   Replace the three placeholders below with that IP, the Uno COM port,
   and your measured empty-box range in centimetres.

```powershell
.\.venv\Scripts\python.exe -m src.webapp.preview --camera CAMERA_IP --arduino COM_PORT --empty-range MIN_CM MAX_CM
```

4. Open **http://127.0.0.1:8080/#cleaning**. Test **Run one cycle** with
   an empty tray under supervision. Also verify **Stop motor**, sensor
   obstruction, blocked switches, and camera/USB loss. Use the physical
   cutoff if movement continues unexpectedly. Check that the tray stops
   at each switch. After a fault, cut motor power, inspect the mechanism,
   return the tray to HOME and reset the Arduino before testing again.
5. Once the supervised checks pass, restart the command with `--auto-clean`.
   The monitor confirms at least 6 seconds of cat presence, waits for at
   least 10 seconds of continuous camera clearance, saves the visit with
   both photos and a waste result, then checks the next fresh frame before
   it can request one cycle for detected waste. Arduino independently
   checks occupancy, the camera lease, and both switches throughout the
   cycle. An interruption stops movement and faults the cycle. Keep the
   PC awake and connected.

Using only `--camera` records visits without connecting the Uno. Using no
arguments opens existing local History. Camera monitoring uploads completed
visits to hosted PawLog using the existing upload key. Use `--no-sync`
for a local-only session. Previously uploaded visits with sync markers
are skipped. Cat names and assignments are stored per browser and site
address. They survive reloads and do not edit camera images or detection
reports.

## Test a photo without hardware

Double-click `src/vision/test-cat-photo.cmd` or
`src/vision/test-poop-photo.cmd` and select an image in the file picker.
Each script prints its detected labels and confidences, and saves a
separate report and annotated image under `outputs/vision`. Use a known
positive and a clean/empty negative image for each detector.
