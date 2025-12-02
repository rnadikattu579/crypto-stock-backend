"""
Advanced Analytics API Handler
"""
import json
import logging
from typing import Dict, Any
from decimal import Decimal

from services.analytics_service import analytics_service

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler for advanced analytics endpoints"""
    logger.info(f"Analytics handler received event: {json.dumps(event)}")

    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    # Handle OPTIONS (CORS preflight) first, before auth check
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
            if '/analytics/metrics' in path:
                return get_metrics(event, user_id)
            elif '/analytics/benchmarks' in path:
                return get_benchmarks(event, user_id)
            elif '/analytics/risk' in path:
                return get_risk(event, user_id)

        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'Not found'})
        }

    except Exception as e:
        logger.error(f"Error in analytics handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def get_metrics(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get advanced portfolio metrics"""
    params = event.get('queryStringParameters', {}) or {}
    period_days = int(params.get('period', 365))

    result = analytics_service.get_advanced_metrics(user_id, period_days)

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


def get_benchmarks(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get benchmark comparison"""
    params = event.get('queryStringParameters', {}) or {}
    period_days = int(params.get('period', 365))
    benchmarks_param = params.get('benchmarks', 'SP500,BTC')
    benchmarks = [b.strip() for b in benchmarks_param.split(',')]

    result = analytics_service.get_benchmark_comparison(user_id, benchmarks, period_days)

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


def get_risk(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get portfolio risk analysis"""
    result = analytics_service.get_risk_metrics(user_id)

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
