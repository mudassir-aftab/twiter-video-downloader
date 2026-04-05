import os
import yt_dlp
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Form, Depends
from fastapi.responses import (
    JSONResponse,
    StreamingResponse,
    HTMLResponse,
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import re
from urllib.parse import urlparse, parse_qs
import time
from datetime import datetime, timedelta
import uuid
import asyncio
from typing import Dict, Optional, Any
import logging
from enum import Enum
import tempfile
import shutil
import threading
import glob
from concurrent.futures import ThreadPoolExecutor
import weakref
import psutil
import signal
import sys
from supabase import create_client, Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase client for admin
from config import settings
if settings.supabase_url and settings.supabase_anon_key:
    supabase: Client = create_client(settings.supabase_url, settings.supabase_anon_key)
else:
    supabase = None  # Admin features disabled if no Supabase config

# Task status enum
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


# ✅ ENHANCED TASK MANAGER FOR TWITTER/X VIDEOS
class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self.cleanup_interval = 7200  # 2 hours
        self._lock = threading.RLock()
        self.max_concurrent_downloads = 3  # Limit concurrent downloads
        self.active_downloads = 0
        self.cancel_requests = set()

    def create_task(self, task_id: str, url: str, format_id: str, quality: str) -> str:
        """Create a new download task"""
        with self._lock:
            self.tasks[task_id] = {
                "id": task_id,
                "url": url,
                "format_id": format_id,
                "quality": quality,
                "status": TaskStatus.PENDING,
                "progress": 0,
                "message": "Task created",
                "filename": None,
                "download_url": None,
                "error": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "download_speed": "0 B/s",
                "eta": "Unknown",
                "file_size": "Unknown",
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "retry_count": 0,
                "max_retries": 5,
            }
        return task_id

    def update_task(self, task_id: str, **kwargs):
        """Update task information"""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].update(kwargs)
                self.tasks[task_id]["updated_at"] = datetime.now()

    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get task information"""
        with self._lock:
            return self.tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        with self._lock:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]
            if task["status"] in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ]:
                return False

            self.cancel_requests.add(task_id)
            self.update_task(
                task_id,
                status=TaskStatus.CANCELLED,
                message="Download cancelled by user",
                progress=0,
            )
            return True

    def is_cancelled(self, task_id: str) -> bool:
        """Check if task is cancelled"""
        with self._lock:
            return task_id in self.cancel_requests

    def can_start_download(self) -> bool:
        """Check if we can start a new download"""
        with self._lock:
            return self.active_downloads < self.max_concurrent_downloads

    def increment_active_downloads(self):
        """Increment active download counter"""
        with self._lock:
            self.active_downloads += 1

    def decrement_active_downloads(self):
        """Decrement active download counter"""
        with self._lock:
            self.active_downloads = max(0, self.active_downloads - 1)

    def cleanup_old_tasks(self):
        """Remove old completed/failed tasks"""
        current_time = datetime.now()
        to_remove = []

        with self._lock:
            for task_id, task in self.tasks.items():
                time_diff = (current_time - task["updated_at"]).total_seconds()
                if time_diff > self.cleanup_interval and task["status"] in [
                    TaskStatus.COMPLETED,
                    TaskStatus.FAILED,
                ]:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self.tasks[task_id]
            logger.info(f"Cleaned up old task: {task_id}")


# Pydantic models
class URLRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: str
    quality: str


# Initialize FastAPI app
app = FastAPI(
    title="Twitter/X Video Downloader API - Advanced Version",
    description="High-performance async Twitter/X video downloader with advanced features",
    version="3.0.0",
)

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory="images"), name="images")

# Initialize task manager
task_manager = TaskManager()


class FileManager:
    def __init__(self):
        self._files = {}
        self._lock = threading.RLock()
        self.max_file_age = 3600  # 1 hour

    def register_file(self, task_id: str, file_path: str, temp_dir: str):
        """Register a file for tracking and cleanup"""
        with self._lock:
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            self._files[task_id] = {
                "file_path": file_path,
                "temp_dir": temp_dir,
                "filename": os.path.basename(file_path),
                "created_at": datetime.now(),
                "downloaded": False,
                "file_size": file_size,
                "access_count": 0,
            }

    def mark_downloaded(self, task_id: str):
        """Mark file as downloaded"""
        with self._lock:
            if task_id in self._files:
                self._files[task_id]["downloaded"] = True
                self._files[task_id]["access_count"] += 1

    def get_file_info(self, task_id: str):
        """Get file information"""
        with self._lock:
            return self._files.get(task_id)

    def cleanup_file(self, task_id: str):
        """Clean up a specific file"""
        with self._lock:
            if task_id in self._files:
                file_info = self._files[task_id]
                try:
                    if os.path.exists(file_info["temp_dir"]):
                        shutil.rmtree(file_info["temp_dir"])
                        logger.info(
                            f"Cleaned up temp directory: {file_info['temp_dir']}"
                        )
                except Exception as e:
                    logger.error(f"Error cleaning up {task_id}: {e}")
                finally:
                    del self._files[task_id]

    def cleanup_old_files(self):
        """Clean up old downloaded files"""
        current_time = datetime.now()
        to_cleanup = []

        with self._lock:
            for task_id, file_info in self._files.items():
                age = (current_time - file_info["created_at"]).total_seconds()
                if age > self.max_file_age or (file_info["downloaded"] and age > 600):
                    to_cleanup.append(task_id)

        for task_id in to_cleanup:
            self.cleanup_file(task_id)


# Initialize file manager
file_manager = FileManager()
executor = ThreadPoolExecutor(max_workers=5)


def sanitize_title(title):
    """Sanitize title for filename"""
    return re.sub(r'[\\/*?:"<>|]', "_", title)


# Create necessary directories
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)


class TwitterDownloader:
    def __init__(self):
        self.download_semaphore = asyncio.Semaphore(3)

    def is_valid_twitter_url(self, url):
        """Validate if the URL is a valid Twitter/X video URL"""
        twitter_patterns = [
            r"https?://(?:www\.)?twitter\.com/\w+/status/\d+",
            r"https?://(?:www\.)?x\.com/\w+/status/\d+",
            r"https?://twitter\.com/\w+/status/\d+/video/\d+",
            r"https?://x\.com/\w+/status/\d+/video/\d+",
            r"https?://(?:mobile\.)?twitter\.com/\w+/status/\d+",
            r"https?://(?:mobile\.)?x\.com/\w+/status/\d+",
        ]

        for pattern in twitter_patterns:
            if re.match(pattern, url):
                return True
        return False

    def extract_status_id(self, url):
        """Extract status ID from Twitter/X URL"""
        patterns = [
            r"(?:twitter|x)\.com/\w+/status/(\d+)",
            r"(?:twitter|x)\.com/\w+/status/(\d+)/video/\d+",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_unique_filename(self, base_path, title, ext):
        """Generate unique filename to avoid conflicts"""
        safe_title = sanitize_title(title)
        base_filename = f"{safe_title}.{ext}"
        full_path = os.path.join(base_path, base_filename)

        if not os.path.exists(full_path):
            return base_filename

        counter = 1
        while True:
            new_filename = f"{safe_title}_{counter}.{ext}"
            new_full_path = os.path.join(base_path, new_filename)
            if not os.path.exists(new_full_path):
                return new_filename
            counter += 1

    async def extract_video_info(self, url):
        """Extract video information using yt-dlp"""
        try:
            # Normalize URL
            status_id = self.extract_status_id(url)
            if status_id:
                clean_url = f"https://twitter.com/i/web/status/{status_id}"
            else:
                clean_url = url

            # ✅ OPTIMIZED YT-DLP OPTIONS FOR TWITTER/X VIDEOS
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "format": "best",
                "socket_timeout": 60,
                "retries": 10,
                "fragment_retries": 10,
                "skip_unavailable_fragments": True,
                "keep_fragments": False,
                "http_chunk_size": 10485760,  # 10MB chunks
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            logger.info(f"Extracting info for: {clean_url}")

            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, self._extract_info_sync, clean_url, ydl_opts
            )

            logger.info(f"Video title: {info.get('title', 'Unknown')}")
            logger.info(f"Duration: {info.get('duration', 0)} seconds")
            logger.info(f"Available formats: {len(info.get('formats', []))}")

            duration = info.get("duration", 0)

            video_info = {
                "title": info.get("title", "Twitter Video"),
                "duration": duration,
                "duration_string": self._format_duration(duration),
                "thumbnail": info.get("thumbnail", ""),
                "uploader": info.get("uploader", "Twitter User"),
                "upload_date": info.get("upload_date", ""),
                "description": (
                    info.get("description", "")[:200] + "..."
                    if info.get("description")
                    else ""
                ),
                "formats": [],
            }

            available_formats = info.get("formats", [])
            has_1080p = any(
                f.get("height", 0) >= 1080
                for f in available_formats
                if f.get("vcodec") != "none"
            )
            has_720p = any(
                f.get("height", 0) >= 720
                for f in available_formats
                if f.get("vcodec") != "none"
            )
            has_480p = any(
                f.get("height", 0) >= 480
                for f in available_formats
                if f.get("vcodec") != "none"
            )

            logger.info(
                f"Available qualities - 1080p: {has_1080p}, 720p: {has_720p}, 480p: {has_480p}"
            )

            video_formats = []
            audio_formats = []

            # Video formats
            if has_1080p:
                video_formats.append(
                    {
                        "format_id": "best[height>=1080]",
                        "quality": "4K Ultra HD (1080p) - Best Quality",
                        "height": 1080,
                        "width": 1920,
                        "ext": "mp4",
                        "filesize": 0,
                        "fps": 30,
                        "has_audio": True,
                        "vcodec": "h264",
                        "acodec": "aac",
                        "recommended": True,
                        "estimated_size": self._estimate_file_size(duration, 1080),
                        "type": "video",
                    }
                )

            if has_720p:
                video_formats.append(
                    {
                        "format_id": "best[height>=720]",
                        "quality": "Full HD (720p) - High Quality ✅ Recommended",
                        "height": 720,
                        "width": 1280,
                        "ext": "mp4",
                        "filesize": 0,
                        "fps": 30,
                        "has_audio": True,
                        "vcodec": "h264",
                        "acodec": "aac",
                        "recommended": not has_1080p,
                        "estimated_size": self._estimate_file_size(duration, 720),
                        "type": "video",
                    }
                )

            if has_480p:
                video_formats.append(
                    {
                        "format_id": "best[height>=480]",
                        "quality": "HD (480p) - Good Quality ⚡ Fast Download",
                        "height": 480,
                        "width": 854,
                        "ext": "mp4",
                        "filesize": 0,
                        "fps": 30,
                        "has_audio": True,
                        "vcodec": "h264",
                        "acodec": "aac",
                        "recommended": False,
                        "estimated_size": self._estimate_file_size(duration, 480),
                        "type": "video",
                    }
                )

            # Audio only format
            audio_formats.append(
                {
                    "format_id": "bestaudio",
                    "quality": "🎵 Audio Only (320kbps MP3)",
                    "height": 0,
                    "width": 0,
                    "ext": "mp3",
                    "filesize": 0,
                    "fps": 0,
                    "has_audio": True,
                    "vcodec": "none",
                    "acodec": "mp3",
                    "estimated_size": self._estimate_audio_size(duration),
                    "type": "audio",
                }
            )

            video_info["video_formats"] = video_formats
            video_info["audio_formats"] = audio_formats
            logger.info(
                f"Processed {len(video_formats)} video formats and {len(audio_formats)} audio formats"
            )

            return video_info

        except Exception as e:
            logger.error(f"Error extracting video info: {str(e)}")
            error_msg = str(e)
            if "Sign in" in error_msg or "private" in error_msg.lower():
                raise Exception("This video is private or requires authentication.")
            elif "unavailable" in error_msg.lower():
                raise Exception("This video is unavailable or has been deleted.")
            else:
                raise Exception(f"Failed to extract video info: {error_msg}")

    def _format_duration(self, seconds):
        """Format duration in human readable format"""
        if not seconds:
            return "Unknown"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def _estimate_file_size(self, duration, height):
        """Estimate file size based on duration and quality"""
        if not duration:
            return "Unknown"

        bitrates = {
            1080: 8,  # 8 MB per minute
            720: 5,  # 5 MB per minute
            480: 3,  # 3 MB per minute
        }

        bitrate = bitrates.get(height, 5)
        size_mb = (duration / 60) * bitrate

        if size_mb > 1024:
            return f"~{size_mb/1024:.1f} GB"
        else:
            return f"~{size_mb:.0f} MB"

    def _estimate_audio_size(self, duration):
        """Estimate audio file size"""
        if not duration:
            return "Unknown"

        size_mb = (duration / 60) * 2.4

        if size_mb > 1024:
            return f"~{size_mb/1024:.1f} GB"
        else:
            return f"~{size_mb:.0f} MB"

    def _extract_info_sync(self, url, ydl_opts):
        """Synchronous info extraction for thread pool"""
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    async def download_video_async(
        self, task_id: str, url: str, format_id: str, quality: str
    ):
        """Download video asynchronously"""
        async with self.download_semaphore:
            try:
                if task_manager.is_cancelled(task_id):
                    return

                while not task_manager.can_start_download():
                    if task_manager.is_cancelled(task_id):
                        return

                    task_manager.update_task(
                        task_id,
                        status=TaskStatus.PENDING,
                        message="Waiting for download slot...",
                    )
                    await asyncio.sleep(5)

                task_manager.increment_active_downloads()

                if task_manager.is_cancelled(task_id):
                    task_manager.decrement_active_downloads()
                    return

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=5,
                    message="Starting download...",
                )

                status_id = self.extract_status_id(url)
                if status_id:
                    clean_url = f"https://twitter.com/i/web/status/{status_id}"
                else:
                    clean_url = url

                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, self._download_sync, task_id, clean_url, format_id, quality
                )

            except Exception as e:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    error=str(e),
                    message=f"Download failed: {str(e)}",
                )
                logger.error(f"Download failed for {task_id}: {str(e)}")
            finally:
                task_manager.decrement_active_downloads()

    def _download_sync(self, task_id: str, url: str, format_id: str, quality: str):
        """Synchronous download for thread pool"""
        temp_dir = tempfile.mkdtemp()
        try:

            def progress_hook(d):
                if task_manager.is_cancelled(task_id):
                    raise Exception("Download cancelled")

                if d["status"] == "downloading":
                    progress = d.get("_percent_str", "0%").replace("%", "")
                    try:
                        progress_val = float(progress)
                    except:
                        progress_val = 0

                    task_manager.update_task(
                        task_id,
                        progress=int(progress_val),
                        message=f"Downloading... {progress}%",
                        download_speed=d.get("_speed_str", "Unknown"),
                        eta=d.get("_eta_str", "Unknown"),
                        downloaded_bytes=d.get("downloaded_bytes", 0),
                        total_bytes=d.get("total_bytes", 0),
                    )
                elif d["status"] == "finished":
                    task_manager.update_task(
                        task_id, progress=95, message="Download finished, processing..."
                    )

            ydl_opts = {
                "format": format_id,
                "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
                "quiet": False,
                "no_warnings": False,
                "progress_hooks": [progress_hook],
                "socket_timeout": 60,
                "retries": 10,
                "fragment_retries": 10,
                "skip_unavailable_fragments": True,
                "http_chunk_size": 10485760,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "postprocessors": (
                    [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]
                    if format_id != "bestaudio"
                    else []
                ),
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                filename = ydl.prepare_filename(info)

                file_manager.register_file(task_id, filename, temp_dir)

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    message="Download completed!",
                    filename=os.path.basename(filename),
                    download_url=f"/api/v1/download/{task_id}",
                )

                logger.info(f"Download completed for {task_id}: {filename}")

        except Exception as e:
            logger.error(f"Error downloading {task_id}: {str(e)}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# API Endpoints
@app.post("/api/v1/info")
async def get_video_info(request: URLRequest):
    """Extract video information from Twitter/X URL"""
    downloader = TwitterDownloader()

    try:
        if not downloader.is_valid_twitter_url(request.url):
            raise HTTPException(status_code=400, detail="Invalid Twitter/X URL")

        video_info = await downloader.extract_video_info(request.url)
        return JSONResponse({"success": True, "data": video_info})

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@app.post("/api/v1/download")
async def download_video(request: DownloadRequest, background_tasks: BackgroundTasks):
    """Start a video download"""
    downloader = TwitterDownloader()

    try:
        if not downloader.is_valid_twitter_url(request.url):
            raise HTTPException(status_code=400, detail="Invalid Twitter/X URL")

        task_id = str(uuid.uuid4())
        task_manager.create_task(
            task_id, request.url, request.format_id, request.quality
        )

        background_tasks.add_task(
            downloader.download_video_async,
            task_id,
            request.url,
            request.format_id,
            request.quality,
        )

        return JSONResponse({"success": True, "task_id": task_id})

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@app.get("/api/v1/status/{task_id}")
async def get_task_status(task_id: str):
    """Get download task status"""
    task = task_manager.get_task(task_id)

    if not task:
        return JSONResponse(
            {"success": False, "error": "Task not found"}, status_code=404
        )

    return JSONResponse(
        {
            "success": True,
            "data": {
                "id": task["id"],
                "status": task["status"],
                "progress": task["progress"],
                "message": task["message"],
                "filename": task["filename"],
                "download_url": task["download_url"],
                "error": task["error"],
                "download_speed": task["download_speed"],
                "eta": task["eta"],
                "created_at": task["created_at"].isoformat(),
                "updated_at": task["updated_at"].isoformat(),
            },
        }
    )


@app.post("/api/v1/cancel/{task_id}")
async def cancel_download(task_id: str):
    """Cancel a download task"""
    success = task_manager.cancel_task(task_id)

    if not success:
        return JSONResponse(
            {"success": False, "error": "Cannot cancel this task"}, status_code=400
        )

    return JSONResponse({"success": True, "message": "Task cancelled"})


@app.get("/api/v1/download/{task_id}")
async def download_file(task_id: str):
    """Download completed file"""
    task = task_manager.get_task(task_id)

    if not task:
        return JSONResponse(
            {"success": False, "error": "Task not found"}, status_code=404
        )

    if task["status"] != TaskStatus.COMPLETED:
        return JSONResponse(
            {"success": False, "error": "Download not completed"}, status_code=400
        )

    file_info = file_manager.get_file_info(task_id)

    if not file_info or not os.path.exists(file_info["file_path"]):
        return JSONResponse(
            {"success": False, "error": "File not found"}, status_code=404
        )

    file_manager.mark_downloaded(task_id)

    return FileResponse(
        file_info["file_path"],
        filename=file_info["filename"],
        media_type="application/octet-stream",
    )


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(
        {
            "success": True,
            "status": "healthy",
            "active_downloads": task_manager.active_downloads,
            "total_tasks": len(task_manager.tasks),
        }
    )


# Admin Authentication Dependency
def get_current_admin(request: Request):
    """Check if user is authenticated as admin"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Admin features not configured")
        
    session_token = request.cookies.get("admin_session")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Verify session with Supabase
    try:
        # For simplicity, assume session_token is JWT, but in real app verify it
        # Here, just check if user exists in admin table
        response = supabase.table("admin_users").select("*").eq("session_token", session_token).execute()
        if not response.data:
            raise HTTPException(status_code=401, detail="Invalid session")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication failed")


