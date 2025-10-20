import requests
import yfinance as yf
from typing import Dict, List
from datetime import datetime
import os


class PriceService:
    def __init__(self):
        self.coingecko_api_key = os.environ.get('COINGECKO_API_KEY', '')
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"

    def get_crypto_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current prices for crypto symbols from CoinGecko
        symbols: list of crypto symbols (e.g., ['BTC', 'ETH', 'ADA'])
        """
        prices = {}

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
        }

        coin_ids = []
        for symbol in symbols:
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

            if self.coingecko_api_key:
                params['x_cg_pro_api_key'] = self.coingecko_api_key

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Map back to original symbols
            for i, symbol in enumerate(symbols):
                coin_id = coin_ids[i]
                if coin_id in data and 'usd' in data[coin_id]:
                    prices[symbol.upper()] = data[coin_id]['usd']
                else:
                    prices[symbol.upper()] = 0.0

        except Exception as e:
            print(f"Error fetching crypto prices: {str(e)}")
            # Return zero prices on error
            for symbol in symbols:
                prices[symbol.upper()] = 0.0

        return prices

    def get_stock_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current prices for stock symbols using yfinance
        symbols: list of stock tickers (e.g., ['AAPL', 'GOOGL', 'MSFT'])
        """
        prices = {}

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")

                if not hist.empty:
                    # Get the most recent closing price
                    prices[symbol.upper()] = float(hist['Close'].iloc[-1])
                else:
                    # Try to get current price from info
                    info = ticker.info
                    price = info.get('currentPrice') or info.get('regularMarketPrice')
                    prices[symbol.upper()] = float(price) if price else 0.0

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
