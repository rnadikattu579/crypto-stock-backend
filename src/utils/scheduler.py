import logging
from datetime import datetime, time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from typing import Optional
import pytz

from services.notification_service import NotificationService
from services.portfolio_service import PortfolioService

logger = logging.getLogger(__name__)


class NotificationScheduler:
    """Background scheduler for sending notifications"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.notification_service = NotificationService()
        self.portfolio_service = PortfolioService()

    def start(self):
        """Start the scheduler"""
        # Daily digest job - runs every day at 8 AM
        self.scheduler.add_job(
            func=self.send_daily_digests,
            trigger=CronTrigger(hour=8, minute=0, timezone=pytz.UTC),
            id='daily_digest',
            name='Send daily portfolio digests',
            replace_existing=True
        )

        # Weekly report job - runs every Monday at 9 AM
        self.scheduler.add_job(
            func=self.send_weekly_reports,
            trigger=CronTrigger(day_of_week='mon', hour=9, minute=0, timezone=pytz.UTC),
            id='weekly_report',
            name='Send weekly portfolio reports',
            replace_existing=True
        )

        # Price alert checker - runs every 5 minutes
        self.scheduler.add_job(
            func=self.check_price_alerts,
            trigger=IntervalTrigger(minutes=5),
            id='price_alert_checker',
            name='Check price alerts',
            replace_existing=True
        )

        # Large movement checker - runs every 15 minutes
        self.scheduler.add_job(
            func=self.check_large_movements,
            trigger=IntervalTrigger(minutes=15),
            id='large_movement_checker',
            name='Check for large portfolio movements',
            replace_existing=True
        )

        # Milestone checker - runs every 30 minutes
        self.scheduler.add_job(
            func=self.check_milestones,
            trigger=IntervalTrigger(minutes=30),
            id='milestone_checker',
            name='Check portfolio milestones',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Notification scheduler started")

    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Notification scheduler stopped")

    def send_daily_digests(self):
        """Send daily digest to all users who have it enabled"""
        logger.info("Starting daily digest job")
        try:
            # Get all users with daily digest enabled
            # This is a simplified version - in production, you'd query all users
            users = self._get_users_with_notification_enabled('daily_digest_enabled')

            sent_count = 0
            for user_id in users:
                try:
                    # Get portfolio summary for user
                    portfolio_summary = self.portfolio_service.get_portfolio_summary(user_id)

                    # Prepare digest data
                    digest_data = {
                        'user_name': portfolio_summary.get('user_name', 'there'),
                        'total_value': f"${portfolio_summary.get('total_value', 0):,.2f}",
                        'total_change_24h': f"{portfolio_summary.get('change_24h', 0):+.2f}%",
                        'crypto_value': f"${portfolio_summary.get('crypto_value', 0):,.2f}",
                        'stock_value': f"${portfolio_summary.get('stock_value', 0):,.2f}",
                        'top_performer': portfolio_summary.get('top_performer', 'N/A'),
                        'date': datetime.utcnow().strftime('%B %d, %Y'),
                    }

                    # Send digest
                    success = self.notification_service.send_daily_digest(user_id, digest_data)
                    if success:
                        sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending daily digest to user {user_id}: {str(e)}")
                    continue

            logger.info(f"Daily digest job completed. Sent to {sent_count} users.")
        except Exception as e:
            logger.error(f"Error in daily digest job: {str(e)}")

    def send_weekly_reports(self):
        """Send weekly report to all users who have it enabled"""
        logger.info("Starting weekly report job")
        try:
            users = self._get_users_with_notification_enabled('weekly_report_enabled')

            sent_count = 0
            for user_id in users:
                try:
                    # Get weekly portfolio data
                    weekly_data = self.portfolio_service.get_weekly_report(user_id)

                    # Send report
                    success = self.notification_service.send_weekly_report(user_id, weekly_data)
                    if success:
                        sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending weekly report to user {user_id}: {str(e)}")
                    continue

            logger.info(f"Weekly report job completed. Sent to {sent_count} users.")
        except Exception as e:
            logger.error(f"Error in weekly report job: {str(e)}")

    def check_price_alerts(self):
        """Check all active price alerts and send notifications"""
        logger.info("Checking price alerts")
        try:
            # Get all active alerts
            # This is simplified - in production, query all alerts from database
            alerts = self._get_active_alerts()

            triggered_count = 0
            for alert in alerts:
                try:
                    user_id = alert['user_id']
                    asset_name = alert['asset_name']
                    alert_type = alert['alert_type']  # 'above' or 'below'
                    threshold = alert['threshold']

                    # Get current price
                    current_price = self._get_current_price(alert['asset_id'])

                    # Check if alert is triggered
                    if alert_type == 'above' and current_price >= threshold:
                        self.notification_service.send_price_alert(
                            user_id=user_id,
                            asset_name=asset_name,
                            current_price=current_price,
                            alert_type='crossed above',
                            threshold=threshold
                        )
                        triggered_count += 1
                    elif alert_type == 'below' and current_price <= threshold:
                        self.notification_service.send_price_alert(
                            user_id=user_id,
                            asset_name=asset_name,
                            current_price=current_price,
                            alert_type='crossed below',
                            threshold=threshold
                        )
                        triggered_count += 1
                except Exception as e:
                    logger.error(f"Error checking alert: {str(e)}")
                    continue

            if triggered_count > 0:
                logger.info(f"Price alerts checked. {triggered_count} alerts triggered.")
        except Exception as e:
            logger.error(f"Error in price alert checker: {str(e)}")

    def check_large_movements(self):
        """Check for large portfolio movements (>5% in 24h)"""
        logger.info("Checking for large movements")
        try:
            users = self._get_users_with_notification_enabled('large_movement_enabled')

            notified_count = 0
            for user_id in users:
                try:
                    # Get 24h portfolio change
                    change_24h = self.portfolio_service.get_24h_change(user_id)

                    if abs(change_24h) >= 5.0:
                        # Send notification
                        direction = "increased" if change_24h > 0 else "decreased"
                        data = {
                            'title': 'Large Portfolio Movement',
                            'change_percentage': f"{abs(change_24h):.2f}%",
                            'direction': direction,
                            'content': f"""
                                <h2>Significant Portfolio Movement Detected</h2>
                                <p>Your portfolio has {direction} by <strong>{abs(change_24h):.2f}%</strong>
                                   in the last 24 hours.</p>
                            """
                        }

                        self.notification_service.send_notification(
                            user_id=user_id,
                            notification_type='large_movement',
                            subject=f"Large Movement Alert: {direction.title()} {abs(change_24h):.2f}%",
                            template_name='large_movement',
                            data=data
                        )
                        notified_count += 1
                except Exception as e:
                    logger.error(f"Error checking movement for user {user_id}: {str(e)}")
                    continue

            if notified_count > 0:
                logger.info(f"Large movement check completed. {notified_count} notifications sent.")
        except Exception as e:
            logger.error(f"Error in large movement checker: {str(e)}")

    def check_milestones(self):
        """Check for portfolio milestones"""
        logger.info("Checking portfolio milestones")
        try:
            users = self._get_users_with_notification_enabled('milestone_enabled')

            notified_count = 0
            milestones = [1000, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000]

            for user_id in users:
                try:
                    # Get current portfolio value
                    portfolio_value = self.portfolio_service.get_total_value(user_id)

                    # Check if any milestone was recently crossed
                    last_checked_value = self._get_last_milestone_check(user_id)

                    for milestone in milestones:
                        if last_checked_value < milestone <= portfolio_value:
                            # Milestone crossed!
                            self.notification_service.send_milestone_notification(
                                user_id=user_id,
                                milestone_type='portfolio_value',
                                milestone_value=milestone
                            )
                            notified_count += 1
                            self._update_last_milestone_check(user_id, portfolio_value)
                            break
                except Exception as e:
                    logger.error(f"Error checking milestones for user {user_id}: {str(e)}")
                    continue

            if notified_count > 0:
                logger.info(f"Milestone check completed. {notified_count} milestones reached.")
        except Exception as e:
            logger.error(f"Error in milestone checker: {str(e)}")

    # Helper methods (simplified - implement properly in production)
    def _get_users_with_notification_enabled(self, preference_field: str) -> list:
        """Get all users with a specific notification preference enabled"""
        # In production, query DynamoDB for users with this preference
        # For now, return empty list
        return []

    def _get_active_alerts(self) -> list:
        """Get all active price alerts"""
        # In production, query DynamoDB for active alerts
        return []

    def _get_current_price(self, asset_id: str) -> float:
        """Get current price for an asset"""
        # In production, call price service
        return 0.0

    def _get_last_milestone_check(self, user_id: str) -> float:
        """Get the portfolio value at last milestone check"""
        # In production, retrieve from database
        return 0.0

    def _update_last_milestone_check(self, user_id: str, value: float):
        """Update the last milestone check value"""
        # In production, save to database
        pass


# Global scheduler instance
notification_scheduler: Optional[NotificationScheduler] = None


def get_scheduler() -> NotificationScheduler:
    """Get or create the global scheduler instance"""
    global notification_scheduler
    if notification_scheduler is None:
        notification_scheduler = NotificationScheduler()
    return notification_scheduler


def start_scheduler():
    """Start the notification scheduler"""
    scheduler = get_scheduler()
    scheduler.start()
    return scheduler


def stop_scheduler():
    """Stop the notification scheduler"""
    global notification_scheduler
    if notification_scheduler:
        notification_scheduler.stop()
        notification_scheduler = None
