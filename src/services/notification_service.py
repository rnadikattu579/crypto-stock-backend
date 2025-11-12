import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from models.notification import (
    Notification,
    NotificationCreate,
    NotificationPreferences,
    NotificationPreferencesUpdate,
    NotificationType,
    NotificationStatus,
    NotificationFrequency
)
from services.email_service import EmailService
from services.dynamodb_service import DynamoDBService

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications and user preferences"""

    def __init__(self):
        self.email_service = EmailService()
        self.db_service = DynamoDBService()

    # Preferences Management
    def get_user_preferences(self, user_id: str) -> Optional[NotificationPreferences]:
        """Get notification preferences for a user"""
        try:
            item = self.db_service.get_item(user_id, f"NOTIF_PREFS#{user_id}")
            if item:
                return NotificationPreferences(**item)
            return None
        except Exception as e:
            logger.error(f"Error getting preferences for user {user_id}: {str(e)}")
            return None

    def create_default_preferences(self, user_id: str, email: str) -> NotificationPreferences:
        """Create default notification preferences for a new user"""
        now = datetime.utcnow()
        preferences = NotificationPreferences(
            user_id=user_id,
            email=email,
            email_verified=False,
            created_at=now,
            updated_at=now
        )

        try:
            self.db_service.put_item({
                'PK': user_id,
                'SK': f"NOTIF_PREFS#{user_id}",
                'entity_type': 'notification_preferences',
                **preferences.dict()
            })
            logger.info(f"Created default preferences for user {user_id}")
            return preferences
        except Exception as e:
            logger.error(f"Error creating default preferences: {str(e)}")
            raise

    def update_user_preferences(
        self,
        user_id: str,
        updates: NotificationPreferencesUpdate
    ) -> Optional[NotificationPreferences]:
        """Update notification preferences for a user"""
        preferences = self.get_user_preferences(user_id)
        if not preferences:
            return None

        # Update fields
        update_data = updates.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(preferences, key, value)

        preferences.updated_at = datetime.utcnow()

        try:
            self.db_service.put_item({
                'PK': user_id,
                'SK': f"NOTIF_PREFS#{user_id}",
                'entity_type': 'notification_preferences',
                **preferences.dict()
            })
            logger.info(f"Updated preferences for user {user_id}")
            return preferences
        except Exception as e:
            logger.error(f"Error updating preferences: {str(e)}")
            return None

    # Notification Creation and Sending
    def create_notification(self, notification_create: NotificationCreate) -> Notification:
        """Create a notification record in the database"""
        notification_id = str(uuid.uuid4())
        now = datetime.utcnow()

        notification = Notification(
            notification_id=notification_id,
            user_id=notification_create.user_id,
            notification_type=notification_create.notification_type,
            to_email=notification_create.to_email,
            subject=notification_create.subject,
            html_content=notification_create.html_content,
            plain_content=notification_create.plain_content,
            data=notification_create.data,
            created_at=now
        )

        try:
            self.db_service.put_item({
                'PK': notification_create.user_id,
                'SK': f"NOTIF#{notification_id}",
                'entity_type': 'notification',
                'GSI1PK': 'NOTIFICATIONS',
                'GSI1SK': f"{notification_create.notification_type}#{now.isoformat()}",
                **notification.dict()
            })
            return notification
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            raise

    def send_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        subject: str,
        template_name: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Send a notification to a user

        Args:
            user_id: User ID
            notification_type: Type of notification
            subject: Email subject
            template_name: Name of the email template
            data: Data for template placeholders

        Returns:
            True if sent successfully, False otherwise
        """
        # Check user preferences
        preferences = self.get_user_preferences(user_id)
        if not preferences:
            logger.warning(f"No preferences found for user {user_id}")
            return False

        # Check if notification type is enabled
        if not self._is_notification_enabled(preferences, notification_type):
            logger.info(f"Notification type {notification_type} disabled for user {user_id}")
            return False

        # Check rate limiting
        if not self._check_rate_limit(preferences):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False

        # Generate unsubscribe token
        unsubscribe_token = self._generate_unsubscribe_token(user_id)

        # Send email
        success = self.email_service.send_template_email(
            to_email=preferences.email,
            subject=subject,
            template_name=template_name,
            data=data,
            unsubscribe_token=unsubscribe_token
        )

        # Create notification record
        notification_create = NotificationCreate(
            user_id=user_id,
            notification_type=notification_type,
            to_email=preferences.email,
            subject=subject,
            html_content=f"Template: {template_name}",
            data=data
        )
        notification = self.create_notification(notification_create)

        # Update status
        if success:
            self._update_notification_status(
                notification.notification_id,
                NotificationStatus.SENT,
                sent_at=datetime.utcnow()
            )
            self._increment_email_count(user_id)
            return True
        else:
            self._update_notification_status(
                notification.notification_id,
                NotificationStatus.FAILED,
                error_message="Failed to send email"
            )
            return False

    def _is_notification_enabled(
        self,
        preferences: NotificationPreferences,
        notification_type: NotificationType
    ) -> bool:
        """Check if a notification type is enabled for the user"""
        type_map = {
            NotificationType.DAILY_DIGEST: preferences.daily_digest_enabled,
            NotificationType.WEEKLY_REPORT: preferences.weekly_report_enabled,
            NotificationType.PRICE_ALERT: preferences.price_alerts_enabled,
            NotificationType.MILESTONE: preferences.milestone_enabled,
            NotificationType.LARGE_MOVEMENT: preferences.large_movement_enabled,
            NotificationType.TRANSACTION_CONFIRMATION: preferences.transaction_confirmation_enabled,
            NotificationType.GOAL_PROGRESS: preferences.goal_progress_enabled,
            NotificationType.WELCOME: True,  # Always enabled
            NotificationType.EMAIL_VERIFICATION: True,  # Always enabled
        }
        return type_map.get(notification_type, False)

    def _check_rate_limit(self, preferences: NotificationPreferences) -> bool:
        """Check if user has exceeded daily email limit"""
        today = date.today().isoformat()

        # Reset counter if it's a new day
        if preferences.last_email_date != today:
            preferences.emails_sent_today = 0
            preferences.last_email_date = today

        return preferences.emails_sent_today < preferences.max_emails_per_day

    def _increment_email_count(self, user_id: str):
        """Increment the daily email count for a user"""
        preferences = self.get_user_preferences(user_id)
        if preferences:
            today = date.today().isoformat()
            if preferences.last_email_date != today:
                preferences.emails_sent_today = 1
            else:
                preferences.emails_sent_today += 1
            preferences.last_email_date = today
            preferences.updated_at = datetime.utcnow()

            self.db_service.put_item({
                'PK': user_id,
                'SK': f"NOTIF_PREFS#{user_id}",
                'entity_type': 'notification_preferences',
                **preferences.dict()
            })

    def _update_notification_status(
        self,
        notification_id: str,
        status: NotificationStatus,
        sent_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ):
        """Update the status of a notification"""
        # For simplicity, we'll log this. In production, use DynamoDB update expressions
        logger.info(f"Notification {notification_id} status updated to {status}")

    def _generate_unsubscribe_token(self, user_id: str) -> str:
        """Generate a token for unsubscribe links"""
        # In production, use JWT or similar
        import hashlib
        return hashlib.sha256(f"{user_id}:unsubscribe".encode()).hexdigest()[:32]

    # Notification History
    def get_notification_history(
        self,
        user_id: str,
        notification_type: Optional[NotificationType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Notification]:
        """Get notification history for a user"""
        try:
            # Query all notifications for user
            items = self.db_service.query_items(
                key_condition_expression='PK = :pk AND begins_with(SK, :sk)',
                expression_values={
                    ':pk': user_id,
                    ':sk': 'NOTIF#'
                },
                limit=limit + offset
            )

            notifications = [Notification(**item) for item in items[offset:]]

            # Filter by type if specified
            if notification_type:
                notifications = [
                    n for n in notifications
                    if n.notification_type == notification_type
                ]

            return notifications
        except Exception as e:
            logger.error(f"Error getting notification history: {str(e)}")
            return []

    # Specific Notification Types
    def send_welcome_email(self, user_id: str, full_name: str, email: str) -> bool:
        """Send welcome email to new user"""
        data = {
            'title': 'Welcome to Portfolio Tracker!',
            'user_name': full_name or 'there',
            'content': f"""
                <h2>Welcome aboard!</h2>
                <p>We're excited to have you join our community of smart investors.</p>
                <p>With Portfolio Tracker, you can:</p>
                <ul>
                    <li>Track your crypto and stock investments in one place</li>
                    <li>Set price alerts to never miss important movements</li>
                    <li>Get daily digests and weekly reports</li>
                    <li>Visualize your portfolio performance with beautiful charts</li>
                </ul>
                <p style="text-align: center; margin-top: 30px;">
                    <a href="{self.email_service.base_url}/dashboard"
                       style="background: #667eea; color: white; padding: 12px 30px;
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        Go to Dashboard
                    </a>
                </p>
            """
        }

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.WELCOME,
            subject="Welcome to Portfolio Tracker!",
            template_name="welcome",
            data=data
        )

    def send_daily_digest(self, user_id: str, portfolio_data: Dict[str, Any]) -> bool:
        """Send daily portfolio digest"""
        data = {
            'title': 'Your Daily Portfolio Digest',
            **portfolio_data
        }

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.DAILY_DIGEST,
            subject=f"Daily Digest - {date.today().strftime('%B %d, %Y')}",
            template_name="daily_digest",
            data=data
        )

    def send_weekly_report(self, user_id: str, report_data: Dict[str, Any]) -> bool:
        """Send weekly portfolio report"""
        data = {
            'title': 'Your Weekly Portfolio Report',
            **report_data
        }

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.WEEKLY_REPORT,
            subject=f"Weekly Report - {date.today().strftime('%B %d, %Y')}",
            template_name="weekly_report",
            data=data
        )

    def send_price_alert(
        self,
        user_id: str,
        asset_name: str,
        current_price: float,
        alert_type: str,
        threshold: float
    ) -> bool:
        """Send price alert notification"""
        data = {
            'title': 'Price Alert Triggered!',
            'asset_name': asset_name,
            'current_price': f"${current_price:,.2f}",
            'alert_type': alert_type,
            'threshold': f"${threshold:,.2f}",
            'content': f"""
                <h2>Price Alert: {asset_name}</h2>
                <p><strong>{asset_name}</strong> has {alert_type} your target price.</p>
                <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0; font-size: 24px; color: #667eea;">
                        <strong>Current Price: ${current_price:,.2f}</strong>
                    </p>
                    <p style="margin: 10px 0 0 0; color: #666;">
                        Target: ${threshold:,.2f}
                    </p>
                </div>
            """
        }

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.PRICE_ALERT,
            subject=f"Price Alert: {asset_name}",
            template_name="price_alert",
            data=data
        )

    def send_milestone_notification(
        self,
        user_id: str,
        milestone_type: str,
        milestone_value: float
    ) -> bool:
        """Send milestone achievement notification"""
        data = {
            'title': 'Milestone Achieved!',
            'milestone_type': milestone_type,
            'milestone_value': f"${milestone_value:,.0f}",
            'content': f"""
                <h2>Congratulations! 🎉</h2>
                <p>Your portfolio has reached a significant milestone!</p>
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white; padding: 30px; border-radius: 10px;
                            text-align: center; margin: 20px 0;">
                    <p style="font-size: 18px; margin: 0;">Total Portfolio Value</p>
                    <p style="font-size: 48px; margin: 10px 0; font-weight: bold;">
                        ${milestone_value:,.0f}
                    </p>
                </div>
                <p>Keep up the great work! Your investment journey continues to grow.</p>
            """
        }

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.MILESTONE,
            subject=f"Milestone Achieved: ${milestone_value:,.0f}!",
            template_name="milestone",
            data=data
        )

    def send_transaction_confirmation(
        self,
        user_id: str,
        transaction_type: str,
        asset_name: str,
        quantity: float,
        price: float
    ) -> bool:
        """Send transaction confirmation"""
        total = quantity * price
        data = {
            'title': 'Transaction Confirmation',
            'transaction_type': transaction_type,
            'asset_name': asset_name,
            'quantity': quantity,
            'price': f"${price:,.2f}",
            'total': f"${total:,.2f}",
            'content': f"""
                <h2>Transaction Confirmed</h2>
                <p>Your {transaction_type.lower()} transaction has been recorded successfully.</p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background: #f5f5f5;">
                        <td style="padding: 12px; border: 1px solid #ddd;"><strong>Asset</strong></td>
                        <td style="padding: 12px; border: 1px solid #ddd;">{asset_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border: 1px solid #ddd;"><strong>Quantity</strong></td>
                        <td style="padding: 12px; border: 1px solid #ddd;">{quantity}</td>
                    </tr>
                    <tr style="background: #f5f5f5;">
                        <td style="padding: 12px; border: 1px solid #ddd;"><strong>Price per unit</strong></td>
                        <td style="padding: 12px; border: 1px solid #ddd;">${price:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border: 1px solid #ddd;"><strong>Total</strong></td>
                        <td style="padding: 12px; border: 1px solid #ddd;"><strong>${total:,.2f}</strong></td>
                    </tr>
                </table>
            """
        }

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.TRANSACTION_CONFIRMATION,
            subject=f"Transaction Confirmed: {transaction_type} {asset_name}",
            template_name="transaction_confirmation",
            data=data
        )
