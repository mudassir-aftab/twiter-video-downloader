@echo off
REM Twitter Video Downloader - Windows Startup Script

echo Twitter Video Downloader Starting...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
pip install -q -r requirements.txt

if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

REM Create necessary directories
if not exist downloads mkdir downloads
if not exist temp mkdir temp

REM Run the Flask application
echo.
echo Starting Flask server on http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

python app.py
pause
