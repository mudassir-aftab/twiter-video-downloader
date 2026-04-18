import logging
from datetime import datetime
from config import supabase_client, supabase_service_client

logger = logging.getLogger(__name__)


# -----------------------------
# SUPABASE CLIENT
# -----------------------------
def get_supabase(use_service_role: bool = False):
    """Return the correct Supabase client.

    Use the service role client for backend writes when available,
    which avoids PostgreSQL RLS insert failures for server-side logs.
    """
    if use_service_role and supabase_service_client:
        return supabase_service_client

    if supabase_client:
        return supabase_client

    if supabase_service_client:
        return supabase_service_client

    raise ValueError("Supabase client is not initialized. Check .env config")


# -----------------------------
# PROXIES
# -----------------------------
def get_all_proxies():
    try:
        res = get_supabase().table("proxies").select("*").execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error fetching proxies: {e}")
        return []


def get_working_proxies():
    try:
        res = get_supabase().table("proxies").select("*").execute()
        proxies = res.data or []

        return [
            p for p in proxies
            if p.get("status", "").lower() in ["active", "slow"]
        ]

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
            "status": "active",
            "success_count": 0,
            "fail_count": 0,
            "avg_response_time": 0,
            "created_at": datetime.utcnow().isoformat()
        }

        res = get_supabase(use_service_role=True).table("proxies").insert(data).execute()
        return res.data or None

    except Exception as e:
        logger.error(f"Error adding proxy: {e}")
        return None


def update_proxy_status(proxy_id: str, status: str, response_time: int = 0, is_failure: bool = False):
    try:
        supabase = get_supabase(use_service_role=True)

        current = supabase.table("proxies") \
            .select("success_count, fail_count") \
            .eq("id", proxy_id) \
            .single() \
            .execute() \
            .data

        current = current or {}

        success_count = current.get("success_count", 0)
        fail_count = current.get("fail_count", 0)

        update_data = {
            "status": status,
            "avg_response_time": response_time,
            "last_checked_at": datetime.utcnow().isoformat()
        }

        if is_failure:
            update_data["fail_count"] = fail_count + 1
        else:
            update_data["success_count"] = success_count + 1

        supabase.table("proxies").update(update_data).eq("id", proxy_id).execute()
        return True

    except Exception as e:
        logger.error(f"Error updating proxy status: {e}")
        return False


def delete_proxy(proxy_id: str):
    try:
        get_supabase(use_service_role=True).table("proxies").delete().eq("id", proxy_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error deleting proxy: {e}")
        return False


# -----------------------------
# LOGGING
# -----------------------------
def log_download(
    twitter_url: str,
    status: str,
    proxy_used: str = None,
    file_size: int = 0,
    processing_time: int = 0,
    user_ip: str = None
):
    try:
        data = {
            "twitter_url": twitter_url,
            "proxy_used": proxy_used,
            "status": status,
            "file_size": file_size,
            "processing_time": processing_time,
            "user_ip": user_ip,
            "created_at": datetime.utcnow().isoformat()
        }

        get_supabase(use_service_role=True).table("download_logs").insert(data).execute()

    except Exception as e:
        logger.error(f"Error logging download: {e}")


def log_error(error_type: str, error_message: str, source: str = None):
    try:
        data = {
            "error_type": error_type,
            "error_message": error_message,
            "source": source,
            "created_at": datetime.utcnow().isoformat()
        }

        get_supabase(use_service_role=True).table("errors").insert(data).execute()

    except Exception as e:
        logger.error(f"Error logging error: {e}")


# -----------------------------
# SETTINGS & SECURITY
# -----------------------------
def get_system_settings():
    try:
        res = get_supabase().table("system_settings").select("*").execute()
        data = res.data or []

        return {
            item["setting_name"]: item["setting_value"]
            for item in data
        }

    except Exception as e:
        logger.error(f"Error fetching system settings: {e}")
        return {}


def is_blocked(block_type: str, block_value: str) -> bool:
    try:
        res = get_supabase().table("security_blocks") \
            .select("id") \
            .eq("block_type", block_type) \
            .eq("block_value", block_value) \
            .limit(1) \
            .execute()

        return bool(res.data)

    except Exception as e:
        logger.error(f"Error checking security blocks: {e}")
        return False


# -----------------------------
# PROXY METRICS & EVENTS
# -----------------------------
def update_proxy_metrics(proxy_id: str, update_data: dict):
    try:
        get_supabase(use_service_role=True).table("proxies") \
            .update(update_data) \
            .eq("id", proxy_id) \
            .execute()

        return True

    except Exception as e:
        logger.error(f"Error updating proxy metrics: {e}")
        return False


def log_proxy_event(event_data: dict):
    try:
        # Map to correct column names
        mapped_data = {
            "proxy_id": event_data.get("proxy_id"),
            "provider_name": event_data.get("provider"),
            "request_url": event_data.get("url"),
            "status": event_data.get("status"),
            "response_time": event_data.get("response_time"),
            "error_message": event_data.get("error"),
            "created_at": event_data.get("created_at")
        }
        get_supabase(use_service_role=True).table("proxy_logs") \
            .insert(mapped_data) \
            .execute()

        return True

    except Exception as e:
        logger.error(f"Error logging proxy event: {e}")
        return False


# -----------------------------
# ADVANCED PROXY
# -----------------------------
def add_advanced_proxy(
    ip: str,
    port: int,
    username: str = None,
    password: str = None,
    provider: str = None,
    priority_level: int = 1,
    status: str = "active"
):
    try:
        data = {
            "ip": ip,
            "port": port,
            "username": username,
            "password": password,
            "provider_name": provider,
            "priority_level": priority_level,
            "status": status,
            "success_count": 0,
            "fail_count": 0,
            "avg_response_time": 0,
            "created_at": datetime.utcnow().isoformat()
        }

        res = get_supabase(use_service_role=True).table("proxies").insert(data).execute()
        return res.data or None

    except Exception as e:
        logger.error(f"Error adding advanced proxy: {e}")
        return None