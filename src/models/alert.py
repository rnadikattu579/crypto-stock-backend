"""
Alert Models for Portfolio Tracker
Supports various alert types: price, percentage change, portfolio value, etc.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class AlertType(str, Enum):
    """Types of alerts supported"""
    PRICE_ABOVE = 'price_above'  # Price goes above threshold
    PRICE_BELOW = 'price_below'  # Price goes below threshold
    PERCENT_GAIN = 'percent_gain'  # Asset gains X%
    PERCENT_LOSS = 'percent_loss'  # Asset loses X%
    PORTFOLIO_VALUE = 'portfolio_value'  # Portfolio reaches value
    PORTFOLIO_GAIN = 'portfolio_gain'  # Portfolio gains X%
    PORTFOLIO_LOSS = 'portfolio_loss'  # Portfolio loses X%
    REBALANCE_NEEDED = 'rebalance_needed'  # Portfolio drifts from targets
    GOAL_MILESTONE = 'goal_milestone'  # Goal reaches milestone
    NEWS_MENTION = 'news_mention'  # Asset mentioned in news
    UNUSUAL_VOLUME = 'unusual_volume'  # Trading volume spike


class AlertStatus(str, Enum):
    """Status of an alert"""
    ACTIVE = 'active'
    TRIGGERED = 'triggered'
    PAUSED = 'paused'
    EXPIRED = 'expired'


class AlertPriority(str, Enum):
    """Priority levels for alerts"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class AlertCondition(BaseModel):
    """Condition that triggers an alert"""
    type: AlertType
    threshold: Optional[float] = None  # Numeric threshold (price, percentage, etc.)
    symbol: Optional[str] = None  # For asset-specific alerts
    asset_type: Optional[str] = None  # 'crypto' or 'stock'
    comparison: str = 'greater'  # 'greater', 'less', 'equal'
    timeframe: Optional[str] = None  # '1H', '24H', '7D', etc.


class AlertNotificationChannel(str, Enum):
    """Channels for sending alert notifications"""
    EMAIL = 'email'
    PUSH = 'push'
    SMS = 'sms'
    IN_APP = 'in_app'


class Alert(BaseModel):
    """Main alert model"""
    alert_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    condition: AlertCondition
    priority: AlertPriority = AlertPriority.MEDIUM
    status: AlertStatus = AlertStatus.ACTIVE
    notification_channels: List[AlertNotificationChannel] = ['in_app']

    # Trigger settings
    trigger_once: bool = False  # True = trigger only once, False = repeatable
    cooldown_minutes: int = 60  # Min time between repeat triggers
    last_triggered_at: Optional[datetime] = None
    trigger_count: int = 0

    # Lifecycle
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None

    # Metadata
    metadata: Optional[dict] = {}


class AlertHistory(BaseModel):
    """Record of an alert being triggered"""
    history_id: str
    alert_id: str
    user_id: str
    triggered_at: datetime
    condition_met: dict  # Snapshot of what triggered the alert
    notification_sent: bool
    notification_channels: List[AlertNotificationChannel]
    asset_price: Optional[float] = None
    portfolio_value: Optional[float] = None


class CreateAlertRequest(BaseModel):
    """Request to create a new alert"""
    name: str
    description: Optional[str] = None
    condition: AlertCondition
    priority: AlertPriority = AlertPriority.MEDIUM
    notification_channels: List[AlertNotificationChannel] = ['in_app']
    trigger_once: bool = False
    cooldown_minutes: int = 60
    expires_at: Optional[datetime] = None


class UpdateAlertRequest(BaseModel):
    """Request to update an alert"""
    name: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[AlertCondition] = None
    priority: Optional[AlertPriority] = None
    status: Optional[AlertStatus] = None
    notification_channels: Optional[List[AlertNotificationChannel]] = None
    trigger_once: Optional[bool] = None
    cooldown_minutes: Optional[int] = None
    expires_at: Optional[datetime] = None


class AlertListResponse(BaseModel):
    """Response for list of alerts"""
    alerts: List[Alert]
    total: int
    active_count: int
    triggered_count: int


class AlertStatsResponse(BaseModel):
    """Statistics about user's alerts"""
    total_alerts: int
    active_alerts: int
    triggered_today: int
    triggered_this_week: int
    triggered_this_month: int
    most_triggered_alert: Optional[dict] = None
