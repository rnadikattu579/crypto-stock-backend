from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum


class TransactionType(str, Enum):
    """Transaction type enum"""
    BUY = 'buy'
    SELL = 'sell'
    TRANSFER_IN = 'transfer_in'
    TRANSFER_OUT = 'transfer_out'


class CostBasisMethod(str, Enum):
    """Cost basis calculation method"""
    FIFO = 'fifo'  # First In First Out
    LIFO = 'lifo'  # Last In First Out
    AVERAGE = 'average'  # Average Cost


class Transaction(BaseModel):
    """Transaction model representing a buy/sell/transfer"""
    transaction_id: str
    user_id: str
    asset_id: str
    symbol: str
    asset_type: Literal['crypto', 'stock']
    transaction_type: TransactionType
    quantity: float
    price: float  # Price per unit at transaction time
    total_value: float  # quantity * price
    fees: float = 0.0
    notes: Optional[str] = None
    transaction_date: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class TransactionCreate(BaseModel):
    """Request model for creating a transaction"""
    asset_id: str
    symbol: str
    asset_type: Literal['crypto', 'stock']
    transaction_type: TransactionType
    quantity: float
    price: float
    fees: float = 0.0
    notes: Optional[str] = None
    transaction_date: datetime

    class Config:
        use_enum_values = True


class TransactionUpdate(BaseModel):
    """Request model for updating a transaction"""
    quantity: Optional[float] = None
    price: Optional[float] = None
    fees: Optional[float] = None
    notes: Optional[str] = None
    transaction_date: Optional[datetime] = None


class TransactionHistory(BaseModel):
    """Response model for transaction history"""
    transactions: list[Transaction]
    total_count: int
    total_bought: float
    total_sold: float
    realized_gains: float  # Profit/loss from sold assets
    unrealized_gains: float  # Current value vs cost basis


class CostBasisCalculation(BaseModel):
    """Cost basis calculation result"""
    asset_id: str
    symbol: str
    total_quantity: float
    total_cost: float
    average_cost_per_unit: float
    method: CostBasisMethod
    remaining_lots: list[dict]  # For FIFO/LIFO tracking
