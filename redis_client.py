"""Redis client for caching and task state management"""
import redis
import json
from typing import Optional, Dict, Any
import logging
from config import settings, get_redis_url
from models import TaskState, VideoInfo
from models import TaskStatus
from datetime import datetime
logger = logging.getLogger(__name__)


class RedisClient:
    """Wrapper for Redis operations"""
    
    def __init__(self):
        """Initialize Redis connection"""
        self.redis_url = get_redis_url()
        self.client = None
        self.connect()
    
    def connect(self):
        """Establish Redis connection"""
        try:
            # Using decode_responses=True to get strings instead of bytes
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )
            self.client.ping()
            logger.info(f"✅ Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise
    
    def set_task_state(self, task_id: str, task_state: Dict[str, Any], ttl: int = None):
        """Store task state in Redis"""
        try:
            ttl = ttl or settings.task_ttl_seconds
            key = f"task:{task_id}"
            value = json.dumps(task_state, default=str)
            self.client.setex(key, ttl, value)
            logger.debug(f"Task {task_id} state saved to Redis")
        except Exception as e:
            logger.error(f"Error saving task state: {e}")
            raise
    
    def get_task_state(self, task_id: str) -> Optional[Dict]:
        """Retrieve task state from Redis"""
        try:
            key = f"task:{task_id}"
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error retrieving task state: {e}")
            return None
    
    def update_task_progress(self, task_id: str, progress: int, message: str, **kwargs):
        """Update task progress in Redis"""
        try:
            task_state = self.get_task_state(task_id)
            if task_state:
                task_state["progress"] = progress
                task_state["message"] = message
                # task_state["updated_at"] = json.dumps({"__timestamp__": True})
                task_state["updated_at"] = datetime.now().isoformat()
                
                # Update any additional fields
                for key, value in kwargs.items():
                    task_state[key] = value
                
                self.set_task_state(task_id, task_state)
                logger.debug(f"Task {task_id} progress updated to {progress}%")
        except Exception as e:
            logger.error(f"Error updating task progress: {e}")
    
    def mark_task_completed(self, task_id: str, filename: str, download_url: str):
        """Mark task as completed"""
        try:
            task_state = self.get_task_state(task_id)
            if task_state:
                task_state["status"] = TaskStatus.COMPLETED
                # task_state["status"] = TaskStatus.FAILED
                # task_state["status"] = TaskStatus.CANCELLED
                # task_state["status"] = "completed"
                task_state["progress"] = 100
                task_state["filename"] = filename
                task_state["download_url"] = download_url
                task_state["message"] = "Download completed"
                self.set_task_state(task_id, task_state)
                logger.info(f"Task {task_id} marked as completed")
        except Exception as e:
            logger.error(f"Error marking task completed: {e}")
    
    def mark_task_failed(self, task_id: str, error: str):
        """Mark task as failed"""
        try:
            task_state = self.get_task_state(task_id)
            if task_state:
                # task_state["status"] = "failed"
                task_state["status"] = TaskStatus.FAILED
                task_state["error"] = error
                task_state["message"] = f"Download failed: {error}"
                self.set_task_state(task_id, task_state)
                logger.error(f"Task {task_id} marked as failed: {error}")
        except Exception as e:
            logger.error(f"Error marking task failed: {e}")
    
    def mark_task_cancelled(self, task_id: str):
        """Mark task as cancelled"""
        try:
            task_state = self.get_task_state(task_id)
            if task_state:
                # task_state["status"] = "cancelled"
                task_state["status"] = TaskStatus.CANCELLED
                task_state["message"] = "Download cancelled by user"
                self.set_task_state(task_id, task_state)
                logger.info(f"Task {task_id} marked as cancelled")
        except Exception as e:
            logger.error(f"Error marking task cancelled: {e}")
    
    def cache_video_info(self, video_id: str, video_info: Dict[str, Any]):
        """Cache video info with TTL"""
        try:
            key = f"video_info:{video_id}"
            value = json.dumps(video_info, default=str)
            ttl = settings.video_info_cache_ttl
            self.client.setex(key, ttl, value)
            logger.debug(f"Video info cached for {video_id}")
        except Exception as e:
            logger.error(f"Error caching video info: {e}")
    
    def get_cached_video_info(self, video_id: str) -> Optional[Dict]:
        """Retrieve cached video info"""
        try:
            key = f"video_info:{video_id}"
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error retrieving cached video info: {e}")
            return None
    
    def delete_task(self, task_id: str):
        """Delete task from Redis"""
        try:
            key = f"task:{task_id}"
            self.client.delete(key)
            logger.debug(f"Task {task_id} deleted from Redis")
        except Exception as e:
            logger.error(f"Error deleting task: {e}")
    
    def get_active_tasks(self) -> Dict[str, Dict]:
        """Get all active tasks from Redis"""
        try:
            pattern = "task:*"
            keys = self.client.keys(pattern)
            tasks = {}
            for key in keys:
                value = self.client.get(key)
                if value:
                    task_id = key.replace("task:", "")
                    tasks[task_id] = json.loads(value)
            return tasks
        except Exception as e:
            logger.error(f"Error retrieving active tasks: {e}")
            return {}
    
    def set_cancellation_request(self, task_id: str):
        """Set cancellation flag for a task"""
        try:
            key = f"cancel:{task_id}"
            self.client.setex(key, 3600, "1")  # Expire after 1 hour
            logger.info(f"Cancellation requested for task {task_id}")
        except Exception as e:
            logger.error(f"Error setting cancellation request: {e}")
    
    def is_cancellation_requested(self, task_id: str) -> bool:
        """Check if cancellation was requested"""
        try:
            key = f"cancel:{task_id}"
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking cancellation request: {e}")
            return False
    
    def clear_cancellation_request(self, task_id: str):
        """Clear cancellation flag"""
        try:
            key = f"cancel:{task_id}"
            self.client.delete(key)
        except Exception as e:
            logger.error(f"Error clearing cancellation request: {e}")
    
    def set_proxy_cooldown(self, proxy_id: str, duration: int = 60):
        """Set a cooldown for a specific proxy in Redis"""
        try:
           key = f"proxy_cooldown:{proxy_id}"
           self.client.setex(key, duration, "1")
           logger.debug(f"Proxy {proxy_id} put on cooldown for {duration}s")
        except Exception as e:
            logger.error(f"Error setting proxy cooldown: {e}")

    def is_proxy_on_cooldown(self, proxy_id: str) -> bool:
        """Check if a proxy is currently on cooldown"""
        try:
           key = f"proxy_cooldown:{proxy_id}"
           return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking proxy cooldown: {e}")
            return False

    def set_active_proxy_cache(self, proxies: list, ttl: int = 300):
        """Cache the list of active proxies from DB"""
        try:
           key = "active_proxies_cache"
           self.client.setex(key, ttl, json.dumps(proxies))
        except Exception as e:
            logger.error(f"Error caching active proxies: {e}")

    def get_active_proxy_cache(self) -> Optional[list]:
        """Retrieve the cached list of active proxies"""
        try:
           key = "active_proxies_cache"
           value = self.client.get(key)
           if value:
               return json.loads(value)
           return None
        except Exception as e:
            logger.error(f"Error retrieving active proxy cache: {e}")
            return None

    def acquire_lock(self, lock_name: str, timeout: int = 10) -> bool:
        """Simple distributed lock using Redis"""
        try:
           return self.client.set(f"lock:{lock_name}", "1", nx=True, ex=timeout)
        except Exception as e:
            logger.error(f"Error acquiring lock {lock_name}: {e}")
            return False

    def release_lock(self, lock_name: str):
        """Release a distributed lock"""
        try:
           self.client.delete(f"lock:{lock_name}")
        except Exception as e:
            logger.error(f"Error releasing lock {lock_name}: {e}")

    def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Global Redis client instance
redis_client = RedisClient()
