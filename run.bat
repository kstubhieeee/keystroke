@echo off
cd /d "%~dp0"
python -c "import pynput" 2>nul || pip install -r requirements.txt
python visualizer.py
pause
