import json
from typing import Dict, Any
from ..models.user import UserCreate, UserLogin
from ..models.response import SuccessResponse, ErrorResponse
from ..services.auth_service import AuthService


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for authentication endpoints"""
    try:
        path = event.get('path', '')
        http_method = event.get('httpMethod', '')
        body = json.loads(event.get('body', '{}'))

        auth_service = AuthService()

        # POST /auth/register
        if path.endswith('/auth/register') and http_method == 'POST':
            user_create = UserCreate(**body)
            token = auth_service.register_user(user_create)

            response = SuccessResponse(
                data=token.dict(),
                message="User registered successfully"
            )

            return {
                'statusCode': 201,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps(response.dict(), default=str)
            }

        # POST /auth/login
        elif path.endswith('/auth/login') and http_method == 'POST':
            user_login = UserLogin(**body)
            token = auth_service.login_user(user_login)

            response = SuccessResponse(
                data=token.dict(),
                message="Login successful"
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
