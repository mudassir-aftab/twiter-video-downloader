"""Refactored FastAPI server with Redis caching and RabbitMQ task distribution"""
import os
import yt_dlp
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Form, Query, Depends
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import re
from urllib.parse import urlparse, parse_qs
import time
from datetime import datetime, timedelta
import uuid
import asyncio
import logging
from pathlib import Path
import tempfile
import shutil
import weakref
from worker import run_worker
import asyncio
from supabase import create_client, Client

from config import settings
from models import (
    DownloadRequest, DownloadResponse, TaskStatusResponse, 
    VideoInfoResponse, DownloadTask, TaskStatus, Proxy
)
from redis_client import redis_client
from rabbitmq_client import rabbitmq_publisher
from database import get_supabase, get_all_proxies, add_proxy, delete_proxy, update_proxy_status, get_system_settings, is_blocked
from cron_jobs import start_cron_jobs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_filesize(size_bytes):
    """Format bytes to human-readable size"""
    if size_bytes == 0:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def format_duration(seconds):
    """Format seconds to HH:MM:SS"""
    if not seconds:
        return "Unknown"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

# Initialize FastAPI app
app = FastAPI(
    title="Twitter/X Video Downloader API",
    description="Download videos from Twitter/X with Redis caching and RabbitMQ scaling",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup static files and templates
base_dir = Path(__file__).parent
static_dir = base_dir / "static"
templates_dir = base_dir / "templates"

# Create directories if they don't exist
static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(templates_dir))

# Supabase client for admin (optional)
supabase: Client | None = None
if settings.supabase_url and settings.supabase_anon_key:
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)

# Default admin credentials (for development)
DEFAULT_ADMIN = {
    "email": "admin@local.com",
    "password": "admin123"
}


# ============================================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================================
async def init_services():
    # Redis
    if not redis_client.health_check():
        raise Exception("Redis connection failed")

    # RabbitMQ
    await rabbitmq_publisher.initialize()

def init_directories():
    base = Path(__file__).parent
    (base / "downloads").mkdir(exist_ok=True)
    (base / "temp").mkdir(exist_ok=True)
def init_background_jobs():
    # Worker (IMPORTANT - uncomment this)
    asyncio.create_task(run_worker())

    # Cron jobs
    start_cron_jobs(app)

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting FastAPI system...")

    try:
        await init_services()  
        init_directories()
        init_background_jobs()

        logger.info("✅ System fully started")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise





@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down FastAPI server...")
    try:
        await rabbitmq_publisher.close()
        logger.info("✅ Connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def extract_video_id(url: str) -> str:
    """Extract video ID from Twitter/X URL"""
    match = re.search(r'/status/(\d+)', url)
    return match.group(1) if match else url


def validate_twitter_url(url: str) -> bool:
    """Validate Twitter/X URL format"""
    patterns = [
        r'https?://(www\.)?twitter\.com/\w+/status/\d+',
        r'https?://(www\.)?x\.com/\w+/status/\d+',
        r'https?://twitter\.com/i/web/status/\d+',
        r'https?://x\.com/i/web/status/\d+'
    ]
    return any(re.match(pattern, url) for pattern in patterns)


# ============================================================================
# HOME PAGE ENDPOINT
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    """Serve the main HTML frontend"""
    html_file = templates_dir / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")  # <<< encoding specified
    return HTMLResponse(content="<h1>404 - Frontend not found</h1>", status_code=404)
# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Check service health"""
    redis_healthy = redis_client.health_check()
    rabbitmq_healthy = await rabbitmq_publisher.client.health_check()
    
    return {
        "status": "healthy" if redis_healthy and rabbitmq_healthy else "unhealthy",
        "redis": "connected" if redis_healthy else "disconnected",
        "rabbitmq": "connected" if rabbitmq_healthy else "disconnected",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# VIDEO INFO ENDPOINT (with Redis caching)
# ============================================================================

@app.post("/api/v1/info")
async def get_video_info(url: str = Query(...)):
    """
    Get video information from Twitter/X URL (with Redis caching)
    
    Args:
        url: Twitter/X video URL
    
    Returns:
        Video metadata with formats
    """
    try:
        # Validate URL
        if not validate_twitter_url(url):
            raise HTTPException(status_code=400, detail="Invalid Twitter/X URL")
        
        video_id = extract_video_id(url)
        
        # Check Redis cache first
        cached_info = redis_client.get_cached_video_info(video_id)
        if cached_info:
            logger.info(f"✅ Video info retrieved from cache: {video_id}")
            return cached_info
        
        logger.info(f"🔄 Fetching video info from Twitter/X: {video_id}")
        
        # Fetch from Twitter/X
        ydl_opts = {
            'quiet': False,
            'no_warnings': False,
            'socket_timeout': 30,
            'retries': 3
        }
        
        video_info = {}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Separate formats into video and audio
            all_formats = info.get('formats', [])
            video_formats = []
            audio_formats = []
            
            for f in all_formats:
                format_obj = {
                    "format_id": f.get('format_id', ''),
                    "ext": f.get('ext', ''),
                    "quality": f.get('format', 'unknown'),
                    "filesize": f.get('filesize', 0),
                    "estimated_size": format_filesize(f.get('filesize', 0)),
                    "vcodec": f.get('vcodec', 'none'),
                    "acodec": f.get('acodec', 'none'),
                    "height": f.get('height', 0),
                    "fps": f.get('fps', 0),
                    "type": "video" if f.get('vcodec') != 'none' else "audio",
                    "recommended": False
                }
                
                if f.get('vcodec') != 'none':
                    video_formats.append(format_obj)
                elif f.get('acodec') != 'none':
                    audio_formats.append(format_obj)
            
            # Mark best quality as recommended
            if video_formats:
                video_formats[0]['recommended'] = True
            if audio_formats:
                audio_formats[0]['recommended'] = True
            
            video_info = {
                "video_id": video_id,
                "title": info.get('title', ''),
                "duration": info.get('duration', 0),
                "duration_string": format_duration(info.get('duration', 0)),
                "uploader": info.get('uploader', ''),
                "description": info.get('description', '')[:500],
                "upload_date": info.get('upload_date', ''),
                "thumbnail": info.get('thumbnail', ''),
                "video_formats": video_formats[:10],
                "audio_formats": audio_formats[:10],
                "cached_at": datetime.now().isoformat()
            }
        
        # Cache the result
        redis_client.cache_video_info(video_id, video_info)
        logger.info(f"✅ Video info cached: {video_id}")
        
        return video_info
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching video info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DOWNLOAD ENDPOINT (publishes to RabbitMQ)
# ============================================================================

@app.post("/api/v1/download", response_model=DownloadResponse)
async def download_video(request: DownloadRequest, http_req: Request):
    """
    Initiate video download (publishes task to RabbitMQ)
    
    Args:
        request: DownloadRequest with URL and format options
        http_req: FastAPI internal request to extract IP
    
    Returns:
        Task ID and status
    """
    try:
        user_ip = http_req.client.host
        # Check security blocks
        if is_blocked("ip", user_ip):
            raise HTTPException(status_code=403, detail="Your IP is blocked.")
        
        # Validate URL
        if not validate_twitter_url(request.url):
            raise HTTPException(status_code=400, detail="Invalid Twitter/X URL")
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        logger.info(f"📝 Creating download task {task_id}")
        
        # Create initial task state in Redis
        task_state = {
            'task_id': task_id,   
            'url': request.url,
            'format_id': request.format_id,
            'quality': request.quality,
            'status': TaskStatus.PENDING,
            'progress': 0,
            'message': 'Task queued, waiting for worker...',
            'filename': None,
            'download_url': None,
            'error': None,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'download_speed': '0 B/s',
            'eta': 'Unknown',
            'file_size': 'Unknown',
            'downloaded_bytes': 0,
            'total_bytes': 0,
            'retry_count': 0,
            'max_retries': 5
        }
        redis_client.set_task_state(task_id, task_state)
        
        # Create download task message
        task = DownloadTask(
            task_id=task_id,
            url=request.url,
            format_id=request.format_id,
            quality=request.quality,
            created_at=datetime.now().isoformat(),
            user_ip=user_ip
        )
        
        # Publish to RabbitMQ
        await rabbitmq_publisher.publish_download_task(task)
        logger.info(f"✅ Task {task_id} published to RabbitMQ")
        
        return DownloadResponse(
            task_id=task_id,
            message="Download queued successfully",
            status="pending"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error initiating download: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TASK STATUS ENDPOINT
# ============================================================================

@app.get("/api/v1/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get current task status from Redis
    
    Args:
        task_id: Task ID
    
    Returns:
        Task status and progress
    """
    try:
        task_state = redis_client.get_task_state(task_id)
        
        if not task_state:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskStatusResponse(**task_state)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CANCEL TASK ENDPOINT
# ============================================================================

@app.post("/api/v1/cancel/{task_id}")
async def cancel_task(task_id: str):
    """
    Cancel a pending or running download task
    
    Args:
        task_id: Task ID to cancel
    
    Returns:
        Cancellation status
    """
    try:
        task_state = redis_client.get_task_state(task_id)
        
        if not task_state:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task_state['status'] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel task with status: {task_state['status']}")
        
        # Set cancellation flag
        redis_client.set_cancellation_request(task_id)
        redis_client.mark_task_cancelled(task_id)
        
        logger.info(f"✅ Task {task_id} cancellation requested")
        
        return {
            "task_id": task_id,
            "message": "Cancellation requested",
            "status": "cancelled"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error cancelling task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# FILE DOWNLOAD ENDPOINT
# ============================================================================

@app.get("/api/v1/download/{task_id}")
async def download_file(task_id: str, background_tasks: BackgroundTasks):
    """
    Download completed video file
    
    Args:
        task_id: Task ID
        background_tasks: Dependency to delete file instantly
    
    Returns:
        File stream or error
    """
    try:
        task_state = redis_client.get_task_state(task_id)
        
        if not task_state:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task_state['status'] != TaskStatus.COMPLETED:
            raise HTTPException(status_code=400, detail=f"Task not completed: {task_state['status']}")
        
        filename = task_state.get('filename')
        if not filename:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Try to use stored file_path first, then construct from filename
        stored_path = task_state.get('file_path')
        if stored_path and os.path.exists(stored_path):
            file_path = Path(stored_path)
        else:
            # Fallback: reconstruct from filename
            file_path = Path(__file__).parent / "downloads" / filename
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            # List what files DO exist in downloads
            downloads_dir = Path(__file__).parent / "downloads"
            if downloads_dir.exists():
                files = list(downloads_dir.glob("*.mp4"))
                logger.error(f"Available files: {[f.name for f in files]}")
            raise HTTPException(status_code=404, detail="Download file not found")
        
        logger.info(f"📥 Downloading file: {filename}")
        
        # Keep the file available for subsequent frontend refreshes.
        # Cleanup should be handled separately by a retention policy / cron job.
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='video/mp4'
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ACTIVE TASKS ENDPOINT
# ============================================================================

@app.get("/api/v1/tasks")
async def get_active_tasks(include_completed: bool = Query(False, description="Include completed or failed tasks in the returned list")):
    """Get active download tasks from Redis.

    By default this endpoint only returns pending and processing tasks.
    Completed and failed tasks are hidden unless include_completed=true.
    """
    try:
        tasks = redis_client.get_active_tasks(include_completed=include_completed)
        return {
            "total": len(tasks),
            "tasks": tasks
        }
    except Exception as e:
        logger.error(f"❌ Error retrieving tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tasks/refresh")
async def refresh_task(task_id: str = Query(..., description="Task ID to refresh"), force_refresh: bool = Query(False, description="Set true to force requeueing a fresh download")):
    """Force a full re-extraction and re-download for a completed or failed task."""
    try:
        if not force_refresh:
            raise HTTPException(status_code=400, detail="force_refresh=true is required to refresh a task")

        task_state = redis_client.get_task_state(task_id)
        if not task_state:
            raise HTTPException(status_code=404, detail="Task not found")

        if task_state["status"] not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            raise HTTPException(status_code=400, detail="Only completed or failed tasks can be refreshed")

        new_task_id = str(uuid.uuid4())
        new_task_state = {
            "task_id": new_task_id,
            "url": task_state["url"],
            "format_id": task_state.get("format_id"),
            "quality": task_state.get("quality"),
            "status": TaskStatus.PENDING,
            "progress": 0,
            "message": "Task refreshed and queued for download",
            "filename": None,
            "download_url": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "download_speed": "0 B/s",
            "eta": "Unknown",
            "file_size": "Unknown",
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "retry_count": 0,
            "max_retries": 5
        }

        redis_client.set_task_state(new_task_id, new_task_state)
        await rabbitmq_publisher.publish_download_task(DownloadTask(
            task_id=new_task_id,
            url=task_state["url"],
            format_id=task_state.get("format_id", "bestvideo[height<=1080]+bestaudio/best[ext=mp4]"),
            quality=task_state.get("quality", "1080p"),
            created_at=new_task_state["created_at"],
            user_ip=task_state.get("user_ip")
        ))

        return {
            "success": True,
            "message": "Task refreshed and requeued successfully",
            "task_id": new_task_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error refreshing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADMIN SYSTEM
# ============================================================================

# Admin Authentication Dependency
def get_current_admin(request: Request):
    """Check if user is authenticated as admin"""
    session_token = request.cookies.get("admin_session")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        user = get_supabase().auth.get_user(session_token)
        if not user or not user.user:
            raise HTTPException(status_code=401, detail="Invalid session")
        return {"email": user.user.email}
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired session")


# Admin Routes
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page"""
    return templates.TemplateResponse("admin_login.html", {"request": request})


@app.post("/admin/login")
async def admin_login(email: str = Form(...), password: str = Form(...)):
    """Admin login authentication using Supabase"""
    try:
        auth_response = get_supabase().auth.sign_in_with_password({"email": email, "password": password})
        session = auth_response.session
        if not session:
            raise Exception("No session returned")
            
        response = JSONResponse(content={"message": "Login successful"})
        response.set_cookie(key="admin_session", value=session.access_token, httponly=True, max_age=session.expires_in)
        return response
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: dict = Depends(get_current_admin)):
    """Admin dashboard"""
    try:
        # Get stats from Redis
        tasks = redis_client.get_active_tasks()
        total_tasks = len(tasks)
        active_tasks = len([t for t in tasks.values() if t.get("status") == "processing"])
        completed_tasks = len([t for t in tasks.values() if t.get("status") == "completed"])
        failed_tasks = len([t for t in tasks.values() if t.get("status") == "failed"])
        
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "admin": {"email": admin["email"]},
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
    try:
        tasks = list(redis_client.get_active_tasks().values())
        return templates.TemplateResponse("admin_tasks.html", {
            "request": request,
            "admin": admin,
            "tasks": tasks
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail="Tasks error")


@app.post("/admin/logout")
async def admin_logout(request: Request):
    """Admin logout via Supabase"""
    try:
        session_token = request.cookies.get("admin_session")
        if session_token:
            get_supabase().auth.sign_out()
    except Exception as e:
        logger.error(f"Logout error: {e}")
        
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("admin_session")
    return response


# ============================================================================
# PROXY MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/admin/proxies/list", response_class=JSONResponse)
async def list_proxies():
    """List all configured proxies"""
    try:
        db_proxies = get_all_proxies()
        admin_proxies = []
        for p in db_proxies:
            if p.get("username") and p.get("password"):
                admin_proxies.append(f"http://{p['username']}:{p['password']}@{p['ip']}:{p['port']}")
            else:
                admin_proxies.append(f"http://{p['ip']}:{p['port']}")
        
        # Combine with default proxies from config
        from config import PROXIES
        all_proxies = list(set(admin_proxies + PROXIES))
        
        return {"success": True, "proxies": all_proxies, "count": len(all_proxies)}
    except Exception as e:
        logger.error(f"❌ Error listing proxies: {e}")
        return {"success": False, "message": f"Error: {str(e)}", "proxies": []}


@app.post("/admin/proxies/add")
async def add_proxy_route(request: Request, admin: dict = Depends(get_current_admin)):
    """Add a new proxy"""
    try:
        data = await request.json()
        proxy_url = data.get("url", "").strip()
        proxy_name = data.get("name", "").strip()
        
        if not proxy_url:
            return {"success": False, "message": "Proxy URL is required"}
            
        # Parse URL to get ip, port, username, password
        from urllib.parse import urlparse
        parsed = urlparse(proxy_url)
        ip = parsed.hostname
        port = parsed.port
        username = parsed.username
        password = parsed.password
        
        if not ip or not port:
            return {"success": False, "message": "Invalid Proxy format. Need IP and Port."}

        # Add to DB
        res = add_proxy(ip=ip, port=port, username=username, password=password)
        if not res:
            return {"success": False, "message": "Failed to add proxy. May already exist."}
            
        logger.info(f"✅ Proxy added: {proxy_url}")
        return {"success": True, "message": f"Proxy added successfully"}
    
    except Exception as e:
        logger.error(f"❌ Error adding proxy: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}


@app.post("/admin/proxies/delete")
async def delete_proxy_route(request: Request, admin: dict = Depends(get_current_admin)):
    """Delete a proxy"""
    try:
        data = await request.json()
        proxy_url = data.get("proxy", "").strip()
        
        if not proxy_url:
            return {"success": False, "message": "Proxy URL is required"}
            
        from urllib.parse import urlparse
        parsed = urlparse(proxy_url)
        ip = parsed.hostname
        port = parsed.port
        
        if not ip or not port:
            return {"success": False, "message": "Invalid proxy url format"}
            
        existing = get_supabase().table("proxies").select("id").eq("ip", ip).eq("port", port).execute()
        if not existing.data:
            from config import PROXIES
            if proxy_url in PROXIES:
                return {"success": False, "message": "Cannot delete default proxies"}
            return {"success": False, "message": "Proxy not found"}
            
        delete_proxy(existing.data[0]["id"])
        
        logger.info(f"✅ Proxy deleted: {proxy_url}")
        return {"success": True, "message": "Proxy deleted successfully"}
    
    except Exception as e:
        logger.error(f"❌ Error deleting proxy: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}


# ---------------------------------------------------------------------------
# Proxy Test Endpoint
# ---------------------------------------------------------------------------

@app.post("/admin/proxies/test")
async def test_proxy(request: Request, admin: dict = Depends(get_current_admin)):
    """Verify that a given proxy is functional by making a simple HTTP request"""
    try:
        data = await request.json()
        proxy_url = data.get("proxy", "").strip()
        if not proxy_url:
            return {"success": False, "message": "Proxy URL is required"}
        
        # strip metadata if present
        base_url = proxy_url.split("#")[0] if "#" in proxy_url else proxy_url
        
        try:
            import requests
            proxies_dict = {"http": base_url, "https": base_url}
            r = requests.get("https://httpbin.org/ip", proxies=proxies_dict, timeout=10)
            success = r.status_code == 200
            message = "Proxy working" if success else f"Unexpected status {r.status_code}"
        except Exception as ex:
            success = False
            message = str(ex)
            
        # Look up proxy in DB to update status
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        ip = parsed.hostname
        port = parsed.port
        
        if ip and port:
            existing = get_supabase().table("proxies").select("id").eq("ip", ip).eq("port", port).execute()
            if existing.data:
                update_proxy_status(existing.data[0]["id"], status="active" if success else "dead", is_failure=not success)
            
        return {"success": success, "message": message}
    except Exception as e:
        logger.error(f"❌ Proxy test error: {e}")
        return {"success": False, "message": str(e)}


# ============================================================================
# ROOT ENDPOINT
# ============================================================================


