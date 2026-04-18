# """Redis client for caching and task state management"""
# import redis
# import json
# from typing import Optional, Dict, Any
# import logging
# from config import settings, get_redis_url
# from models import TaskState, VideoInfo
# from models import TaskStatus
# from datetime import datetime

# logger = logging.getLogger(__name__)

# class RedisClient:
#     """Wrapper for Redis operations"""
    
#     def __init__(self):
#         """Initialize Redis connection"""
#         self.redis_url = get_redis_url()
#         self.client = None
#         self.connect()
    
#     def connect(self):
#         """Establish Redis connection"""
#         try:
#             # Using decode_responses=True to get strings instead of bytes
#             # use_ssl = self.redis_url.startswith("rediss://")
#             # self.client = redis.from_url(
#             #     self.redis_url, 
#             #     decode_responses=True, 
#             #     socket_connect_timeout=5, 
#             #     socket_keepalive=True, 
               
#             # )

#             import ssl

# self.client = redis.from_url(
#     self.redis_url,
#     decode_responses=True,
#     socket_connect_timeout=5,
#     socket_keepalive=True,
#     ssl_cert_reqs=ssl.CERT_NONE,
# )

#             self.client.ping()
#             logger.info(f"✅ Connected to Redis at {self.redis_url}")
#         except Exception as e:
#             logger.error(f"❌ Failed to connect to Redis: {e}")
#             raise

#     # ---------------- Task state management ----------------
#     def set_task_state(self, task_id: str, task_state: Dict[str, Any], ttl: int = None):
#         """Store task state in Redis"""
#         try:
#             ttl = ttl or settings.task_ttl_seconds
#             key = f"task:{task_id}"
#             value = json.dumps(task_state, default=str)
#             self.client.setex(key, ttl, value)
#             logger.debug(f"Task {task_id} state saved to Redis")
#         except Exception as e:
#             logger.error(f"Error saving task state: {e}")
#             raise

#     def get_task_state(self, task_id: str) -> Optional[Dict]:
#         """Retrieve task state from Redis"""
#         try:
#             key = f"task:{task_id}"
#             value = self.client.get(key)
#             if value:
#                 return json.loads(value)
#             return None
#         except Exception as e:
#             logger.error(f"Error retrieving task state: {e}")
#             return None

#     def update_task_progress(self, task_id: str, progress: int, message: str, **kwargs):
#         """Update task progress in Redis"""
#         try:
#             task_state = self.get_task_state(task_id)
#             if task_state:
#                 task_state["progress"] = progress
#                 task_state["message"] = message
#                 task_state["updated_at"] = datetime.now().isoformat()
                
#                 for key, value in kwargs.items():
#                     task_state[key] = value
                
#                 self.set_task_state(task_id, task_state)
#                 logger.debug(f"Task {task_id} progress updated to {progress}%")
#         except Exception as e:
#             logger.error(f"Error updating task progress: {e}")

#     def mark_task_completed(self, task_id: str, filename: str, download_url: str, file_path: str = None):
#         """Mark task as completed"""
#         try:
#             task_state = self.get_task_state(task_id)
#             if task_state:
#                 task_state["status"] = TaskStatus.COMPLETED
#                 task_state["progress"] = 100
#                 task_state["filename"] = filename
#                 task_state["file_path"] = file_path or filename  # Store full path if available
#                 task_state["download_url"] = download_url
#                 task_state["message"] = "Download completed"
#                 self.set_task_state(task_id, task_state)
#                 logger.info(f"Task {task_id} marked as completed: {filename}")
#         except Exception as e:
#             logger.error(f"Error marking task completed: {e}")

#     def mark_task_failed(self, task_id: str, error: str):
#         """Mark task as failed"""
#         try:
#             task_state = self.get_task_state(task_id)
#             if task_state:
#                 task_state["status"] = TaskStatus.FAILED
#                 task_state["error"] = error
#                 task_state["message"] = f"Download failed: {error}"
#                 self.set_task_state(task_id, task_state)
#                 logger.error(f"Task {task_id} marked as failed: {error}")
#         except Exception as e:
#             logger.error(f"Error marking task failed: {e}")

#     def mark_task_cancelled(self, task_id: str):
#         """Mark task as cancelled"""
#         try:
#             task_state = self.get_task_state(task_id)
#             if task_state:
#                 task_state["status"] = TaskStatus.CANCELLED
#                 task_state["message"] = "Download cancelled by user"
#                 self.set_task_state(task_id, task_state)
#                 logger.info(f"Task {task_id} marked as cancelled")
#         except Exception as e:
#             logger.error(f"Error marking task cancelled: {e}")

#     # ---------------- Video info caching ----------------
#     def cache_video_info(self, video_id: str, video_info: Dict[str, Any]):
#         """Cache video info with TTL"""
#         try:
#             key = f"video_info:{video_id}"
#             value = json.dumps(video_info, default=str)
#             ttl = settings.video_info_cache_ttl
#             self.client.setex(key, ttl, value)
#             logger.debug(f"Video info cached for {video_id}")
#         except Exception as e:
#             logger.error(f"Error caching video info: {e}")

