import logging

from apscheduler.schedulers.background import BackgroundScheduler

import db
import fetcher

logger = logging.getLogger(__name__)

# (snapshot_type, fetch_function) pairs for all data sources
_SOURCES = [
    ("llms",           fetcher.fetch_llms),
    ("text-to-image",  fetcher.fetch_text_to_image),
    ("text-to-speech", fetcher.fetch_text_to_speech),
    ("text-to-video",  fetcher.fetch_text_to_video),
    ("image-to-video", fetcher.fetch_image_to_video),
]


def refresh_all():
    for snapshot_type, fetch_fn in _SOURCES:
        if db.get_snapshot(snapshot_type):
            logger.info("%s snapshot already up to date, skipping", snapshot_type)
            continue
        try:
            data = fetch_fn()
            db.save_snapshot(snapshot_type, data)
            logger.info("%s snapshot saved (%d models)", snapshot_type, data.get("total_models", 0))
        except Exception as e:
            logger.error("Failed to refresh %s: %s", snapshot_type, e)


def refresh_trmnl_ips():
    if db.get_trmnl_ips() is not None:
        logger.info("TRMNL IPs already up to date, skipping")
        return
    try:
        ips = fetcher.fetch_trmnl_ips()
        db.save_trmnl_ips(ips)
        logger.info("TRMNL IPs refreshed: %d entries", len(ips))
    except Exception as e:
        logger.error("Failed to refresh TRMNL IPs: %s", e)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh_trmnl_ips, "cron", hour=0, minute=1, id="trmnl_ips_refresh")
    scheduler.add_job(refresh_all, "cron", hour=0, minute=5, id="data_refresh")
    return scheduler
