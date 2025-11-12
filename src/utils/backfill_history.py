"""
Utility script to backfill historical portfolio snapshots
This creates snapshots for past dates to populate the history charts
"""
import sys
import os
import uuid
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.dynamodb_service import DynamoDBService
from services.portfolio_service import PortfolioService
from models.portfolio import AssetType


def backfill_snapshots_for_user(user_id: str, days: int = 30):
    """
    Create historical snapshots for a user going back N days
    Simulates daily snapshot creation with slight variations in portfolio value
    """
    db_service = DynamoDBService()
    portfolio_service = PortfolioService()

    print(f"Starting backfill for user {user_id} - {days} days")

    # Get current portfolio to use as baseline
    try:
        crypto_portfolio = portfolio_service.get_portfolio(user_id, AssetType.CRYPTO)
        stock_portfolio = portfolio_service.get_portfolio(user_id, AssetType.STOCK)
    except Exception as e:
        print(f"Error getting portfolio: {e}")
        return

    if not crypto_portfolio and not stock_portfolio:
        print(f"No portfolio found for user {user_id}")
        return

    # Create snapshots for each day going backwards
    for day_offset in range(days, -1, -1):
        snapshot_date = datetime.utcnow() - timedelta(days=day_offset)
        snapshot_date = snapshot_date.replace(hour=0, minute=0, second=0, microsecond=0)
        snapshot_id = str(uuid.uuid4())

        # Add some variation to make the chart interesting
        # Simulate portfolio growing over time with some fluctuation
        growth_factor = 1.0 - (day_offset * 0.01)  # Gradual growth
        daily_variation = 1.0 + ((day_offset % 7 - 3) * 0.02)  # Daily ups and downs
        value_multiplier = growth_factor * daily_variation

        snapshots_created = []

        # Create crypto snapshot
        if crypto_portfolio:
            crypto_value = crypto_portfolio.total_value * value_multiplier
            crypto_invested = crypto_portfolio.total_invested
            crypto_gain_loss = crypto_value - crypto_invested
            crypto_gain_loss_pct = (crypto_gain_loss / crypto_invested * 100) if crypto_invested > 0 else 0

            crypto_snapshot = {
                'PK': user_id,
                'SK': f"SNAPSHOT#crypto#{snapshot_date.date().isoformat()}",
                'entity_type': 'portfolio_snapshot',
                'snapshot_id': snapshot_id,
                'GSI1PK': f"USER#{user_id}",
                'GSI1SK': f"SNAPSHOT#{snapshot_date.isoformat()}",
                'user_id': user_id,
                'portfolio_type': 'crypto',
                'snapshot_date': snapshot_date.isoformat(),
                'total_value': crypto_value,
                'total_invested': crypto_invested,
                'total_gain_loss': crypto_gain_loss,
                'total_gain_loss_percentage': crypto_gain_loss_pct,
                'asset_count': len(crypto_portfolio.assets),
                'created_at': snapshot_date.isoformat()
            }
            db_service.put_item(crypto_snapshot)
            snapshots_created.append('crypto')

        # Create stock snapshot
        if stock_portfolio:
            stock_value = stock_portfolio.total_value * value_multiplier
            stock_invested = stock_portfolio.total_invested
            stock_gain_loss = stock_value - stock_invested
            stock_gain_loss_pct = (stock_gain_loss / stock_invested * 100) if stock_invested > 0 else 0

            stock_snapshot = {
                'PK': user_id,
                'SK': f"SNAPSHOT#stock#{snapshot_date.date().isoformat()}",
                'entity_type': 'portfolio_snapshot',
                'snapshot_id': snapshot_id,
                'GSI1PK': f"USER#{user_id}",
                'GSI1SK': f"SNAPSHOT#{snapshot_date.isoformat()}",
                'user_id': user_id,
                'portfolio_type': 'stock',
                'snapshot_date': snapshot_date.isoformat(),
                'total_value': stock_value,
                'total_invested': stock_invested,
                'total_gain_loss': stock_gain_loss,
                'total_gain_loss_percentage': stock_gain_loss_pct,
                'asset_count': len(stock_portfolio.assets),
                'created_at': snapshot_date.isoformat()
            }
            db_service.put_item(stock_snapshot)
            snapshots_created.append('stock')

        # Create combined snapshot
        if crypto_portfolio and stock_portfolio:
            combined_value = (crypto_portfolio.total_value * value_multiplier) + (stock_portfolio.total_value * value_multiplier)
            combined_invested = crypto_portfolio.total_invested + stock_portfolio.total_invested
            combined_gain_loss = combined_value - combined_invested
            combined_gain_loss_pct = (combined_gain_loss / combined_invested * 100) if combined_invested > 0 else 0

            combined_snapshot = {
                'PK': user_id,
                'SK': f"SNAPSHOT#combined#{snapshot_date.date().isoformat()}",
                'entity_type': 'portfolio_snapshot',
                'snapshot_id': snapshot_id,
                'GSI1PK': f"USER#{user_id}",
                'GSI1SK': f"SNAPSHOT#{snapshot_date.isoformat()}",
                'user_id': user_id,
                'portfolio_type': 'combined',
                'snapshot_date': snapshot_date.isoformat(),
                'total_value': combined_value,
                'total_invested': combined_invested,
                'total_gain_loss': combined_gain_loss,
                'total_gain_loss_percentage': combined_gain_loss_pct,
                'asset_count': len(crypto_portfolio.assets) + len(stock_portfolio.assets),
                'created_at': snapshot_date.isoformat()
            }
            db_service.put_item(combined_snapshot)
            snapshots_created.append('combined')

        print(f"Created snapshots for {snapshot_date.date()}: {', '.join(snapshots_created)}")

    print(f"Backfill complete! Created {days + 1} days of snapshots")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python backfill_history.py <user_id> [days]")
        print("Example: python backfill_history.py user123 30")
        sys.exit(1)

    user_id = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    backfill_snapshots_for_user(user_id, days)