#     def get_cached_video_info(self, video_id: str) -> Optional[Dict]:
#         """Retrieve cached video info"""
#         try:
#             key = f"video_info:{video_id}"
#             value = self.client.get(key)
#             if value:
#                 return json.loads(value)
#             return None
#         except Exception as e:
#             logger.error(f"Error retrieving cached video info: {e}")
#             return None

#     # ---------------- Task management helpers ----------------
#     def delete_task(self, task_id: str):
#         try:
#             key = f"task:{task_id}"
#             self.client.delete(key)
#             logger.debug(f"Task {task_id} deleted from Redis")
#         except Exception as e:
#             logger.error(f"Error deleting task: {e}")

#     def get_active_tasks(self, include_completed: bool = False) -> Dict[str, Dict]:
#         try:
#             pattern = "task:*"
#             keys = self.client.keys(pattern)
#             tasks = {}
#             for key in keys:
#                 value = self.client.get(key)
#                 if not value:
#                     continue

#                 task_id = key.replace("task:", "")
#                 task_state = json.loads(value)
#                 status = task_state.get("status", "")

#                 if not include_completed and status not in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
#                     continue

#                 tasks[task_id] = task_state
#             return tasks
#         except Exception as e:
#             logger.error(f"Error retrieving active tasks: {e}")
#             return {}

#     # ---------------- Cancellation ----------------
#     def set_cancellation_request(self, task_id: str):
#         try:
#             key = f"cancel:{task_id}"
#             self.client.setex(key, 3600, "1")
#             logger.info(f"Cancellation requested for task {task_id}")
#         except Exception as e:
#             logger.error(f"Error setting cancellation request: {e}")

#     def is_cancellation_requested(self, task_id: str) -> bool:
#         try:
#             key = f"cancel:{task_id}"
#             return self.client.exists(key) > 0
#         except Exception as e:
#             logger.error(f"Error checking cancellation request: {e}")
#             return False

#     def clear_cancellation_request(self, task_id: str):
#         try:
#             key = f"cancel:{task_id}"
#             self.client.delete(key)
#         except Exception as e:
#             logger.error(f"Error clearing cancellation request: {e}")

#     # ---------------- Proxy caching ----------------
#     def set_proxy_cooldown(self, proxy_id: str, duration: int = 60):
#         try:
#             key = f"proxy_cooldown:{proxy_id}"
#             self.client.setex(key, duration, "1")
#             logger.debug(f"Proxy {proxy_id} put on cooldown for {duration}s")
#         except Exception as e:
#             logger.error(f"Error setting proxy cooldown: {e}")

#     def is_proxy_on_cooldown(self, proxy_id: str) -> bool:
#         try:
#             key = f"proxy_cooldown:{proxy_id}"
#             return self.client.exists(key) > 0
#         except Exception as e:
#             logger.error(f"Error checking proxy cooldown: {e}")
#             return False

#     def set_active_proxy_cache(self, proxies: list, ttl: int = 300):
#         try:
#             key = "active_proxies_cache"
#             self.client.setex(key, ttl, json.dumps(proxies))
#         except Exception as e:
#             logger.error(f"Error caching active proxies: {e}")

#     def get_active_proxy_cache(self) -> Optional[list]:
#         try:
#             key = "active_proxies_cache"
#             value = self.client.get(key)
#             if value:
#                 return json.loads(value)
#             return None
#         except Exception as e:
#             logger.error(f"Error retrieving active proxy cache: {e}")

#     # ---------------- Distributed locks ----------------
#     def acquire_lock(self, lock_name: str, timeout: int = 10) -> bool:
#         try:
#             return self.client.set(f"lock:{lock_name}", "1", nx=True, ex=timeout)
#         except Exception as e:
#             logger.error(f"Error acquiring lock {lock_name}: {e}")
#             return False

#     def release_lock(self, lock_name: str):
#         try:
#             self.client.delete(f"lock:{lock_name}")
#         except Exception as e:
#             logger.error(f"Error releasing lock {lock_name}: {e}")

#     # ---------------- Health check ----------------
#     def health_check(self) -> bool:
#         try:
#             self.client.ping()
#             return True
#         except Exception as e:
#             logger.error(f"Redis health check failed: {e}")
#             return False

# # Global Redis client instance
# # redis_client = RedisClient()
# # SAFE GLOBAL INSTANCE (NO AUTO CONNECT)
# redis_client = None

# def get_redis_client():
#     global redis_client
#     if redis_client is None:
#         redis_client = RedisClient()
#     return redis_client

# if __name__ == "__main__":
#     client = RedisClient()
#     print("Redis test done")

"""Redis client for caching and task state management (Railway Safe Version)"""




import redis
import json
from typing import Optional, Dict, Any
import logging
from datetime import datetime
import ssl

