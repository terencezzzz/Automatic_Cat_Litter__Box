# Wi-Fi Setup Using a Phone

## Current Startup Sequence: WiFi-first v3

The current main sketch keeps the camera in power-down standby and the flash off while starting Wi-Fi. It connects to a saved network or opens Camera-Setup first, then initializes the camera and starts the camera webpage. This separates Wi-Fi startup from an already running camera. It does not disable brownout protection and is not a verified fix for an electrical fault.

Upload `CameraWebServer.ino` normally; no separate diagnostic sketch is needed. Serial Monitor at 115200 should show `[BOOT] CameraWebServer WiFi-first v3`, then `WiFi connected`, camera initialization, and finally `Camera Ready!`. If camera initialization fails, Wi-Fi may remain connected but the camera webpage is unavailable. Previously saved networks and the setup-page privacy changes are retained. Keep Erase All Flash disabled.

WiFi-first v3 compiled successfully on 2026-10-26 with ESP32 Arduino core 3.3.12 and the ESP32 Dev Module settings used below: program storage 1,289,109 bytes (40%), global variables 72,312 bytes (22%). A source-order check confirmed standby -> Wi-Fi setup/connection -> camera initialization -> HTTP server. This revision has not yet been uploaded or verified on the physical board.

## First-Time Setup

1. Open `CameraWebServer.ino` from this folder in Arduino IDE. Keep the entire project folder together.
2. Use the same AI Thinker ESP32-CAM board selection and upload wiring as before, then upload the program once.
3. After uploading, disconnect IO0 from GND and press RST to start the camera normally.
4. The camera scans for saved Wi-Fi networks and attempts to connect. If none connects, the `Camera-Setup` hotspot appears on your phone. Allow scan time plus up to 20 seconds per connection attempt; several saved networks can take longer.
5. Connect your phone to this hotspot using the password `camera123`. If your phone reports that the network has no internet access, choose to stay connected.
6. Open `http://192.168.4.1` in your browser and tap **Configure WiFi**.
7. Select your **2.4 GHz Wi-Fi** network, enter its password, and tap **Save**.
8. Once connected successfully, the setup hotspot turns off. Reconnect your phone and computer to the same local network as the camera.
9. Set Arduino Serial Monitor to **115200 baud**. Find the camera address after `Camera Ready!` and open it in your browser to test the camera feed.

If you enter the wrong password, reconnect to the setup hotspot and enter the details again. The setup page waits for your input without a timeout.

## Moving to Another Location

The camera remembers up to **five Wi-Fi networks**, even after power loss. Power it on at your destination and it scans for saved networks, preferring stronger signals. If a candidate fails, it tries other saved candidates before opening the setup hotspot. If no saved network connects, repeat steps 5-9 above to add a new network. No further upload is required.

Example: configure your home Wi-Fi once, then configure your school Wi-Fi once at school. After that, returning home or to school only requires powering on the camera; you do not need to enter those passwords again. The last network saved by the previous single-network firmware is imported automatically on first startup, provided the ESP32 flash has not been erased. Networks overwritten before this upgrade must be configured once again.

Configuring an existing network name updates its password without adding a duplicate. Adding a sixth network replaces the oldest configured entry. Networks must have different names to retain separate passwords; this version stores one password per network name.

If Wi-Fi disconnects during operation, the camera first attempts automatic reconnection for 60 seconds. If the connection is still unavailable, it restarts and scans the saved networks again. It opens Wi-Fi setup only if none connects. This prevents the setup page and camera server from competing for port 80.

The camera IP address may change when switching networks. Update the detection program on your computer or Raspberry Pi to use the new IP address with `/capture`. The setup address `192.168.4.1` is not the camera address after it connects to your Wi-Fi network. Campus or public networks that require a browser login are outside this setup flow; use a 2.4 GHz phone hotspot for testing instead.

`secrets.h` is no longer used. You do not need to edit your home or school Wi-Fi credentials there.

## Setup Page Privacy

The setup homepage and connection-status messages do not display the previously saved network name. The SSID and password fields start blank, and the Info page hides the saved SSID. Select a nearby network or type its name before saving; submitting an empty SSID does not reuse the previous network. Nearby networks still appear in the live scan list for selection, including a previously used network if it is currently broadcasting nearby. This display change does not erase the five saved networks or affect automatic connection.

These changes are maintained in the bundled WiFiManager sources. Replacing that folder with an unmodified upstream library would remove the customizations.

The privacy revision compiled successfully on 2026-10-26 with the ESP32 Dev Module settings listed below: program storage 1,288,733 bytes (40%), global variables 72,312 bytes (22%). Source/template checks confirmed blank credential placeholders, generic status text and removal of the empty-SSID fallback. Actual phone display still requires uploading this revision and reopening the portal.

## Dependencies and Verification

WiFiManager **2.0.17** is bundled in `src/WiFiManager`. Arduino compiles it automatically, so no separate library installation is needed. Source: [WiFiManager v2.0.17](https://github.com/tzapu/WiFiManager/tree/v2.0.17). The original MIT LICENSE is retained.

The setup hotspot password is defined by `SETUP_AP_PASSWORD` in the main sketch. The current password, `camera123`, is intended for prototype testing.

Hardware checks:

1. Configure network A and power-cycle the camera; confirm automatic reconnection.
2. Turn off A and configure network B through `Camera-Setup`.
3. Turn off B, restore A, and restart; confirm connection without setup.
4. Turn off A, restore B, and restart; confirm connection without setup.
5. Turn off both; confirm that `Camera-Setup` becomes available.
6. Update a saved network's password through setup, restart, and confirm reconnection.
7. After a successful connection, check both the camera webpage and `/capture`.

The previous single-network firmware compiled on 2026-10-24 and was subsequently uploaded successfully. The multi-network update requires a new upload and the hardware checks above.

Multi-network compilation passed on 2026-10-26 using ESP32 Arduino core 3.3.12 and board `esp32:esp32:esp32cam`: program storage 1,286,745 bytes (40%), global variables 72,312 bytes (22%). Automatic switching and persistence still require the hardware checks above.

After the startup review on 2026-10-26, the diagnostic revision also compiled with the ESP32 Dev Module settings shown in `CODE_REVIEW.md`: program storage 1,288,905 bytes (40%), global variables 72,312 bytes (22%). Startup now prints `[BOOT] CameraWebServer multi-WiFi diagnostics v2` and `[CAMERA]` status messages with Core Debug Level None. Server startup errors no longer print Camera Ready. These changes do not establish or fix the cause of a sensor-detection error or brownout; see `CODE_REVIEW.md` for findings and limitations.
