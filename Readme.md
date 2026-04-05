# Twitter Video Downloader

A production-ready, scalable Twitter/X video downloader application built with Flask and modern frontend technologies.

## Features

✅ **Download Twitter Videos** - Download any public Twitter/X video  
✅ **Multiple Quality Options** - Choose from 1080p, 720p, 480p, or audio-only (MP3)  
✅ **Real-time Progress Tracking** - See download progress in real-time  
✅ **Extract Metadata** - Get video info before downloading  
✅ **Concurrent Downloads** - Download multiple videos simultaneously  
✅ **Scalable Architecture** - Thread-safe, production-ready backend  
✅ **Beautiful UI** - Modern, responsive frontend  
✅ **Error Handling** - Comprehensive error handling with user-friendly messages  

## Project Structure

```
├── app.py                      # Flask server application
├── scripts/
│   └── twitter_downloader.py   # Core downloader logic
├── template/
│   └── index.html              # Frontend HTML
├── static/
│   ├── style.css               # Styling
│   └── script.js               # Frontend JavaScript
├── requirements.txt            # Python dependencies
├── run.sh                       # Linux/Mac startup script
├── run.bat                      # Windows startup script
└── README.md                    # This file
```

## Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)
- Git

### Setup Instructions

#### Linux / macOS

1. Clone or extract the project
   ```bash
   cd twitter-video-downloader
   ```

2. Make the startup script executable
   ```bash
   chmod +x run.sh
   ```

3. Run the application
   ```bash
   ./run.sh
   ```

#### Windows

1. Extract the project directory
2. Double-click `run.bat` or run from Command Prompt:
   ```cmd
   run.bat
   ```

#### Manual Installation (All Platforms)

1. Navigate to the project directory
   ```bash
   cd twitter-video-downloader
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Create necessary directories
   ```bash
   mkdir downloads
   mkdir temp
   ```

4. Run the Flask server
   ```bash
   python app.py
   ```

## Usage

Once the server starts, open your browser and go to:

```
http://localhost:8000
```

### How to Use

1. **Enter URL** - Paste a Twitter video URL in the input field
2. **Extract Info** - Click "Get Video Info" to see video metadata
3. **Select Quality** - Choose your preferred video quality
4. **Download** - Click the download button to start
5. **Track Progress** - Watch real-time progress updates
6. **Download File** - Your video will automatically download when complete

## API Endpoints

### Extract Video Information
```
POST /api/v1/info
{
    "url": "https://twitter.com/user/status/1234567890"
}
```

### Start Download
```
POST /api/v1/download
{
    "url": "https://twitter.com/user/status/1234567890",
    "quality": "best"
}
```

### Check Download Status
```
GET /api/v1/status/{task_id}
```

### Download Completed File
```
GET /api/v1/download/{task_id}
```

### Cancel Download
```
POST /api/v1/cancel/{task_id}
```

### Health Check
```
GET /api/v1/health
```

### List All Tasks
```
GET /api/v1/tasks
```

## Configuration

The application stores downloads in the `downloads/` directory and temporary files in the `temp/` directory. These are created automatically on first run.

### Adjustable Settings (in scripts/twitter_downloader.py)

- `MAX_CONCURRENT_DOWNLOADS` - Maximum simultaneous downloads (default: 3)
- `DOWNLOAD_TIMEOUT` - Download timeout in seconds (default: 300)
- `MAX_RETRIES` - Maximum retry attempts (default: 5)
- `TASK_RETENTION_TIME` - How long to keep completed tasks (default: 2 hours)

## Supported URL Formats

- `https://twitter.com/username/status/1234567890`
- `https://x.com/username/status/1234567890`
- `https://twitter.com/username/status/1234567890/video/1`
- Short URLs and direct links also supported

## Troubleshooting

### Port 8000 Already in Use
If port 8000 is already in use, you can modify the port in `app.py`:
```python
app.run(port=8001)  # Change to any available port
```

### Dependencies Installation Failed
Try installing with a specific Python version:
```bash
python3.9 -m pip install -r requirements.txt
```

### Video Download Fails
- Verify the Twitter URL is correct and public
- Check your internet connection
- Try a different video
- The video might be private, deleted, or from a protected account

### No Downloads Folder Showing
The downloads folder is in the same directory as the app. Navigate there to find your videos:
- Linux/Mac: `./downloads/`
- Windows: `downloads\`

## Performance

- **Concurrent Downloads** - Up to 3 simultaneous downloads
- **Memory Usage** - Efficient streaming downloads
- **Processing Speed** - Depends on video length and your connection
- **Storage** - Downloaded videos stored in `downloads/` folder

## Security

- Input validation on all URLs
- Filename sanitization to prevent path traversal
- Thread-safe operations
- No sensitive data stored
- CORS enabled for development

## License

This project is provided as-is for educational and personal use.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Verify all dependencies are installed correctly
3. Ensure Python 3.8+ is installed
4. Check that port 8000 is available

## Version

Twitter Video Downloader v1.0.0 - Production Ready

---

**Enjoy downloading your favorite Twitter videos!**
