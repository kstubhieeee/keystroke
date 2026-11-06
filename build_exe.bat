@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onefile --name "KeystrokeVisualizer" visualizer.py
echo.
echo Built: dist\KeystrokeVisualizer.exe
pause
