import asyncio
import logging
from config import settings
from supabase import create_client, Client
from database import get_supabase, add_advanced_proxy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_proxies():
    """Manually seed the database with the requested 10 static proxies"""
    
    # 1. New Hardcoded 10 Proxies List
    new_proxies = [
        { "host": "31.59.20.176", "port": 6754, "username": "gblilwji", "password": "5sgduge4k7s8", "country": "UK", "city": "London", "status": "active" },
        { "host": "23.95.150.145", "port": 6114, "username": "gblilwji", "password": "5sgduge4k7s8", "country": "US", "city": "Buffalo", "status": "active" },
        { "host": "198.23.239.134", "port": 6540, "username": "gblilwji", "password": "5sgduge4k7s8", "country": "US", "city": "Buffalo", "status": "active" },
        { "host": "45.38.107.97", "port": 6014, "username": "gblilwji", "password": "5sgduge4k7s8", "country": "UK", "city": "London", "status": "active" },
        { "host": "107.172.163.27", "port": 6543, "username": "gblilwji", "password": "5sgduge4k7s8", "country": "US", "city": "Bloomingdale", "status": "active" },
        { "host": "198.105.121.200", "port": 6462, "username": "gblilwji", "password": "5sgduge4k7s8", "country": "UK", "city": "City of London", "status": "active" },
        { "host": "216.10.27.159", "port": 6837, "username": "gblilwji", "password": "5sgduge4k7s8", "country": "US", "city": "Dallas", "status": "active" },
        { "host": "142.111.67.146", "port": 5611, "username": "gblilwji", "password": "5sgduge4k7s8", "country": "JP", "city": "Tokyo", "status": "active" },
        { "host": "191.96.254.138", "port": 6185, "username": "gblilwji", "password": "5sgduge4k7s8", "country": "US", "city": "Los Angeles", "status": "active" },
        { "host": "31.58.9.4", "port": 6077, "username": "gblilwji", "password": "5sgduge4k7s8", "country": "DE", "city": "Frankfurt", "status": "active" }
    ]
    
    try:
        supabase = get_supabase()
        
        logger.info("🚀 Seeding 10 Premium Static Proxies into 'proxies' table...")
        
        for p in new_proxies:
            # MINIMAL data required to avoid schema errors
            p_data = {
                "host": p["host"],
                "port": p["port"],
                "username": p["username"],
                "password": p["password"],
                "country": p.get("country"),
                "city": p.get("city"),
                "status": "active",
                "provider_name": "WEBSHARE",
                "type": "static"
            }
            
            try:
                # Upsert based on (host, port) 
                res = supabase.table("proxies").upsert(p_data, on_conflict="host,port").execute()
                logger.info(f"✅ Upserted Proxy: {p['host']}:{p['port']}")
            except Exception as ups_e:
                logger.error(f"❌ Failed to upsert {p['host']}: {ups_e}")

        # Final check
        count_res = supabase.table("proxies").select("id", count="exact").execute()
        logger.info(f"🎉 Seed complete. Total proxies in DB: {count_res.count}")
        
    except Exception as e:
        logger.error(f"❌ Seeding failed at top level: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_proxies())
