import time
import aiohttp
import asyncio
import hmac
from hashlib import sha256
from typing import List, Dict, Optional
from decimal import Decimal

class BybitFundingRateFetcher:
    BASE_URL = "https://api.bybit.com/v5/market/tickers"
    HISTORY_URL = "https://api.bybit.com/v5/market/funding/history"
    api_key = ""
    secret_key = ""

    def __init__(self, symbol: str, proxy: Optional[str] = None):
        self.symbol = symbol
        self.proxy = proxy

    async def fetch_history_funding(self, token, session: aiohttp.ClientSession):
        symbol = token.replace('_USDT', 'USDT')
        history_url = f"{self.HISTORY_URL}?category=linear&symbol={symbol}&limit=4"
        async with session.get(history_url) as response:
            response.raise_for_status()
            data = await response.json()
            result = {}
            if len(data['result']['list']) > 0:
                for i in range(0, 4):
                    result[Decimal(data['result']['list'][i]['fundingRate']).normalize() * 100] = data['result']['list'][i]['fundingRateTimestamp']

                return result
            else:
                return {
                    "ex": "Bybit",
                    "symbol": self.symbol,
                    "fundingRate": "History Not supported",
                    "price": "Not supported"
                    # "fundingRate": 0.3
                }

    async def fetch_funding_rate(self, session: aiohttp.ClientSession) -> Dict:
        symbol = self.symbol.replace('_', '')
        url = f"{self.BASE_URL}?category=linear&symbol={symbol}"
        async with session.get(url) as response:
            data = await response.json()
            if len(data['result']['list']) > 0:
                return {
                    "ex": "Bybit",
                    "symbol": self.symbol,
                    # "fundingRate": 1.9,
                    "fundingRate": str(float(data['result']['list'][0]['fundingRate'])*100),
                    "price": data['result']['list'][0]['indexPrice']
                }
            else:
                return {
                    "ex": "Bybit",
                    "symbol": self.symbol,
                    "fundingRate": "Not supported",
                    "price": "Not supported"
                    # "fundingRate": 0.3
                }

def load_data(filename: str) -> List[str]:
    with open(filename, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]

async def main():
    symbols = load_data("TOKENS.txt")
    proxies = load_data("proxies.txt")

    if not symbols:
        print("No symbols found in TOKENS.txt")
        return
    if not proxies:
        print("No proxies found in proxies.txt")
        return

    batch_size = 20
    tasks = []
    sessions = []

    for i, symbol in enumerate(symbols):
        proxy_index = (i // batch_size) % len(proxies)
        proxy = proxies[proxy_index]

        session = aiohttp.ClientSession()
        sessions.append(session)

        fetcher = BybitFundingRateFetcher(symbol, proxy)
        tasks.append(fetcher.fetch_funding_rate(session))
        tasks.append(fetcher.fetch_history_funding(symbol, session))

    results = await asyncio.gather(*tasks)

    for session in sessions:
        await session.close()

    for result in results:
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
