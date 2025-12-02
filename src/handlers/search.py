"""
Global Search API Handler
"""
import json
import logging
from typing import Dict, Any
from decimal import Decimal

from services.search_service import search_service

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler for search endpoints"""
    logger.info(f"Search handler received event: {json.dumps(event)}")

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
            if '/search/global' in path:
                return global_search(event, user_id)
            elif '/search/filters' in path:
                return get_filters(event, user_id)
            elif '/search/tags' in path:
                if '/assets' in path:
                    return get_assets_by_tag(event, user_id)
                return get_tags(event, user_id)
            elif '/search/quick' in path:
                return quick_filter(event, user_id)
        elif http_method == 'POST':
            if '/search/filters' in path:
                return save_filter(event, user_id)
            elif '/search/tags' in path:
                return add_tag(event, user_id)
        elif http_method == 'DELETE':
            if '/search/filters/' in path:
                return delete_filter(event, user_id)
            elif '/search/tags' in path:
                return remove_tag(event, user_id)

        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'Not found'})
        }

    except Exception as e:
        logger.error(f"Error in search handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def global_search(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Global search across all entities"""
    params = event.get('queryStringParameters', {}) or {}

    query = params.get('q', '')
    search_types = params.get('types', 'assets,transactions,goals').split(',')
    limit = int(params.get('limit', 50))

    result = search_service.global_search(user_id, query, search_types, limit)

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


def get_filters(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get saved filters"""
    result = search_service.get_saved_filters(user_id)

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


def save_filter(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Save a custom filter"""
    body = json.loads(event.get('body', '{}'))

    filter_name = body.get('filter_name')
    filter_config = body.get('filter_config', {})

    if not filter_name:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'filter_name is required'})
        }

    result = search_service.save_filter(user_id, filter_name, filter_config)

    return {
        'statusCode': 201,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'success': True,
            'data': result
        }, cls=DecimalEncoder)
    }


def delete_filter(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Delete a saved filter"""
    path_params = event.get('pathParameters', {}) or {}
    filter_id = path_params.get('filter_id')

    if not filter_id:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'filter_id is required'})
        }

    result = search_service.delete_filter(user_id, filter_id)

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


def get_tags(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get all tags"""
    result = search_service.get_all_tags(user_id)

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


def add_tag(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Add a tag to an asset"""
    body = json.loads(event.get('body', '{}'))

    asset_id = body.get('asset_id')
    tag = body.get('tag')

    if not asset_id or not tag:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'asset_id and tag are required'})
        }

    result = search_service.add_tag(user_id, asset_id, tag)

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


def remove_tag(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Remove a tag from an asset"""
    body = json.loads(event.get('body', '{}'))

    asset_id = body.get('asset_id')
    tag = body.get('tag')

    if not asset_id or not tag:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'asset_id and tag are required'})
        }

    result = search_service.remove_tag(user_id, asset_id, tag)

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


def get_assets_by_tag(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get assets with a specific tag"""
    params = event.get('queryStringParameters', {}) or {}
    tag = params.get('tag', '')

    if not tag:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'tag parameter is required'})
        }

    result = search_service.get_assets_by_tag(user_id, tag)

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


def quick_filter(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Apply quick filter"""
    params = event.get('queryStringParameters', {}) or {}
    filter_type = params.get('type', 'profitable')

    result = search_service.quick_filter(user_id, filter_type)

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
