#!/usr/bin/env python3
"""
Proxy Manager Worker
Periodically tests all proxies and updates their status in the database.
"""
import asyncio
import logging
import time
from datetime import datetime
from database import SessionLocal, Proxy as DBProxy

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_proxy(proxy_url: str) -> tuple[bool, str]:
    """Test a single proxy"""
    try:
        import requests
        proxies = {"http": proxy_url, "https": proxy_url}
        r = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10)
        if r.status_code == 200:
            return True, "Proxy working"
        else:
            return False, f"Unexpected status {r.status_code}"
    except Exception as ex:
        return False, str(ex)


async def test_all_proxies():
    """Test all proxies in the database"""
    try:
        logger.info("🔄 Starting proxy health check...")
        db = SessionLocal()
        try:
            proxies = db.query(DBProxy).all()
            
            for proxy in proxies:
                proxy_id = proxy.id
                proxy_url = proxy.url
                
                success, message = await test_proxy(proxy_url)
                
                # Update DB
                proxy.last_tested = datetime.utcnow()
                proxy.test_result = message
                proxy.is_active = success
                proxy.updated_at = datetime.utcnow()
                
                status = "✅ OK" if success else "❌ FAIL"
                logger.info(f"{status} Proxy {proxy_url}: {message}")
            
            db.commit()
            logger.info("✅ Proxy health check completed")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ Error in proxy health check: {e}")


async def main():
    """Main worker loop"""
    logger.info("🚀 Proxy Manager Worker started")
    
    while True:
        await test_all_proxies()
        # Wait 1 hour before next check
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())