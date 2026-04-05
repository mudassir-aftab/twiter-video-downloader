


# """Standalone worker process for handling download tasks"""
# import asyncio
# import logging
# import os
# import yt_dlp
# import tempfile
# import shutil
# import signal
# import sys
# import json
# from datetime import datetime
# from pathlib import Path
# from typing import Optional

# from config import settings
# from models import DownloadTask, TaskStatus
# from redis_client import redis_client
# from rabbitmq_client import rabbitmq_client

# # -------------------------
# # Logging configuration
# # -------------------------
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)

# # -------------------------
# # Global shutdown variables
# # -------------------------
# worker_running = True
# current_task_id: Optional[str] = None

# def signal_handler(sig, frame):
#     """Gracefully shutdown worker"""
#     global worker_running
#     logger.info("🛑 Shutdown signal received")
#     worker_running = False
#     if current_task_id:
#         logger.info(f"⚠️  Cancelling current task {current_task_id}")
#     sys.exit(0)

# # -------------------------
# # Twitter Downloader Class
# # -------------------------
# class TwitterDownloader:
#     """Twitter/X video downloader with progress tracking"""

#     def __init__(self, task_id: str):
#         self.task_id = task_id
#         self.temp_dir = tempfile.mkdtemp()
#         self.downloaded_file = None
#         self.total_bytes = 0
#         self.downloaded_bytes = 0

#     def progress_hook(self, d):
#         """Progress hook for yt-dlp"""
#         try:
#             if redis_client.is_cancellation_requested(self.task_id):
#                 raise Exception("Download cancelled by user")
            
#             status = d.get('status', '')
            
#             if status == 'downloading':
#                 self.total_bytes = d.get('total_bytes', 0) or 0
#                 self.downloaded_bytes = d.get('downloaded_bytes', 0) or 0

#                 progress = int((self.downloaded_bytes / self.total_bytes) * 100) if self.total_bytes > 0 else 0
#                 speed = d.get('_speed_str', '0 B/s')
#                 eta = d.get('_eta_str', 'Unknown')
#                 filename = d.get('filename', 'Unknown')

#                 redis_client.update_task_progress(
#                     self.task_id,
#                     progress=progress,
#                     message=f"Downloading: {filename}",
#                     download_speed=speed,
#                     eta=eta,
#                     downloaded_bytes=self.downloaded_bytes,
#                     total_bytes=self.total_bytes
#                 )

#             elif status == 'finished':
#                 filename = d.get('filename', '')
#                 self.downloaded_file = filename
#                 redis_client.update_task_progress(
#                     self.task_id,
#                     progress=100,
#                     message="Download finished, processing..."
#                 )
#         except Exception as e:
#             logger.error(f"Progress hook error: {e}")

#     def extract_video_id(self, url: str) -> str:
#         """Extract video ID from Twitter/X URL"""
#         import re
#         match = re.search(r'/status/(\d+)', url)
#         return match.group(1) if match else url

#     async def download(self, url: str, format_id: str, quality: str) -> str:
#         """Download video from Twitter/X"""
#         global current_task_id
#         current_task_id = self.task_id

#         try:
#             if redis_client.is_cancellation_requested(self.task_id):
#                 raise Exception("Download cancelled before start")

#             video_id = self.extract_video_id(url)
#             output_path = os.path.join(self.temp_dir, f"{video_id}_%(ext)s")

#             # Update task to processing
#             task_state = redis_client.get_task_state(self.task_id)
#             if task_state:
#                 task_state['status'] = TaskStatus.PROCESSING
#                 task_state['message'] = 'Starting download...'
#                 redis_client.set_task_state(self.task_id, task_state)

#             logger.info(f"🎬 Starting download for task {self.task_id}: {url}")

#             ydl_opts = {
#                 'format': format_id,
#                 'quiet': False,
#                 'no_warnings': False,
#                 'socket_timeout': 30,
#                 'retries': 3,
#                 'fragment_retries': 3,
#                 'skip_unavailable_fragments': True,
#                 'outtmpl': output_path,
#                 'progress_hooks': [self.progress_hook],
#                 'postprocessors': [],
#                 'http_headers': {
#                     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
#                 }
#             }

#             # Run download in thread to avoid blocking asyncio
#             info = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=True))
#             filename = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info)

