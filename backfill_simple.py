"""
Simple backfill script that directly uses boto3 without importing services
"""
import boto3
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('portfolio-tracker')

USER_ID = '7aedc2b3-7168-4244-afaf-85b719b7151e'
DAYS = 30

print(f"Backfilling {DAYS} days of history for user {USER_ID}")

# First, get current portfolio value to use as baseline
response = table.query(
    KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
    ExpressionAttributeValues={
        ':pk': USER_ID,
        ':sk': 'SNAPSHOT#combined#'
    },
    ScanIndexForward=False,
    Limit=1
)

if not response['Items']:
    print("No existing snapshots found. Please load the Analytics page first to create initial snapshot.")
    exit(1)

latest_snapshot = response['Items'][0]
baseline_value = float(latest_snapshot.get('total_value', 10000))
baseline_invested = float(latest_snapshot.get('total_invested', 8000))
asset_count = int(latest_snapshot.get('asset_count', 5))

print(f"Using baseline value: ${baseline_value:.2f}")

# Create snapshots for each day going backwards
for day_offset in range(DAYS, -1, -1):
    snapshot_date = datetime.utcnow() - timedelta(days=day_offset)
    snapshot_date = snapshot_date.replace(hour=0, minute=0, second=0, microsecond=0)
    snapshot_id = str(uuid.uuid4())

    # Add variation to make the chart interesting
    # Portfolio grows over time with daily fluctuation
    growth_factor = 0.70 + (DAYS - day_offset) * 0.01  # Start at 70%, grow to 100%
    daily_variation = 1.0 + ((hash(snapshot_date.date().isoformat()) % 10 - 5) * 0.02)  # ±10%
    value_multiplier = growth_factor * daily_variation

    # Calculate values
    total_value = baseline_value * value_multiplier
    total_invested = baseline_invested
    total_gain_loss = total_value - total_invested
    total_gain_loss_pct = (total_gain_loss / total_invested * 100) if total_invested > 0 else 0

    # Create combined snapshot
    snapshot = {
        'PK': USER_ID,
        'SK': f"SNAPSHOT#combined#{snapshot_date.date().isoformat()}",
        'entity_type': 'portfolio_snapshot',
        'snapshot_id': snapshot_id,
        'GSI1PK': f"USER#{USER_ID}",
        'GSI1SK': f"SNAPSHOT#{snapshot_date.isoformat()}",
        'user_id': USER_ID,
        'portfolio_type': 'combined',
        'snapshot_date': snapshot_date.isoformat(),
        'total_value': Decimal(str(round(total_value, 2))),
        'total_invested': Decimal(str(round(total_invested, 2))),
        'total_gain_loss': Decimal(str(round(total_gain_loss, 2))),
        'total_gain_loss_percentage': Decimal(str(round(total_gain_loss_pct, 2))),
        'asset_count': asset_count,
        'created_at': snapshot_date.isoformat()
    }

    try:
        table.put_item(Item=snapshot)
        print(f"✓ {snapshot_date.date()}: ${total_value:,.2f} ({total_gain_loss_pct:+.1f}%)")
    except Exception as e:
        print(f"✗ {snapshot_date.date()}: Error - {e}")

print(f"\nBackfill complete! Created {DAYS + 1} days of snapshots.")
print("Refresh your Analytics page to see the updated chart.")
