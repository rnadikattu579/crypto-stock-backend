"""
Alerts Service
Handles alert creation, evaluation, and triggering
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from models.alert import (
    Alert, AlertHistory, AlertType, AlertStatus, AlertPriority,
    CreateAlertRequest, UpdateAlertRequest, AlertCondition,
    AlertListResponse, AlertStatsResponse
)
from services.dynamodb_service import DynamoDBService
from services.portfolio_service import portfolio_service
from services.price_service import price_service

logger = logging.getLogger(__name__)


class AlertsService:
    """Service for managing portfolio alerts"""

    def __init__(self):
        self.db_service = DynamoDBService()

    def create_alert(self, user_id: str, request: CreateAlertRequest) -> Alert:
        """
        Create a new alert for a user

        Args:
            user_id: User ID
            request: Alert creation request

        Returns:
            Created alert
        """
        alert_id = str(uuid.uuid4())
        now = datetime.utcnow()

        alert = Alert(
            alert_id=alert_id,
            user_id=user_id,
            name=request.name,
            description=request.description,
            condition=request.condition,
            priority=request.priority,
            status=AlertStatus.ACTIVE,
            notification_channels=request.notification_channels,
            trigger_once=request.trigger_once,
            cooldown_minutes=request.cooldown_minutes,
            created_at=now,
            updated_at=now,
            expires_at=request.expires_at
        )

        # Store in DynamoDB
        self.db_service.put_item({
            'PK': user_id,
            'SK': f'ALERT#{alert_id}',
            'entity_type': 'alert',
            'GSI1PK': f'USER#{user_id}',
            'GSI1SK': f'ALERT#{alert.status.value}#{now.isoformat()}',
            **alert.dict()
        })

        logger.info(f"Created alert {alert_id} for user {user_id}")
        return alert

    def get_alert(self, user_id: str, alert_id: str) -> Optional[Alert]:
        """Get a specific alert"""
        item = self.db_service.get_item(user_id, f'ALERT#{alert_id}')
        if item and item.get('entity_type') == 'alert':
            return Alert(**item)
        return None

    def list_alerts(self, user_id: str, status: Optional[AlertStatus] = None) -> AlertListResponse:
        """
        List all alerts for a user

        Args:
            user_id: User ID
            status: Optional filter by status

        Returns:
            List of alerts with statistics
        """
        items = self.db_service.query(user_id, 'ALERT#')

        alerts = []
        for item in items:
            if item.get('entity_type') == 'alert':
                alert = Alert(**item)
                if status is None or alert.status == status:
                    alerts.append(alert)

        # Calculate statistics
        total = len(alerts)
        active_count = sum(1 for a in alerts if a.status == AlertStatus.ACTIVE)
        triggered_count = sum(1 for a in alerts if a.status == AlertStatus.TRIGGERED)

        return AlertListResponse(
            alerts=alerts,
            total=total,
            active_count=active_count,
            triggered_count=triggered_count
        )

    def update_alert(self, user_id: str, alert_id: str, request: UpdateAlertRequest) -> Optional[Alert]:
        """Update an existing alert"""
        alert = self.get_alert(user_id, alert_id)
        if not alert:
            return None

        # Update fields
        update_data = request.dict(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(alert, key, value)

        alert.updated_at = datetime.utcnow()

        # Save to DynamoDB
        self.db_service.put_item({
            'PK': user_id,
            'SK': f'ALERT#{alert_id}',
            'entity_type': 'alert',
            'GSI1PK': f'USER#{user_id}',
            'GSI1SK': f'ALERT#{alert.status.value}#{alert.updated_at.isoformat()}',
            **alert.dict()
        })

        logger.info(f"Updated alert {alert_id} for user {user_id}")
        return alert

    def delete_alert(self, user_id: str, alert_id: str) -> bool:
        """Delete an alert"""
        try:
            self.db_service.table.delete_item(
                Key={'PK': user_id, 'SK': f'ALERT#{alert_id}'}
            )
            logger.info(f"Deleted alert {alert_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting alert {alert_id}: {str(e)}")
            return False

    def get_alert_stats(self, user_id: str) -> AlertStatsResponse:
        """Get statistics about user's alerts"""
        alerts = self.list_alerts(user_id).alerts

        # Get alert history
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)

        history_items = self.db_service.query(user_id, 'ALERT_HISTORY#')

        triggered_today = 0
        triggered_week = 0
        triggered_month = 0
        trigger_counts = {}

        for item in history_items:
            if item.get('entity_type') == 'alert_history':
                triggered_at = datetime.fromisoformat(item['triggered_at'])
                alert_id = item['alert_id']

                if triggered_at >= today_start:
                    triggered_today += 1
                if triggered_at >= week_start:
                    triggered_week += 1
                if triggered_at >= month_start:
                    triggered_month += 1

                trigger_counts[alert_id] = trigger_counts.get(alert_id, 0) + 1

        # Find most triggered alert
        most_triggered = None
        if trigger_counts:
            most_triggered_id = max(trigger_counts, key=trigger_counts.get)
            alert = self.get_alert(user_id, most_triggered_id)
            if alert:
                most_triggered = {
                    'alert_id': most_triggered_id,
                    'name': alert.name,
                    'trigger_count': trigger_counts[most_triggered_id]
                }

        return AlertStatsResponse(
            total_alerts=len(alerts),
            active_alerts=sum(1 for a in alerts if a.status == AlertStatus.ACTIVE),
            triggered_today=triggered_today,
            triggered_this_week=triggered_week,
            triggered_this_month=triggered_month,
            most_triggered_alert=most_triggered
        )

    def evaluate_alert(self, alert: Alert) -> tuple[bool, Dict[str, Any]]:
        """
        Evaluate if an alert condition is met

        Args:
            alert: Alert to evaluate

        Returns:
            Tuple of (condition_met, context_data)
        """
        condition = alert.condition
        context = {}

        try:
            if condition.type in [AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW]:
                return self._evaluate_price_alert(alert, context)

            elif condition.type in [AlertType.PERCENT_GAIN, AlertType.PERCENT_LOSS]:
                return self._evaluate_percent_change_alert(alert, context)

            elif condition.type in [AlertType.PORTFOLIO_VALUE, AlertType.PORTFOLIO_GAIN, AlertType.PORTFOLIO_LOSS]:
                return self._evaluate_portfolio_alert(alert, context)

            elif condition.type == AlertType.REBALANCE_NEEDED:
                return self._evaluate_rebalance_alert(alert, context)

            else:
                logger.warning(f"Alert type {condition.type} not yet implemented")
                return False, context

        except Exception as e:
            logger.error(f"Error evaluating alert {alert.alert_id}: {str(e)}")
            return False, context

    def _evaluate_price_alert(self, alert: Alert, context: Dict) -> tuple[bool, Dict]:
        """Evaluate price-based alerts"""
        condition = alert.condition

        if not condition.symbol:
            return False, context

        # Get current price
        current_price = price_service.get_current_price(
            condition.symbol,
            condition.asset_type or 'crypto'
        )

        if current_price is None:
            return False, context

        context['current_price'] = float(current_price)
        context['symbol'] = condition.symbol
        context['threshold'] = condition.threshold

        # Check condition
        if condition.type == AlertType.PRICE_ABOVE:
            return current_price > condition.threshold, context
        elif condition.type == AlertType.PRICE_BELOW:
            return current_price < condition.threshold, context

        return False, context

    def _evaluate_percent_change_alert(self, alert: Alert, context: Dict) -> tuple[bool, Dict]:
        """Evaluate percentage change alerts"""
        condition = alert.condition

        if not condition.symbol:
            return False, context

        # Get asset from portfolio
        portfolio = portfolio_service.get_portfolio(
            alert.user_id,
            condition.asset_type or 'crypto'
        )

        asset = next((a for a in portfolio.assets if a.symbol == condition.symbol), None)
        if not asset:
            return False, context

        context['symbol'] = condition.symbol
        context['gain_loss_percentage'] = float(asset.gain_loss_percentage)
        context['threshold'] = condition.threshold

        # Check condition
        if condition.type == AlertType.PERCENT_GAIN:
            return asset.gain_loss_percentage >= condition.threshold, context
        elif condition.type == AlertType.PERCENT_LOSS:
            return asset.gain_loss_percentage <= -condition.threshold, context

        return False, context

    def _evaluate_portfolio_alert(self, alert: Alert, context: Dict) -> tuple[bool, Dict]:
        """Evaluate portfolio-level alerts"""
        condition = alert.condition

        # Get portfolio summary
        summary = portfolio_service.get_portfolio_summary(alert.user_id)

        context['portfolio_value'] = float(summary.total_value)
        context['portfolio_gain_loss_percentage'] = float(summary.total_gain_loss_percentage)
        context['threshold'] = condition.threshold

        # Check condition
        if condition.type == AlertType.PORTFOLIO_VALUE:
            if condition.comparison == 'greater':
                return summary.total_value >= condition.threshold, context
            elif condition.comparison == 'less':
                return summary.total_value <= condition.threshold, context

        elif condition.type == AlertType.PORTFOLIO_GAIN:
            return summary.total_gain_loss_percentage >= condition.threshold, context

        elif condition.type == AlertType.PORTFOLIO_LOSS:
            return summary.total_gain_loss_percentage <= -condition.threshold, context

        return False, context

    def _evaluate_rebalance_alert(self, alert: Alert, context: Dict) -> tuple[bool, Dict]:
        """Evaluate if portfolio needs rebalancing"""
        # This would integrate with rebalance service
        # For now, return False
        return False, context

    def trigger_alert(self, alert: Alert, context: Dict[str, Any]) -> AlertHistory:
        """
        Trigger an alert and create history record

        Args:
            alert: Alert that was triggered
            context: Context data from evaluation

        Returns:
            Alert history record
        """
        history_id = str(uuid.uuid4())
        now = datetime.utcnow()

        history = AlertHistory(
            history_id=history_id,
            alert_id=alert.alert_id,
            user_id=alert.user_id,
            triggered_at=now,
            condition_met=context,
            notification_sent=True,  # Would integrate with notification service
            notification_channels=alert.notification_channels,
            asset_price=context.get('current_price'),
            portfolio_value=context.get('portfolio_value')
        )

        # Store history
        self.db_service.put_item({
            'PK': alert.user_id,
            'SK': f'ALERT_HISTORY#{history_id}',
            'entity_type': 'alert_history',
            'GSI1PK': f'ALERT#{alert.alert_id}',
            'GSI1SK': f'HISTORY#{now.isoformat()}',
            **history.dict()
        })

        # Update alert
        alert.last_triggered_at = now
        alert.trigger_count += 1

        if alert.trigger_once:
            alert.status = AlertStatus.TRIGGERED

        self.db_service.put_item({
            'PK': alert.user_id,
            'SK': f'ALERT#{alert.alert_id}',
            'entity_type': 'alert',
            'GSI1PK': f'USER#{alert.user_id}',
            'GSI1SK': f'ALERT#{alert.status.value}#{now.isoformat()}',
            **alert.dict()
        })

        logger.info(f"Triggered alert {alert.alert_id} for user {alert.user_id}")
        return history

    def check_all_alerts_for_user(self, user_id: str) -> List[AlertHistory]:
        """
        Check all active alerts for a user

        Args:
            user_id: User ID

        Returns:
            List of triggered alerts
        """
        triggered_histories = []

        # Get all active alerts
        alerts = self.list_alerts(user_id, status=AlertStatus.ACTIVE).alerts
        now = datetime.utcnow()

        for alert in alerts:
            # Check if expired
            if alert.expires_at and now > alert.expires_at:
                alert.status = AlertStatus.EXPIRED
                self.update_alert(user_id, alert.alert_id, UpdateAlertRequest(status=AlertStatus.EXPIRED))
                continue

            # Check cooldown
            if alert.last_triggered_at:
                cooldown_end = alert.last_triggered_at + timedelta(minutes=alert.cooldown_minutes)
                if now < cooldown_end:
                    continue

            # Evaluate alert
            condition_met, context = self.evaluate_alert(alert)

            if condition_met:
                history = self.trigger_alert(alert, context)
                triggered_histories.append(history)

        return triggered_histories


# Create singleton instance
alerts_service = AlertsService()
