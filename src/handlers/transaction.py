import json
import logging
from typing import Dict, Any
from datetime import datetime
from decimal import Decimal
from models.transaction import TransactionCreate, TransactionUpdate, CostBasisMethod
from services.transaction_service import TransactionService
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


transaction_service = TransactionService()


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler for transaction endpoints"""
    try:
        path = event.get('path', '')
        http_method = event.get('httpMethod', '')

        # Handle CORS preflight
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
        if path.endswith('/transactions') and http_method == 'GET':
            return list_transactions(event, user_id)
        elif path.endswith('/transactions') and http_method == 'POST':
            return create_transaction(event, user_id)
        elif path.endswith('/transactions/history') and http_method == 'GET':
            return get_transaction_history(event, user_id)
        elif '/transactions/' in path and http_method == 'GET':
            return get_transaction(event, user_id)
        elif '/transactions/' in path and http_method == 'PUT':
            return update_transaction(event, user_id)
        elif '/transactions/' in path and http_method == 'DELETE':
            return delete_transaction(event, user_id)
        elif path.endswith('/cost-basis') and http_method == 'GET':
            return get_cost_basis(event, user_id)
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Not found'})
            }

    except Exception as e:
        logger.error(f"Error in transaction handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def create_transaction(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Create a new transaction"""
    try:
        body = json.loads(event.get('body', '{}'))

        # Parse transaction_date
        if 'transaction_date' in body:
            body['transaction_date'] = datetime.fromisoformat(body['transaction_date'].replace('Z', '+00:00'))

        transaction_data = TransactionCreate(**body)
        transaction = transaction_service.create_transaction(user_id, transaction_data)

        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': True,
                'data': transaction.dict()
            }, cls=DateTimeEncoder)
        }

    except ValueError as e:
        logger.error(f"Validation error creating transaction: {str(e)}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        logger.error(f"Error creating transaction: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def get_transaction(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get a specific transaction"""
    try:
        # Extract transaction_id from path
        path = event.get('path', '')
        transaction_id = path.split('/transactions/')[-1]

        transaction = transaction_service.get_transaction(user_id, transaction_id)

        if not transaction:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Transaction not found'})
            }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': True,
                'data': transaction.dict()
            }, cls=DateTimeEncoder)
        }

    except Exception as e:
        logger.error(f"Error getting transaction: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def list_transactions(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """List transactions with optional filters"""
    try:
        query_params = event.get('queryStringParameters') or {}

        # Parse filters
        asset_id = query_params.get('asset_id')
        asset_type = query_params.get('asset_type')
        transaction_type = query_params.get('transaction_type')
        limit = int(query_params.get('limit', 100))

        # Parse date filters
        start_date = None
        end_date = None
        if 'start_date' in query_params:
            start_date = datetime.fromisoformat(query_params['start_date'].replace('Z', '+00:00'))
        if 'end_date' in query_params:
            end_date = datetime.fromisoformat(query_params['end_date'].replace('Z', '+00:00'))

        transactions = transaction_service.get_transactions(
            user_id,
            asset_id=asset_id,
            asset_type=asset_type,
            transaction_type=transaction_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': True,
                'data': {
                    'transactions': [t.dict() for t in transactions],
                    'count': len(transactions)
                }
            }, cls=DateTimeEncoder)
        }

    except Exception as e:
        logger.error(f"Error listing transactions: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def update_transaction(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Update a transaction"""
    try:
        # Extract transaction_id from path
        path = event.get('path', '')
        transaction_id = path.split('/transactions/')[-1]

        body = json.loads(event.get('body', '{}'))

        # Parse transaction_date if present
        if 'transaction_date' in body:
            body['transaction_date'] = datetime.fromisoformat(body['transaction_date'].replace('Z', '+00:00'))

        update_data = TransactionUpdate(**body)
        transaction = transaction_service.update_transaction(user_id, transaction_id, update_data)

        if not transaction:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Transaction not found'})
            }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': True,
                'data': transaction.dict()
            }, cls=DateTimeEncoder)
        }

    except ValueError as e:
        logger.error(f"Validation error updating transaction: {str(e)}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        logger.error(f"Error updating transaction: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def delete_transaction(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Delete a transaction"""
    try:
        # Extract transaction_id from path
        path = event.get('path', '')
        transaction_id = path.split('/transactions/')[-1]

        success = transaction_service.delete_transaction(user_id, transaction_id)

        if not success:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Transaction not found'})
            }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': True,
                'message': 'Transaction deleted successfully'
            })
        }

    except Exception as e:
        logger.error(f"Error deleting transaction: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def get_transaction_history(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get transaction history with aggregated statistics"""
    try:
        query_params = event.get('queryStringParameters') or {}

        asset_id = query_params.get('asset_id')
        asset_type = query_params.get('asset_type')

        history = transaction_service.get_transaction_history(
            user_id,
            asset_id=asset_id,
            asset_type=asset_type
        )

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': True,
                'data': history.dict()
            }, cls=DateTimeEncoder)
        }

    except Exception as e:
        logger.error(f"Error getting transaction history: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def get_cost_basis(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get cost basis calculation for an asset"""
    try:
        query_params = event.get('queryStringParameters') or {}

        asset_id = query_params.get('asset_id')
        if not asset_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'asset_id is required'})
            }

        method_str = query_params.get('method', 'fifo').lower()
        method = CostBasisMethod(method_str)

        cost_basis = transaction_service.calculate_cost_basis(user_id, asset_id, method)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': True,
                'data': cost_basis.dict()
            }, cls=DateTimeEncoder)
        }

    except ValueError as e:
        logger.error(f"Validation error getting cost basis: {str(e)}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        logger.error(f"Error getting cost basis: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }
