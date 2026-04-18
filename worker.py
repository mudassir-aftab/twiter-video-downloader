
# import asyncio
# import logging
# import os
# import yt_dlp
# import tempfile
# import shutil
# import signal
# import sys
# import random
# import time
# from datetime import datetime
# from pathlib import Path
# from typing import Optional

# from config import (
#     settings,
#     get_random_user_agent,
#     get_random_delay
# )
# from models import DownloadTask, TaskStatus
# from redis_client import redis_client
# from rabbitmq_client import rabbitmq_client
# from database import log_download, log_error
# from proxy_manager import proxy_manager

# # -------------------------------------------------
# # Logging
# # -------------------------------------------------
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s - %(levelname)s - %(message)s"
# )
# logger = logging.getLogger("worker")

# # -------------------------------------------------
# # Concurrency Control
# # -------------------------------------------------
# semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)

# # -------------------------------------------------
# # Graceful shutdown
# # -------------------------------------------------
# worker_running = True
# current_task_id: Optional[str] = None


# def signal_handler(sig, frame):
#     global worker_running
#     logger.info("🛑 Worker shutdown signal received")
#     worker_running = False
#     sys.exit(0)


# # -------------------------------------------------
# # Twitter Downloader with High-Scale Proxy Manager
# # -------------------------------------------------
# class TwitterDownloader:
#     def __init__(self, task_id: str):
#         self.task_id = task_id
#         # Use shared temp directory from config
#         self.temp_dir = os.path.join(settings.temp_dir, f"task_{task_id}")
#         os.makedirs(self.temp_dir, exist_ok=True)
#         self.total_bytes = 0
#         self.downloaded_bytes = 0

#     def extract_video_id(self, url: str) -> str:
#         import re
#         match = re.search(r"/status/(\d+)", url)
#         return match.group(1) if match else "twitter_video"

#     def progress_hook(self, d):
#         try:
#             if redis_client.is_cancellation_requested(self.task_id):
#                 raise Exception("Cancelled by user")

#             if d["status"] == "downloading":
#                 self.total_bytes = d.get("total_bytes") or 0
#                 self.downloaded_bytes = d.get("downloaded_bytes") or 0

#                 progress = (
#                     int(self.downloaded_bytes / self.total_bytes * 100)
#                     if self.total_bytes > 0 else 0
#                 )

#                 redis_client.update_task_progress(
#                     self.task_id,
#                     progress=progress,
#                     message="Downloading...",
#                     download_speed=d.get("_speed_str", "0 B/s"),
#                     eta=d.get("_eta_str", "Unknown"),
#                     downloaded_bytes=self.downloaded_bytes,
#                     total_bytes=self.total_bytes
#                 )

#             elif d["status"] == "finished":
#                 redis_client.update_task_progress(
#                     self.task_id,
#                     progress=100,
#                     message="Finalizing MP4..."
#                 )

#         except Exception as e:
#             logger.error(f"Progress hook error: {e}")

#     async def download(self, url: str) -> str:
#         """Attempt to download the given URL with high-scale proxy management.
        
#         Uses ProxyManager for intelligent routing, scoring, and cooldowns.
#         Reports every attempt to database for performance tracking.
#         """
#         global current_task_id
#         current_task_id = self.task_id

#         video_id = self.extract_video_id(url)
#         output_template = os.path.join(self.temp_dir, f"{video_id}.%(ext)s")

#         base_opts = {
#             "format": "bv*+ba/best",
#             "merge_output_format": "mp4",
#             "outtmpl": output_template,
#             "progress_hooks": [self.progress_hook],
#             "retries": 1,
#             "fragment_retries": 2,
#             "socket_timeout": 20,
#             "quiet": True,
#             "no_warnings": True,
#             "noplaylist": True,
#             "postprocessors": [
#                 {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
#             ],
#         }

#         attempt = 0
#         max_attempts = 5
#         last_error = ""

#         while attempt < max_attempts:
#             attempt += 1
#             start_time = time.time()
            
#             # 1. Select best proxy
#             proxy_obj = proxy_manager.get_best_proxy()
#             if not proxy_obj:
#                 logger.error("No proxies available for download.")
#                 raise Exception("Proxy infrastructure failure: No available proxies")

#             proxy_url = proxy_manager.format_proxy_url(proxy_obj)
#             user_agent = get_random_user_agent()
            
#             opts = base_opts.copy()
#             opts["proxy"] = proxy_url
#             opts["http_headers"] = {"User-Agent": user_agent}

#             # 2. Anti-detection: Random delay
#             delay = get_random_delay()
#             await asyncio.sleep(delay)

#             logger.info(f"Task {self.task_id} | Attempt {attempt}/{max_attempts} | Provider: {proxy_obj['provider_name']} | Proxy: {proxy_obj['host']}")

