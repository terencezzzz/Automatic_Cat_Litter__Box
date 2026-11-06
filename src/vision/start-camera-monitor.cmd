@echo off
setlocal
cd /d "%~dp0"
set "camera_ip="
set /p "camera_ip=ESP32-CAM current IP: "
if not defined camera_ip exit /b 1
"..\..\.venv\Scripts\python.exe" monitor_camera.py "%camera_ip%"
pause
