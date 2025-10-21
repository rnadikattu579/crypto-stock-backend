import os
from typing import Dict, Any
from jose import jwt, JWTError


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda authorizer for JWT validation"""
    try:
        # Extract token from Authorization header (case-insensitive)
        headers = event.get('headers', {})

        # Try different header casings
        token = (headers.get('Authorization') or
                headers.get('authorization') or
                headers.get('AUTHORIZATION') or '')

        print(f"Token received: {token[:20]}..." if token else "No token found")
        print(f"Available headers: {list(headers.keys())}")

        if token.startswith('Bearer ') or token.startswith('bearer '):
            token = token[7:]
        elif not token:
            raise ValueError("No authorization token provided")

        # Verify token
        secret_key = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])

        user_id = payload.get('user_id')
        email = payload.get('email')

        if not user_id or not email:
            raise ValueError("Invalid token payload")

        # Return allow policy
        return {
            'principalId': user_id,
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Action': 'execute-api:Invoke',
                        'Effect': 'Allow',
                        'Resource': event['methodArn']
                    }
                ]
            },
            'context': {
                'user_id': user_id,
                'email': email
            }
        }

    except (JWTError, ValueError) as e:
        print(f"Authorization failed: {str(e)}")
        # Return deny policy
        return {
            'principalId': 'unauthorized',
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Action': 'execute-api:Invoke',
                        'Effect': 'Deny',
                        'Resource': event['methodArn']
                    }
                ]
            }
        }
