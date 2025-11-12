"""
Scheduler for portfolio history snapshots

This module sets up background jobs to automatically create portfolio snapshots
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler = None


def create_daily_snapshot_job():
    """Job to create daily portfolio snapshots"""
    try:
        from services.portfolio_history_service import PortfolioHistoryService

        service = PortfolioHistoryService()
        result = service.create_daily_snapshots_for_all_users()
        logger.info(f"Daily snapshot job completed: {result}")

    except Exception as e:
        logger.error(f"Error in daily snapshot job: {str(e)}")


def start_history_scheduler():
    """
    Start the background scheduler for portfolio history

    Schedules:
    - Daily snapshots at midnight UTC
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("History scheduler already running")
        return _scheduler

    try:
        _scheduler = BackgroundScheduler(
            timezone=pytz.UTC,
            job_defaults={
                'coalesce': True,  # Combine missed runs
                'max_instances': 1,  # Only one instance at a time
                'misfire_grace_time': 3600  # Allow 1 hour grace period
            }
        )

        # Schedule daily snapshots at midnight UTC
        _scheduler.add_job(
            create_daily_snapshot_job,
            trigger=CronTrigger(hour=0, minute=0, timezone=pytz.UTC),
            id='daily_portfolio_snapshot',
            name='Create daily portfolio snapshots',
            replace_existing=True
        )

        _scheduler.start()
        logger.info("History scheduler started successfully")

        return _scheduler

    except Exception as e:
        logger.error(f"Failed to start history scheduler: {str(e)}")
        raise


def stop_history_scheduler():
    """Stop the background scheduler"""
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("History scheduler stopped")


def get_history_scheduler():
    """Get the scheduler instance"""
    return _scheduler


# Initialize scheduler on module import (for local development)
# In production (AWS Lambda), use EventBridge instead
try:
    import os
    if os.getenv('ENABLE_SCHEDULER', 'false').lower() == 'true':
        start_history_scheduler()
        logger.info("Auto-started history scheduler from environment variable")
except Exception as e:
    logger.warning(f"Could not auto-start scheduler: {str(e)}")
