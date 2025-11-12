import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP"""

    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.email_from = os.getenv('EMAIL_FROM', 'Portfolio Tracker <noreply@portfoliotracker.com>')
        self.email_enabled = os.getenv('EMAIL_ENABLED', 'true').lower() == 'true'
        self.base_url = os.getenv('BASE_URL', 'http://localhost:5173')

        # Template directory
        self.template_dir = Path(__file__).parent.parent / 'templates' / 'emails'

    def _load_template(self, template_name: str) -> str:
        """Load email template from file"""
        template_path = self.template_dir / f"{template_name}.html"
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Template {template_name} not found, using fallback")
            return self._get_fallback_template()

    def _get_fallback_template(self) -> str:
        """Simple fallback template when template file is not found"""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
        <h1 style="margin: 0;">{{title}}</h1>
    </div>
    <div style="background: #ffffff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px;">
        {{content}}
    </div>
    <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
        <p>© 2025 Portfolio Tracker. All rights reserved.</p>
        <p><a href="{{unsubscribe_url}}" style="color: #667eea;">Unsubscribe</a></p>
    </div>
</body>
</html>
"""

    def _replace_placeholders(self, template: str, data: Dict[str, Any]) -> str:
        """Replace placeholders in template with actual data"""
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            template = template.replace(placeholder, str(value))
        return template

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None
    ) -> bool:
        """
        Send an email via SMTP

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            plain_content: Plain text fallback content

        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.email_enabled:
            logger.info(f"Email sending is disabled. Would have sent to {to_email}: {subject}")
            return True

        if not self.smtp_username or not self.smtp_password:
            logger.error("SMTP credentials not configured")
            return False

        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['From'] = self.email_from
            message['To'] = to_email
            message['Subject'] = subject
            message['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')

            # Add plain text version if provided
            if plain_content:
                part1 = MIMEText(plain_content, 'plain')
                message.attach(part1)

            # Add HTML version
            part2 = MIMEText(html_content, 'html')
            message.attach(part2)

            # Connect to SMTP server and send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed. Check credentials.")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {str(e)}")
            return False

    def send_template_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        data: Dict[str, Any],
        unsubscribe_token: str
    ) -> bool:
        """
        Send an email using a template

        Args:
            to_email: Recipient email address
            subject: Email subject
            template_name: Name of the template file (without .html)
            data: Dictionary of data to fill template placeholders
            unsubscribe_token: Token for unsubscribe link

        Returns:
            True if email was sent successfully, False otherwise
        """
        # Add common data
        data['base_url'] = self.base_url
        data['unsubscribe_url'] = f"{self.base_url}/unsubscribe?token={unsubscribe_token}"
        data['current_year'] = datetime.utcnow().year

        # Load and fill template
        template = self._load_template(template_name)
        html_content = self._replace_placeholders(template, data)

        # Create plain text version (basic)
        plain_content = self._html_to_plain(html_content)

        return self.send_email(to_email, subject, html_content, plain_content)

    def _html_to_plain(self, html: str) -> str:
        """
        Basic conversion of HTML to plain text
        For production, consider using a library like html2text
        """
        import re

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html)
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')

        return text.strip()

    def validate_email_config(self) -> Dict[str, Any]:
        """
        Validate email configuration

        Returns:
            Dictionary with validation results
        """
        issues = []

        if not self.email_enabled:
            issues.append("Email sending is disabled (EMAIL_ENABLED=false)")

        if not self.smtp_username:
            issues.append("SMTP_USERNAME is not configured")

        if not self.smtp_password:
            issues.append("SMTP_PASSWORD is not configured")

        if not self.smtp_host:
            issues.append("SMTP_HOST is not configured")

        if self.template_dir and not self.template_dir.exists():
            issues.append(f"Template directory does not exist: {self.template_dir}")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'config': {
                'smtp_host': self.smtp_host,
                'smtp_port': self.smtp_port,
                'smtp_username': self.smtp_username[:3] + '***' if self.smtp_username else None,
                'email_from': self.email_from,
                'email_enabled': self.email_enabled,
                'template_dir': str(self.template_dir),
            }
        }
