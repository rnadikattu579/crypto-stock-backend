from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    DAILY_DIGEST = "daily_digest"
    WEEKLY_REPORT = "weekly_report"
    PRICE_ALERT = "price_alert"
    MILESTONE = "milestone"
    LARGE_MOVEMENT = "large_movement"
    TRANSACTION_CONFIRMATION = "transaction_confirmation"
    GOAL_PROGRESS = "goal_progress"
    WELCOME = "welcome"
    EMAIL_VERIFICATION = "email_verification"


class NotificationFrequency(str, Enum):
    IMMEDIATE = "immediate"
    DAILY = "daily"
    WEEKLY = "weekly"
    DISABLED = "disabled"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"


class NotificationPreferences(BaseModel):
    user_id: str
    email: EmailStr
    email_verified: bool = False

    # Notification type preferences
    daily_digest_enabled: bool = True
    weekly_report_enabled: bool = True
    price_alerts_enabled: bool = True
    milestone_enabled: bool = True
    large_movement_enabled: bool = True
    transaction_confirmation_enabled: bool = True
    goal_progress_enabled: bool = True

    # Frequency preferences
    price_alert_frequency: NotificationFrequency = NotificationFrequency.IMMEDIATE
    digest_time: str = "08:00"  # HH:MM format
    weekly_day: int = 1  # 1 = Monday
    timezone: str = "UTC"

    # Rate limiting
    max_emails_per_day: int = 10
    emails_sent_today: int = 0
    last_email_date: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        use_enum_values = True


class NotificationPreferencesUpdate(BaseModel):
    email: Optional[EmailStr] = None
    daily_digest_enabled: Optional[bool] = None
    weekly_report_enabled: Optional[bool] = None
    price_alerts_enabled: Optional[bool] = None
    milestone_enabled: Optional[bool] = None
    large_movement_enabled: Optional[bool] = None
    transaction_confirmation_enabled: Optional[bool] = None
    goal_progress_enabled: Optional[bool] = None
    price_alert_frequency: Optional[NotificationFrequency] = None
    digest_time: Optional[str] = None
    weekly_day: Optional[int] = None
    timezone: Optional[str] = None


class Notification(BaseModel):
    notification_id: str
    user_id: str
    notification_type: NotificationType
    status: NotificationStatus = NotificationStatus.PENDING

    # Email details
    to_email: EmailStr
    subject: str
    html_content: str
    plain_content: Optional[str] = None

    # Metadata
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None

    created_at: datetime

    class Config:
        from_attributes = True
        use_enum_values = True


class NotificationCreate(BaseModel):
    user_id: str
    notification_type: NotificationType
    to_email: EmailStr
    subject: str
    html_content: str
    plain_content: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class NotificationHistoryQuery(BaseModel):
    user_id: str
    notification_type: Optional[NotificationType] = None
    status: Optional[NotificationStatus] = None
    limit: int = Field(default=50, le=100)
    offset: int = 0


class TestEmailRequest(BaseModel):
    notification_type: NotificationType = NotificationType.DAILY_DIGEST


class SendNotificationRequest(BaseModel):
    notification_type: NotificationType
    user_id: Optional[str] = None  # If None, sends to current user
    data: Optional[Dict[str, Any]] = None


class EmailVerificationRequest(BaseModel):
    email: EmailStr


class EmailVerificationConfirm(BaseModel):
    token: str


class UnsubscribeRequest(BaseModel):
    token: str
    notification_types: Optional[List[NotificationType]] = None  # None = unsubscribe from all
