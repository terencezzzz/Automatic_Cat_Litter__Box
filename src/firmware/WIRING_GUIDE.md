# Prototype Wiring Guide

This wiring supports both `MotorTest.ino` and `SensorMotorTest.ino` on the Arduino Uno. Keep the motor power switch off while wiring or uploading a sketch.

## Arduino Uno and HC-SR04

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
