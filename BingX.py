import time
import aiohttp
import asyncio
import hmac
from hashlib import sha256
from typing import List, Dict, Optional
from decimal import Decimal

class BingXFundingRateFetcher:
    BASE_URL = "https://open-api.bingx.com/openApi/swap/v2/quote/premiumIndex"
    HISTORY_URL = "https://open-api.bingx.com/openApi/swap/v2/quote/fundingRate"
    api_key = ""
    secret_key = ""

    def __init__(self, symbol: str, proxy: Optional[str] = None):
        self.symbol = symbol
        self.proxy = proxy

    async def fetch_history_funding(self, token, session: aiohttp.ClientSession):
        symbol = token.replace('USDT', '-USDT')
        history_url = f"{self.HISTORY_URL}?symbol={symbol}"
        async with session.get(history_url) as response:
            response.raise_for_status()
            data = await response.json()
            result = {}
            if len(data['data'])>0:
                for i in range(0, 4):
                    result[Decimal(data['data'][i]['fundingRate']).normalize() * 100] = data['data'][i]['fundingTime']
                return result
            else:
                return {
                    "ex": "BingX",
                    "symbol": self.symbol,
                    "fundingRate": "History Not supported",
                    "price": "Not supported"
                    # "fundingRate": 0.3
                }

    async def fetch_funding_rate(self, session: aiohttp.ClientSession) -> Dict:
        symbol = self.symbol.replace('_', '-')
        url = f"{self.BASE_URL}?symbol={symbol}"
        async with session.get(url) as response:
            data = await response.json()
            if 'lastFundingRate' in data['data']:
                return {
                    "ex": "BingX",
                    "symbol": self.symbol,
                    # "fundingRate": 1.9,
                    "fundingRate": str(float(data['data']['lastFundingRate']) * 100),
                    "price": data['data']['indexPrice']
                }
            else:
                return {
                    "ex": "BingX",
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

        fetcher = BingXFundingRateFetcher(symbol, proxy)
        tasks.append(fetcher.fetch_funding_rate(session))
        tasks.append(fetcher.fetch_history_funding(symbol, session))

    results = await asyncio.gather(*tasks)

    for session in sessions:
        await session.close()

    for result in results:
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
