from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PortfolioSnapshot(BaseModel):
    """Snapshot of portfolio at a specific point in time"""
    snapshot_id: str
    user_id: str
    portfolio_type: str  # 'crypto' or 'stock' or 'combined'
    snapshot_date: datetime
    total_value: float
    total_invested: float
    total_gain_loss: float
    total_gain_loss_percentage: float
    asset_count: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AssetSnapshot(BaseModel):
    """Snapshot of individual asset at a specific point in time"""
    snapshot_id: str
    user_id: str
    asset_id: str
    symbol: str
    asset_type: str  # 'crypto' or 'stock'
    snapshot_date: datetime
    quantity: float
    purchase_price: float
    current_price: float
    current_value: float
    gain_loss: float
    gain_loss_percentage: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HistoricalDataPoint(BaseModel):
    """Single data point for charts"""
    date: str
    timestamp: datetime
    portfolio_value: float
    crypto_value: Optional[float] = None
    stock_value: Optional[float] = None
    invested_value: Optional[float] = None
    gain_loss: Optional[float] = None
    gain_loss_percentage: Optional[float] = None


class PortfolioHistory(BaseModel):
    """Historical portfolio data for a specific period"""
    user_id: str
    period: str  # '24H', '7D', '30D', '90D', '1Y', 'ALL'
    start_date: datetime
    end_date: datetime
    data_points: List[HistoricalDataPoint]
    current_value: float
    period_change: float
    period_change_percentage: float


class SnapshotRequest(BaseModel):
    """Request to create a snapshot"""
    portfolio_type: str = 'combined'  # 'crypto', 'stock', or 'combined'


class HistoryRequest(BaseModel):
    """Request for historical data"""
    period: str = '30D'  # '24H', '7D', '30D', '90D', '1Y', 'ALL'
    portfolio_type: str = 'combined'  # 'crypto', 'stock', or 'combined'
    include_benchmarks: bool = False  # Include BTC and S&P 500 comparison
