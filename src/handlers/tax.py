"""
Tax Report API Handler
"""
import json
import logging
from typing import Dict, Any
from datetime import datetime
from decimal import Decimal

from services.tax_service import tax_service

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler for tax report endpoints"""
    logger.info(f"Tax handler received event: {json.dumps(event)}")

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
            if '/tax/summary' in path:
                return get_tax_summary(event, user_id)
            elif '/tax/form-8949' in path:
                return get_form_8949(event, user_id)
            elif '/tax/unrealized' in path:
                return get_unrealized_gains(event, user_id)
            elif '/tax/harvesting' in path:
                return get_tax_loss_harvesting(event, user_id)

        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'Not found'})
        }

    except Exception as e:
        logger.error(f"Error in tax handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def get_tax_summary(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get tax year summary"""
    params = event.get('queryStringParameters', {}) or {}
    tax_year = int(params.get('year', datetime.utcnow().year))

    summary = tax_service.get_tax_year_summary(user_id, tax_year)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': summary
        }, cls=DecimalEncoder)
    }


def get_form_8949(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get Form 8949 data"""
    params = event.get('queryStringParameters', {}) or {}
    tax_year = int(params.get('year', datetime.utcnow().year))

    form_data = tax_service.generate_form_8949(user_id, tax_year)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': {
                'tax_year': tax_year,
                'entries': form_data
            }
        }, cls=DecimalEncoder)
    }


def get_unrealized_gains(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get unrealized gains/losses"""
    unrealized = tax_service.get_unrealized_gains(user_id)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': unrealized
        }, cls=DecimalEncoder)
    }


def get_tax_loss_harvesting(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get tax loss harvesting opportunities"""
    opportunities = tax_service.get_tax_loss_harvesting_opportunities(user_id)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': {
                'opportunities': opportunities,
                'total_potential_loss': sum(o['unrealized_loss'] for o in opportunities)
            }
        }, cls=DecimalEncoder)
    }
