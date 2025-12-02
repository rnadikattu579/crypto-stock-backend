"""
Portfolio Rebalancing Service
Manages target allocations and calculates rebalancing recommendations
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key
import os
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('DYNAMODB_TABLE', 'portfolio-tracker'))


class RebalanceService:
    """Service for portfolio rebalancing calculations"""

    DEFAULT_DRIFT_THRESHOLD = Decimal('5.0')  # 5% drift threshold

    def get_target_allocations(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get user's target allocation settings
        """
        try:
            response = table.query(
                KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') &
                                      Key('SK').begins_with('TARGET_ALLOCATION#')
            )

            allocations = []
            for item in response.get('Items', []):
                allocations.append({
                    'allocation_id': item['allocation_id'],
                    'asset_type': item['asset_type'],
                    'symbol': item.get('symbol'),
                    'category': item.get('category'),
                    'target_percentage': float(item['target_percentage']),
                    'created_at': item.get('created_at'),
                    'updated_at': item.get('updated_at')
                })

            return allocations
        except Exception as e:
            logger.error(f"Error getting target allocations: {str(e)}")
            return []

    def set_target_allocation(
        self,
        user_id: str,
        asset_type: str,
        target_percentage: float,
        symbol: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Set or update a target allocation
        """
        try:
            # Generate ID based on what we're targeting
            if symbol:
                allocation_id = f"{asset_type}_{symbol}"
            elif category:
                allocation_id = f"{asset_type}_{category}"
            else:
                allocation_id = asset_type

            now = datetime.utcnow().isoformat()

            item = {
                'PK': f'USER#{user_id}',
                'SK': f'TARGET_ALLOCATION#{allocation_id}',
                'allocation_id': allocation_id,
                'asset_type': asset_type,
                'target_percentage': Decimal(str(target_percentage)),
                'updated_at': now
            }

            if symbol:
                item['symbol'] = symbol
            if category:
                item['category'] = category

            # Check if exists to set created_at
            existing = table.get_item(
                Key={'PK': f'USER#{user_id}', 'SK': f'TARGET_ALLOCATION#{allocation_id}'}
            ).get('Item')

            if existing:
                item['created_at'] = existing.get('created_at', now)
            else:
                item['created_at'] = now

            table.put_item(Item=item)

            return {
                'allocation_id': allocation_id,
                'asset_type': asset_type,
                'symbol': symbol,
                'category': category,
                'target_percentage': target_percentage
            }
        except Exception as e:
            logger.error(f"Error setting target allocation: {str(e)}")
            raise

    def delete_target_allocation(self, user_id: str, allocation_id: str) -> bool:
        """
        Delete a target allocation
        """
        try:
            table.delete_item(
                Key={
                    'PK': f'USER#{user_id}',
                    'SK': f'TARGET_ALLOCATION#{allocation_id}'
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting target allocation: {str(e)}")
            return False

    def calculate_rebalance(
        self,
        user_id: str,
        additional_investment: float = 0
    ) -> Dict[str, Any]:
        """
        Calculate rebalancing recommendations based on target allocations
        """
        # Get current holdings
        holdings = self._get_current_holdings(user_id)

        # Get target allocations
        targets = self.get_target_allocations(user_id)

        if not holdings:
            return {
                'status': 'no_holdings',
                'message': 'No current holdings to rebalance',
                'recommendations': []
            }

        if not targets:
            return {
                'status': 'no_targets',
                'message': 'No target allocations set',
                'recommendations': []
            }

        # Calculate total portfolio value
        total_value = sum(
            Decimal(str(h.get('current_value', 0)))
            for h in holdings
        )

        if total_value == 0:
            return {
                'status': 'zero_value',
                'message': 'Portfolio has zero value',
                'recommendations': []
            }

        # Add additional investment
        total_with_investment = total_value + Decimal(str(additional_investment))

        # Create holdings map for easy lookup
        holdings_map = {}
        for h in holdings:
            key = h.get('symbol', h.get('asset_id'))
            if key:
                holdings_map[key] = {
                    'symbol': h.get('symbol'),
                    'asset_type': h.get('asset_type'),
                    'current_value': Decimal(str(h.get('current_value', 0))),
                    'quantity': Decimal(str(h.get('quantity', 0))),
                    'current_price': Decimal(str(h.get('current_price', 0)))
                }

        # Calculate recommendations
        recommendations = []

        for target in targets:
            target_pct = Decimal(str(target['target_percentage']))
            target_value = (target_pct / 100) * total_with_investment

            # Find matching holding
            symbol = target.get('symbol')
            asset_type = target.get('asset_type')

            if symbol and symbol in holdings_map:
                # Specific symbol target
                holding = holdings_map[symbol]
                current_value = holding['current_value']
                current_pct = (current_value / total_value * 100) if total_value > 0 else Decimal('0')
                drift = current_pct - target_pct

                value_difference = target_value - current_value

                # Calculate quantity to buy/sell
                current_price = holding.get('current_price', Decimal('1'))
                if current_price > 0:
                    quantity_change = value_difference / current_price
                else:
                    quantity_change = Decimal('0')

                recommendations.append({
                    'symbol': symbol,
                    'asset_type': asset_type,
                    'target_percentage': float(target_pct),
                    'current_percentage': float(current_pct),
                    'drift': float(drift),
                    'current_value': float(current_value),
                    'target_value': float(target_value),
                    'value_difference': float(value_difference),
                    'quantity_change': float(quantity_change),
                    'current_price': float(current_price),
                    'action': 'buy' if value_difference > 0 else 'sell' if value_difference < 0 else 'hold'
                })

            elif asset_type and not symbol:
                # Asset type target (crypto vs stock)
                type_holdings = [
                    h for h in holdings
                    if h.get('asset_type') == asset_type
                ]
                current_value = sum(
                    Decimal(str(h.get('current_value', 0)))
                    for h in type_holdings
                )
                current_pct = (current_value / total_value * 100) if total_value > 0 else Decimal('0')
                drift = current_pct - target_pct

                value_difference = target_value - current_value

                recommendations.append({
                    'category': asset_type,
                    'asset_type': asset_type,
                    'target_percentage': float(target_pct),
                    'current_percentage': float(current_pct),
                    'drift': float(drift),
                    'current_value': float(current_value),
                    'target_value': float(target_value),
                    'value_difference': float(value_difference),
                    'action': 'buy' if value_difference > 0 else 'sell' if value_difference < 0 else 'hold'
                })

        # Sort by absolute drift (most out of balance first)
        recommendations.sort(key=lambda x: abs(x['drift']), reverse=True)

        # Calculate summary
        total_target_pct = sum(Decimal(str(t['target_percentage'])) for t in targets)
        max_drift = max(abs(r['drift']) for r in recommendations) if recommendations else 0

        return {
            'status': 'calculated',
            'portfolio_value': float(total_value),
            'additional_investment': additional_investment,
            'total_with_investment': float(total_with_investment),
            'total_target_percentage': float(total_target_pct),
            'max_drift': max_drift,
            'needs_rebalancing': max_drift > float(self.DEFAULT_DRIFT_THRESHOLD),
            'recommendations': recommendations
        }

    def get_portfolio_drift(self, user_id: str) -> Dict[str, Any]:
        """
        Get current portfolio drift from target allocations
        """
        result = self.calculate_rebalance(user_id)

        if result['status'] != 'calculated':
            return result

        # Filter to only items with significant drift
        threshold = float(self.DEFAULT_DRIFT_THRESHOLD)
        drifted_items = [
            r for r in result['recommendations']
            if abs(r['drift']) > threshold
        ]

        return {
            'status': 'calculated',
            'drift_threshold': threshold,
            'max_drift': result['max_drift'],
            'needs_rebalancing': result['needs_rebalancing'],
            'drifted_items': drifted_items,
            'total_items': len(result['recommendations'])
        }

    def _get_current_holdings(self, user_id: str) -> List[Dict]:
        """Get current portfolio holdings"""
        try:
            response = table.query(
                KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') &
                                      Key('SK').begins_with('ASSET#')
            )
            return response.get('Items', [])
        except Exception as e:
            logger.error(f"Error getting holdings: {str(e)}")
            return []


# Singleton instance
rebalance_service = RebalanceService()
