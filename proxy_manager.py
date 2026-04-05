import random
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

import httpx

from database import (
    get_working_proxies,
    update_proxy_metrics as db_update_proxy_metrics,
    log_proxy_event as db_log_proxy_event,
    get_supabase
)

from redis_client import redis_client

logger = logging.getLogger(__name__)


class ProxyManager:

    def __init__(self):
        self.cooldown_duration = 30
        self.retry_limit = 3

    # -----------------------------
    # GET BEST PROXY
    # -----------------------------
    def get_best_proxy(self) -> Optional[Dict[str, Any]]:
        try:
            # 1. Redis cache
            proxies = redis_client.get_active_proxy_cache()

            # 2. DB fallback
            if not proxies:
                proxies = get_working_proxies()
                if proxies:
                    redis_client.set_active_proxy_cache(proxies)

            if not proxies:
                logger.warning("⚠️ No proxies found → using DIRECT mode")
                return None

            # 3. filter cooldown + dead
            available = []
            for p in proxies:
                if not p:
                    continue

                if p.get("status", "").lower() in ["dead", "banned"]:
                    continue

                if redis_client.is_proxy_on_cooldown(p.get("id")):
                    continue

                available.append(p)

            if not available:
                available = proxies  # fallback

            # 4. scoring system (stable version)
            scored = []

            for p in available:
                success = p.get("success_count") or 0
                fail = p.get("fail_count") or 0
                speed = p.get("avg_response_time") or 0

                # avoid divide crash + stabilize score
                score = (success + 1) * 2 - (fail * 2) - (speed * 0.01)

                scored.append((score, p))

            scored.sort(key=lambda x: x[0], reverse=True)

            best = scored[0][1] if scored else None

            if best:
                redis_client.set_proxy_cooldown(best["id"], self.cooldown_duration)

            return best

        except Exception as e:
            logger.error(f"Proxy selection error: {e}")
            return None

    # -----------------------------
    # FORMAT PROXY URL
    # -----------------------------
    def format_proxy_url(self, proxy: Dict[str, Any]) -> Optional[str]:
        try:
            if not proxy:
                return None

            auth = ""
            if proxy.get("username") and proxy.get("password"):
                auth = f"{proxy['username']}:{proxy['password']}@"

            ip = (
                proxy.get("ip")
                or proxy.get("proxy_ip")
                or proxy.get("host")
            )

            port = proxy.get("port")

            if not ip or not port:
                return None

            return f"http://{auth}{ip}:{port}"

        except Exception as e:
            logger.error(f"Proxy format error: {e}")
            return None

    # -----------------------------
    # UPDATE METRICS (SAFE + SMOOTHING)
    # -----------------------------
    def update_proxy_metrics(
        self,
        proxy_id: str,
        success: bool,
        response_time: float,
        status: str = "active"
    ):
        try:
            supabase = get_supabase()

            data = supabase.table("proxies") \
                .select("success_count, fail_count, avg_response_time") \
                .eq("id", proxy_id) \
                .single() \
                .execute() \
                .data

            data = data or {}

            success_count = data.get("success_count") or 0
            fail_count = data.get("fail_count") or 0
            old_avg = data.get("avg_response_time") or 0

            # exponential moving average (IMPORTANT FIX)
            new_avg = (
                (old_avg * 0.7) + (response_time * 0.3)
                if old_avg else response_time
            )

            update_data = {
                "avg_response_time": new_avg,
                "last_used_at": datetime.utcnow().isoformat(),
                "status": status
            }

            if success:
                update_data["success_count"] = success_count + 1
            else:
                update_data["fail_count"] = fail_count + 1

            db_update_proxy_metrics(proxy_id, update_data)

        except Exception as e:
            logger.error(f"Metrics update error: {e}")

    # -----------------------------
    # LOG EVENT
    # -----------------------------
    def log_proxy_event(
        self,
        proxy_id: str,
        provider: str,
        url: str,
        status: str,
        response_time: float,
        error: str = None
    ):
        try:
            db_log_proxy_event({
                "proxy_id": proxy_id,
                "provider": provider,
                "url": url,
                "status": status,
                "response_time": response_time,
                "error": error,
                "created_at": datetime.utcnow().isoformat()
            })

        except Exception as e:
            logger.error(f"Proxy event log error: {e}")

    # -----------------------------
    # REPORT RESULT (MAIN FLOW)
    # -----------------------------
    async def report_result(
        self,
        proxy: Dict[str, Any],
        url: str,
        success: bool,
        response_time: float,
        error: str = None
    ):
        try:
            if not proxy:
                return

            # detect ban
            status = "success"

            if not success:
                if error and ("429" in str(error) or "403" in str(error) or "402" in str(error)):
                    status = "banned"
                else:
                    status = "fail"

            self.update_proxy_metrics(
                proxy_id=proxy["id"],
                success=success,
                response_time=response_time,
                status="active" if success else status
            )

            self.log_proxy_event(
                proxy_id=proxy["id"],
                provider=proxy.get("provider_name", "STATIC"),
                url=url,
                status=status,
                response_time=response_time,
                error=error
            )

        except Exception as e:
            logger.error(f"Report result error: {e}")

    # -----------------------------
    # TEST PROXY (FIXED httpx)
    # -----------------------------
    async def test_proxy(self, proxy: Dict[str, Any]) -> Dict[str, Any]:
        proxy_url = self.format_proxy_url(proxy)
        test_url = "https://api.ipify.org?format=json"

        start = time.time()

        try:
            # FIX: httpx proxy format (new correct way)
            async with httpx.AsyncClient(
                proxies={
                    "http://": proxy_url,
                    "https://": proxy_url
                } if proxy_url else None,
                timeout=10.0
            ) as client:

                r = await client.get(test_url)

            duration = (time.time() - start) * 1000

            if r.status_code == 200:
                return {
                    "success": True,
                    "status": "active",
                    "ip": r.json().get("ip"),
                    "latency": f"{duration:.0f}ms"
                }

            return {
                "success": False,
                "status": "failed",
                "error": f"HTTP {r.status_code}"
            }

        except Exception as e:
            return {
                "success": False,
                "status": "dead",
                "error": str(e)
            }


# GLOBAL INSTANCE
proxy_manager = ProxyManager()