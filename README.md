# Keystroke Visualizer (Windows)

Desktop app that shows pressed keys as Magic Keyboard–style keycaps at the bottom center of the screen, over any app.

Visible display only — keystrokes are not logged or saved.

## Requirements

- Windows 10/11
- Python 3.10+

## Setup

```bash
pip install -r requirements.txt
```

## Run (Python)

```bash
python visualizer.py
```

Or double-click `run.bat`.

## Windows exe

A built executable is at:

`dist\KeystrokeVisualizer.exe`

Double-click it to launch (no Python needed on that machine). To rebuild:

```bash
build_exe.bat
```

## Features

- **Light / Dark** key style (and matching control window)
- Toggle overlay on/off from the app
- Theme preference saved in `settings.json`
- Click-through overlay; quit with **Ctrl+Alt+Q** or by closing the app window

## Notes

- If keys from an elevated (Run as administrator) app do not appear, run this app as administrator too.