#             try:
#                 # 3. Execute download
#                 info = await asyncio.to_thread(
#                     lambda: yt_dlp.YoutubeDL(opts).extract_info(url, download=True)
#                 )

#                 final_file = yt_dlp.YoutubeDL(opts).prepare_filename(info)
#                 duration = time.time() - start_time

#                 # 4. Report success
#                 await proxy_manager.report_result(proxy_obj, url, success=True, response_time=duration)

#                 # Use shared downloads directory from config
#                 downloads_dir = Path(settings.downloads_dir).resolve()
#                 downloads_dir.mkdir(parents=True, exist_ok=True)  # Ensure it exists
#                 dest_path = downloads_dir / Path(final_file).name
                
#                 logger.info(f"Moving file from {final_file} to {dest_path}")
                
#                 if os.path.exists(final_file):
#                     shutil.move(str(final_file), str(dest_path))
#                     logger.info(f"File successfully moved to {dest_path}")
#                 elif not os.path.exists(dest_path):
#                     # If final_file doesn't exist, it might already be in dest_path
#                     raise Exception(f"Final file {final_file} not found after download")
#                 else:
#                     logger.info(f"File already at destination: {dest_path}")
#                 file_path = str(dest_path.resolve())
#                 # Cache metadata
#                 video_info = {
#                     "video_id": video_id,
#                     "title": info.get("title", ""),
#                     "duration": info.get("duration", 0),
#                     "download_path": file_path,
#                     "cached_at": datetime.now().isoformat()
#                 }
#                 redis_client.cache_video_info(video_id, video_info)

#                 return str(dest_path)

#             except Exception as e:
#                 duration = time.time() - start_time
#                 error_msg = str(e)
#                 logger.warning(f"Attempt {attempt} failed with {proxy_obj['provider_name']}: {error_msg}")
                
#                 # 5. Report failure
#                 await proxy_manager.report_result(proxy_obj, url, success=False, response_time=duration, error=error_msg)
                
#                 last_error = error_msg
#                 if attempt >= max_attempts:
#                     raise Exception(f"Failed after {max_attempts} attempts. Last error: {last_error}")
                
#                 # Dynamic backoff before next retry
#                 await asyncio.sleep(retry_delay := (1 * attempt))
        
#         raise Exception("Download loop exhausted")


# # -------------------------------------------------
# # Task Processor with Concurrency Control
# # -------------------------------------------------
# async def process_download_task(task: DownloadTask):
#     async with semaphore:  # Limit concurrent downloads
#         logger.info(f"Task received {task.task_id} url={task.url}")

#         # initialize state object
#         redis_client.set_task_state(task.task_id, {
#             "task_id": task.task_id,
#             "url": task.url,
#             "status": TaskStatus.PROCESSING,
#             "progress": 0,
#             "message": "Starting download...",
#             "filename": None,
#             "download_url": None,
#             "error": None,
#             "created_at": task.created_at,
#             "updated_at": datetime.now().isoformat()
#         })

#         downloader = TwitterDownloader(task.task_id)
#         video_id = downloader.extract_video_id(task.url)

#         # quick cache hit check for already‑downloaded file
#         cached = redis_client.get_cached_video_info(video_id)
#         if cached and cached.get("download_path") and os.path.exists(cached.get("download_path")):
#             logger.info(f"Cache hit – skipping download for {video_id}")
#             path = cached["download_path"]
#             filename = os.path.basename(path)
#             download_url = f"/api/v1/download/{task.task_id}"
#             redis_client.mark_task_completed(task.task_id, filename=filename, download_url=download_url)
#             return

#         try:
#             file_path = await downloader.download(task.url)
#             file_path = os.path.abspath(file_path)
#             # Ensure file exists before marking as completed
#             if not os.path.exists(file_path):
#                 raise Exception(f"Downloaded file does not exist: {file_path}")
            
#             filename = os.path.basename(file_path)
#             file_size = os.path.getsize(file_path)
#             download_url = f"/api/v1/download/{task.task_id}"

#             redis_client.mark_task_completed(
#                 task.task_id,
#                 filename=filename,
#                 download_url=download_url,
#                 file_path=file_path  # Store full path
#             )

#             logger.info(f"Task completed {task.task_id}")
#             log_download(twitter_url=task.url, status="success", file_size=file_size, user_ip=task.user_ip)

#         except Exception as e:
#             logger.error(f"Task failed {task.task_id}: {e}")
#             redis_client.mark_task_failed(task.task_id, str(e))
#             log_error(error_type="download_failed", error_message=str(e), source="worker")
#             log_download(twitter_url=task.url, status="failed", user_ip=task.user_ip)

#         finally:
#             redis_client.clear_cancellation_request(task.task_id)


# # -------------------------------------------------
# # Worker Loop
# # -------------------------------------------------
# async def run_worker():
#     logger.info("Worker started with rate limiting features")
#     logger.info(f"Max concurrent downloads: {settings.max_concurrent_downloads}")
#     logger.info(f"Request delay range: {settings.min_request_delay}-{settings.max_request_delay}s")