#             logger.info(f"✅ Download completed: {filename}")

#             # Move to downloads folder
#             downloads_dir = Path(__file__).parent / "downloads"
#             downloads_dir.mkdir(exist_ok=True)
#             dest_path = downloads_dir / Path(filename).name
#             shutil.move(filename, str(dest_path))

#             return str(dest_path)

#         except Exception as e:
#             logger.error(f"❌ Download failed: {e}")
#             raise

#         finally:
#             current_task_id = None
#             # Cleanup temp
#             if os.path.exists(self.temp_dir):
#                 try:
#                     shutil.rmtree(self.temp_dir)
#                 except:
#                     pass

#     def cleanup(self):
#         """Clean temp dir"""
#         try:
#             if os.path.exists(self.temp_dir):
#                 shutil.rmtree(self.temp_dir)
#         except Exception as e:
#             logger.error(f"Cleanup error: {e}")


# # -------------------------
# # Task Processing
# # -------------------------
# async def process_download_task(task: DownloadTask):
#     """Process a single download task"""
#     logger.info(f"🔄 Processing task {task.task_id}")

#     try:
#         # Initialize task state
#         task_state = {
#             'task_id': task.task_id,
#             'url': task.url,
#             'format_id': task.format_id,
#             'quality': task.quality,
#             'status': TaskStatus.PROCESSING,
#             'progress': 0,
#             'message': 'Starting download...',
#             'filename': None,
#             'download_url': None,
#             'error': None,
#             'created_at': task.created_at,
#             'updated_at': datetime.now().isoformat(),
#             'download_speed': '0 B/s',
#             'eta': 'Unknown',
#             'file_size': 'Unknown',
#             'downloaded_bytes': 0,
#             'total_bytes': 0,
#             'retry_count': 0,
#             'max_retries': 5
#         }
#         redis_client.set_task_state(task.task_id, task_state)

#         downloader = TwitterDownloader(task.task_id)

#         try:
#             filepath = await downloader.download(task.url, task.format_id, task.quality)
#             filename = os.path.basename(filepath)
#             # download_url = f"/api/v1/download/{task.task_id}/{filename}"
#             download_url = f"/api/v1/file/{task.task_id}"
#             # Mark completed
#             redis_client.mark_task_completed(task.task_id, filename, download_url)
#             logger.info(f"✅ Task {task.task_id} completed successfully")

#         except Exception as e:
#             logger.error(f"❌ Task {task.task_id} failed: {str(e)}")
#             redis_client.mark_task_failed(task.task_id, str(e))

#         finally:
#             downloader.cleanup()
#             redis_client.clear_cancellation_request(task.task_id)

#     except Exception as e:
#         logger.error(f"❌ Unexpected error processing task {task.task_id}: {e}")
#         redis_client.mark_task_failed(task.task_id, f"Unexpected error: {str(e)}")


# # -------------------------
# # Worker loop
# # -------------------------
# async def run_worker():
#     """Main worker event loop"""
#     logger.info("🚀 Starting worker process...")

#     try:
#         if not redis_client.health_check():
#             raise Exception("Redis connection failed")

#         if not await rabbitmq_client.health_check():
#             raise Exception("RabbitMQ connection failed")

#         logger.info("✅ All connections verified")

#         # Consume tasks safely
#         async def safe_process(task: DownloadTask):
#             try:
#                 await process_download_task(task)
#             except Exception as e:
#                 logger.error(f"❌ Error in task processing: {e}")

#         # Consume with safe ack handling
#         # await rabbitmq_client.consume_tasks(safe_process, ignore_processed=True)
#         await rabbitmq_client.consume_tasks(safe_process)


#     except KeyboardInterrupt:
#         logger.info("⚠️  Worker interrupted")
#     except Exception as e:
#         logger.error(f"❌ Worker error: {e}")
#     finally:
#         await rabbitmq_client.close()
#         logger.info("🛑 Worker stopped")


# # -------------------------
# # Entry point
# # -------------------------
# def main():
#     signal.signal(signal.SIGINT, signal_handler)
#     signal.signal(signal.SIGTERM, signal_handler)
#     asyncio.run(run_worker())


# if __name__ == "__main__":
#     main()

