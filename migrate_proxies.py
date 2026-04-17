import asyncio
import logging
from config import settings
from supabase import create_client, Client
from database import get_supabase, add_advanced_proxy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

new_proxies = [
    {"host": "31.59.20.176", "port": 6754, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "198.23.239.134", "port": 6540, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "45.38.107.97", "port": 6014, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "107.172.163.27", "port": 6543, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "198.105.121.200", "port": 6462, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "216.10.27.159", "port": 6837, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "142.111.67.146", "port": 5611, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "191.96.254.138", "port": 6185, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "31.58.9.4", "port": 6077, "username": "atjoplnk", "password": "g5so8c2amqv1"},
    {"host": "23.26.71.145", "port": 5628, "username": "atjoplnk", "password": "g5so8c2amqv1"},
]


async def migrate_proxies():
    """Manually seed the database with static proxies"""

    try:
        supabase = get_supabase()

        logger.info("🚀 Seeding 10 Premium Static Proxies into 'proxies' table...")

        for p in new_proxies:
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
                supabase.table("proxies") \
                    .upsert(p_data, on_conflict="host,port") \
                    .execute()

                logger.info(f"✅ Upserted Proxy: {p['host']}:{p['port']}")

            except Exception as ups_e:
                logger.error(f"❌ Failed to upsert {p['host']}:{p['port']} -> {ups_e}")

        # Final count check
        count_res = supabase.table("proxies").select("id", count="exact").execute()

        logger.info(f"🎉 Seed complete. Total proxies in DB: {count_res.count}")

    except Exception as e:
        logger.error(f"❌ Seeding failed at top level: {e}")


if __name__ == "__main__":
    asyncio.run(migrate_proxies())