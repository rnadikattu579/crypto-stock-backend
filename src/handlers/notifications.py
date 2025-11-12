import json
import logging
from typing import Dict, Any
from models.notification import (
    NotificationPreferencesUpdate,
    TestEmailRequest,
    SendNotificationRequest,
    NotificationHistoryQuery,
    EmailVerificationRequest
)
from models.response import SuccessResponse, ErrorResponse
from services.notification_service import NotificationService
from services.auth_service import AuthService

logger = logging.getLogger(__name__)


def get_user_id_from_event(event: Dict[str, Any]) -> str:
    """Extract user ID from authorization context"""
    # In Lambda with authorizer, user_id comes from authorizer context
    request_context = event.get('requestContext', {})
    authorizer = request_context.get('authorizer', {})
    user_id = authorizer.get('user_id')

    if not user_id:
        # Fallback: try to decode from Authorization header
        headers = event.get('headers', {})
        auth_header = headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.replace('Bearer ', '')
            # Decode token to get user_id
            auth_service = AuthService()
            token_data = auth_service.verify_token(token)
            user_id = token_data.user_id if token_data else None

    return user_id


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for notification endpoints"""
    try:
        path = event.get('path', '')
        http_method = event.get('httpMethod', '')

        # CORS preflight
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Max-Age': '600',
                },
                'body': ''
            }

        # Get user ID from auth
        user_id = get_user_id_from_event(event)
        if not user_id:
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Unauthorized'})
            }

        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        notification_service = NotificationService()

        # GET /notifications/preferences - Get user notification preferences
        if path.endswith('/notifications/preferences') and http_method == 'GET':
            preferences = notification_service.get_user_preferences(user_id)

            if not preferences:
                # Create default preferences
                # Get user email from database
                preferences = notification_service.create_default_preferences(user_id, "user@example.com")

            response = SuccessResponse(
                data=preferences.dict(),
                message="Preferences retrieved successfully"
            )

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps(response.dict(), default=str)
            }

        # POST /notifications/preferences - Update preferences
        elif path.endswith('/notifications/preferences') and http_method == 'POST':
            updates = NotificationPreferencesUpdate(**body)
            preferences = notification_service.update_user_preferences(user_id, updates)

            if not preferences:
                return {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'error': 'Preferences not found'})
                }

            response = SuccessResponse(
                data=preferences.dict(),
                message="Preferences updated successfully"
            )

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps(response.dict(), default=str)
            }

        # POST /notifications/test - Send test email
        elif path.endswith('/notifications/test') and http_method == 'POST':
            test_request = TestEmailRequest(**body)

            # Send test notification based on type
            if test_request.notification_type == 'daily_digest':
                test_data = {
                    'user_name': 'Test User',
                    'total_value': '$50,000.00',
                    'total_change_24h': '+2.5%',
                    'crypto_value': '$30,000.00',
                    'stock_value': '$20,000.00',
                    'top_performer': 'Bitcoin (BTC)',
                    'top_performer_change': '+5.2%',
                    'date': 'Today'
                }
                success = notification_service.send_daily_digest(user_id, test_data)
            elif test_request.notification_type == 'price_alert':
                success = notification_service.send_price_alert(
                    user_id=user_id,
                    asset_name='Bitcoin (BTC)',
                    current_price=50000.00,
                    alert_type='crossed above',
                    threshold=48000.00
                )
            elif test_request.notification_type == 'milestone':
                success = notification_service.send_milestone_notification(
                    user_id=user_id,
                    milestone_type='portfolio_value',
                    milestone_value=100000
                )
            elif test_request.notification_type == 'transaction_confirmation':
                success = notification_service.send_transaction_confirmation(
                    user_id=user_id,
                    transaction_type='BUY',
                    asset_name='Bitcoin (BTC)',
                    quantity=0.5,
                    price=50000.00
                )
            elif test_request.notification_type == 'welcome':
                preferences = notification_service.get_user_preferences(user_id)
                success = notification_service.send_welcome_email(
                    user_id=user_id,
                    full_name='Test User',
                    email=preferences.email if preferences else 'test@example.com'
                )
            else:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'error': f'Unsupported test notification type: {test_request.notification_type}'})
                }

            if success:
                response = SuccessResponse(
                    data={'sent': True, 'notification_type': test_request.notification_type},
                    message="Test email sent successfully"
                )
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps(response.dict())
                }
            else:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'error': 'Failed to send test email'})
                }

        # POST /notifications/send - Send specific notification
        elif path.endswith('/notifications/send') and http_method == 'POST':
            send_request = SendNotificationRequest(**body)
            target_user_id = send_request.user_id or user_id

            # For now, just return success
            # In production, this would trigger the appropriate notification
            response = SuccessResponse(
                data={'notification_type': send_request.notification_type, 'queued': True},
                message="Notification queued successfully"
            )

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps(response.dict())
            }

        # GET /notifications/history - Get notification history
        elif path.endswith('/notifications/history') and http_method == 'GET':
            query_params = event.get('queryStringParameters', {}) or {}

            limit = int(query_params.get('limit', 50))
            offset = int(query_params.get('offset', 0))
            notification_type = query_params.get('type')

            notifications = notification_service.get_notification_history(
                user_id=user_id,
                notification_type=notification_type,
                limit=limit,
                offset=offset
            )

            response = SuccessResponse(
                data={
                    'notifications': [n.dict() for n in notifications],
                    'count': len(notifications),
                    'limit': limit,
                    'offset': offset
                },
                message="Notification history retrieved successfully"
            )

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps(response.dict(), default=str)
            }

        # GET /notifications/config - Get email configuration status
        elif path.endswith('/notifications/config') and http_method == 'GET':
            from services.email_service import EmailService
            email_service = EmailService()
            config = email_service.validate_email_config()

            response = SuccessResponse(
                data=config,
                message="Email configuration retrieved"
            )

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps(response.dict())
            }

        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Not found'})
            }

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        error_response = ErrorResponse(error=str(e))
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(error_response.dict())
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        error_response = ErrorResponse(
            error="Internal server error",
            detail=str(e)
        )
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(error_response.dict())
        }
