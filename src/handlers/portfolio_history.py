import json
import logging
from typing import Dict, Any
from datetime import datetime
from decimal import Decimal
from models.portfolio_history import HistoryRequest, SnapshotRequest
from services.portfolio_history_service import PortfolioHistoryService
from models.response import SuccessResponse, ErrorResponse

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime and Decimal objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

portfolio_history_service = PortfolioHistoryService()


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for portfolio history endpoints
    Routes requests to appropriate handlers
    """
    try:
        path = event.get('path', '')
        http_method = event.get('httpMethod', '')

        # Handle OPTIONS request for CORS preflight
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Max-Age': '600',
                },
                'body': ''
            }

        # Get user_id from authorizer context
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

        # Route to appropriate handler
        if path.endswith('/history') and http_method == 'GET':
            return get_portfolio_history(event, user_id)
        elif path.endswith('/history/snapshot') and http_method == 'POST':
            return create_snapshot(event, user_id)
        elif path.endswith('/history/snapshots') and http_method == 'GET':
            return list_snapshots(event, user_id)
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Not Found'})
            }

    except Exception as e:
        logger.error(f"Error in portfolio history handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def get_portfolio_history(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    GET /portfolio/history
    Get historical portfolio data for charts

    Query parameters:
    - period: 24H, 7D, 30D, 90D, 1Y, ALL (default: 30D)
    - portfolio_type: crypto, stock, combined (default: combined)
    - include_benchmarks: true/false (default: false)
    """
    try:
        query_params = event.get('queryStringParameters') or {}

        # Parse request parameters
        request = HistoryRequest(
            period=query_params.get('period', '30D'),
            portfolio_type=query_params.get('portfolio_type', 'combined'),
            include_benchmarks=query_params.get('include_benchmarks', 'false').lower() == 'true'
        )

        # Get history data
        history = portfolio_history_service.get_portfolio_history(user_id, request)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'success': True, 'data': history.dict()}, cls=DateTimeEncoder)
        }

    except ValueError as e:
        logger.error(f"Invalid parameters: {str(e)}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'success': False, 'error': f"Invalid parameters: {str(e)}"})
        }
    except Exception as e:
        logger.error(f"Error getting portfolio history: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'success': False, 'error': str(e)})
        }


def create_snapshot(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    POST /portfolio/history/snapshot
    Create a snapshot of current portfolio

    Body:
    {
        "portfolio_type": "combined"  // crypto, stock, or combined
    }
    """
    try:
        body = json.loads(event.get('body', '{}'))

        # Parse request
        request = SnapshotRequest(
            portfolio_type=body.get('portfolio_type', 'combined')
        )

        # Create snapshot
        result = portfolio_history_service.create_snapshot(user_id, request.portfolio_type)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'success': True, 'data': result, 'message': 'Snapshot created successfully'}, cls=DateTimeEncoder)
        }

    except ValueError as e:
        logger.error(f"Invalid parameters: {str(e)}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'success': False, 'error': f"Invalid parameters: {str(e)}"})
        }
    except Exception as e:
        logger.error(f"Error creating snapshot: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'success': False, 'error': str(e)})
        }


def list_snapshots(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    GET /portfolio/history/snapshots
    List all snapshots for user

    Query parameters:
    - portfolio_type: crypto, stock, combined (default: combined)
    - limit: number of snapshots to return (default: 30)
    """
    try:
        query_params = event.get('queryStringParameters') or {}
        portfolio_type = query_params.get('portfolio_type', 'combined')
        limit = int(query_params.get('limit', '30'))

        # For now, return a simple message
        # In production, you'd implement a proper snapshot listing
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': True,
                'data': {
                    'message': 'Snapshots list endpoint',
                    'user_id': user_id,
                    'portfolio_type': portfolio_type,
                    'limit': limit
                }
            })
        }

    except Exception as e:
        logger.error(f"Error listing snapshots: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'success': False, 'error': str(e)})
        }


# Scheduled job handler
def daily_snapshot_job(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for scheduled daily snapshot creation
    Called by CloudWatch Events / EventBridge
    """
    try:
        logger.info("Starting daily snapshot job")

        result = portfolio_history_service.create_daily_snapshots_for_all_users()

        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        logger.error(f"Error in daily snapshot job: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
