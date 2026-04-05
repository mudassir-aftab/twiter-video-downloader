
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class DownloadTask(BaseModel):
    task_id: str
    url: str
    format_id: str
    quality: str
    created_at: str
    user_ip: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "url": "https://x.com/user/status/123456",
                "format_id": "bestvideo[height<=1080]+bestaudio/best[ext=mp4]",
                "quality": "1080p",
                "created_at": "2024-03-01T10:00:00Z"
            }
        }


class TaskUpdateMessage(BaseModel):
    task_id: str
    status: TaskStatus
    progress: int = 0
    message: str = "Pending"
    filename: Optional[str] = None
    error: Optional[str] = None
    download_speed: str = "0 B/s"
    eta: str = "Unknown"
    file_size: str = "Unknown"
    downloaded_bytes: int = 0
    total_bytes: int = 0


class TaskState(BaseModel):
    id: str
    url: str
    format_id: str
    quality: str
    status: TaskStatus
    progress: int = 0
    message: str = "Pending"
    filename: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
    download_speed: str = "0 B/s"
    eta: str = "Unknown"
    file_size: str = "Unknown"
    downloaded_bytes: int = 0
    total_bytes: int = 0
    retry_count: int = 0
    max_retries: int = 5


class DownloadRequest(BaseModel):
    url: str
    # ✅ Safe format for up to 1080p download
    format_id: str = "bestvideo[height<=1080]+bestaudio/best[ext=mp4]"
    quality: str = "1080p"
    user_ip: Optional[str] = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: int = 0
    message: str = "Pending"
    filename: Optional[str] = None
    download_url: Optional[str] = None
    error: Optional[str] = None
    download_speed: str = "0 B/s"
    eta: str = "Unknown"
    file_size: str = "Unknown"
    downloaded_bytes: int = 0
    total_bytes: int = 0


class VideoInfo(BaseModel):
    video_id: str
    title: str
    duration: int
    uploader: str
    description: str
    download_path: Optional[str] = None  # local file path when cached
    upload_date: str
    formats: List[dict]
    cached_at: str


class DownloadResponse(BaseModel):
    task_id: str
    message: str
    status: str


class VideoInfoResponse(BaseModel):
    video_id: str
    title: str
    duration: int
    uploader: str
    description: str
    upload_date: str
    formats: List[dict]


class Proxy(BaseModel):
    id: Optional[int] = None
    url: str
    name: Optional[str] = None
    is_active: bool = True
    last_tested: Optional[str] = None
    test_result: Optional[str] = None
    created_at: str
    updated_at: str