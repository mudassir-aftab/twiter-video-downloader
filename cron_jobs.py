import asyncio
import os
import time
import httpx
import shutil
import logging
import subprocess
from datetime import datetime

from config import settings
from database import get_all_proxies, update_proxy_metrics, log_error, get_supabase, add_advanced_proxy, log_proxy_event

logger = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.getcwd(), "temp")
DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")

async def update_yt_dlp():
    """Update yt-dlp every 1 hour (3600 seconds)"""
    while True:
        try:
            logger.info("Running scheduled yt-dlp update...")
            # Run pip install -U yt-dlp
            result = subprocess.run(["pip", "install", "-U", "yt-dlp"], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("yt-dlp updated successfully.")
            else:
                logger.error(f"Failed to update yt-dlp: {result.stderr}")
                log_error("yt-dlp", f"Update failed: {result.stderr}", "cron_yt_dlp")
        except Exception as e:
            logger.error(f"Error in yt-dlp updater cron: {e}")
            log_error("yt-dlp", f"Update process error: {str(e)}", "cron_yt_dlp")
            
        await asyncio.sleep(3600)

async def check_proxies():
    """Check all proxies every 10 minutes (600 seconds)"""
    while True:
        try:
            logger.info("Running scheduled proxy health checks...")
            proxies = get_all_proxies()
            if not proxies:
                logger.debug("No proxies to check.")
                await asyncio.sleep(600)
                continue

            for proxy in proxies:

                    proxy_url = ""
                    if proxy.get("username") and proxy.get("password"):
                        proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['host']}:{proxy['port']}"
                    else:
                        proxy_url = f"http://{proxy['host']}:{proxy['port']}"
                    
                    start_time = time.time()
                    proxy_status = "active"
                    try:
                        async with httpx.AsyncClient(proxy=proxy_url, timeout=10.0) as client:
                            resp = await client.get("https://httpbin.org/ip")
                            resp.raise_for_status()
                    except Exception as e:
                        proxy_status = "dead"
                        host_display = proxy.get('host', 'unknown-host')
                        logger.warning(f"Proxy {host_display} failed check: {e}")
                    
                    response_time = int((time.time() - start_time) * 1000)
                    is_failure = proxy_status == "dead"
                    
                    # Update DB using advanced metrics
                    try:
                        update_proxy_metrics(
                            proxy_id=proxy["id"], 
                            success=not is_failure, 
                            response_time=float(response_time), 
                            status=proxy_status
                        )
                        
                        # Log the event
                        log_proxy_event(
                            proxy_id=proxy["id"],
                            provider=proxy.get("provider_name", "UNKNOWN"),
                            url="https://httpbin.org/ip",
                            status="success" if not is_failure else "fail",
                            response_time=float(response_time),
                            error=str(e) if is_failure else None
                        )
                    except Exception as db_e:
                        logger.error(f"Failed to update proxy status in DB: {db_e}")

        except Exception as e:
            logger.error(f"Error in proxy checker cron: {e}")
            
        await asyncio.sleep(600)

async def cleanup_temp_folder():
    """Scheduled cleanup of temporary and downloaded files to prevent disk bloating."""
    while True:
        try:
            logger.debug("Running scheduled file cleanup...")
            for directory in [TEMP_DIR, DOWNLOADS_DIR]:
                if os.path.exists(directory):
                    for filename in os.listdir(directory):
                        file_path = os.path.join(directory, filename)
                        try:
                            # 1. Handle Files (Only delete if older than 1 hour)
                            if os.path.isfile(file_path):
                                if time.time() - os.path.getmtime(file_path) > 3600:
                                    os.remove(file_path)
                                    logger.info(f"🗑️ Cron auto-wiped old file: {filename}")
                                    
                            # 2. Handle Directories (Older than 1 hour)
                            elif os.path.isdir(file_path):
                                if time.time() - os.path.getmtime(file_path) > 3600:
                                    shutil.rmtree(file_path)
                                    logger.info(f"🗑️ Cron auto-wiped old task directory: {filename}")
                        except Exception as e:
                            logger.error(f"Failed to delete {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error in file cleanup cron: {e}")
            
        await asyncio.sleep(600) # Run every 10 minutes

async def fetch_free_proxies_cron():
    """Logic to fetch free proxies has been DISABLED to maintain premium status."""
    logger.info("ℹ️ Free Proxy Scraper is currently disabled as requested.")
    while True:
        await asyncio.sleep(86400)


def start_cron_jobs(app):
    """Schedule the cron jobs on the main asyncio event loop."""
    @app.on_event("startup")
    async def startup_event():
        loop = asyncio.get_event_loop()
        loop.create_task(update_yt_dlp())
        loop.create_task(check_proxies())
        loop.create_task(cleanup_temp_folder())
        loop.create_task(fetch_free_proxies_cron())
        logger.info("Cron jobs started successfully.")
