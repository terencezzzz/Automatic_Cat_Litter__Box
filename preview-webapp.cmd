@echo off
cd /d "%~dp0"
echo Starting PawLog UI preview at http://127.0.0.1:8080
echo Open this address in your browser. Keep this window open.
python -m src.webapp.preview
if errorlevel 1 pause
