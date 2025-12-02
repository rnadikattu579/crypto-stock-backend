"""
Tax Reporting Service
Calculates capital gains/losses, generates tax reports, and detects wash sales
"""
import logging
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


class TaxService:
    """Service for tax calculations and reporting"""

    # IRS wash sale rule: 30 days before and after
    WASH_SALE_WINDOW_DAYS = 30

    def get_tax_year_summary(self, user_id: str, tax_year: int) -> Dict[str, Any]:
        """
        Get comprehensive tax summary for a given year
        """
        # Get all transactions for the year
        start_date = datetime(tax_year, 1, 1)
        end_date = datetime(tax_year, 12, 31, 23, 59, 59)

        transactions = self._get_transactions_for_period(user_id, start_date, end_date)

        # Separate buys and sells
        buys = [t for t in transactions if t['transaction_type'] in ['buy', 'transfer_in']]
        sells = [t for t in transactions if t['transaction_type'] in ['sell', 'transfer_out']]

        # Calculate gains/losses for each sell
        capital_gains = []
        total_short_term_gain = Decimal('0')
        total_long_term_gain = Decimal('0')
        total_short_term_loss = Decimal('0')
        total_long_term_loss = Decimal('0')

        # Get all historical buys to calculate cost basis
        all_buys = self._get_all_buys_before(user_id, end_date)

        for sell in sells:
            gain_info = self._calculate_gain_for_sale(sell, all_buys, tax_year)
            if gain_info:
                capital_gains.append(gain_info)

                gain_amount = Decimal(str(gain_info['gain_loss']))
                if gain_info['holding_period'] == 'short_term':
                    if gain_amount >= 0:
                        total_short_term_gain += gain_amount
                    else:
                        total_short_term_loss += abs(gain_amount)
                else:
                    if gain_amount >= 0:
                        total_long_term_gain += gain_amount
                    else:
                        total_long_term_loss += abs(gain_amount)

        # Detect wash sales
        wash_sales = self._detect_wash_sales(sells, all_buys)
        wash_sale_disallowed = sum(Decimal(str(ws['disallowed_loss'])) for ws in wash_sales)

        # Calculate totals
        net_short_term = total_short_term_gain - total_short_term_loss
        net_long_term = total_long_term_gain - total_long_term_loss

        return {
            'tax_year': tax_year,
            'summary': {
                'total_proceeds': float(sum(Decimal(str(s['total_value'])) for s in sells)),
                'total_cost_basis': float(sum(Decimal(str(cg['cost_basis'])) for cg in capital_gains)),
                'short_term': {
                    'gains': float(total_short_term_gain),
                    'losses': float(total_short_term_loss),
                    'net': float(net_short_term)
                },
                'long_term': {
                    'gains': float(total_long_term_gain),
                    'losses': float(total_long_term_loss),
                    'net': float(net_long_term)
                },
                'total_net_gain_loss': float(net_short_term + net_long_term),
                'wash_sale_disallowed': float(wash_sale_disallowed),
                'adjusted_net_gain_loss': float(net_short_term + net_long_term + wash_sale_disallowed)
            },
            'capital_gains': capital_gains,
            'wash_sales': wash_sales,
            'transaction_count': {
                'buys': len(buys),
                'sells': len(sells),
                'total': len(transactions)
            }
        }

    def generate_form_8949(self, user_id: str, tax_year: int) -> List[Dict[str, Any]]:
        """
        Generate Form 8949 data (Sales and Other Dispositions of Capital Assets)
        Returns data formatted for IRS Form 8949
        """
        summary = self.get_tax_year_summary(user_id, tax_year)

        form_8949_entries = []

        for gain in summary['capital_gains']:
            # Check if this sale has wash sale adjustment
            wash_adjustment = Decimal('0')
            for ws in summary['wash_sales']:
                if ws['sell_transaction_id'] == gain.get('transaction_id'):
                    wash_adjustment = Decimal(str(ws['disallowed_loss']))
                    break

            entry = {
                'description': f"{gain['quantity']} {gain['symbol']}",
                'date_acquired': gain['acquisition_date'],
                'date_sold': gain['sale_date'],
                'proceeds': gain['proceeds'],
                'cost_basis': gain['cost_basis'],
                'adjustment_code': 'W' if wash_adjustment > 0 else '',
                'adjustment_amount': float(wash_adjustment),
                'gain_or_loss': gain['gain_loss'] + float(wash_adjustment),
                'holding_period': gain['holding_period'],
                'asset_type': gain['asset_type'],
                'symbol': gain['symbol']
            }
            form_8949_entries.append(entry)

        # Sort by date sold
        form_8949_entries.sort(key=lambda x: x['date_sold'])

        return form_8949_entries

    def get_unrealized_gains(self, user_id: str, as_of_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Calculate unrealized gains/losses for current holdings
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        # Get current holdings
        holdings = self._get_current_holdings(user_id)

        unrealized_gains = []
        total_unrealized = Decimal('0')

        for holding in holdings:
            # Calculate cost basis for this holding
            cost_basis = self._get_holding_cost_basis(user_id, holding['asset_id'])
            current_value = Decimal(str(holding.get('current_value', 0)))
            unrealized = current_value - cost_basis

            # Determine if it would be short or long term if sold today
            acquisition_date = holding.get('first_purchase_date')
            if acquisition_date:
                acq_date = datetime.fromisoformat(acquisition_date.replace('Z', '+00:00'))
                days_held = (as_of_date - acq_date).days
                holding_period = 'long_term' if days_held > 365 else 'short_term'
            else:
                holding_period = 'unknown'

            unrealized_gains.append({
                'symbol': holding['symbol'],
                'asset_type': holding['asset_type'],
                'quantity': holding['quantity'],
                'cost_basis': float(cost_basis),
                'current_value': float(current_value),
                'unrealized_gain_loss': float(unrealized),
                'gain_loss_percentage': float((unrealized / cost_basis * 100) if cost_basis > 0 else 0),
                'holding_period': holding_period
            })

            total_unrealized += unrealized

        return {
            'as_of_date': as_of_date.isoformat(),
            'total_unrealized_gain_loss': float(total_unrealized),
            'holdings': unrealized_gains
        }

    def get_tax_loss_harvesting_opportunities(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Identify assets with unrealized losses that could be sold for tax benefits
        """
        unrealized = self.get_unrealized_gains(user_id)

        opportunities = []
        for holding in unrealized['holdings']:
            if holding['unrealized_gain_loss'] < 0:
                # Check for wash sale risk
                wash_sale_risk = self._check_wash_sale_risk(
                    user_id,
                    holding['symbol'],
                    datetime.utcnow()
                )

                opportunities.append({
                    'symbol': holding['symbol'],
                    'asset_type': holding['asset_type'],
                    'unrealized_loss': abs(holding['unrealized_gain_loss']),
                    'quantity': holding['quantity'],
                    'current_value': holding['current_value'],
                    'cost_basis': holding['cost_basis'],
                    'potential_tax_savings_estimate': abs(holding['unrealized_gain_loss']) * 0.25,  # Rough estimate
                    'wash_sale_risk': wash_sale_risk,
                    'holding_period': holding['holding_period']
                })

        # Sort by largest loss first
        opportunities.sort(key=lambda x: x['unrealized_loss'], reverse=True)

        return opportunities

    def _get_transactions_for_period(self, user_id: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get transactions within a date range"""
        try:
            response = table.query(
                KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') &
                                      Key('SK').begins_with('TRANSACTION#')
            )

            transactions = []
            for item in response.get('Items', []):
                tx_date = datetime.fromisoformat(item['transaction_date'].replace('Z', '+00:00'))
                if start_date <= tx_date <= end_date:
                    transactions.append(item)

            return transactions
        except Exception as e:
            logger.error(f"Error getting transactions: {str(e)}")
            return []

    def _get_all_buys_before(self, user_id: str, before_date: datetime) -> List[Dict]:
        """Get all buy transactions before a given date"""
        try:
            response = table.query(
                KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') &
                                      Key('SK').begins_with('TRANSACTION#')
            )

            buys = []
            for item in response.get('Items', []):
                if item['transaction_type'] in ['buy', 'transfer_in']:
                    tx_date = datetime.fromisoformat(item['transaction_date'].replace('Z', '+00:00'))
                    if tx_date <= before_date:
                        buys.append(item)

            # Sort by date (oldest first for FIFO)
            buys.sort(key=lambda x: x['transaction_date'])
            return buys
        except Exception as e:
            logger.error(f"Error getting buys: {str(e)}")
            return []

    def _calculate_gain_for_sale(self, sell: Dict, all_buys: List[Dict], tax_year: int) -> Optional[Dict]:
        """Calculate capital gain/loss for a single sale using FIFO"""
        symbol = sell['symbol']
        sell_quantity = Decimal(str(sell['quantity']))
        sell_price = Decimal(str(sell['price']))
        sell_date = datetime.fromisoformat(sell['transaction_date'].replace('Z', '+00:00'))

        # Filter buys for this symbol
        symbol_buys = [b for b in all_buys if b['symbol'] == symbol]

        if not symbol_buys:
            return None

        # FIFO matching
        remaining_to_match = sell_quantity
        total_cost_basis = Decimal('0')
        earliest_acquisition = None

        for buy in symbol_buys:
            if remaining_to_match <= 0:
                break

            buy_quantity = Decimal(str(buy.get('remaining_quantity', buy['quantity'])))
            buy_price = Decimal(str(buy['price']))
            buy_date = datetime.fromisoformat(buy['transaction_date'].replace('Z', '+00:00'))

            if buy_quantity <= 0:
                continue

            matched_quantity = min(remaining_to_match, buy_quantity)
            cost = matched_quantity * buy_price
            total_cost_basis += cost
            remaining_to_match -= matched_quantity

            if earliest_acquisition is None or buy_date < earliest_acquisition:
                earliest_acquisition = buy_date

        if earliest_acquisition is None:
            return None

        # Calculate gain/loss
        proceeds = sell_quantity * sell_price
        gain_loss = proceeds - total_cost_basis

        # Determine holding period
        days_held = (sell_date - earliest_acquisition).days
        holding_period = 'long_term' if days_held > 365 else 'short_term'

        return {
            'transaction_id': sell.get('transaction_id', ''),
            'symbol': symbol,
            'asset_type': sell['asset_type'],
            'quantity': float(sell_quantity),
            'acquisition_date': earliest_acquisition.strftime('%Y-%m-%d'),
            'sale_date': sell_date.strftime('%Y-%m-%d'),
            'proceeds': float(proceeds),
            'cost_basis': float(total_cost_basis),
            'gain_loss': float(gain_loss),
            'holding_period': holding_period,
            'days_held': days_held
        }

    def _detect_wash_sales(self, sells: List[Dict], all_buys: List[Dict]) -> List[Dict]:
        """
        Detect wash sales based on IRS 30-day rule
        A wash sale occurs when you sell at a loss and buy substantially identical
        securities within 30 days before or after the sale
        """
        wash_sales = []

        for sell in sells:
            sell_date = datetime.fromisoformat(sell['transaction_date'].replace('Z', '+00:00'))
            symbol = sell['symbol']

            # Calculate if this sale was at a loss
            gain_info = self._calculate_gain_for_sale(sell, all_buys, sell_date.year)
            if not gain_info or gain_info['gain_loss'] >= 0:
                continue  # Not a loss, skip

            loss_amount = abs(Decimal(str(gain_info['gain_loss'])))

            # Check for replacement buys within wash sale window
            window_start = sell_date - timedelta(days=self.WASH_SALE_WINDOW_DAYS)
            window_end = sell_date + timedelta(days=self.WASH_SALE_WINDOW_DAYS)

            replacement_buys = []
            for buy in all_buys:
                if buy['symbol'] != symbol:
                    continue
                buy_date = datetime.fromisoformat(buy['transaction_date'].replace('Z', '+00:00'))
                if window_start <= buy_date <= window_end and buy_date != sell_date:
                    replacement_buys.append(buy)

            if replacement_buys:
                # Wash sale detected
                wash_sales.append({
                    'sell_transaction_id': sell.get('transaction_id', ''),
                    'symbol': symbol,
                    'sale_date': sell_date.strftime('%Y-%m-%d'),
                    'loss_amount': float(loss_amount),
                    'disallowed_loss': float(loss_amount),  # Full loss disallowed
                    'replacement_purchases': [
                        {
                            'date': datetime.fromisoformat(b['transaction_date'].replace('Z', '+00:00')).strftime('%Y-%m-%d'),
                            'quantity': b['quantity'],
                            'price': b['price']
                        }
                        for b in replacement_buys
                    ]
                })

        return wash_sales

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

    def _get_holding_cost_basis(self, user_id: str, asset_id: str) -> Decimal:
        """Calculate cost basis for a specific holding using FIFO"""
        all_buys = self._get_all_buys_before(user_id, datetime.utcnow())
        asset_buys = [b for b in all_buys if b.get('asset_id') == asset_id]

        total_cost = Decimal('0')
        for buy in asset_buys:
            quantity = Decimal(str(buy['quantity']))
            price = Decimal(str(buy['price']))
            fees = Decimal(str(buy.get('fees', 0)))
            total_cost += (quantity * price) + fees

        return total_cost

    def _check_wash_sale_risk(self, user_id: str, symbol: str, as_of_date: datetime) -> bool:
        """Check if selling this asset now would risk a wash sale"""
        window_start = as_of_date - timedelta(days=self.WASH_SALE_WINDOW_DAYS)

        # Check for recent buys
        all_buys = self._get_all_buys_before(user_id, as_of_date)

        for buy in all_buys:
            if buy['symbol'] != symbol:
                continue
            buy_date = datetime.fromisoformat(buy['transaction_date'].replace('Z', '+00:00'))
            if buy_date >= window_start:
                return True  # Recent buy within 30 days

        return False


# Singleton instance
tax_service = TaxService()
