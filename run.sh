#!/bin/bash

# Twitter Video Downloader - Startup Script

echo "Twitter Video Downloader Starting..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip3 install -q -r requirements.txt

if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies"
    exit 1
fi

# Create necessary directories
mkdir -p downloads
mkdir -p temp

# Run the Flask application
echo "Starting Flask server on http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo ""

python3 app.py
