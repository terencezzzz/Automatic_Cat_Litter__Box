@echo off
setlocal
cd /d "%~dp0"
set "camera_ip=pawlog-cam.local"
set /p "camera_ip=Camera address [Enter for pawlog-cam.local]: "
if not defined camera_ip exit /b 1
"..\..\.venv\Scripts\python.exe" monitor_camera.py "%camera_ip%"
pause
