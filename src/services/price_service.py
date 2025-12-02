import requests
from typing import Dict, List
from datetime import datetime, timedelta
import os
import json


class PriceService:
    # Class-level cache shared across instances
    _price_cache = {}
    _cache_timestamps = {}
    _cache_ttl_seconds = 60  # Cache prices for 60 seconds

    def __init__(self):
        self.coingecko_api_key = os.environ.get('COINGECKO_API_KEY', '')
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"

    def _get_cached_price(self, symbol: str, asset_type: str) -> float:
        """Get price from cache if available and not expired"""
        cache_key = f"{asset_type}:{symbol.upper()}"

        if cache_key in self._price_cache:
            cached_time = self._cache_timestamps.get(cache_key)
            if cached_time and (datetime.utcnow() - cached_time).total_seconds() < self._cache_ttl_seconds:
                return self._price_cache[cache_key]

        return None

    def _set_cached_price(self, symbol: str, asset_type: str, price: float):
        """Store price in cache"""
        cache_key = f"{asset_type}:{symbol.upper()}"
        self._price_cache[cache_key] = price
        self._cache_timestamps[cache_key] = datetime.utcnow()

    def get_crypto_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current prices for crypto symbols from CoinGecko (with caching)
        symbols: list of crypto symbols (e.g., ['BTC', 'ETH', 'ADA'])
        """
        prices = {}
        symbols_to_fetch = []

        # Check cache first
        for symbol in symbols:
            cached_price = self._get_cached_price(symbol, 'crypto')
            if cached_price is not None:
                prices[symbol.upper()] = cached_price
            else:
                symbols_to_fetch.append(symbol)

        # If all prices are cached, return immediately
        if not symbols_to_fetch:
            return prices

        # Convert symbols to CoinGecko IDs (simplified mapping)
        symbol_to_id = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'ADA': 'cardano',
            'DOT': 'polkadot',
            'SOL': 'solana',
            'MATIC': 'matic-network',
            'AVAX': 'avalanche-2',
            'LINK': 'chainlink',
            'UNI': 'uniswap',
            'ATOM': 'cosmos',
            'DOGE': 'dogecoin',
            'XRP': 'ripple',
            'LTC': 'litecoin',
            'BCH': 'bitcoin-cash',
            'USDT': 'tether',
            'USDC': 'usd-coin',
        }

        coin_ids = []
        for symbol in symbols_to_fetch:
            symbol_upper = symbol.upper()
            if symbol_upper in symbol_to_id:
                coin_ids.append(symbol_to_id[symbol_upper])
            else:
                # Try to search for the coin
                coin_ids.append(symbol.lower())

        if not coin_ids:
            return prices

        try:
            # Use simple price endpoint (works with free tier)
            url = f"{self.coingecko_base_url}/simple/price"
            params = {
                'ids': ','.join(coin_ids),
                'vs_currencies': 'usd'
            }

            # Only add API key if it's actually set and not empty
            if self.coingecko_api_key and len(self.coingecko_api_key.strip()) > 0:
                params['x_cg_pro_api_key'] = self.coingecko_api_key

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Map back to original symbols and cache results
            for i, symbol in enumerate(symbols_to_fetch):
                coin_id = coin_ids[i]
                if coin_id in data and 'usd' in data[coin_id]:
                    price = data[coin_id]['usd']
                    prices[symbol.upper()] = price
                    self._set_cached_price(symbol, 'crypto', price)
                else:
                    prices[symbol.upper()] = 0.0

        except Exception as e:
            print(f"Error fetching crypto prices: {str(e)}")
            # Return zero prices on error
            for symbol in symbols_to_fetch:
                prices[symbol.upper()] = 0.0

        return prices

    def get_stock_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current prices for stock symbols using Yahoo Finance API (with caching)
        symbols: list of stock tickers (e.g., ['AAPL', 'GOOGL', 'MSFT'])
        """
        prices = {}
        symbols_to_fetch = []

        # Check cache first
        for symbol in symbols:
            cached_price = self._get_cached_price(symbol, 'stock')
            if cached_price is not None:
                prices[symbol.upper()] = cached_price
            else:
                symbols_to_fetch.append(symbol)

        # If all prices are cached, return immediately
        if not symbols_to_fetch:
            return prices

        for symbol in symbols_to_fetch:
            try:
                # Use Yahoo Finance Quote API
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.upper()}"
                params = {
                    'interval': '1d',
                    'range': '1d'
                }

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }

                response = requests.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()

                data = response.json()

                # Extract price from response
                if 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
                    result = data['chart']['result'][0]

                    # Try to get current price from meta
                    if 'meta' in result and 'regularMarketPrice' in result['meta']:
                        price = float(result['meta']['regularMarketPrice'])
                        prices[symbol.upper()] = price
                        self._set_cached_price(symbol, 'stock', price)
                    # Fallback to latest close price
                    elif 'indicators' in result and 'quote' in result['indicators']:
                        quote = result['indicators']['quote'][0]
                        if 'close' in quote and quote['close']:
                            # Get the last non-null close price
                            close_prices = [p for p in quote['close'] if p is not None]
                            if close_prices:
                                price = float(close_prices[-1])
                                prices[symbol.upper()] = price
                                self._set_cached_price(symbol, 'stock', price)
                            else:
                                prices[symbol.upper()] = 0.0
                        else:
                            prices[symbol.upper()] = 0.0
                    else:
                        prices[symbol.upper()] = 0.0
                else:
                    prices[symbol.upper()] = 0.0

            except Exception as e:
                print(f"Error fetching price for {symbol}: {str(e)}")
                prices[symbol.upper()] = 0.0

        return prices

    def get_prices(self, symbols: List[str], asset_type: str) -> Dict[str, float]:
        """
        Get prices based on asset type
        """
        if asset_type.lower() == 'crypto':
            return self.get_crypto_prices(symbols)
        elif asset_type.lower() == 'stock':
            return self.get_stock_prices(symbols)
        else:
            raise ValueError(f"Invalid asset type: {asset_type}")

# Create a singleton instance for import
price_service = PriceService()
