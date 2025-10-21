import uuid
from datetime import datetime, date
from typing import List, Optional, Union
from models.portfolio import Asset, AssetCreate, AssetUpdate, Portfolio, PortfolioSummary, AssetType
from services.dynamodb_service import DynamoDBService
from services.price_service import PriceService


class PortfolioService:
    def __init__(self):
        self.db = DynamoDBService()
        self.price_service = PriceService()

    def _normalize_date(self, date_input: Union[date, datetime, str]) -> datetime:
        """Convert date/datetime/string to datetime object"""
        if isinstance(date_input, datetime):
            return date_input
        elif isinstance(date_input, date):
            return datetime.combine(date_input, datetime.min.time())
        elif isinstance(date_input, str):
            # Try to parse date string
            try:
                # Try datetime format first
                return datetime.fromisoformat(date_input)
            except:
                # Try date format (YYYY-MM-DD)
                try:
                    parsed_date = datetime.strptime(date_input, '%Y-%m-%d')
                    return parsed_date
                except:
                    # Fallback to current datetime
                    return datetime.utcnow()
        return datetime.utcnow()

    def _enrich_asset_with_prices(self, asset: Asset) -> Asset:
        """Calculate current value and gain/loss for an asset"""
        try:
            prices = self.price_service.get_prices([asset.symbol], asset.asset_type.value)
            current_price = prices.get(asset.symbol.upper(), 0.0)

            asset.current_price = current_price
            asset.current_value = current_price * asset.quantity
            cost_basis = asset.purchase_price * asset.quantity

            asset.gain_loss = asset.current_value - cost_basis
            if cost_basis > 0:
                asset.gain_loss_percentage = (asset.gain_loss / cost_basis) * 100
            else:
                asset.gain_loss_percentage = 0.0

        except Exception as e:
            print(f"Error enriching asset {asset.symbol}: {str(e)}")
            asset.current_price = 0.0
            asset.current_value = 0.0
            asset.gain_loss = 0.0
            asset.gain_loss_percentage = 0.0

        return asset

    def add_asset(self, user_id: str, asset_create: AssetCreate) -> Asset:
        """Add a new asset to user's portfolio"""
        asset_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Normalize purchase_date to datetime
        purchase_datetime = self._normalize_date(asset_create.purchase_date)

        asset_data = {
            'PK': f'USER#{user_id}',
            'SK': f'ASSET#{asset_id}',
            'GSI1PK': f'ASSET#{asset_id}',
            'GSI1SK': f'USER#{user_id}',
            'asset_id': asset_id,
            'user_id': user_id,
            'asset_type': asset_create.asset_type.value,
            'symbol': asset_create.symbol.upper(),
            'quantity': asset_create.quantity,
            'purchase_price': asset_create.purchase_price,
            'purchase_date': purchase_datetime.isoformat(),
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
        }

        self.db.put_item(asset_data)

        asset = Asset(
            asset_id=asset_id,
            user_id=user_id,
            asset_type=asset_create.asset_type,
            symbol=asset_create.symbol.upper(),
            quantity=asset_create.quantity,
            purchase_price=asset_create.purchase_price,
            purchase_date=purchase_datetime,
            created_at=now,
            updated_at=now,
        )

        return self._enrich_asset_with_prices(asset)

    def get_user_assets(self, user_id: str, asset_type: Optional[AssetType] = None) -> List[Asset]:
        """Get all assets for a user, optionally filtered by type"""
        asset_items = self.db.query(f'USER#{user_id}', 'ASSET#')

        assets = []
        for item in asset_items:
            if asset_type and item['asset_type'] != asset_type.value:
                continue

            asset = Asset(
                asset_id=item['asset_id'],
                user_id=item['user_id'],
                asset_type=AssetType(item['asset_type']),
                symbol=item['symbol'],
                quantity=item['quantity'],
                purchase_price=item['purchase_price'],
                purchase_date=datetime.fromisoformat(item['purchase_date']),
                created_at=datetime.fromisoformat(item['created_at']),
                updated_at=datetime.fromisoformat(item['updated_at']),
            )

            assets.append(self._enrich_asset_with_prices(asset))

        return assets

    def get_asset(self, user_id: str, asset_id: str) -> Optional[Asset]:
        """Get a specific asset"""
        item = self.db.get_item(f'USER#{user_id}', f'ASSET#{asset_id}')

        if not item:
            return None

        asset = Asset(
            asset_id=item['asset_id'],
            user_id=item['user_id'],
            asset_type=AssetType(item['asset_type']),
            symbol=item['symbol'],
            quantity=item['quantity'],
            purchase_price=item['purchase_price'],
            purchase_date=datetime.fromisoformat(item['purchase_date']),
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at']),
        )

        return self._enrich_asset_with_prices(asset)

    def update_asset(self, user_id: str, asset_id: str, asset_update: AssetUpdate) -> Asset:
        """Update an asset"""
        updates = {'updated_at': datetime.utcnow().isoformat()}

        if asset_update.quantity is not None:
            updates['quantity'] = asset_update.quantity
        if asset_update.purchase_price is not None:
            updates['purchase_price'] = asset_update.purchase_price
        if asset_update.purchase_date is not None:
            purchase_datetime = self._normalize_date(asset_update.purchase_date)
            updates['purchase_date'] = purchase_datetime.isoformat()

        updated_item = self.db.update_item(f'USER#{user_id}', f'ASSET#{asset_id}', updates)

        asset = Asset(
            asset_id=updated_item['asset_id'],
            user_id=updated_item['user_id'],
            asset_type=AssetType(updated_item['asset_type']),
            symbol=updated_item['symbol'],
            quantity=updated_item['quantity'],
            purchase_price=updated_item['purchase_price'],
            purchase_date=datetime.fromisoformat(updated_item['purchase_date']),
            created_at=datetime.fromisoformat(updated_item['created_at']),
            updated_at=datetime.fromisoformat(updated_item['updated_at']),
        )

        return self._enrich_asset_with_prices(asset)

    def delete_asset(self, user_id: str, asset_id: str) -> None:
        """Delete an asset"""
        self.db.delete_item(f'USER#{user_id}', f'ASSET#{asset_id}')

    def get_portfolio(self, user_id: str, asset_type: Optional[AssetType] = None) -> Portfolio:
        """Get user's portfolio with calculations"""
        assets = self.get_user_assets(user_id, asset_type)

        total_value = sum(asset.current_value or 0.0 for asset in assets)
        total_invested = sum(asset.purchase_price * asset.quantity for asset in assets)
        total_gain_loss = total_value - total_invested
        total_gain_loss_percentage = (total_gain_loss / total_invested * 100) if total_invested > 0 else 0.0

        return Portfolio(
            user_id=user_id,
            assets=assets,
            total_value=total_value,
            total_invested=total_invested,
            total_gain_loss=total_gain_loss,
            total_gain_loss_percentage=total_gain_loss_percentage,
        )

    def get_portfolio_summary(self, user_id: str) -> PortfolioSummary:
        """Get summary statistics for user's portfolio"""
        all_assets = self.get_user_assets(user_id)

        crypto_assets = [a for a in all_assets if a.asset_type == AssetType.CRYPTO]
        stock_assets = [a for a in all_assets if a.asset_type == AssetType.STOCK]

        crypto_value = sum(a.current_value or 0.0 for a in crypto_assets)
        stock_value = sum(a.current_value or 0.0 for a in stock_assets)
        total_value = crypto_value + stock_value

        total_invested = sum(a.purchase_price * a.quantity for a in all_assets)
        total_gain_loss = total_value - total_invested
        total_gain_loss_percentage = (total_gain_loss / total_invested * 100) if total_invested > 0 else 0.0

        return PortfolioSummary(
            crypto_count=len(crypto_assets),
            stock_count=len(stock_assets),
            total_assets=len(all_assets),
            crypto_value=crypto_value,
            stock_value=stock_value,
            total_value=total_value,
            total_invested=total_invested,
            total_gain_loss=total_gain_loss,
            total_gain_loss_percentage=total_gain_loss_percentage,
        )