#     if not redis_client.health_check():
#         raise Exception("Redis not available")

#     if not await rabbitmq_client.health_check():
#         raise Exception("RabbitMQ not available")

#     async def safe_process(task: DownloadTask):
#         try:
#             await process_download_task(task)
#         except Exception as e:
#             logger.error(f"Worker error: {e}")

#     await rabbitmq_client.consume_tasks(safe_process)


# # -------------------------------------------------
# # Entry Point
# # -------------------------------------------------
# def main():
#     signal.signal(signal.SIGINT, signal_handler)
#     signal.signal(signal.SIGTERM, signal_handler)
#     asyncio.run(run_worker())


# if __name__ == "__main__":
#     main()

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
# Safe Redis Helper
# -------------------------------------------------
def redis_safe():
    return redis_client is not None


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
            if redis_safe() and redis_client.is_cancellation_requested(self.task_id):
                raise Exception("Cancelled by user")

            if d["status"] == "downloading":
                self.total_bytes = d.get("total_bytes") or 0
                self.downloaded_bytes = d.get("downloaded_bytes") or 0

                progress = (
                    int(self.downloaded_bytes / self.total_bytes * 100)
                    if self.total_bytes > 0 else 0
                )

                if redis_safe():
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
                if redis_safe():
                    redis_client.update_task_progress(
                        self.task_id,
                        progress=100,
                        message="Finalizing MP4..."
                    )

        except Exception as e:
            logger.error(f"Progress hook error: {e}")

    async def download(self, url: str) -> str:
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

            proxy_obj = proxy_manager.get_best_proxy()
            if not proxy_obj:
                logger.error("No proxies available for download.")
                raise Exception("Proxy infrastructure failure")

            proxy_url = proxy_manager.format_proxy_url(proxy_obj)
            user_agent = get_random_user_agent()

            opts = base_opts.copy()
            opts["proxy"] = proxy_url
            opts["http_headers"] = {"User-Agent": user_agent}

            delay = get_random_delay()
            await asyncio.sleep(delay)

            logger.info(
                f"Task {self.task_id} | Attempt {attempt}/{max_attempts}"
            )

            try:
                info = await asyncio.to_thread(
                    lambda: yt_dlp.YoutubeDL(opts).extract_info(
                        url, download=True)
                )

                final_file = yt_dlp.YoutubeDL(opts).prepare_filename(info)

                downloads_dir = Path(settings.downloads_dir).resolve()
                downloads_dir.mkdir(parents=True, exist_ok=True)

                dest_path = downloads_dir / Path(final_file).name

                if os.path.exists(final_file):
                    shutil.move(str(final_file), str(dest_path))

                file_path = str(dest_path.resolve())

                if redis_safe():
                    video_info = {
                        "video_id": video_id,
                        "title": info.get("title", ""),
                        "duration": info.get("duration", 0),
                        "download_path": file_path,
                        "cached_at": datetime.now().isoformat()
                    }
                    redis_client.cache_video_info(video_id, video_info)

                return file_path

            except Exception as e:
                last_error = str(e)
                await asyncio.sleep(2 * attempt)

        raise Exception(last_error)


# -------------------------------------------------
# Task Processor
# -------------------------------------------------
async def process_download_task(task: DownloadTask):
    async with semaphore:

        logger.info(f"Task received {task.task_id}")

        if redis_safe():
            redis_client.set_task_state(task.task_id, {
                "task_id": task.task_id,
                "status": TaskStatus.PROCESSING,
                "progress": 0
            })

        downloader = TwitterDownloader(task.task_id)

        try:
            file_path = await downloader.download(task.url)

            filename = os.path.basename(file_path)
            download_url = f"/api/v1/download/{task.task_id}"

            if redis_safe():
                redis_client.mark_task_completed(
                    task.task_id,
                    filename=filename,
                    download_url=download_url,
                    file_path=file_path
                )

            log_download(
                twitter_url=task.url,
                status="success",
                file_size=os.path.getsize(file_path),
                user_ip=task.user_ip
            )

        except Exception as e:

            logger.error(f"Task failed {task.task_id}: {e}")

            if redis_safe():
                redis_client.mark_task_failed(
                    task.task_id, str(e))

            log_error(
                error_type="download_failed",
                error_message=str(e),
                source="worker"
            )


# -------------------------------------------------
# Worker Loop
# -------------------------------------------------
async def run_worker():
    logger.info("Worker started with rate limiting features")
    logger.info(
        f"Max concurrent downloads: {settings.max_concurrent_downloads}")
    logger.info(
        f"Request delay range: {settings.min_request_delay}-{settings.max_request_delay}s")

    if redis_safe():
        if not redis_client.health_check():
            logger.warning("Redis not available")
    else:
        logger.warning("Redis not initialized")

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