import logging

from apscheduler.schedulers.background import BackgroundScheduler

import db
import fetcher

logger = logging.getLogger(__name__)


def refresh_llm_data():
    existing = db.get_snapshot("llms")
    if existing:
        logger.info("LLM snapshot already up to date for today, skipping fetch")
        return
    try:
        data = fetcher.fetch_llm_models()
        db.save_snapshot("llms", data)
        logger.info("LLM snapshot saved (%d models)", data.get("total_models", 0))
    except Exception as e:
        logger.error("Failed to refresh LLM data: %s", e)


def refresh_trmnl_ips():
    existing = db.get_trmnl_ips()
    if existing is not None:
        logger.info("TRMNL IPs already up to date for today, skipping fetch")
        return
    try:
        ips = fetcher.fetch_trmnl_ips()
        db.save_trmnl_ips(ips)
        logger.info("TRMNL IPs refreshed: %d entries", len(ips))
    except Exception as e:
        logger.error("Failed to refresh TRMNL IPs: %s", e)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    # Refresh data daily at 00:05 UTC
    scheduler.add_job(refresh_llm_data, "cron", hour=0, minute=5, id="llm_refresh")
    scheduler.add_job(refresh_trmnl_ips, "cron", hour=0, minute=1, id="trmnl_ips_refresh")
    return scheduler