"""
Standalone worker process for handling Twitter/X video download tasks
RATE LIMIT RESISTANT VERSION - MP4 OUTPUT
"""

import asyncio
import logging
import os
import yt_dlp
import tempfile
import shutil
import signal
import sys
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import (
    settings,
    get_random_user_agent,
    get_random_delay
)
from models import DownloadTask, TaskStatus
from redis_client import redis_client
from rabbitmq_client import rabbitmq_client
from database import log_download, log_error
from proxy_manager import proxy_manager

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("worker")

# -------------------------------------------------
# Concurrency Control
# -------------------------------------------------
semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)

# -------------------------------------------------
# Graceful shutdown
# -------------------------------------------------
worker_running = True
current_task_id: Optional[str] = None


def signal_handler(sig, frame):
    global worker_running
    logger.info("🛑 Worker shutdown signal received")
    worker_running = False
    sys.exit(0)


# -------------------------------------------------
# Twitter Downloader with High-Scale Proxy Manager
# -------------------------------------------------
class TwitterDownloader:
    def __init__(self, task_id: str):
        self.task_id = task_id
        # Use shared temp directory from config
        self.temp_dir = os.path.join(settings.temp_dir, f"task_{task_id}")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.total_bytes = 0
        self.downloaded_bytes = 0

    def extract_video_id(self, url: str) -> str:
        import re
        match = re.search(r"/status/(\d+)", url)
        return match.group(1) if match else "twitter_video"

    def progress_hook(self, d):
        try:
            if redis_client.is_cancellation_requested(self.task_id):
                raise Exception("Cancelled by user")

            if d["status"] == "downloading":
                self.total_bytes = d.get("total_bytes") or 0
                self.downloaded_bytes = d.get("downloaded_bytes") or 0

                progress = (
                    int(self.downloaded_bytes / self.total_bytes * 100)
                    if self.total_bytes > 0 else 0
                )

                redis_client.update_task_progress(
                    self.task_id,
                    progress=progress,
                    message="Downloading...",
                    download_speed=d.get("_speed_str", "0 B/s"),
                    eta=d.get("_eta_str", "Unknown"),
                    downloaded_bytes=self.downloaded_bytes,
                    total_bytes=self.total_bytes
                )

            elif d["status"] == "finished":
                redis_client.update_task_progress(
                    self.task_id,
                    progress=100,
                    message="Finalizing MP4..."
                )

        except Exception as e:
            logger.error(f"Progress hook error: {e}")

    async def download(self, url: str) -> str:
        """Attempt to download the given URL with high-scale proxy management.
        
        Uses ProxyManager for intelligent routing, scoring, and cooldowns.
        Reports every attempt to database for performance tracking.
        """
        global current_task_id
        current_task_id = self.task_id

        video_id = self.extract_video_id(url)
        output_template = os.path.join(self.temp_dir, f"{video_id}.%(ext)s")

        base_opts = {
            "format": "bv*+ba/best",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "progress_hooks": [self.progress_hook],
            "retries": 1,
            "fragment_retries": 2,
            "socket_timeout": 20,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "postprocessors": [
                {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
            ],
        }

        attempt = 0
        max_attempts = 5
        last_error = ""

        while attempt < max_attempts:
            attempt += 1
            start_time = time.time()
            
            # 1. Select best proxy
            proxy_obj = proxy_manager.get_best_proxy()
            if not proxy_obj:
                logger.error("No proxies available for download.")
                raise Exception("Proxy infrastructure failure: No available proxies")

            proxy_url = proxy_manager.format_proxy_url(proxy_obj)
            user_agent = get_random_user_agent()
            
            opts = base_opts.copy()
            opts["proxy"] = proxy_url
            opts["http_headers"] = {"User-Agent": user_agent}

            # 2. Anti-detection: Random delay
            delay = get_random_delay()
            await asyncio.sleep(delay)

            logger.info(f"Task {self.task_id} | Attempt {attempt}/{max_attempts} | Provider: {proxy_obj['provider_name']} | Proxy: {proxy_obj['host']}")

            try:
                # 3. Execute download
                info = await asyncio.to_thread(
                    lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=True)
                )

                final_file = yt_dlp.YoutubeDL(opts).prepare_filename(info)
                duration = time.time() - start_time

                # 4. Report success
                await proxy_manager.report_result(proxy_obj, url, success=True, response_time=duration)

                # Use shared downloads directory from config
                downloads_dir = Path(settings.downloads_dir)
                dest_path = downloads_dir / Path(final_file).name
                
                if os.path.exists(final_file):
                    shutil.move(str(final_file), str(dest_path))
                elif not os.path.exists(dest_path):
                    # If final_file doesn't exist, it might already be in dest_path
                    raise Exception(f"Final file {final_file} not found after download")
                
                # Cache metadata
                video_info = {
                    "video_id": video_id,
                    "title": info.get("title", ""),
                    "duration": info.get("duration", 0),
                    "download_path": str(dest_path),
                    "cached_at": datetime.now().isoformat()
                }
                redis_client.cache_video_info(video_id, video_info)

                return str(dest_path)

            except Exception as e:
                duration = time.time() - start_time
                error_msg = str(e)
                logger.warning(f"Attempt {attempt} failed with {proxy_obj['provider_name']}: {error_msg}")
                
                # 5. Report failure
                await proxy_manager.report_result(proxy_obj, url, success=False, response_time=duration, error=error_msg)
                
                last_error = error_msg
                if attempt >= max_attempts:
                    raise Exception(f"Failed after {max_attempts} attempts. Last error: {last_error}")
                
                # Dynamic backoff before next retry
                await asyncio.sleep(retry_delay := (1 * attempt))
        
        raise Exception("Download loop exhausted")


