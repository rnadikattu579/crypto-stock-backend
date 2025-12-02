"""
Portfolio Scenarios & Projections Service
Provides future value calculations, goal tracking, and Monte Carlo simulations
"""
import math
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
import logging

from services.portfolio_service import portfolio_service
from services.portfolio_history_service import portfolio_history_service
from models.portfolio_history import HistoryRequest

logger = logging.getLogger()


class ScenariosService:
    """Service for portfolio projections and scenario analysis"""

    def __init__(self):
        self.risk_free_rate = 0.04  # 4% annual risk-free rate

    def calculate_future_value(
        self,
        user_id: str,
        years: int = 10,
        monthly_contribution: float = 0,
        expected_return: Optional[float] = None,
        inflation_rate: float = 0.03
    ) -> Dict[str, Any]:
        """
        Calculate future portfolio value with compound growth

        Args:
            user_id: User ID
            years: Number of years to project
            monthly_contribution: Monthly contribution amount
            expected_return: Expected annual return (if None, use historical)
            inflation_rate: Annual inflation rate for real value calculation
        """
        # Get current portfolio value
        summary = portfolio_service.get_portfolio_summary(user_id)
        current_value = float(summary.total_value)

        if current_value == 0 and monthly_contribution == 0:
            return {
                'status': 'error',
                'message': 'No portfolio value or contributions to project'
            }

        # Calculate expected return from historical data if not provided
        if expected_return is None:
            expected_return = self._calculate_historical_return(user_id)

        # Monthly rate
        monthly_rate = expected_return / 12
        months = years * 12

        # Calculate projections
        projections = []
        nominal_value = current_value
        real_value = current_value
        total_contributions = 0

        for month in range(1, months + 1):
            # Add monthly contribution
            nominal_value += monthly_contribution
            total_contributions += monthly_contribution

            # Apply monthly return
            nominal_value *= (1 + monthly_rate)

            # Calculate real value (inflation-adjusted)
            inflation_factor = (1 + inflation_rate) ** (month / 12)
            real_value = nominal_value / inflation_factor

            # Record yearly snapshots
            if month % 12 == 0:
                year = month // 12
                projections.append({
                    'year': year,
                    'nominal_value': round(nominal_value, 2),
                    'real_value': round(real_value, 2),
                    'total_contributions': round(total_contributions, 2),
                    'investment_gain': round(nominal_value - current_value - total_contributions, 2)
                })

        final_nominal = projections[-1]['nominal_value'] if projections else current_value
        final_real = projections[-1]['real_value'] if projections else current_value
        total_gain = final_nominal - current_value - total_contributions

        return {
            'status': 'success',
            'current_value': current_value,
            'projection_years': years,
            'monthly_contribution': monthly_contribution,
            'expected_annual_return': round(expected_return * 100, 2),
            'inflation_rate': round(inflation_rate * 100, 2),
            'final_nominal_value': round(final_nominal, 2),
            'final_real_value': round(final_real, 2),
            'total_contributions': round(total_contributions, 2),
            'total_investment_gain': round(total_gain, 2),
            'projections': projections
        }

    def run_monte_carlo(
        self,
        user_id: str,
        years: int = 10,
        simulations: int = 1000,
        monthly_contribution: float = 0
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation for portfolio projections

        Args:
            user_id: User ID
            years: Number of years to project
            simulations: Number of simulation runs
            monthly_contribution: Monthly contribution amount
        """
        # Get current portfolio value
        summary = portfolio_service.get_portfolio_summary(user_id)
        current_value = float(summary.total_value)

        if current_value == 0 and monthly_contribution == 0:
            return {
                'status': 'error',
                'message': 'No portfolio value or contributions to simulate'
            }

        # Get historical volatility and return
        historical_return = self._calculate_historical_return(user_id)
        historical_volatility = self._calculate_historical_volatility(user_id)

        # Default values if no history
        if historical_return == 0.08:  # Default was used
            historical_volatility = 0.15  # 15% default volatility

        # Run simulations
        results = []
        monthly_return = historical_return / 12
        monthly_volatility = historical_volatility / math.sqrt(12)

        for _ in range(simulations):
            value = current_value
            for month in range(years * 12):
                # Add contribution
                value += monthly_contribution
                # Random return based on normal distribution
                random_return = random.gauss(monthly_return, monthly_volatility)
                value *= (1 + random_return)
                # Prevent negative values
                value = max(0, value)
            results.append(value)

        # Sort results for percentile calculation
        results.sort()

        # Calculate percentiles
        def percentile(data, p):
            index = int(len(data) * p / 100)
            return data[min(index, len(data) - 1)]

        p5 = percentile(results, 5)
        p25 = percentile(results, 25)
        p50 = percentile(results, 50)
        p75 = percentile(results, 75)
        p95 = percentile(results, 95)

        avg = sum(results) / len(results)

        # Calculate probability of different outcomes
        prob_double = sum(1 for r in results if r >= current_value * 2) / simulations * 100
        prob_loss = sum(1 for r in results if r < current_value) / simulations * 100

        # Create distribution buckets
        min_val = min(results)
        max_val = max(results)
        bucket_size = (max_val - min_val) / 20
        distribution = []

        for i in range(20):
            bucket_min = min_val + i * bucket_size
            bucket_max = bucket_min + bucket_size
            count = sum(1 for r in results if bucket_min <= r < bucket_max)
            distribution.append({
                'range_min': round(bucket_min, 2),
                'range_max': round(bucket_max, 2),
                'count': count,
                'percentage': round(count / simulations * 100, 2)
            })

        return {
            'status': 'success',
            'current_value': current_value,
            'projection_years': years,
            'simulations': simulations,
            'monthly_contribution': monthly_contribution,
            'expected_return': round(historical_return * 100, 2),
            'volatility': round(historical_volatility * 100, 2),
            'results': {
                'worst_case': round(p5, 2),
                'pessimistic': round(p25, 2),
                'median': round(p50, 2),
                'optimistic': round(p75, 2),
                'best_case': round(p95, 2),
                'average': round(avg, 2)
            },
            'probabilities': {
                'double_investment': round(prob_double, 1),
                'loss': round(prob_loss, 1)
            },
            'distribution': distribution
        }

    def create_goal(
        self,
        user_id: str,
        goal_name: str,
        target_amount: float,
        target_date: str,
        priority: str = 'medium',
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a financial goal"""
        from utils.db import get_table
        import uuid

        table = get_table()
        goal_id = str(uuid.uuid4())

        # Calculate months until target
        target_dt = datetime.strptime(target_date, '%Y-%m-%d')
        months_remaining = (target_dt.year - datetime.now().year) * 12 + (target_dt.month - datetime.now().month)

        # Get current portfolio value
        summary = portfolio_service.get_portfolio_summary(user_id)
        current_value = float(summary.total_value)

        # Calculate required monthly contribution (simplified)
        if months_remaining > 0:
            gap = target_amount - current_value
            monthly_required = gap / months_remaining if gap > 0 else 0
        else:
            monthly_required = 0

        goal = {
            'PK': f'USER#{user_id}',
            'SK': f'GOAL#{goal_id}',
            'goal_id': goal_id,
            'user_id': user_id,
            'goal_name': goal_name,
            'target_amount': Decimal(str(target_amount)),
            'target_date': target_date,
            'priority': priority,
            'notes': notes,
            'current_progress': Decimal(str(current_value)),
            'monthly_required': Decimal(str(round(monthly_required, 2))),
            'status': 'active',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }

        table.put_item(Item=goal)

        return {
            'status': 'success',
            'goal': {
                'goal_id': goal_id,
                'goal_name': goal_name,
                'target_amount': target_amount,
                'target_date': target_date,
                'priority': priority,
                'current_progress': current_value,
                'progress_percentage': round(current_value / target_amount * 100, 1) if target_amount > 0 else 0,
                'monthly_required': round(monthly_required, 2),
                'months_remaining': months_remaining,
                'on_track': current_value >= (target_amount * (1 - months_remaining / max(1, months_remaining + 1)))
            }
        }

    def get_goals(self, user_id: str) -> Dict[str, Any]:
        """Get all goals for a user"""
        from utils.db import get_table
        from boto3.dynamodb.conditions import Key

        table = get_table()

        response = table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('GOAL#')
        )

        # Get current portfolio value for progress calculation
        summary = portfolio_service.get_portfolio_summary(user_id)
        current_value = float(summary.total_value)

        goals = []
        for item in response.get('Items', []):
            target_amount = float(item.get('target_amount', 0))
            target_date = item.get('target_date', '')

            # Calculate months remaining
            try:
                target_dt = datetime.strptime(target_date, '%Y-%m-%d')
                months_remaining = (target_dt.year - datetime.now().year) * 12 + (target_dt.month - datetime.now().month)
            except:
                months_remaining = 0

            # Calculate required monthly contribution
            if months_remaining > 0:
                gap = target_amount - current_value
                monthly_required = gap / months_remaining if gap > 0 else 0
            else:
                monthly_required = 0

            progress_pct = round(current_value / target_amount * 100, 1) if target_amount > 0 else 0

            goals.append({
                'goal_id': item.get('goal_id'),
                'goal_name': item.get('goal_name'),
                'target_amount': target_amount,
                'target_date': target_date,
                'priority': item.get('priority', 'medium'),
                'notes': item.get('notes'),
                'current_progress': current_value,
                'progress_percentage': min(100, progress_pct),
                'monthly_required': round(monthly_required, 2),
                'months_remaining': max(0, months_remaining),
                'status': 'completed' if progress_pct >= 100 else item.get('status', 'active'),
                'on_track': progress_pct >= (100 - months_remaining) if months_remaining > 0 else progress_pct >= 100
            })

        # Sort by priority and target date
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        goals.sort(key=lambda g: (priority_order.get(g['priority'], 1), g['target_date']))

        return {
            'status': 'success',
            'goals': goals,
            'total_goals': len(goals),
            'completed_goals': sum(1 for g in goals if g['status'] == 'completed'),
            'current_portfolio_value': current_value
        }

    def delete_goal(self, user_id: str, goal_id: str) -> Dict[str, Any]:
        """Delete a goal"""
        from utils.db import get_table

        table = get_table()

        table.delete_item(
            Key={
                'PK': f'USER#{user_id}',
                'SK': f'GOAL#{goal_id}'
            }
        )

        return {'status': 'success', 'message': 'Goal deleted'}

    def get_retirement_projection(
        self,
        user_id: str,
        retirement_age: int = 65,
        current_age: int = 30,
        monthly_contribution: float = 500,
        monthly_expense_retirement: float = 5000,
        social_security: float = 2000
    ) -> Dict[str, Any]:
        """
        Calculate retirement projection

        Args:
            user_id: User ID
            retirement_age: Age at retirement
            current_age: Current age
            monthly_contribution: Monthly savings until retirement
            monthly_expense_retirement: Monthly expenses in retirement
            social_security: Expected monthly social security
        """
        # Get current portfolio
        summary = portfolio_service.get_portfolio_summary(user_id)
        current_value = float(summary.total_value)

        years_to_retirement = retirement_age - current_age
        if years_to_retirement <= 0:
            return {
                'status': 'error',
                'message': 'Retirement age must be greater than current age'
            }

        # Accumulation phase
        expected_return = self._calculate_historical_return(user_id)
        monthly_rate = expected_return / 12

        # Calculate value at retirement
        retirement_value = current_value
        accumulation_projections = []

        for year in range(1, years_to_retirement + 1):
            for _ in range(12):
                retirement_value += monthly_contribution
                retirement_value *= (1 + monthly_rate)

            accumulation_projections.append({
                'age': current_age + year,
                'portfolio_value': round(retirement_value, 2)
            })

        # Distribution phase - how long will it last?
        # Assume 4% withdrawal rate with 5% return in retirement
        retirement_return = 0.05
        monthly_retirement_return = retirement_return / 12
        monthly_need = monthly_expense_retirement - social_security

        distribution_value = retirement_value
        distribution_projections = []
        years_lasted = 0

        for year in range(1, 51):  # Project up to 50 years in retirement
            for _ in range(12):
                distribution_value *= (1 + monthly_retirement_return)
                distribution_value -= monthly_need

                if distribution_value <= 0:
                    break

            if distribution_value <= 0:
                break

            years_lasted = year
            distribution_projections.append({
                'age': retirement_age + year,
                'portfolio_value': round(distribution_value, 2)
            })

        # Safe withdrawal rate
        annual_need = monthly_need * 12
        safe_withdrawal_rate = (annual_need / retirement_value * 100) if retirement_value > 0 else 0

        return {
            'status': 'success',
            'current_age': current_age,
            'retirement_age': retirement_age,
            'current_portfolio': current_value,
            'monthly_contribution': monthly_contribution,
            'years_to_retirement': years_to_retirement,
            'projected_retirement_value': round(retirement_value, 2),
            'monthly_expense_retirement': monthly_expense_retirement,
            'social_security': social_security,
            'monthly_shortfall': monthly_need,
            'years_funds_last': years_lasted,
            'age_funds_depleted': retirement_age + years_lasted if years_lasted < 50 else None,
            'safe_withdrawal_rate': round(safe_withdrawal_rate, 2),
            'is_sustainable': years_lasted >= 30,
            'accumulation_projections': accumulation_projections,
            'distribution_projections': distribution_projections
        }

    def _calculate_historical_return(self, user_id: str) -> float:
        """Calculate historical annualized return from portfolio history"""
        try:
            request = HistoryRequest(period='1Y', portfolio_type='combined')
            history = portfolio_history_service.get_portfolio_history(user_id, request)
            data_points = history.data_points

            if len(data_points) < 2:
                return 0.08  # Default 8% if not enough data

            first_value = data_points[0].portfolio_value
            last_value = data_points[-1].portfolio_value

            if first_value <= 0:
                return 0.08

            # Calculate total return
            total_return = (last_value - first_value) / first_value

            # Annualize based on data points (assuming daily)
            days = len(data_points)
            if days < 30:
                return 0.08

            annualized = (1 + total_return) ** (365 / days) - 1

            # Clamp to reasonable bounds
            return max(-0.5, min(0.5, annualized))

        except Exception as e:
            logger.error(f"Error calculating historical return: {e}")
            return 0.08

    def _calculate_historical_volatility(self, user_id: str) -> float:
        """Calculate historical volatility from portfolio history"""
        try:
            request = HistoryRequest(period='1Y', portfolio_type='combined')
            history = portfolio_history_service.get_portfolio_history(user_id, request)
            data_points = history.data_points

            if len(data_points) < 30:
                return 0.15  # Default 15% if not enough data

            # Calculate daily returns
            returns = []
            for i in range(1, len(data_points)):
                prev_value = data_points[i-1].portfolio_value
                curr_value = data_points[i].portfolio_value

                if prev_value > 0:
                    daily_return = (curr_value - prev_value) / prev_value
                    returns.append(daily_return)

            if len(returns) < 20:
                return 0.15

            # Calculate standard deviation
            avg_return = sum(returns) / len(returns)
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            daily_volatility = math.sqrt(variance)

            # Annualize
            annual_volatility = daily_volatility * math.sqrt(252)

            # Clamp to reasonable bounds
            return max(0.05, min(0.60, annual_volatility))

        except Exception as e:
            logger.error(f"Error calculating historical volatility: {e}")
            return 0.15


scenarios_service = ScenariosService()