from config import settings, get_redis_url
from models import TaskStatus

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self):
        self.redis_url = get_redis_url()
        self.client = None

    # ============================================================
    # 🔌 CONNECTION (FIXED SSL BUG)
    # ============================================================
    def connect(self):
        try:
            if self.redis_url.startswith("rediss://"):
                # ✅ CLOUD REDIS (SSL)
                self.client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    ssl_cert_reqs=ssl.CERT_NONE,  # 🔥 FIXED (NO ssl=True)
                )
            else:
                # ✅ LOCAL REDIS (NO SSL)
                self.client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                )

            self.client.ping()
            logger.info(f"✅ Connected to Redis: {self.redis_url}")

        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.client = None  # 🚫 prevent crash

    def ensure_connection(self):
        if self.client is None:
            self.connect()

    # ============================================================
    # 🧠 TASK STATE
    # ============================================================
    def set_task_state(self, task_id: str, task_state: Dict[str, Any], ttl: int = None):
        try:
            self.ensure_connection()
            if not self.client:
                return

            ttl = ttl or settings.task_ttl_seconds
            key = f"task:{task_id}"
            value = json.dumps(task_state, default=str)

            self.client.setex(key, ttl, value)

        except Exception as e:
            logger.error(f"Error saving task state: {e}")

    def get_task_state(self, task_id: str) -> Optional[Dict]:
        try:
            self.ensure_connection()
            if not self.client:
                return None

            value = self.client.get(f"task:{task_id}")
            return json.loads(value) if value else None

        except Exception as e:
            logger.error(f"Error retrieving task state: {e}")
            return None

    def update_task_progress(self, task_id: str, progress: int, message: str, **kwargs):
        try:
            state = self.get_task_state(task_id)
            if not state:
                return

            state["progress"] = progress
            state["message"] = message
            state["updated_at"] = datetime.now().isoformat()

            for k, v in kwargs.items():
                state[k] = v

            self.set_task_state(task_id, state)

        except Exception as e:
            logger.error(f"Error updating progress: {e}")

    def mark_task_completed(self, task_id: str, filename: str, download_url: str, file_path: str = None):
        try:
            state = self.get_task_state(task_id)
            if not state:
                return

            state.update({
                "status": TaskStatus.COMPLETED,
                "progress": 100,
                "filename": filename,
                "file_path": file_path or filename,
                "download_url": download_url,
                "message": "Download completed"
            })

            self.set_task_state(task_id, state)

        except Exception as e:
            logger.error(f"Error marking completed: {e}")

    def mark_task_failed(self, task_id: str, error: str):
        try:
            state = self.get_task_state(task_id)
            if not state:
                return

            state.update({
                "status": TaskStatus.FAILED,
                "error": error,
                "message": f"Download failed: {error}"
            })

            self.set_task_state(task_id, state)

        except Exception as e:
            logger.error(f"Error marking failed: {e}")

    # ============================================================
    # 🎥 VIDEO CACHE
    # ============================================================
    def cache_video_info(self, video_id: str, data: Dict[str, Any]):
        try:
            self.ensure_connection()
            if not self.client:
                return

            key = f"video_info:{video_id}"
            self.client.setex(
                key,
                settings.video_info_cache_ttl,
                json.dumps(data, default=str)
            )

        except Exception as e:
            logger.error(f"Cache error: {e}")

    def get_cached_video_info(self, video_id: str) -> Optional[Dict]:
        try:
            self.ensure_connection()
            if not self.client:
                return None

            val = self.client.get(f"video_info:{video_id}")
            return json.loads(val) if val else None

        except Exception as e:
            logger.error(f"Cache fetch error: {e}")
            return None

    # ============================================================
    # 📋 TASK LIST
    # ============================================================
    def get_active_tasks(self, include_completed=False):
        try:
            self.ensure_connection()
            if not self.client:
                return {}

            keys = self.client.keys("task:*")
            tasks = {}

            for k in keys:
                val = self.client.get(k)
                if not val:
                    continue

                data = json.loads(val)
                status = data.get("status")

                if not include_completed and status not in ["pending", "processing"]:
                    continue

                task_id = k.replace("task:", "")
                tasks[task_id] = data

            return tasks

        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return {}

    # ============================================================
    # ❌ CANCEL
    # ============================================================
    def set_cancellation_request(self, task_id: str):
        try:
            self.ensure_connection()
            if not self.client:
                return

            self.client.setex(f"cancel:{task_id}", 3600, "1")

        except Exception as e:
            logger.error(f"Cancel error: {e}")

    def is_cancellation_requested(self, task_id: str) -> bool:
        try:
            self.ensure_connection()
            if not self.client:
                return False

            return self.client.exists(f"cancel:{task_id}") > 0

        except Exception:
            return False

    # ============================================================
    # ❤️ HEALTH
    # ============================================================
    def health_check(self):
        try:
            self.ensure_connection()
            if not self.client:
                return False

            self.client.ping()
            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# ============================================================
# 🌍 GLOBAL INSTANCE (SAFE LAZY LOAD)
# ============================================================

redis_client = None


def get_redis_client():
    global redis_client
    if redis_client is None:
        redis_client = RedisClient()
    return redis_client