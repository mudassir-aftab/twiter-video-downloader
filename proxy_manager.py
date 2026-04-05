import random
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from database import get_working_proxies, update_proxy_metrics, log_proxy_event
from redis_client import redis_client

logger = logging.getLogger(__name__)

class ProxyManager:
    """
    High-Scale Intelligent Proxy Management System
    Handles multi-provider routing, scoring, and self-healing.
    """

    def __init__(self):
        self.cooldown_duration = 30  # Default cooldown in seconds
        self.retry_limit = 5
        self.fail_threshold = 10     # Auto-disable after 10 fails if success rate is low

    def get_best_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Selects the best available proxy based on scoring and routing rules.
        1. Always tries OXYLABS first.
        2. Filter out proxies on cooldown via Redis.
        3. Use weighted scoring system.
        """
        # Try to get from cache first
        proxies = redis_client.get_active_proxy_cache()
        if not proxies:
            proxies = get_working_proxies()
            if proxies:
                redis_client.set_active_proxy_cache(proxies)
        
        if not proxies:
            logger.warning("No active proxies found in database.")
            return None

        # Filter out proxies on cooldown
        available_proxies = [p for p in proxies if not redis_client.is_proxy_on_cooldown(p['id'])]
        
        if not available_proxies:
            logger.warning("All proxies are currently on cooldown. Falling back to all (forced reuse).")
            available_proxies = proxies

        # Calculate scores
        scored_proxies = []
        for p in available_proxies:
            # priority_weight: High (1) = 1.0, Medium (2) = 0.5, Low (3) = 0.0
            # Fallback to 1.0 if not present
            p_priority = p.get('priority_level', 1) 
            p_weight = 1.0 if p_priority == 1 else (0.5 if p_priority == 2 else 0.0)
            
            # Score formula: (S+1)/(F+1) - (RT * 0.01) + Weight
            s_count = p.get('success_count', 0) or 0
            f_count = p.get('fail_count', 0) or 0
            avg_rt = p.get('avg_response_time', 0) or 0
            
            score = (s_count + 1) / (f_count + 1) - (avg_rt * 0.01) + p_weight
            
            # Add provider boost (Oxylabs priority)
            if p.get('provider_name') == 'OXYLABS':
                score += 2.0
                
            scored_proxies.append((score, p))

        # Sort by score descending
        scored_proxies.sort(key=lambda x: x[0], reverse=True)
        
        # Pick the best one (or top 3 randomly to avoid extreme hot-spotting)
        best_p = scored_proxies[0][1] if scored_proxies else None
        
        if best_p:
            # Put on cooldown instantly to avoid duplicate usage in parallel tasks
            redis_client.set_proxy_cooldown(best_p['id'], self.cooldown_duration)
            
        return best_p

    def format_proxy_url(self, proxy: Dict[str, Any]) -> str:
        """Converts proxy dict to standard URI format"""
        auth = ""
        if proxy.get('username') and proxy.get('password'):
            auth = f"{proxy['username']}:{proxy['password']}@"
        
        return f"http://{auth}{proxy['host']}:{proxy['port']}"

    async def report_result(self, proxy: Dict[str, Any], url: str, success: bool, response_time: float, error: str = None):
        """Logs the result of a proxy usage and updates metrics"""
        status = "success" if success else ("banned" if "429" in str(error) or "403" in str(error) else "fail")
        
        # 1. Update DB metrics
        update_proxy_metrics(proxy['id'], success, response_time, status if not success else "active")
        
        # 2. Log event
        log_proxy_event(
            proxy_id=proxy['id'],
            provider=proxy['provider_name'],
            url=url,
            status=status,
            response_time=response_time,
            error=error
        )
        
        # 3. Self-healing logic
        if not success:
            # If fail count is high and success rate is low, could auto-disable here
            # For now, we rely on the scoring system to naturally deprioritize it
            pass

    async def test_proxy(self, proxy: Dict[str, Any]) -> Dict[str, Any]:
        """Test a specific proxy via ipify and return detailed diagnostics"""
        proxy_url = self.format_proxy_url(proxy)
        test_target = "https://api.ipify.org?format=json"
        start_time = time.time()
        
        try:
            import httpx
            async with httpx.AsyncClient(proxies=proxy_url, timeout=12.0) as client:
                resp = await client.get(test_target)
                duration = (time.time() - start_time) * 1000 # ms
                
                if resp.status_code == 200:
                    ip_data = resp.json()
                    return {
                        "success": True,
                        "status": "active",
                        "status_code": resp.status_code,
                        "ip": ip_data.get("ip"),
                        "latency": f"{duration:.0f}ms",
                        "provider": proxy.get('provider_name', 'STATIC'),
                        "target": test_target,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    return {
                        "success": False, 
                        "status": "error",
                        "status_code": resp.status_code,
                        "error": f"HTTP {resp.status_code}",
                        "latency": f"{duration:.0f}ms",
                        "target": test_target
                    }
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return {
                "success": False, 
                "status": "dead",
                "error": str(e), 
                "latency": f"{duration:.0f}ms",
                "target": test_target
            }

# Global instance
proxy_manager = ProxyManager()
