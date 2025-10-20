import json
from typing import Dict, Any
from datetime import datetime
from ..models.portfolio import PriceRequest
from ..models.response import SuccessResponse, ErrorResponse
from ..services.price_service import PriceService


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for price fetching endpoints"""
    try:
        http_method = event.get('httpMethod', '')
        body = json.loads(event.get('body', '{}'))

        # POST /prices
        if http_method == 'POST':
            price_request = PriceRequest(**body)
            price_service = PriceService()

            prices = price_service.get_prices(
                price_request.symbols,
                price_request.asset_type.value
            )

            # Format response
            price_responses = [
                {
                    'symbol': symbol,
                    'price': price,
                    'currency': 'USD',
                    'timestamp': datetime.utcnow().isoformat()
                }
                for symbol, price in prices.items()
            ]

            response = SuccessResponse(data=price_responses)

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