# Admin Routes
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page"""
    return templates.TemplateResponse("admin_login.html", {"request": request})


@app.post("/admin/login")
async def admin_login(email: str = Form(...), password: str = Form(...)):
    """Admin login authentication"""
    if not supabase:
        raise HTTPException(status_code=503, detail="Admin features not configured")
        
    try:
        # Authenticate with Supabase
        auth_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = auth_response.user
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Check if user is admin
        admin_check = supabase.table("admin_users").select("*").eq("user_id", user.id).execute()
        if not admin_check.data:
            raise HTTPException(status_code=403, detail="Not authorized as admin")
        
        # Create session token (simplified)
        session_token = str(uuid.uuid4())
        
        # Store session in Supabase
        supabase.table("admin_sessions").insert({
            "user_id": user.id,
            "session_token": session_token,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        response = JSONResponse(content={"message": "Login successful"})
        response.set_cookie(key="admin_session", value=session_token, httponly=True)
        return response
    
    except Exception as e:
        raise HTTPException(status_code=401, detail="Login failed")


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: dict = Depends(get_current_admin)):
    """Admin dashboard"""
    # Get stats from Supabase or Redis
    try:
        # For now, get from task_manager, later can store in Supabase
        total_tasks = len(task_manager.tasks)
        active_tasks = len([t for t in task_manager.tasks.values() if t["status"] == "processing"])
        completed_tasks = len([t for t in task_manager.tasks.values() if t["status"] == "completed"])
        failed_tasks = len([t for t in task_manager.tasks.values() if t["status"] == "failed"])
        
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "admin": admin,
            "stats": {
                "total_tasks": total_tasks,
                "active_tasks": active_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks
            }
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail="Dashboard error")


@app.get("/admin/tasks", response_class=HTMLResponse)
async def admin_tasks(request: Request, admin: dict = Depends(get_current_admin)):
    """Admin tasks management"""
    tasks = list(task_manager.tasks.values())
    return templates.TemplateResponse("admin_tasks.html", {
        "request": request,
        "admin": admin,
        "tasks": tasks
    })


@app.post("/admin/logout")
async def admin_logout(request: Request):
    """Admin logout"""
    session_token = request.cookies.get("admin_session")
    if session_token:
        # Remove session from Supabase
        supabase.table("admin_sessions").delete().eq("session_token", session_token).execute()
    
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("admin_session")
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
