import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from models.transaction import (
    Transaction,
    TransactionCreate,
    TransactionUpdate,
    TransactionHistory,
    TransactionType,
    CostBasisMethod,
    CostBasisCalculation
)
from services.dynamodb_service import DynamoDBService

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for managing transactions and cost basis calculations"""

    def __init__(self):
        self.db_service = DynamoDBService()

    def create_transaction(self, user_id: str, transaction_data: TransactionCreate) -> Transaction:
        """
        Create a new transaction

        Args:
            user_id: User ID
            transaction_data: Transaction creation data

        Returns:
            Created Transaction object
        """
        try:
            transaction_id = str(uuid.uuid4())
            now = datetime.utcnow()

            # Calculate total value
            total_value = transaction_data.quantity * transaction_data.price

            transaction = Transaction(
                transaction_id=transaction_id,
                user_id=user_id,
                asset_id=transaction_data.asset_id,
                symbol=transaction_data.symbol,
                asset_type=transaction_data.asset_type,
                transaction_type=transaction_data.transaction_type,
                quantity=transaction_data.quantity,
                price=transaction_data.price,
                total_value=total_value,
                fees=transaction_data.fees,
                notes=transaction_data.notes,
                transaction_date=transaction_data.transaction_date,
                created_at=now,
                updated_at=now
            )

            # Store in DynamoDB
            self.db_service.put_item({
                'PK': user_id,
                'SK': f"TRANSACTION#{transaction_id}",
                'entity_type': 'transaction',
                'GSI1PK': f"ASSET#{transaction_data.asset_id}",
                'GSI1SK': f"TRANSACTION#{transaction_data.transaction_date.isoformat()}",
                **transaction.dict()
            })

            logger.info(f"Created transaction {transaction_id} for user {user_id}")
            return transaction

        except Exception as e:
            logger.error(f"Error creating transaction for user {user_id}: {str(e)}")
            raise

    def get_transaction(self, user_id: str, transaction_id: str) -> Optional[Transaction]:
        """
        Get a specific transaction by ID

        Args:
            user_id: User ID
            transaction_id: Transaction ID

        Returns:
            Transaction object or None if not found
        """
        try:
            item = self.db_service.get_item(user_id, f"TRANSACTION#{transaction_id}")

            if not item or item.get('entity_type') != 'transaction':
                return None

            return Transaction(**item)

        except Exception as e:
            logger.error(f"Error getting transaction {transaction_id}: {str(e)}")
            return None

    def get_transactions(
        self,
        user_id: str,
        asset_id: Optional[str] = None,
        asset_type: Optional[str] = None,
        transaction_type: Optional[TransactionType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Transaction]:
        """
        Get transactions with optional filtering

        Args:
            user_id: User ID
            asset_id: Filter by specific asset
            asset_type: Filter by asset type ('crypto' or 'stock')
            transaction_type: Filter by transaction type
            start_date: Filter transactions after this date
            end_date: Filter transactions before this date
            limit: Maximum number of transactions to return

        Returns:
            List of Transaction objects
        """
        try:
            # Query all transactions for user
            items = self.db_service.query(user_id, 'TRANSACTION#')

            transactions = []
            for item in items:
                if item.get('entity_type') != 'transaction':
                    continue

                # Apply filters
                if asset_id and item.get('asset_id') != asset_id:
                    continue

                if asset_type and item.get('asset_type') != asset_type:
                    continue

                if transaction_type and item.get('transaction_type') != transaction_type.value:
                    continue

                transaction_date = datetime.fromisoformat(item['transaction_date'])

                if start_date and transaction_date < start_date:
                    continue

                if end_date and transaction_date > end_date:
                    continue

                transactions.append(Transaction(**item))

                if len(transactions) >= limit:
                    break

            # Sort by transaction date (newest first)
            transactions.sort(key=lambda x: x.transaction_date, reverse=True)

            return transactions

        except Exception as e:
            logger.error(f"Error getting transactions for user {user_id}: {str(e)}")
            return []

    def update_transaction(
        self,
        user_id: str,
        transaction_id: str,
        update_data: TransactionUpdate
    ) -> Optional[Transaction]:
        """
        Update an existing transaction

        Args:
            user_id: User ID
            transaction_id: Transaction ID
            update_data: Transaction update data

        Returns:
            Updated Transaction object or None if not found
        """
        try:
            # Get existing transaction
            existing = self.get_transaction(user_id, transaction_id)
            if not existing:
                logger.warning(f"Transaction {transaction_id} not found for user {user_id}")
                return None

            # Build update dict
            updates = {}
            if update_data.quantity is not None:
                updates['quantity'] = update_data.quantity
            if update_data.price is not None:
                updates['price'] = update_data.price
            if update_data.fees is not None:
                updates['fees'] = update_data.fees
            if update_data.notes is not None:
                updates['notes'] = update_data.notes
            if update_data.transaction_date is not None:
                updates['transaction_date'] = update_data.transaction_date

            # Recalculate total_value if quantity or price changed
            quantity = updates.get('quantity', existing.quantity)
            price = updates.get('price', existing.price)
            updates['total_value'] = quantity * price
            updates['updated_at'] = datetime.utcnow()

            # Update in DynamoDB
            self.db_service.update_item(
                user_id,
                f"TRANSACTION#{transaction_id}",
                updates
            )

            # Return updated transaction
            return self.get_transaction(user_id, transaction_id)

        except Exception as e:
            logger.error(f"Error updating transaction {transaction_id}: {str(e)}")
            raise

    def delete_transaction(self, user_id: str, transaction_id: str) -> bool:
        """
        Delete a transaction

        Args:
            user_id: User ID
            transaction_id: Transaction ID

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Verify transaction exists
            existing = self.get_transaction(user_id, transaction_id)
            if not existing:
                logger.warning(f"Transaction {transaction_id} not found for user {user_id}")
                return False

            # Delete from DynamoDB
            self.db_service.delete_item(user_id, f"TRANSACTION#{transaction_id}")
            logger.info(f"Deleted transaction {transaction_id} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting transaction {transaction_id}: {str(e)}")
            return False

    def get_transaction_history(
        self,
        user_id: str,
        asset_id: Optional[str] = None,
        asset_type: Optional[str] = None
    ) -> TransactionHistory:
        """
        Get transaction history with aggregated statistics

        Args:
            user_id: User ID
            asset_id: Optional asset ID to filter
            asset_type: Optional asset type to filter

        Returns:
            TransactionHistory with aggregated data
        """
        try:
            transactions = self.get_transactions(
                user_id,
                asset_id=asset_id,
                asset_type=asset_type,
                limit=1000
            )

            total_bought = 0.0
            total_sold = 0.0

            for txn in transactions:
                if txn.transaction_type == TransactionType.BUY:
                    total_bought += txn.total_value + txn.fees
                elif txn.transaction_type == TransactionType.SELL:
                    total_sold += txn.total_value - txn.fees

            # Calculate realized gains (simplified - actual calculation needs cost basis)
            realized_gains = total_sold - total_bought

            # Unrealized gains would need current portfolio value
            unrealized_gains = 0.0

            return TransactionHistory(
                transactions=transactions,
                total_count=len(transactions),
                total_bought=total_bought,
                total_sold=total_sold,
                realized_gains=realized_gains,
                unrealized_gains=unrealized_gains
            )

        except Exception as e:
            logger.error(f"Error getting transaction history for user {user_id}: {str(e)}")
            raise

    def calculate_cost_basis(
        self,
        user_id: str,
        asset_id: str,
        method: CostBasisMethod = CostBasisMethod.FIFO
    ) -> CostBasisCalculation:
        """
        Calculate cost basis for an asset using specified method

        Args:
            user_id: User ID
            asset_id: Asset ID
            method: Cost basis calculation method (FIFO, LIFO, or AVERAGE)

        Returns:
            CostBasisCalculation with detailed cost basis info
        """
        try:
            # Get all transactions for this asset
            transactions = self.get_transactions(user_id, asset_id=asset_id, limit=1000)

            # Sort by date
            transactions.sort(key=lambda x: x.transaction_date)

            # Separate buys and sells
            buys = [t for t in transactions if t.transaction_type == TransactionType.BUY]
            sells = [t for t in transactions if t.transaction_type == TransactionType.SELL]

            if not buys:
                # No purchases yet
                return CostBasisCalculation(
                    asset_id=asset_id,
                    symbol=transactions[0].symbol if transactions else '',
                    total_quantity=0,
                    total_cost=0,
                    average_cost_per_unit=0,
                    method=method,
                    remaining_lots=[]
                )

            if method == CostBasisMethod.FIFO:
                return self._calculate_fifo(asset_id, buys, sells)
            elif method == CostBasisMethod.LIFO:
                return self._calculate_lifo(asset_id, buys, sells)
            else:  # AVERAGE
                return self._calculate_average(asset_id, buys, sells)

        except Exception as e:
            logger.error(f"Error calculating cost basis for asset {asset_id}: {str(e)}")
            raise

    def _calculate_fifo(
        self,
        asset_id: str,
        buys: List[Transaction],
        sells: List[Transaction]
    ) -> CostBasisCalculation:
        """Calculate cost basis using FIFO (First In First Out) method"""

        # Create lots from buys
        lots = []
        for buy in buys:
            lots.append({
                'date': buy.transaction_date.isoformat(),
                'quantity': buy.quantity,
                'price': buy.price,
                'total_cost': buy.total_value + buy.fees
            })

        # Process sells (remove from oldest lots first)
        for sell in sells:
            remaining_to_sell = sell.quantity

            while remaining_to_sell > 0 and lots:
                lot = lots[0]

                if lot['quantity'] <= remaining_to_sell:
                    # Consume entire lot
                    remaining_to_sell -= lot['quantity']
                    lots.pop(0)
                else:
                    # Partial lot consumption
                    lot['quantity'] -= remaining_to_sell
                    lot['total_cost'] = lot['quantity'] * lot['price']
                    remaining_to_sell = 0

        # Calculate totals from remaining lots
        total_quantity = sum(lot['quantity'] for lot in lots)
        total_cost = sum(lot['total_cost'] for lot in lots)
        average_cost = total_cost / total_quantity if total_quantity > 0 else 0

        return CostBasisCalculation(
            asset_id=asset_id,
            symbol=buys[0].symbol,
            total_quantity=total_quantity,
            total_cost=total_cost,
            average_cost_per_unit=average_cost,
            method=CostBasisMethod.FIFO,
            remaining_lots=lots
        )

    def _calculate_lifo(
        self,
        asset_id: str,
        buys: List[Transaction],
        sells: List[Transaction]
    ) -> CostBasisCalculation:
        """Calculate cost basis using LIFO (Last In First Out) method"""

        # Create lots from buys (reverse order for LIFO)
        lots = []
        for buy in reversed(buys):
            lots.append({
                'date': buy.transaction_date.isoformat(),
                'quantity': buy.quantity,
                'price': buy.price,
                'total_cost': buy.total_value + buy.fees
            })

        # Process sells (remove from newest lots first)
        for sell in reversed(sells):
            remaining_to_sell = sell.quantity

            while remaining_to_sell > 0 and lots:
                lot = lots[0]

                if lot['quantity'] <= remaining_to_sell:
                    # Consume entire lot
                    remaining_to_sell -= lot['quantity']
                    lots.pop(0)
                else:
                    # Partial lot consumption
                    lot['quantity'] -= remaining_to_sell
                    lot['total_cost'] = lot['quantity'] * lot['price']
                    remaining_to_sell = 0

        # Calculate totals from remaining lots
        total_quantity = sum(lot['quantity'] for lot in lots)
        total_cost = sum(lot['total_cost'] for lot in lots)
        average_cost = total_cost / total_quantity if total_quantity > 0 else 0

        return CostBasisCalculation(
            asset_id=asset_id,
            symbol=buys[0].symbol,
            total_quantity=total_quantity,
            total_cost=total_cost,
            average_cost_per_unit=average_cost,
            method=CostBasisMethod.LIFO,
            remaining_lots=lots
        )

    def _calculate_average(
        self,
        asset_id: str,
        buys: List[Transaction],
        sells: List[Transaction]
    ) -> CostBasisCalculation:
        """Calculate cost basis using Average Cost method"""

        # Calculate total bought
        total_quantity_bought = sum(buy.quantity for buy in buys)
        total_cost_bought = sum(buy.total_value + buy.fees for buy in buys)

        # Calculate total sold
        total_quantity_sold = sum(sell.quantity for sell in sells)

        # Remaining quantity
        total_quantity = total_quantity_bought - total_quantity_sold

        # Average cost per unit
        average_cost = total_cost_bought / total_quantity_bought if total_quantity_bought > 0 else 0

        # Total cost of remaining units
        total_cost = total_quantity * average_cost

        # Create a single lot representing average
        lots = [{
            'date': 'average',
            'quantity': total_quantity,
            'price': average_cost,
            'total_cost': total_cost
        }] if total_quantity > 0 else []

        return CostBasisCalculation(
            asset_id=asset_id,
            symbol=buys[0].symbol,
            total_quantity=total_quantity,
            total_cost=total_cost,
            average_cost_per_unit=average_cost,
            method=CostBasisMethod.AVERAGE,
            remaining_lots=lots
        )
