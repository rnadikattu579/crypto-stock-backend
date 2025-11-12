#!/usr/bin/env python3
"""
Quick test script to validate email configuration and send a test email.
Usage: python test_email.py
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from services.email_service import EmailService
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    print("=" * 60)
    print("Email Configuration Test")
    print("=" * 60)
    print()

    # Initialize email service
    email_service = EmailService()

    # Validate configuration
    print("1. Validating email configuration...")
    config = email_service.validate_email_config()

    print(f"\n✓ Email Enabled: {config['config']['email_enabled']}")
    print(f"✓ SMTP Host: {config['config']['smtp_host']}")
    print(f"✓ SMTP Port: {config['config']['smtp_port']}")
    print(f"✓ SMTP Username: {config['config']['smtp_username']}")
    print(f"✓ Email From: {config['config']['email_from']}")
    print(f"✓ Template Dir: {config['config']['template_dir']}")

    if not config['valid']:
        print("\n❌ Configuration Issues Found:")
        for issue in config['issues']:
            print(f"   - {issue}")
        print("\nPlease fix these issues before sending emails.")
        return False

    print("\n✅ Email configuration is valid!")

    # Ask user if they want to send a test email
    print("\n2. Send a test email?")
    to_email = input("Enter recipient email address (or press Enter to skip): ").strip()

    if not to_email:
        print("\nSkipping test email.")
        return True

    print(f"\nSending test email to {to_email}...")

    # Create a simple test email
    subject = "Portfolio Tracker - Test Email"
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
        .body { background: #ffffff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 10px 10px; }
        .success { background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px; color: #155724; margin: 20px 0; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">Portfolio Tracker</h1>
            <p style="margin: 10px 0 0 0;">Email System Test</p>
        </div>
        <div class="body">
            <div class="success">
                <strong>✓ Success!</strong> Your email configuration is working correctly.
            </div>
            <h2>Email System Status</h2>
            <p>Congratulations! Your Portfolio Tracker email notification system is properly configured and ready to send emails.</p>
            <h3>What's Next?</h3>
            <ul>
                <li>Configure your notification preferences in the settings</li>
                <li>Set up price alerts for your assets</li>
                <li>Enable daily digest for portfolio summaries</li>
                <li>Receive weekly reports every Monday</li>
            </ul>
            <p style="margin-top: 30px;">
                <strong>Need help?</strong> Check the NOTIFICATIONS_README.md file for detailed documentation.
            </p>
        </div>
        <div class="footer">
            <p>This is a test email from Portfolio Tracker</p>
            <p>&copy; 2025 Portfolio Tracker. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""

    plain_content = """
Portfolio Tracker - Email System Test

Success! Your email configuration is working correctly.

Email System Status:
Congratulations! Your Portfolio Tracker email notification system is properly configured and ready to send emails.

What's Next?
- Configure your notification preferences in the settings
- Set up price alerts for your assets
- Enable daily digest for portfolio summaries
- Receive weekly reports every Monday

Need help? Check the NOTIFICATIONS_README.md file for detailed documentation.

---
This is a test email from Portfolio Tracker
© 2025 Portfolio Tracker. All rights reserved.
"""

    # Send the email
    success = email_service.send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        plain_content=plain_content
    )

    if success:
        print(f"\n✅ Test email sent successfully to {to_email}")
        print("Please check your inbox (and spam folder) for the test email.")
        return True
    else:
        print("\n❌ Failed to send test email")
        print("Check the error messages above for details.")
        return False


if __name__ == '__main__':
    print()
    try:
        success = main()
        print()
        print("=" * 60)
        if success:
            print("✅ Email system is ready to use!")
        else:
            print("❌ Please fix the issues and try again.")
        print("=" * 60)
        print()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
