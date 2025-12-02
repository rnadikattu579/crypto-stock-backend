"""
Advanced Analytics Service
Calculates Sharpe ratio, volatility, drawdown, and benchmark comparisons
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('DYNAMODB_TABLE', 'portfolio-tracker'))

# Annual risk-free rate (approximate US Treasury rate)
RISK_FREE_RATE = 0.05  # 5%


class AnalyticsService:
    """Service for advanced portfolio analytics"""

    def get_advanced_metrics(self, user_id: str, period_days: int = 365) -> Dict[str, Any]:
        """
        Calculate advanced portfolio metrics
        """
        # Get historical portfolio values
        history = self._get_portfolio_history(user_id, period_days)

        if len(history) < 2:
            return {
                'status': 'insufficient_data',
                'message': f'Need at least 2 data points. Found {len(history)}.',
                'metrics': None
            }

        # Calculate returns
        returns = self._calculate_returns(history)

        if len(returns) < 1:
            return {
                'status': 'insufficient_data',
                'message': 'Unable to calculate returns',
                'metrics': None
            }

        # Calculate metrics
        avg_return = sum(returns) / len(returns)
        volatility = self._calculate_volatility(returns)
        sharpe_ratio = self._calculate_sharpe_ratio(avg_return, volatility, period_days)
        sortino_ratio = self._calculate_sortino_ratio(returns, period_days)
        max_drawdown = self._calculate_max_drawdown(history)

        # Calculate cumulative return
        start_value = history[0]['value']
        end_value = history[-1]['value']
        total_return = ((end_value - start_value) / start_value * 100) if start_value > 0 else 0

        # Annualized return
        days = (datetime.fromisoformat(history[-1]['date']) -
                datetime.fromisoformat(history[0]['date'])).days
        if days > 0:
            annualized_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100
        else:
            annualized_return = 0

        return {
            'status': 'calculated',
            'period_days': period_days,
            'data_points': len(history),
            'metrics': {
                'sharpe_ratio': round(sharpe_ratio, 3),
                'sortino_ratio': round(sortino_ratio, 3),
                'volatility': round(volatility * 100, 2),  # As percentage
                'annualized_volatility': round(volatility * math.sqrt(252) * 100, 2),
                'max_drawdown': round(max_drawdown * 100, 2),
                'total_return': round(total_return, 2),
                'annualized_return': round(annualized_return, 2),
                'avg_daily_return': round(avg_return * 100, 4),
                'best_day': round(max(returns) * 100, 2) if returns else 0,
                'worst_day': round(min(returns) * 100, 2) if returns else 0,
                'positive_days': sum(1 for r in returns if r > 0),
                'negative_days': sum(1 for r in returns if r < 0),
                'win_rate': round(sum(1 for r in returns if r > 0) / len(returns) * 100, 1) if returns else 0
            }
        }

    def get_benchmark_comparison(
        self,
        user_id: str,
        benchmarks: List[str] = ['SP500', 'BTC'],
        period_days: int = 365
    ) -> Dict[str, Any]:
        """
        Compare portfolio performance against benchmarks
        """
        # Get portfolio history
        portfolio_history = self._get_portfolio_history(user_id, period_days)

        if len(portfolio_history) < 2:
            return {
                'status': 'insufficient_data',
                'message': 'Not enough portfolio history',
                'comparisons': []
            }

        # Calculate portfolio metrics
        portfolio_returns = self._calculate_returns(portfolio_history)
        portfolio_total = self._calculate_total_return(portfolio_history)

        # Get benchmark data (mock data for now - would integrate with real APIs)
        benchmark_data = self._get_benchmark_data(benchmarks, period_days)

        comparisons = []

        # Portfolio metrics
        portfolio_metrics = {
            'name': 'Your Portfolio',
            'symbol': 'PORTFOLIO',
            'total_return': round(portfolio_total * 100, 2),
            'volatility': round(self._calculate_volatility(portfolio_returns) * math.sqrt(252) * 100, 2),
            'sharpe_ratio': round(self._calculate_sharpe_ratio(
                sum(portfolio_returns) / len(portfolio_returns),
                self._calculate_volatility(portfolio_returns),
                period_days
            ), 3),
            'max_drawdown': round(self._calculate_max_drawdown(portfolio_history) * 100, 2),
            'data_points': len(portfolio_history)
        }
        comparisons.append(portfolio_metrics)

        # Benchmark metrics
        for benchmark in benchmark_data:
            if benchmark['history']:
                returns = self._calculate_returns(benchmark['history'])
                total_return = self._calculate_total_return(benchmark['history'])
                volatility = self._calculate_volatility(returns)

                comparisons.append({
                    'name': benchmark['name'],
                    'symbol': benchmark['symbol'],
                    'total_return': round(total_return * 100, 2),
                    'volatility': round(volatility * math.sqrt(252) * 100, 2),
                    'sharpe_ratio': round(self._calculate_sharpe_ratio(
                        sum(returns) / len(returns) if returns else 0,
                        volatility,
                        period_days
                    ), 3),
                    'max_drawdown': round(self._calculate_max_drawdown(benchmark['history']) * 100, 2),
                    'data_points': len(benchmark['history'])
                })

        # Calculate alpha and beta vs S&P 500
        sp500_data = next((b for b in benchmark_data if b['symbol'] == 'SP500'), None)
        if sp500_data and sp500_data['history']:
            sp500_returns = self._calculate_returns(sp500_data['history'])
            alpha, beta = self._calculate_alpha_beta(portfolio_returns, sp500_returns)
            portfolio_metrics['alpha'] = round(alpha * 100, 2)
            portfolio_metrics['beta'] = round(beta, 3)

        return {
            'status': 'calculated',
            'period_days': period_days,
            'comparisons': comparisons,
            'outperforming': [
                c['name'] for c in comparisons[1:]
                if portfolio_metrics['total_return'] > c['total_return']
            ]
        }

    def get_risk_metrics(self, user_id: str) -> Dict[str, Any]:
        """
        Get portfolio risk analysis
        """
        # Get different period metrics
        metrics_30d = self.get_advanced_metrics(user_id, 30)
        metrics_90d = self.get_advanced_metrics(user_id, 90)
        metrics_365d = self.get_advanced_metrics(user_id, 365)

        return {
            'risk_analysis': {
                '30_day': metrics_30d.get('metrics'),
                '90_day': metrics_90d.get('metrics'),
                '365_day': metrics_365d.get('metrics')
            },
            'risk_score': self._calculate_risk_score(metrics_365d.get('metrics')),
            'risk_level': self._get_risk_level(metrics_365d.get('metrics'))
        }

    def _get_portfolio_history(self, user_id: str, days: int) -> List[Dict]:
        """Get portfolio value history"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            response = table.query(
                KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') &
                                      Key('SK').begins_with('SNAPSHOT#combined#')
            )

            history = []
            for item in response.get('Items', []):
                snapshot_date = datetime.fromisoformat(item['date'].replace('Z', '+00:00'))
                if start_date <= snapshot_date <= end_date:
                    history.append({
                        'date': item['date'],
                        'value': float(item.get('total_value', 0))
                    })

            # Sort by date
            history.sort(key=lambda x: x['date'])
            return history

        except Exception as e:
            logger.error(f"Error getting portfolio history: {str(e)}")
            return []

    def _calculate_returns(self, history: List[Dict]) -> List[float]:
        """Calculate daily returns from price history"""
        returns = []
        for i in range(1, len(history)):
            prev_value = history[i - 1]['value']
            curr_value = history[i]['value']
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                returns.append(daily_return)
        return returns

    def _calculate_total_return(self, history: List[Dict]) -> float:
        """Calculate total return over period"""
        if len(history) < 2:
            return 0
        start = history[0]['value']
        end = history[-1]['value']
        if start > 0:
            return (end - start) / start
        return 0

    def _calculate_volatility(self, returns: List[float]) -> float:
        """Calculate standard deviation of returns"""
        if len(returns) < 2:
            return 0

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(variance)

    def _calculate_sharpe_ratio(
        self,
        avg_return: float,
        volatility: float,
        period_days: int
    ) -> float:
        """
        Calculate Sharpe ratio
        (Return - Risk-free rate) / Volatility
        """
        if volatility == 0:
            return 0

        # Annualize
        annual_return = avg_return * 252
        annual_volatility = volatility * math.sqrt(252)

        sharpe = (annual_return - RISK_FREE_RATE) / annual_volatility
        return sharpe

    def _calculate_sortino_ratio(self, returns: List[float], period_days: int) -> float:
        """
        Calculate Sortino ratio (uses downside deviation only)
        """
        if not returns:
            return 0

        avg_return = sum(returns) / len(returns)

        # Calculate downside deviation (only negative returns)
        negative_returns = [r for r in returns if r < 0]
        if not negative_returns:
            return 0

        downside_variance = sum(r ** 2 for r in negative_returns) / len(returns)
        downside_deviation = math.sqrt(downside_variance)

        if downside_deviation == 0:
            return 0

        # Annualize
        annual_return = avg_return * 252
        annual_downside = downside_deviation * math.sqrt(252)

        sortino = (annual_return - RISK_FREE_RATE) / annual_downside
        return sortino

    def _calculate_max_drawdown(self, history: List[Dict]) -> float:
        """Calculate maximum drawdown"""
        if len(history) < 2:
            return 0

        peak = history[0]['value']
        max_dd = 0

        for point in history:
            value = point['value']
            if value > peak:
                peak = value
            elif peak > 0:
                dd = (peak - value) / peak
                max_dd = max(max_dd, dd)

        return max_dd

    def _calculate_alpha_beta(
        self,
        portfolio_returns: List[float],
        benchmark_returns: List[float]
    ) -> tuple:
        """Calculate alpha and beta vs benchmark"""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 0, 1

        # Calculate means
        port_mean = sum(portfolio_returns) / len(portfolio_returns)
        bench_mean = sum(benchmark_returns) / len(benchmark_returns)

        # Calculate covariance and variance
        covariance = sum(
            (p - port_mean) * (b - bench_mean)
            for p, b in zip(portfolio_returns, benchmark_returns)
        ) / len(portfolio_returns)

        bench_variance = sum(
            (b - bench_mean) ** 2 for b in benchmark_returns
        ) / len(benchmark_returns)

        if bench_variance == 0:
            return 0, 1

        # Beta = Covariance / Variance of benchmark
        beta = covariance / bench_variance

        # Alpha = Portfolio return - (Risk-free + Beta * (Benchmark return - Risk-free))
        alpha = port_mean - (RISK_FREE_RATE / 252 + beta * (bench_mean - RISK_FREE_RATE / 252))

        return alpha * 252, beta  # Annualized alpha

    def _get_benchmark_data(
        self,
        benchmarks: List[str],
        period_days: int
    ) -> List[Dict]:
        """
        Get benchmark historical data
        In production, this would fetch from real APIs
        """
        benchmark_info = {
            'SP500': {'name': 'S&P 500', 'base_return': 0.10},
            'BTC': {'name': 'Bitcoin', 'base_return': 0.50},
            'ETH': {'name': 'Ethereum', 'base_return': 0.60},
            'NASDAQ': {'name': 'NASDAQ', 'base_return': 0.12}
        }

        results = []

        for symbol in benchmarks:
            info = benchmark_info.get(symbol, {'name': symbol, 'base_return': 0.08})

            # Generate synthetic benchmark data
            # In production, replace with real API calls
            history = self._generate_synthetic_benchmark(
                info['base_return'],
                period_days
            )

            results.append({
                'symbol': symbol,
                'name': info['name'],
                'history': history
            })

        return results

    def _generate_synthetic_benchmark(
        self,
        annual_return: float,
        days: int
    ) -> List[Dict]:
        """
        Generate synthetic benchmark data for demo purposes
        In production, use real market data APIs
        """
        import random
        random.seed(42)  # Reproducible results

        daily_return = annual_return / 252
        volatility = 0.02  # 2% daily volatility

        history = []
        value = 10000  # Starting value

        end_date = datetime.utcnow()
        for i in range(days, 0, -1):
            date = (end_date - timedelta(days=i)).isoformat()
            history.append({
                'date': date,
                'value': value
            })
            # Random walk with drift
            change = daily_return + random.gauss(0, volatility)
            value = value * (1 + change)

        return history

    def _calculate_risk_score(self, metrics: Optional[Dict]) -> int:
        """Calculate overall risk score (1-100)"""
        if not metrics:
            return 50

        score = 50  # Base score

        # Adjust for volatility (higher = more risk)
        volatility = metrics.get('annualized_volatility', 20)
        if volatility > 40:
            score += 20
        elif volatility > 25:
            score += 10
        elif volatility < 15:
            score -= 10

        # Adjust for max drawdown
        max_dd = metrics.get('max_drawdown', 10)
        if max_dd > 30:
            score += 15
        elif max_dd > 20:
            score += 8
        elif max_dd < 10:
            score -= 5

        # Adjust for Sharpe ratio (higher = less risk-adjusted)
        sharpe = metrics.get('sharpe_ratio', 0)
        if sharpe < 0:
            score += 15
        elif sharpe < 0.5:
            score += 5
        elif sharpe > 1.5:
            score -= 10

        return max(1, min(100, score))

    def _get_risk_level(self, metrics: Optional[Dict]) -> str:
        """Get risk level description"""
        score = self._calculate_risk_score(metrics)

        if score >= 75:
            return 'Very High'
        elif score >= 60:
            return 'High'
        elif score >= 40:
            return 'Moderate'
        elif score >= 25:
            return 'Low'
        else:
            return 'Very Low'


# Singleton instance
analytics_service = AnalyticsService()
