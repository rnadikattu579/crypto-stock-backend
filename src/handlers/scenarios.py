"""
Portfolio Scenarios & Projections API Handler
"""
import json
import logging
from typing import Dict, Any
from decimal import Decimal

from services.scenarios_service import scenarios_service

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main handler for scenarios endpoints"""
    logger.info(f"Scenarios handler received event: {json.dumps(event)}")

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
            if '/scenarios/projection' in path:
                return get_projection(event, user_id)
            elif '/scenarios/monte-carlo' in path:
                return get_monte_carlo(event, user_id)
            elif '/scenarios/retirement' in path:
                return get_retirement(event, user_id)
            elif '/scenarios/goals' in path:
                return get_goals(event, user_id)
        elif http_method == 'POST':
            if '/scenarios/goals' in path:
                return create_goal(event, user_id)
        elif http_method == 'DELETE':
            if '/scenarios/goals/' in path:
                return delete_goal(event, user_id)

        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'Not found'})
        }

    except Exception as e:
        logger.error(f"Error in scenarios handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }


def get_projection(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get future value projection"""
    params = event.get('queryStringParameters', {}) or {}

    years = int(params.get('years', 10))
    monthly_contribution = float(params.get('monthly_contribution', 0))
    expected_return = params.get('expected_return')
    if expected_return:
        expected_return = float(expected_return) / 100  # Convert percentage to decimal
    inflation_rate = float(params.get('inflation_rate', 3)) / 100

    result = scenarios_service.calculate_future_value(
        user_id,
        years=years,
        monthly_contribution=monthly_contribution,
        expected_return=expected_return,
        inflation_rate=inflation_rate
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


def get_monte_carlo(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Run Monte Carlo simulation"""
    params = event.get('queryStringParameters', {}) or {}

    years = int(params.get('years', 10))
    simulations = int(params.get('simulations', 1000))
    monthly_contribution = float(params.get('monthly_contribution', 0))

    result = scenarios_service.run_monte_carlo(
        user_id,
        years=years,
        simulations=simulations,
        monthly_contribution=monthly_contribution
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


def get_retirement(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get retirement projection"""
    params = event.get('queryStringParameters', {}) or {}

    retirement_age = int(params.get('retirement_age', 65))
    current_age = int(params.get('current_age', 30))
    monthly_contribution = float(params.get('monthly_contribution', 500))
    monthly_expense = float(params.get('monthly_expense', 5000))
    social_security = float(params.get('social_security', 2000))

    result = scenarios_service.get_retirement_projection(
        user_id,
        retirement_age=retirement_age,
        current_age=current_age,
        monthly_contribution=monthly_contribution,
        monthly_expense_retirement=monthly_expense,
        social_security=social_security
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


def get_goals(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Get all goals"""
    result = scenarios_service.get_goals(user_id)

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


def create_goal(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Create a new goal"""
    body = json.loads(event.get('body', '{}'))

    goal_name = body.get('goal_name')
    target_amount = float(body.get('target_amount', 0))
    target_date = body.get('target_date')
    priority = body.get('priority', 'medium')
    notes = body.get('notes')

    if not goal_name or not target_amount or not target_date:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'goal_name, target_amount, and target_date are required'})
        }

    result = scenarios_service.create_goal(
        user_id,
        goal_name=goal_name,
        target_amount=target_amount,
        target_date=target_date,
        priority=priority,
        notes=notes
    )

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


def delete_goal(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Delete a goal"""
    path_params = event.get('pathParameters', {}) or {}
    goal_id = path_params.get('goal_id')

    if not goal_id:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': 'goal_id is required'})
        }

    result = scenarios_service.delete_goal(user_id, goal_id)

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