# -------------------------------------------------
# Task Processor with Concurrency Control
# -------------------------------------------------
async def process_download_task(task: DownloadTask):
    async with semaphore:  # Limit concurrent downloads
        logger.info(f"Task received {task.task_id} url={task.url}")

        # initialize state object
        redis_client.set_task_state(task.task_id, {
            "task_id": task.task_id,
            "url": task.url,
            "status": TaskStatus.PROCESSING,
            "progress": 0,
            "message": "Starting download...",
            "filename": None,
            "download_url": None,
            "error": None,
            "created_at": task.created_at,
            "updated_at": datetime.now().isoformat()
        })

        downloader = TwitterDownloader(task.task_id)
        video_id = downloader.extract_video_id(task.url)

        # quick cache hit check for already‑downloaded file
        cached = redis_client.get_cached_video_info(video_id)
        if cached and cached.get("download_path") and os.path.exists(cached.get("download_path")):
            logger.info(f"Cache hit – skipping download for {video_id}")
            path = cached["download_path"]
            filename = os.path.basename(path)
            download_url = f"/api/v1/download/{task.task_id}"
            redis_client.mark_task_completed(task.task_id, filename=filename, download_url=download_url)
            return

        try:
            file_path = await downloader.download(task.url)
            filename = os.path.basename(file_path)

            download_url = f"/api/v1/download/{task.task_id}"

            redis_client.mark_task_completed(
                task.task_id,
                filename=filename,
                download_url=download_url
            )

            logger.info(f"Task completed {task.task_id}")
            log_download(twitter_url=task.url, status="success", file_size=os.path.getsize(file_path), user_ip=task.user_ip)

        except Exception as e:
            logger.error(f"Task failed {task.task_id}: {e}")
            redis_client.mark_task_failed(task.task_id, str(e))
            log_error(error_type="download_failed", error_message=str(e), source="worker")
            log_download(twitter_url=task.url, status="failed", user_ip=task.user_ip)

        finally:
            redis_client.clear_cancellation_request(task.task_id)


# -------------------------------------------------
# Worker Loop
# -------------------------------------------------
async def run_worker():
    logger.info("Worker started with rate limiting features")
    logger.info(f"Max concurrent downloads: {settings.max_concurrent_downloads}")
    logger.info(f"Request delay range: {settings.min_request_delay}-{settings.max_request_delay}s")

    if not redis_client.health_check():
        raise Exception("Redis not available")

    if not await rabbitmq_client.health_check():
        raise Exception("RabbitMQ not available")

    async def safe_process(task: DownloadTask):
        try:
            await process_download_task(task)
        except Exception as e:
            logger.error(f"Worker error: {e}")

    await rabbitmq_client.consume_tasks(safe_process)


# -------------------------------------------------
# Entry Point
# -------------------------------------------------
def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()