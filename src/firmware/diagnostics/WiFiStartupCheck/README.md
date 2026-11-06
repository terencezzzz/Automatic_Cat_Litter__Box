# Wi-Fi Startup Isolation Test

This separate sketch starts the Wi-Fi driver without initializing the camera,
loading the five-network store, connecting to an access point, or opening a
configuration portal. It does not disable brownout protection or erase stored
credentials. Keep Erase All Flash Before Sketch Upload disabled.

Open WiFiStartupCheck.ino in Arduino IDE. Use the same board settings as the
camera project. Upload in download mode, then disconnect IO0 from GND and reset.
Read Serial Monitor at 115200 baud.

- If `[TEST] Alive` continues for at least 30 seconds, this test is stable;
  investigate differences between combined camera/Wi-Fi operation and this test.
  This does not prove that the combined hardware load is electrically stable.
- If it repeats the boot sequence and reports Brownout, the five-network and
  camera application code is not needed to reproduce that event. The cause still
  requires investigation; this test does not distinguish supply behavior from
  a core/driver or board issue.

Uploading this test temporarily replaces the camera application. Camera-Setup
and the camera feed are unavailable until CameraWebServer.ino is uploaded again.
Stored Wi-Fi data is retained unless flash is erased.
