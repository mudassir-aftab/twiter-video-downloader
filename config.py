"""Configuration management for Redis and RabbitMQ"""
import random
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
import logging

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # RabbitMQ Configuration
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"

    # Application Settings
    max_concurrent_downloads: int = 3
    task_ttl_seconds: int = 604800   # 7 days
    video_info_cache_ttl: int = 3600  # 1 hour

    # RabbitMQ Queue Names
    download_queue_name: str = "download_tasks"
    download_exchange_name: str = "downloads"

    # Rate limiting and anti-detection settings
    min_request_delay: float = 2.0
    max_request_delay: float = 5.0

    # Supabase Configuration for Admin
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    


settings = Settings()


# Supabase client for proxies (optional)
supabase_client = None
try:
    from supabase import create_client
    if settings.supabase_url and settings.supabase_anon_key:
        supabase_client = create_client(settings.supabase_url, settings.supabase_anon_key)
except ImportError:
    pass


# User Agent Rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.109 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0"
]


# Proxy Rotation (replace with real proxies in production)
PROXIES = [
    "http://user:pass@103.152.112.145:80",
    "http://user:pass@45.77.46.206:3128",
    "http://user:pass@159.65.69.186:9200",
    "http://user:pass@51.158.68.133:8811"
]


def get_random_proxy() -> str | None:
    """
    Return a random proxy or None.
    - Checks DB for admin-added proxies
    - Falls back to default PROXIES list
    - 50% chance direct connection, 50% proxy.
    """
    if random.random() < 0.5:
        return None
    
    admin_proxies = []
    
    # Try DB first
    try:
        from database import get_working_proxies
        proxies = get_working_proxies()
        if proxies:
            for p in proxies:
                if p.get("username") and p.get("password"):
                    admin_proxies.append(f"http://{p['username']}:{p['password']}@{p['ip']}:{p['port']}")
                else:
                    admin_proxies.append(f"http://{p['ip']}:{p['port']}")
    except Exception as e:
        logger.debug(f"Could not fetch proxies from DB: {e}")
    
    # Combine with default proxies
    all_proxies = list(set(admin_proxies + PROXIES))
    
    if all_proxies:
        return random.choice(all_proxies)
    
    return None


def get_random_user_agent() -> str:
    """Get a random user agent"""
    return random.choice(USER_AGENTS)


def get_random_delay() -> float:
    """Random delay between requests"""
    return random.uniform(settings.min_request_delay, settings.max_request_delay)


def get_redis_url() -> str:
    """Generate Redis connection URL"""
    if settings.redis_password:
        return f"redis://:{settings.redis_password}@{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
    return f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"


def get_rabbitmq_url() -> str:
    """Generate RabbitMQ connection URL"""
    return f"amqp://{settings.rabbitmq_user}:{settings.rabbitmq_password}@{settings.rabbitmq_host}:{settings.rabbitmq_port}/{settings.rabbitmq_vhost}"