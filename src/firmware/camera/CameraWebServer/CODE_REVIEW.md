# Startup and Wi-Fi Review — 2026-10-26

Latest revision: **WiFi-first v3** intentionally changes the startup order described in the original review below. It holds camera PWDN high and the flash low, completes Wi-Fi connection/setup, then initializes the camera. The camera driver's initialization releases PWDN. The original camera-before-Wi-Fi findings describe the earlier diagnostics v2 revision. Brownout protection remains enabled; hardware operation still requires verification after upload.

## What was verified

- The AI Thinker pin-definition block exactly matches the CameraWebServer example bundled with ESP32 Arduino core 3.3.12. In particular: PWDN 32, XCLK 0, SCCB SDA 26 and SCL 27.
- Camera configuration assignments match that example. The project additionally zero-initializes the configuration and checks for a null sensor pointer.
- Camera initialization runs before WiFiManager, WiFiMulti, saved-network loading, or Wi-Fi connection attempts. A camera initialization error returns from setup; the loop then waits without calling the application's restart paths.
- The three application restart paths occur after Wi-Fi setup exits without a connection, or after a running camera loses Wi-Fi for 60 seconds. These are not proof of the cause of any particular SW_RESET log.
- Up to five networks are retained. A new sixth entry drops the oldest configured entry. Updating an existing SSID replaces its password. A connected network is saved; failed portal passwords do not overwrite the custom list. Legacy ESP32 credentials are imported when the custom list is empty.
- The setup portal is destroyed before the camera HTTP server starts, avoiding simultaneous use of port 80.
- The sketch does not include secrets.h and does not disable brownout detection.

## Changes made during this review

- Added a firmware identifier, build timestamp, PSRAM availability, free heap and camera control-pin diagnostics before camera initialization. These messages do not require Core Debug Level Verbose and do not print network passwords.
- Camera initialization failures now include a newline, error name and explicit stop message. This distinguishes a camera failure from a Wi-Fi attempt and helps identify whether the new firmware actually reached setup.
- Disabled automatic Wi-Fi reconnect while WiFiMulti and WiFiManager control connection attempts; enabled it after setup succeeds.
- Disabled WiFiManager's own debug output; retained explicit setup instructions.
- Reset the saved-network count before loading, so repeated calls cannot accumulate entries past the array capacity.
- Changed startCameraServer to return a result. HTTP/stream startup failures now print their error, clean up partial server startup, and do not print Camera Ready.
- Added a message and delay before the previously silent no-connection restart.

## Limits of this review

- No source-level cause of the reported 0x106 sensor-detection failure has been established. The changes above are not a verified fix for that error.
- Brownout detector was triggered is evidence of a detected supply-voltage drop; source review does not identify which physical component or workload caused it. Brownout protection remains enabled.
- Failed to connect / No serial data received occurs in esptool's bootloader connection phase, before it writes the newly compiled application. Editing the sketch cannot establish this serial handshake. A failed upload also cannot confirm that the board is running the latest build.
- Actual sensor detection, power stability, two-network switching, persistence and camera endpoints still require hardware testing.
- The five-network store uses separate Preferences keys. It does not provide a transactional multi-key save across sudden power loss. Credentials are local flash data, not encrypted secrets in this prototype.
- The setup portal is intentionally unavailable if camera initialization fails; the explicit stop message now explains this behavior.

## Next upload

Compilation passed on 2026-10-26 with ESP32 Arduino core 3.3.12 and `esp32:esp32:esp32:PSRAM=enabled,PartitionScheme=huge_app,FlashMode=dio,FlashFreq=40,UploadSpeed=115200,DebugLevel=none`. Program storage: 1,288,905 bytes (40%); global variables: 72,312 bytes (22%). This review did not upload firmware or perform hardware tests.

Use the existing ESP32 Dev Module settings: PSRAM Enabled, Huge APP, DIO, 40 MHz, 4 MB and upload speed 115200. Do not erase all flash. Diagnostic startup messages are available with Core Debug Level None.

For uploading only, connect ESP32-CAM IO0 to GND and reset that board to enter download mode. Close Serial Monitor before uploading. After a successful upload, disconnect IO0 from GND and reset again for normal operation. IO0 is also the configured camera XCLK pin during normal operation, so it must not remain grounded then.

Record the complete startup log including the new [BOOT] marker and [CAMERA] messages. If the marker is absent, do not assume the new application reached setup.
