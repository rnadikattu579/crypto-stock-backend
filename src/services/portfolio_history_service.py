import logging
import uuid
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from models.portfolio_history import (
    PortfolioSnapshot,
    AssetSnapshot,
    HistoricalDataPoint,
    PortfolioHistory,
    HistoryRequest
)
from models.portfolio import AssetType
from services.dynamodb_service import DynamoDBService
from services.portfolio_service import PortfolioService

logger = logging.getLogger(__name__)


class PortfolioHistoryService:
    """Service for managing portfolio historical data and snapshots"""

    def __init__(self):
        self.db_service = DynamoDBService()
        self.portfolio_service = PortfolioService()

    def create_snapshot(self, user_id: str, portfolio_type: str = 'combined') -> Dict[str, Any]:
        """
        Create a snapshot of user's portfolio at current moment

        Args:
            user_id: User ID
            portfolio_type: 'crypto', 'stock', or 'combined'

        Returns:
            Dictionary with snapshot details
        """
        try:
            snapshot_id = str(uuid.uuid4())
            now = datetime.utcnow()
            snapshot_date = now.replace(hour=0, minute=0, second=0, microsecond=0)  # Normalize to midnight

            snapshots_created = []

            # Get portfolio data
            if portfolio_type in ['crypto', 'combined']:
                crypto_portfolio = self.portfolio_service.get_portfolio(user_id, AssetType.CRYPTO)
                if crypto_portfolio:
                    # Convert Portfolio object to dict
                    crypto_dict = {
                        'total_value': crypto_portfolio.total_value,
                        'total_invested': crypto_portfolio.total_invested,
                        'total_gain_loss': crypto_portfolio.total_gain_loss,
                        'total_gain_loss_percentage': crypto_portfolio.total_gain_loss_percentage,
                        'assets': [asset.dict() for asset in crypto_portfolio.assets]
                    }
                    crypto_snapshot = self._create_portfolio_snapshot(
                        snapshot_id, user_id, 'crypto', snapshot_date, crypto_dict, now
                    )
                    snapshots_created.append(crypto_snapshot)

                    # Create asset snapshots
                    for asset in crypto_portfolio.assets:
                        self._create_asset_snapshot(
                            snapshot_id, user_id, snapshot_date, asset.dict(), now
                        )

            if portfolio_type in ['stock', 'combined']:
                stock_portfolio = self.portfolio_service.get_portfolio(user_id, AssetType.STOCK)
                if stock_portfolio:
                    # Convert Portfolio object to dict
                    stock_dict = {
                        'total_value': stock_portfolio.total_value,
                        'total_invested': stock_portfolio.total_invested,
                        'total_gain_loss': stock_portfolio.total_gain_loss,
                        'total_gain_loss_percentage': stock_portfolio.total_gain_loss_percentage,
                        'assets': [asset.dict() for asset in stock_portfolio.assets]
                    }
                    stock_snapshot = self._create_portfolio_snapshot(
                        snapshot_id, user_id, 'stock', snapshot_date, stock_dict, now
                    )
                    snapshots_created.append(stock_snapshot)

                    # Create asset snapshots
                    for asset in stock_portfolio.assets:
                        self._create_asset_snapshot(
                            snapshot_id, user_id, snapshot_date, asset.dict(), now
                        )

            # Create combined snapshot if requested
            if portfolio_type == 'combined' and len(snapshots_created) > 0:
                combined_snapshot = self._create_combined_snapshot(
                    snapshot_id, user_id, snapshot_date, snapshots_created, now
                )
                snapshots_created.append(combined_snapshot)

            logger.info(f"Created {len(snapshots_created)} snapshot(s) for user {user_id}")

            return {
                'snapshot_id': snapshot_id,
                'snapshot_date': snapshot_date.isoformat(),
                'snapshots_created': len(snapshots_created),
                'portfolio_type': portfolio_type
            }

        except Exception as e:
            logger.error(f"Error creating snapshot for user {user_id}: {str(e)}")
            raise

    def _create_portfolio_snapshot(
        self,
        snapshot_id: str,
        user_id: str,
        portfolio_type: str,
        snapshot_date: datetime,
        portfolio_data: Dict[str, Any],
        created_at: datetime
    ) -> PortfolioSnapshot:
        """Create a portfolio snapshot record"""

        snapshot = PortfolioSnapshot(
            snapshot_id=snapshot_id,
            user_id=user_id,
            portfolio_type=portfolio_type,
            snapshot_date=snapshot_date,
            total_value=portfolio_data.get('total_value', 0),
            total_invested=portfolio_data.get('total_invested', 0),
            total_gain_loss=portfolio_data.get('total_gain_loss', 0),
            total_gain_loss_percentage=portfolio_data.get('total_gain_loss_percentage', 0),
            asset_count=len(portfolio_data.get('assets', [])),
            created_at=created_at
        )

        # Store in DynamoDB
        self.db_service.put_item({
            'PK': user_id,
            'SK': f"SNAPSHOT#{portfolio_type}#{snapshot_date.date().isoformat()}",
            'entity_type': 'portfolio_snapshot',
            'snapshot_id': snapshot_id,
            'GSI1PK': f"USER#{user_id}",
            'GSI1SK': f"SNAPSHOT#{snapshot_date.isoformat()}",
            **snapshot.dict()
        })

        return snapshot

    def _create_asset_snapshot(
        self,
        snapshot_id: str,
        user_id: str,
        snapshot_date: datetime,
        asset_data: Dict[str, Any],
        created_at: datetime
    ):
        """Create an asset snapshot record"""

        asset_id = asset_data.get('asset_id', asset_data.get('symbol'))
        invested = asset_data.get('quantity', 0) * asset_data.get('purchase_price', 0)
        current_value = asset_data.get('current_value', 0)
        gain_loss = current_value - invested
        gain_loss_percentage = (gain_loss / invested * 100) if invested > 0 else 0

        snapshot = AssetSnapshot(
            snapshot_id=snapshot_id,
            user_id=user_id,
            asset_id=asset_id,
            symbol=asset_data.get('symbol', ''),
            asset_type=asset_data.get('asset_type', ''),
            snapshot_date=snapshot_date,
            quantity=asset_data.get('quantity', 0),
            purchase_price=asset_data.get('purchase_price', 0),
            current_price=asset_data.get('current_price', 0),
            current_value=current_value,
            gain_loss=gain_loss,
            gain_loss_percentage=gain_loss_percentage,
            created_at=created_at
        )

        # Store in DynamoDB
        self.db_service.put_item({
            'PK': user_id,
            'SK': f"ASSET_SNAPSHOT#{asset_id}#{snapshot_date.date().isoformat()}",
            'entity_type': 'asset_snapshot',
            'snapshot_id': snapshot_id,
            **snapshot.dict()
        })

    def _create_combined_snapshot(
        self,
        snapshot_id: str,
        user_id: str,
        snapshot_date: datetime,
        snapshots: List[PortfolioSnapshot],
        created_at: datetime
    ) -> PortfolioSnapshot:
        """Create a combined snapshot from crypto and stock snapshots"""

        total_value = sum(s.total_value for s in snapshots)
        total_invested = sum(s.total_invested for s in snapshots)
        total_gain_loss = total_value - total_invested
        total_gain_loss_percentage = (total_gain_loss / total_invested * 100) if total_invested > 0 else 0
        asset_count = sum(s.asset_count for s in snapshots)

        combined = PortfolioSnapshot(
            snapshot_id=snapshot_id,
            user_id=user_id,
            portfolio_type='combined',
            snapshot_date=snapshot_date,
            total_value=total_value,
            total_invested=total_invested,
            total_gain_loss=total_gain_loss,
            total_gain_loss_percentage=total_gain_loss_percentage,
            asset_count=asset_count,
            created_at=created_at
        )

        # Store in DynamoDB
        self.db_service.put_item({
            'PK': user_id,
            'SK': f"SNAPSHOT#combined#{snapshot_date.date().isoformat()}",
            'entity_type': 'portfolio_snapshot',
            'snapshot_id': snapshot_id,
            'GSI1PK': f"USER#{user_id}",
            'GSI1SK': f"SNAPSHOT#{snapshot_date.isoformat()}",
            **combined.dict()
        })

        return combined

    def get_portfolio_history(
        self,
        user_id: str,
        request: HistoryRequest
    ) -> PortfolioHistory:
        """
        Get historical portfolio data for specified period

        Args:
            user_id: User ID
            request: History request parameters

        Returns:
            PortfolioHistory with data points
        """
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = self._get_start_date(request.period, end_date)

            # Fetch snapshots from database
            snapshots = self._fetch_snapshots(
                user_id,
                start_date,
                end_date,
                request.portfolio_type
            )

            # If no snapshots exist, create initial one
            if not snapshots:
                logger.info(f"No snapshots found for user {user_id}, creating initial snapshot")
                self.create_snapshot(user_id, request.portfolio_type)
                snapshots = self._fetch_snapshots(user_id, start_date, end_date, request.portfolio_type)

            # Convert to data points
            data_points = self._snapshots_to_data_points(snapshots, request.period)

            # Fill gaps if needed (interpolate missing days)
            data_points = self._fill_data_gaps(data_points, start_date, end_date, request.period)

            # Calculate period change
            current_value = data_points[-1].portfolio_value if data_points else 0
            start_value = data_points[0].portfolio_value if data_points else 0
            period_change = current_value - start_value
            period_change_percentage = (period_change / start_value * 100) if start_value > 0 else 0

            return PortfolioHistory(
                user_id=user_id,
                period=request.period,
                start_date=start_date,
                end_date=end_date,
                data_points=data_points,
                current_value=current_value,
                period_change=period_change,
                period_change_percentage=period_change_percentage
            )

        except Exception as e:
            logger.error(f"Error getting portfolio history for user {user_id}: {str(e)}")
            raise

    def _get_start_date(self, period: str, end_date: datetime) -> datetime:
        """Calculate start date based on period"""
        period_map = {
            '24H': timedelta(hours=24),
            '7D': timedelta(days=7),
            '30D': timedelta(days=30),
            '90D': timedelta(days=90),
            '1Y': timedelta(days=365),
            'ALL': timedelta(days=730),  # 2 years
        }
        delta = period_map.get(period, timedelta(days=30))
        return end_date - delta

    def _fetch_snapshots(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        portfolio_type: str
    ) -> List[Dict[str, Any]]:
        """Fetch snapshots from database for date range"""
        try:
            # Query snapshots for user within date range
            items = self.db_service.query(user_id, f'SNAPSHOT#{portfolio_type}#')

            # Filter by date range
            snapshots = []
            for item in items:
                if item.get('entity_type') == 'portfolio_snapshot':
                    snapshot_date = datetime.fromisoformat(item['snapshot_date'])
                    if start_date <= snapshot_date <= end_date:
                        snapshots.append(item)

            # Sort by date
            snapshots.sort(key=lambda x: x['snapshot_date'])

            return snapshots

        except Exception as e:
            logger.error(f"Error fetching snapshots: {str(e)}")
            return []

    def _snapshots_to_data_points(
        self,
        snapshots: List[Dict[str, Any]],
        period: str
    ) -> List[HistoricalDataPoint]:
        """Convert snapshots to data points"""
        data_points = []

        for snapshot in snapshots:
            timestamp = datetime.fromisoformat(snapshot['snapshot_date'])

            # Format date based on period
            if period == '24H':
                date_str = timestamp.strftime('%H:%M')
            else:
                date_str = timestamp.strftime('%b %d')

            data_points.append(HistoricalDataPoint(
                date=date_str,
                timestamp=timestamp,
                portfolio_value=snapshot.get('total_value', 0),
                invested_value=snapshot.get('total_invested', 0),
                gain_loss=snapshot.get('total_gain_loss', 0),
                gain_loss_percentage=snapshot.get('total_gain_loss_percentage', 0)
            ))

        return data_points

    def _fill_data_gaps(
        self,
        data_points: List[HistoricalDataPoint],
        start_date: datetime,
        end_date: datetime,
        period: str
    ) -> List[HistoricalDataPoint]:
        """Fill gaps in data with interpolated values"""
        if not data_points:
            return []

        # For 24H period, don't fill gaps (too granular)
        if period == '24H':
            return data_points

        # Create map of existing data points
        existing_data = {dp.timestamp.date(): dp for dp in data_points}

        # Generate complete date range
        filled_points = []
        current_date = start_date.date()
        end = end_date.date()

        last_known_value = data_points[0].portfolio_value

        while current_date <= end:
            if current_date in existing_data:
                # Use actual data
                filled_points.append(existing_data[current_date])
                last_known_value = existing_data[current_date].portfolio_value
            else:
                # Interpolate (use last known value)
                timestamp = datetime.combine(current_date, datetime.min.time())
                filled_points.append(HistoricalDataPoint(
                    date=timestamp.strftime('%b %d'),
                    timestamp=timestamp,
                    portfolio_value=last_known_value,
                    invested_value=last_known_value,  # Approximation
                    gain_loss=0,
                    gain_loss_percentage=0
                ))

            current_date += timedelta(days=1)

        return filled_points

    def create_daily_snapshots_for_all_users(self) -> Dict[str, Any]:
        """
        Create daily snapshots for all users (called by scheduler)

        Returns:
            Summary of snapshots created
        """
        try:
            logger.info("Starting daily snapshot creation for all users")

            # Get all unique user IDs from the database
            # Scan for all items and extract unique user IDs
            user_ids = set()

            # Query all items and extract user IDs
            # We look for items where PK is a user ID (not starting with special prefixes)
            scan_params = {}
            while True:
                response = self.db_service.table.scan(**scan_params)

                for item in response.get('Items', []):
                    pk = item.get('PK')
                    # User IDs are UUIDs (not prefixed keys like USER#, SNAPSHOT#, etc.)
                    if pk and not any(pk.startswith(prefix) for prefix in ['USER#', 'SNAPSHOT#', 'ASSET#', 'PRICE#']):
                        # Check if this looks like a UUID (contains hyphens and is 36 chars)
                        if len(pk) == 36 and pk.count('-') == 4:
                            user_ids.add(pk)

                # Check if there are more items to scan
                if 'LastEvaluatedKey' not in response:
                    break
                scan_params['ExclusiveStartKey'] = response['LastEvaluatedKey']

            logger.info(f"Found {len(user_ids)} users to create snapshots for")

            # Create snapshots for each user
            snapshots_created = 0
            errors = []

            for user_id in user_ids:
                try:
                    self.create_snapshot(user_id, 'combined')
                    snapshots_created += 1
                    logger.info(f"Created snapshot for user {user_id}")
                except Exception as user_error:
                    logger.error(f"Error creating snapshot for user {user_id}: {str(user_error)}")
                    errors.append({'user_id': user_id, 'error': str(user_error)})

            return {
                'success': True,
                'message': f'Daily snapshots created for {snapshots_created} users',
                'users_processed': len(user_ids),
                'snapshots_created': snapshots_created,
                'errors': len(errors),
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error creating daily snapshots: {str(e)}")
            raise
