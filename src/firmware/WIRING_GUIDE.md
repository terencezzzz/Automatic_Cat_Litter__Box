# Prototype Wiring Guide

This wiring supports both `MotorTest.ino` and `SensorMotorTest.ino` on the Arduino Uno. Keep the motor power switch off while wiring or uploading a sketch.

## Current integration

For the camera and MotorTest setup, start camera monitoring from the repository root with `.\.venv\Scripts\python.exe -m src.webapp.preview --camera CAMERA_IP` (replace CAMERA_IP with the address after `Camera Ready!`). Use the Uno USB Serial Monitor at 9600 baud for supervised motor tests. The timed sketch does not have occupancy or position feedback.

## Arduino Uno and HC-SR04 (optional diagnostic)

| From | Connect to |
| --- | --- |
| HC-SR04 `VCC` | Uno `5V` |
| HC-SR04 `GND` | Uno `GND` |
| HC-SR04 `Trig` | Uno `D9` |
| HC-SR04 `Echo` | Uno `D10` |
| Uno USB port | Computer USB port |

Leave Uno pins `D0` and `D1` free for USB serial communication and uploads.

## IBT-2 (BTS7960) and DC motor

| From | Connect to |
| --- | --- |
| IBT-2 `VCC` | Uno `5V` |
| IBT-2 `GND` | Uno `GND` |
| IBT-2 `RPWM` | Uno `D5` |
| IBT-2 `LPWM` | Uno `D6` |
| IBT-2 `R_EN` and `L_EN` | Both to Uno `D7` |
| IBT-2 `R_IS` and `L_IS` | Leave disconnected |
| 10 kΩ pull-down resistor | One end to Uno `D7`, the other to Uno `GND` |
| Motor power supply positive | Through the motor power switch to IBT-2 `B+` |
| Motor power supply negative | IBT-2 `B−` |
| DC motor wires | IBT-2 `M+` and `M−`, one wire per terminal |

Choose the motor supply voltage according to the motor's rating. Keep the motor supply positive separate from the Uno and ESP32-CAM `5V` pins. The pull-down resistor holds the driver's enable inputs low while the Uno resets.

## ESP32-CAM

| From | Connect to |
| --- | --- |
| ESP32-CAM `5V` | Uno `5V` (prototype power) |
| ESP32-CAM `GND` | Uno `GND` |
| ESP32-CAM and computer | The same Wi-Fi network, with the camera reachable from the computer |

The Uno supplies power to the ESP32-CAM through the two wires above. The camera sends snapshots directly to the computer over Wi-Fi. Leave the camera TX and RX disconnected from the Uno. Use the camera's own programming interface to upload [CameraWebServer.ino](camera/CameraWebServer/CameraWebServer.ino).

The Uno 5 V connection is for the current prototype. If the camera shows brownout messages or restarts, move both camera power wires to a regulated 5 V supply with sufficient current. Keep the motor supply separate.

## Uploading and testing

1. Switch off the motor power supply. Leave the wiring in the tables connected.
2. In Arduino IDE, select **Arduino Uno** and the Uno's USB COM port.
3. Upload [MotorTest.ino](diagnostics/MotorTest/MotorTest.ino) to test the motor alone, or [SensorMotorTest.ino](diagnostics/SensorMotorTest/SensorMotorTest.ino) to test the sensor and motor together. Upload one sketch at a time.
4. Secure the motor and disengage it from the cleaning mechanism before powering it for a bench test.

`SensorMotorTest.ino` uses a manual serial command to simulate the computer's camera status. Automatic cleaning still requires camera status integration and testing on the assembled prototype.

## Timed tray cycle without limit switches

### Camera-triggered cycle

Upload the updated MotorTest sketch, close Arduino IDE Serial Monitor, and
start PawLog from the project root. Replace COM_PORT with the Uno USB port.
Check that the tray is level before starting and supervise the prototype.

```powershell
.\.venv\Scripts\python.exe -m src.webapp.preview --camera pawlog-cam.local --motor-test COM_PORT
```

A confirmed visit (six seconds of continuous cat detections) followed by
ten seconds without a cat detection and fresh confirming frames requests
one timed cycle. The waste result is saved separately. Camera loss during
movement expires the Uno watchdog, and a returning detection cancels the
cycle. After an interrupted cycle, inspect and level the tray, reset the Uno,
and restart PawLog. Camera-only clearance is an estimate based on visible
frames. Tray return is timed. Keep the motor cutoff within reach.

### Serial Monitor test

Upload diagnostics/MotorTest/MotorTest.ino to UNO and use Serial Monitor at 9600 baud. With the tray initially level, send r for a timed forward-pause-return cycle, or x to stop and cancel the remaining cycle. Repeated run requests while moving are ignored. After stopping, allow one second before a new command.

The current sketch uses PWM 255, forward 1000 ms, pause 1000 ms, and return 200 ms. Tune FORWARD_MS and RETURN_MS independently with the actual mechanism. Set FORWARD_USES_RPWM to false if the first movement is reversed. The driver is disabled during the pause, so verify the tray cannot fall or back-drive. Program timing cannot confirm an angle or home position. After an interrupted cycle or power loss, manually check tray position before starting again. Use supervised tests with no animals near the mechanism.
