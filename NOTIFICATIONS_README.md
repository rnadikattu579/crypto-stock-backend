# Email Notification System - Setup Guide

This document provides comprehensive instructions for setting up and using the email notification system for the Crypto-Stock Portfolio Tracker.

## Table of Contents
1. [Overview](#overview)
2. [Backend Setup](#backend-setup)
3. [Email Configuration](#email-configuration)
4. [API Endpoints](#api-endpoints)
5. [Email Templates](#email-templates)
6. [Frontend Integration](#frontend-integration)
7. [Testing](#testing)
8. [Deployment](#deployment)
9. [Troubleshooting](#troubleshooting)

## Overview

The notification system provides:
- **Daily Digest**: Portfolio summary sent every morning
- **Weekly Report**: Detailed performance report every Monday
- **Price Alerts**: Notifications when alert conditions are triggered
- **Portfolio Milestones**: Alerts when portfolio reaches round numbers
- **Large Movements**: Notifications for >5% portfolio changes in 24h
- **Transaction Confirmations**: Confirmations for asset additions/removals
- **Goal Progress**: Updates on investment goal milestones
- **Welcome Email**: Onboarding email for new users

## Backend Setup

### 1. Install Dependencies

```bash
cd crypto-stock-backend
pip install -r requirements.txt
```

New dependencies added:
- `apscheduler==3.10.4` - Background job scheduling
- `pytz==2024.1` - Timezone support

### 2. Environment Variables

Copy `.env.example` to `.env` and configure email settings:

```bash
cp .env.example .env
```

Edit `.env` with your SMTP credentials:

```env
# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=Portfolio Tracker <noreply@portfoliotracker.com>
EMAIL_ENABLED=true
BASE_URL=http://localhost:5173
```

### 3. Gmail App Password Setup

If using Gmail:

1. Go to Google Account → Security
2. Enable 2-Factor Authentication
3. Go to Security → App Passwords
4. Generate app password for "Mail"
5. Use this password in `SMTP_PASSWORD`

**Important**: Never use your regular Gmail password!

### 4. File Structure

```
crypto-stock-backend/
├── src/
│   ├── models/
│   │   └── notification.py          # Notification data models
│   ├── services/
│   │   ├── email_service.py         # Email sending logic
│   │   └── notification_service.py  # Notification business logic
│   ├── handlers/
│   │   └── notifications.py         # API endpoints
│   ├── templates/
│   │   └── emails/                  # HTML email templates
│   │       ├── base.html
│   │       ├── welcome.html
│   │       ├── daily_digest.html
│   │       ├── weekly_report.html
│   │       ├── price_alert.html
│   │       ├── milestone.html
│   │       └── transaction_confirmation.html
│   └── utils/
│       └── scheduler.py             # Background job scheduler
```

## Email Configuration

### Supported SMTP Providers

#### Gmail
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

#### SendGrid
```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-sendgrid-api-key
```

#### AWS SES
```env
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=your-ses-access-key
SMTP_PASSWORD=your-ses-secret-key
```

#### Outlook/Office 365
```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
```

### Testing Email Configuration

Check if email is configured correctly:

```bash
# API endpoint to validate config
GET /notifications/config
```

## API Endpoints

### Get Notification Preferences
```http
GET /notifications/preferences
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user_id": "user123",
    "email": "user@example.com",
    "email_verified": false,
    "daily_digest_enabled": true,
    "weekly_report_enabled": true,
    "price_alerts_enabled": true,
    "digest_time": "08:00",
    "timezone": "UTC"
  }
}
```

### Update Notification Preferences
```http
POST /notifications/preferences
Authorization: Bearer <token>
Content-Type: application/json

{
  "daily_digest_enabled": true,
  "digest_time": "09:00",
  "timezone": "America/New_York"
}
```

### Send Test Email
```http
POST /notifications/test
Authorization: Bearer <token>
Content-Type: application/json

{
  "notification_type": "daily_digest"
}
```

Supported types:
- `daily_digest`
- `weekly_report`
- `price_alert`
- `milestone`
- `transaction_confirmation`
- `welcome`

### Get Notification History
```http
GET /notifications/history?type=daily_digest&limit=50&offset=0
Authorization: Bearer <token>
```

### Validate Email Config
```http
GET /notifications/config
Authorization: Bearer <token>
```

## Email Templates

Templates are located in `src/templates/emails/`.

### Template Variables

All templates support these variables:
- `{{title}}` - Email title
- `{{base_url}}` - Application base URL
- `{{unsubscribe_url}}` - Unsubscribe link
- `{{current_year}}` - Current year

### Customizing Templates

Templates use simple `{{variable}}` syntax. To customize:

1. Edit HTML files in `src/templates/emails/`
2. Use inline CSS for email client compatibility
3. Test across different email clients
4. Maintain mobile responsiveness

### Template Examples

#### Daily Digest Variables
```python
{
    'user_name': 'John Doe',
    'total_value': '$50,000.00',
    'total_change_24h': '+2.5%',
    'crypto_value': '$30,000.00',
    'stock_value': '$20,000.00',
    'top_performer': 'Bitcoin (BTC)',
    'top_performer_change': '+5.2%',
    'date': 'November 12, 2025'
}
```

#### Price Alert Variables
```python
{
    'asset_name': 'Bitcoin (BTC)',
    'current_price': '$50,000.00',
    'alert_type': 'crossed above',
    'threshold': '$48,000.00'
}
```

## Frontend Integration

### 1. Install in App.tsx

Add NotificationProvider:

```tsx
import { NotificationProvider } from './contexts/NotificationContext';

function App() {
  return (
    <NotificationProvider>
      {/* Your app content */}
    </NotificationProvider>
  );
}
```

### 2. Add Notification Center to Navigation

```tsx
import NotificationCenter from './components/Notifications/NotificationCenter';

// In your navigation component
<NotificationCenter />
```

### 3. Add Settings Page

```tsx
import NotificationSettings from './components/Notifications/NotificationSettings';

// In your settings/preferences page
<NotificationSettings />
```

### 4. Using Notifications

```tsx
import { useNotifications } from './contexts/NotificationContext';

function MyComponent() {
  const { addNotification } = useNotifications();

  // Add a notification
  addNotification({
    type: 'price_alert',
    title: 'Price Alert',
    message: 'Bitcoin has crossed $50,000',
    actionUrl: '/dashboard'
  });
}
```

## Testing

### 1. Test Email Service

```python
# Test in Python
from services.email_service import EmailService

email_service = EmailService()
config = email_service.validate_email_config()
print(config)
```

### 2. Send Test Emails

Use the API or frontend:

```bash
# Via API
curl -X POST http://localhost:3000/notifications/test \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notification_type": "daily_digest"}'
```

Or use the "Test" button in the frontend settings page.

### 3. Test Background Jobs

```python
from utils.scheduler import start_scheduler

# Start scheduler
scheduler = start_scheduler()

# It will run jobs according to schedule
# Daily digest: Every day at 8 AM
# Weekly report: Every Monday at 9 AM
# Price alerts: Every 5 minutes
```

### 4. Preview Templates

Open template files directly in a browser to preview:

```bash
open src/templates/emails/daily_digest.html
```

## Deployment

### AWS Lambda Deployment

1. **Add notification handler to template.yaml**:

```yaml
NotificationFunction:
  Type: AWS::Serverless::Function
  Properties:
    Handler: src/handlers/notifications.handler
    Runtime: python3.11
    Events:
      NotificationAPI:
        Type: Api
        Properties:
          Path: /notifications/{proxy+}
          Method: ANY
    Environment:
      Variables:
        SMTP_HOST: !Ref SMTPHost
        SMTP_USERNAME: !Ref SMTPUsername
        SMTP_PASSWORD: !Ref SMTPPassword
```

2. **Set environment variables in AWS**:
   - Go to Lambda → Configuration → Environment Variables
   - Add all SMTP credentials

3. **Background Jobs**:
   - For Lambda, use EventBridge (CloudWatch Events) instead of APScheduler
   - Create scheduled rules for daily/weekly jobs
   - Or use AWS Step Functions

### Docker Deployment

If using Docker:

```dockerfile
# Add to Dockerfile
COPY src/templates /app/src/templates
```

### Traditional Server Deployment

1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variables
3. Start scheduler on application startup
4. Ensure templates directory is accessible

## Troubleshooting

### Email Not Sending

1. **Check configuration**:
   ```bash
   GET /notifications/config
   ```

2. **Verify SMTP credentials**:
   - Test with mail client
   - Ensure app password (not regular password)

3. **Check logs**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

4. **Common issues**:
   - Firewall blocking port 587
   - 2FA not enabled (Gmail)
   - Incorrect app password
   - `EMAIL_ENABLED=false` in environment

### Templates Not Loading

1. **Check template directory path**:
   ```python
   from pathlib import Path
   print(Path(__file__).parent.parent / 'templates' / 'emails')
   ```

2. **Verify file permissions**:
   ```bash
   ls -la src/templates/emails/
   ```

3. **Use fallback template** for testing

### Rate Limiting Issues

Default: 10 emails per day per user

To adjust:
```python
# Update in notification preferences
max_emails_per_day: 20
```

### Scheduler Not Running

1. **Verify scheduler started**:
   ```python
   from utils.scheduler import get_scheduler
   scheduler = get_scheduler()
   print(scheduler.scheduler.running)
   ```

2. **Check timezone configuration**

3. **Lambda users**: Use CloudWatch Events instead

### Email Goes to Spam

1. **Set up SPF/DKIM records** for your domain
2. **Use authenticated email service** (SendGrid, SES)
3. **Avoid spam trigger words** in subject/content
4. **Include unsubscribe link** (already included)
5. **Use consistent "From" address**

## Production Recommendations

1. **Use professional email service**:
   - SendGrid (transactional emails)
   - AWS SES (scalable, cheap)
   - Mailgun
   - Not Gmail for production!

2. **Set up email tracking**:
   - Open rates
   - Click rates
   - Bounce handling

3. **Implement email queue**:
   - Use Redis/SQS for queue
   - Retry failed sends
   - Rate limiting

4. **Monitor email health**:
   - Delivery rates
   - Bounce rates
   - Complaint rates

5. **Security**:
   - Never commit credentials
   - Use secret management (AWS Secrets Manager)
   - Rotate credentials regularly
   - Use TLS/SSL

6. **Database**:
   - Store sent notifications
   - Track open/click events
   - Clean up old notifications

## Support

For issues or questions:
1. Check logs for error messages
2. Verify environment variables
3. Test with simple email first
4. Check email provider status
5. Review template syntax

## Next Steps

- [ ] Set up email verification flow
- [ ] Add email template previews in settings
- [ ] Implement notification preferences per type
- [ ] Add notification scheduling (send at specific time)
- [ ] Implement email tracking (opens, clicks)
- [ ] Add support for multiple languages
- [ ] Create admin dashboard for email analytics
- [ ] Implement A/B testing for email templates
