import json
from typing import Dict, Any
from models.portfolio import AssetCreate, AssetUpdate, AssetType
from models.response import SuccessResponse, ErrorResponse
from services.portfolio_service import PortfolioService


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for portfolio endpoints"""
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

        body = json.loads(event.get('body', '{}')) if event.get('body') else {}

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

        portfolio_service = PortfolioService()

        # GET /portfolio/crypto
        if path.endswith('/portfolio/crypto') and http_method == 'GET':
            portfolio = portfolio_service.get_portfolio(user_id, AssetType.CRYPTO)
            response = SuccessResponse(data=portfolio.dict())

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps(response.dict(), default=str)
            }

        # GET /portfolio/stocks
        elif path.endswith('/portfolio/stocks') and http_method == 'GET':
            portfolio = portfolio_service.get_portfolio(user_id, AssetType.STOCK)
            response = SuccessResponse(data=portfolio.dict())

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps(response.dict(), default=str)
            }

        # GET /portfolio/summary
        elif path.endswith('/portfolio/summary') and http_method == 'GET':
            summary = portfolio_service.get_portfolio_summary(user_id)
            response = SuccessResponse(data=summary.dict())

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps(response.dict(), default=str)
            }

        # POST /portfolio/assets
        elif path.endswith('/portfolio/assets') and http_method == 'POST':
            asset_create = AssetCreate(**body)
            asset = portfolio_service.add_asset(user_id, asset_create)
            response = SuccessResponse(
                data=asset.dict(),
                message="Asset added successfully"
            )

            return {
                'statusCode': 201,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps(response.dict(), default=str)
            }

        # PUT /portfolio/assets/{asset_id}
        elif '/portfolio/assets/' in path and http_method == 'PUT':
            asset_id = event.get('pathParameters', {}).get('asset_id')
            if not asset_id:
                raise ValueError("Asset ID is required")

            asset_update = AssetUpdate(**body)
            asset = portfolio_service.update_asset(user_id, asset_id, asset_update)
            response = SuccessResponse(
                data=asset.dict(),
                message="Asset updated successfully"
            )

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps(response.dict(), default=str)
            }

        # DELETE /portfolio/assets/{asset_id}
        elif '/portfolio/assets/' in path and http_method == 'DELETE':
            asset_id = event.get('pathParameters', {}).get('asset_id')
            if not asset_id:
                raise ValueError("Asset ID is required")

            portfolio_service.delete_asset(user_id, asset_id)
            response = SuccessResponse(
                data=None,
                message="Asset deleted successfully"
            )

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps(response.dict(), default=str)
            }

        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'Not found'})
            }

    except ValueError as e:
        error_response = ErrorResponse(error=str(e))
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps(error_response.dict())
        }

    except Exception as e:
        error_response = ErrorResponse(
            error="Internal server error",
            detail=str(e)
        )
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps(error_response.dict())
        }
