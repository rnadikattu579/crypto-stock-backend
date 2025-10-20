from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AssetType(str, Enum):
    CRYPTO = "crypto"
    STOCK = "stock"


class Asset(BaseModel):
    asset_id: Optional[str] = None
    user_id: str
    asset_type: AssetType
    symbol: str = Field(..., description="Stock ticker or crypto symbol")
    name: Optional[str] = None
    quantity: float = Field(..., gt=0)
    purchase_price: float = Field(..., gt=0)
    purchase_date: datetime
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    gain_loss: Optional[float] = None
    gain_loss_percentage: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AssetCreate(BaseModel):
    asset_type: AssetType
    symbol: str
    quantity: float = Field(..., gt=0)
    purchase_price: float = Field(..., gt=0)
    purchase_date: datetime


class AssetUpdate(BaseModel):
    quantity: Optional[float] = Field(None, gt=0)
    purchase_price: Optional[float] = Field(None, gt=0)
    purchase_date: Optional[datetime] = None


class Portfolio(BaseModel):
    user_id: str
    assets: List[Asset]
    total_value: float
    total_invested: float
    total_gain_loss: float
    total_gain_loss_percentage: float


class PortfolioSummary(BaseModel):
    crypto_count: int
    stock_count: int
    total_assets: int
    crypto_value: float
    stock_value: float
    total_value: float
    total_invested: float
    total_gain_loss: float
    total_gain_loss_percentage: float


class PriceRequest(BaseModel):
    symbols: List[str]
    asset_type: AssetType


class PriceResponse(BaseModel):
    symbol: str
    price: float
    currency: str = "USD"
    timestamp: datetime
