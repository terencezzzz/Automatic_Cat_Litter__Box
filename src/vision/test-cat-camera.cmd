@echo off
setlocal
cd /d "%~dp0"
set /p "camera_ip=ESP32-CAM current IP (example 192.168.1.61): "
"..\..\.venv\Scripts\python.exe" detect_cat.py "http://%camera_ip%/capture"
pause
