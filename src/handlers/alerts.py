"""
Alerts API Handler
Handles HTTP requests for alert management
"""
import json
import logging
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime

from services.alerts_service import alerts_service
from models.alert import (
    CreateAlertRequest, UpdateAlertRequest, AlertStatus,
    AlertCondition, AlertType, AlertPriority
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal and datetime objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler for alerts endpoints"""
    logger.info(f"Alerts handler received event: {json.dumps(event, default=str)}")

    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    # Handle OPTIONS for CORS preflight
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
            },
            'body': ''
        }

    # Get user ID from authorizer
    user_id = event.get('requestContext', {}).get('authorizer', {}).get('user_id')

    if not user_id:
        return {
            'statusCode': 401,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'Unauthorized'})
        }

    try:
        if http_method == 'GET':
            if '/alerts/stats' in path:
                return get_alert_stats(event, user_id)
            elif '/alerts/' in path and path.count('/') > 2:
                return get_alert(event, user_id)
            else:
                return list_alerts(event, user_id)

        elif http_method == 'POST':
            return create_alert(event, user_id)

        elif http_method == 'PUT':
            return update_alert(event, user_id)

        elif http_method == 'DELETE':
            return delete_alert(event, user_id)

        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'Not found'})
        }

    except Exception as e:
        logger.error(f"Error in alerts handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def create_alert(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Create a new alert"""
    body = json.loads(event.get('body', '{}'))

    # Validate required fields
    if 'name' not in body or 'condition' not in body:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'name and condition are required'})
        }

    # Create alert condition
    condition_data = body['condition']
    condition = AlertCondition(
        type=AlertType(condition_data['type']),
        threshold=condition_data.get('threshold'),
        symbol=condition_data.get('symbol'),
        asset_type=condition_data.get('asset_type'),
        comparison=condition_data.get('comparison', 'greater'),
        timeframe=condition_data.get('timeframe')
    )

    # Create request
    request = CreateAlertRequest(
        name=body['name'],
        description=body.get('description'),
        condition=condition,
        priority=AlertPriority(body.get('priority', 'medium')),
        notification_channels=body.get('notification_channels', ['in_app']),
        trigger_once=body.get('trigger_once', False),
        cooldown_minutes=body.get('cooldown_minutes', 60),
        expires_at=datetime.fromisoformat(body['expires_at']) if body.get('expires_at') else None
    )

    alert = alerts_service.create_alert(user_id, request)

    return {
        'statusCode': 201,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': alert.dict()
        }, cls=DecimalEncoder)
    }


def get_alert(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get a specific alert"""
    path_params = event.get('pathParameters', {}) or {}
    alert_id = path_params.get('alert_id')

    if not alert_id:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'alert_id is required'})
        }

    alert = alerts_service.get_alert(user_id, alert_id)

    if not alert:
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'Alert not found'})
        }

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': alert.dict()
        }, cls=DecimalEncoder)
    }


def list_alerts(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """List all alerts for a user"""
    params = event.get('queryStringParameters', {}) or {}
    status = params.get('status')

    if status:
        status = AlertStatus(status)

    response = alerts_service.list_alerts(user_id, status)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': response.dict()
        }, cls=DecimalEncoder)
    }


def update_alert(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Update an alert"""
    path_params = event.get('pathParameters', {}) or {}
    alert_id = path_params.get('alert_id')

    if not alert_id:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'alert_id is required'})
        }

    body = json.loads(event.get('body', '{}'))

    # Build update request
    update_data = {}

    if 'name' in body:
        update_data['name'] = body['name']
    if 'description' in body:
        update_data['description'] = body['description']
    if 'priority' in body:
        update_data['priority'] = AlertPriority(body['priority'])
    if 'status' in body:
        update_data['status'] = AlertStatus(body['status'])
    if 'notification_channels' in body:
        update_data['notification_channels'] = body['notification_channels']
    if 'trigger_once' in body:
        update_data['trigger_once'] = body['trigger_once']
    if 'cooldown_minutes' in body:
        update_data['cooldown_minutes'] = body['cooldown_minutes']
    if 'condition' in body:
        condition_data = body['condition']
        update_data['condition'] = AlertCondition(
            type=AlertType(condition_data['type']),
            threshold=condition_data.get('threshold'),
            symbol=condition_data.get('symbol'),
            asset_type=condition_data.get('asset_type'),
            comparison=condition_data.get('comparison', 'greater'),
            timeframe=condition_data.get('timeframe')
        )

    request = UpdateAlertRequest(**update_data)
    alert = alerts_service.update_alert(user_id, alert_id, request)

    if not alert:
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'Alert not found'})
        }

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': alert.dict()
        }, cls=DecimalEncoder)
    }


def delete_alert(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Delete an alert"""
    path_params = event.get('pathParameters', {}) or {}
    alert_id = path_params.get('alert_id')

    if not alert_id:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'alert_id is required'})
        }

    success = alerts_service.delete_alert(user_id, alert_id)

    return {
        'statusCode': 200 if success else 500,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': success
        })
    }


def get_alert_stats(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get alert statistics"""
    stats = alerts_service.get_alert_stats(user_id)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': stats.dict()
        }, cls=DecimalEncoder)
    }
