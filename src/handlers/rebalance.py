"""
Portfolio Rebalancing API Handler
"""
import json
import logging
from typing import Dict, Any
from decimal import Decimal

from services.rebalance_service import rebalance_service

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler for rebalancing endpoints"""
    logger.info(f"Rebalance handler received event: {json.dumps(event)}")

    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    # Handle OPTIONS for CORS preflight - must come before auth check
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
            if '/rebalance/targets' in path:
                return get_targets(event, user_id)
            elif '/rebalance/calculate' in path:
                return calculate_rebalance(event, user_id)
            elif '/rebalance/drift' in path:
                return get_drift(event, user_id)
        elif http_method == 'POST':
            if '/rebalance/targets' in path:
                return set_target(event, user_id)
        elif http_method == 'DELETE':
            if '/rebalance/targets/' in path:
                return delete_target(event, user_id)

        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'Not found'})
        }

    except Exception as e:
        logger.error(f"Error in rebalance handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def get_targets(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get all target allocations"""
    targets = rebalance_service.get_target_allocations(user_id)

    # Calculate total
    total_percentage = sum(t['target_percentage'] for t in targets)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': {
                'targets': targets,
                'total_percentage': total_percentage,
                'is_valid': abs(total_percentage - 100) < 0.01
            }
        }, cls=DecimalEncoder)
    }


def set_target(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Set or update a target allocation"""
    body = json.loads(event.get('body', '{}'))

    asset_type = body.get('asset_type')
    target_percentage = body.get('target_percentage')
    symbol = body.get('symbol')
    category = body.get('category')

    if not asset_type or target_percentage is None:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'asset_type and target_percentage are required'})
        }

    if target_percentage < 0 or target_percentage > 100:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'target_percentage must be between 0 and 100'})
        }

    result = rebalance_service.set_target_allocation(
        user_id,
        asset_type,
        target_percentage,
        symbol,
        category
    )

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': result
        }, cls=DecimalEncoder)
    }


def delete_target(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Delete a target allocation"""
    # Extract allocation_id from path
    path_params = event.get('pathParameters', {}) or {}
    allocation_id = path_params.get('allocation_id')

    if not allocation_id:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'allocation_id is required'})
        }

    success = rebalance_service.delete_target_allocation(user_id, allocation_id)

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


def calculate_rebalance(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Calculate rebalancing recommendations"""
    params = event.get('queryStringParameters', {}) or {}
    additional_investment = float(params.get('additional_investment', 0))

    result = rebalance_service.calculate_rebalance(user_id, additional_investment)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': result
        }, cls=DecimalEncoder)
    }


def get_drift(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get portfolio drift from targets"""
    result = rebalance_service.get_portfolio_drift(user_id)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': result
        }, cls=DecimalEncoder)
    }
