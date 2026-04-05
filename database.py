import os
import logging
from datetime import datetime
from config import supabase_client

logger = logging.getLogger(__name__)

def get_supabase():
    """Returns the initialized Supabase client."""
    if not supabase_client:
        raise ValueError("Supabase client is not initialized. Check your .env configuration.")
    return supabase_client

# --- Proxy Operations ---

def get_all_proxies():
    try:
        res = get_supabase().table("proxies").select("*").execute()
        return res.data
    except Exception as e:
        logger.error(f"Error fetching proxies: {e}")
        return []

def get_working_proxies():
    try:
        res = get_supabase().table("proxies").select("*").eq("status", "active").execute()
        return res.data
    except Exception as e:
        logger.error(f"Error fetching active proxies: {e}")
        return []

def add_proxy(ip: str, port: int, username: str = None, password: str = None):
    try:
        data = {
            "ip": ip,
            "port": port,
            "username": username,
            "password": password,
            "status": "active"
        }
        res = get_supabase().table("proxies").insert(data).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error adding proxy: {e}")
        return None

def update_proxy_status(proxy_id: str, status: str, response_time: int = 0, is_failure: bool = False):
    try:
        update_data = {
            "status": status,
            "response_time": response_time,
            "last_checked": datetime.utcnow().isoformat()
        }
        
        # We need to fetch current counts to increment, but Supabase RPC is better.
        # For simplicity, we just update status and time here if we don't have RPC.
        # More advanced: use RPC to increment usage_count/failure_count
        get_supabase().table("proxies").update(update_data).eq("id", proxy_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error updating proxy status: {e}")
        return False

def delete_proxy(proxy_id: str):
    try:
        get_supabase().table("proxies").delete().eq("id", proxy_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error deleting proxy: {e}")
        return False

# --- Logging Operations ---

def log_download(twitter_url: str, status: str, proxy_used: str = None, file_size: int = 0, processing_time: int = 0, user_ip: str = None):
    try:
        data = {
            "twitter_url": twitter_url,
            "proxy_used": proxy_used,
            "status": status,
            "file_size": file_size,
            "processing_time": processing_time,
            "user_ip": user_ip
        }
        get_supabase().table("download_logs").insert(data).execute()
    except Exception as e:
        logger.error(f"Error logging download: {e}")

def log_error(error_type: str, error_message: str, source: str = None):
    try:
        data = {
            "error_type": error_type,
            "error_message": error_message,
            "source": source
        }
        get_supabase().table("errors").insert(data).execute()
    except Exception as e:
        logger.error(f"Error logging error: {e}")

# --- Settings & Security ---

def get_system_settings():
    try:
        res = get_supabase().table("system_settings").select("*").execute()
        return {item["setting_name"]: item["setting_value"] for item in res.data}
    except Exception as e:
        logger.error(f"Error fetching system settings: {e}")
        return {}

def is_blocked(block_type: str, block_value: str) -> bool:
    try:
        res = get_supabase().table("security_blocks").select("*").eq("block_type", block_type).eq("block_value", block_value).execute()
        return len(res.data) > 0
    except Exception as e:
        logger.error(f"Error checking security blocks: {e}")
        return False