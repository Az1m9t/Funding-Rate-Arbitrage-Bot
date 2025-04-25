import aiohttp
import asyncio
from aiohttp_socks import ProxyConnector
from typing import List, Dict, Optional
import time
from datetime import datetime, timedelta
from decimal import Decimal

class GateFundingRateFetcher:
    BASE_URL = 'https://www.gate.io/futures/usdt/contract'
    PRICE_URL = 'https://www.gate.io/futures/usdt/contract?contract='

    def __init__(self, symbol: str, proxy: Optional[str] = None):
        self.symbol = symbol
        self.proxy = proxy

    async def fetch_history_funding(self, token, session: aiohttp.ClientSession):
        token = token.replace('USDT', '_USDT')
        now = datetime.now()
        to_time = datetime(now.year, now.month, now.day, 23, 59, 59)
        from_time = to_time - timedelta(days=15)

        from_timestamp = int(time.mktime(from_time.timetuple()))
        to_timestamp = int(time.mktime(to_time.timetuple()))

        history_url = f"https://www.gate.io/apiw/v2/futures/usdt/funding_rate?contract={token}&from={from_timestamp}&to={to_timestamp}"
        async with session.get(history_url) as response:
            response.raise_for_status()
            data = await response.json()
            result = {}
            for i in range(0, 4):
                result[Decimal(data['data'][i]['r']).normalize() * 100] = data['data'][i]['t']
            return result

    async def fetch_funding_rate(self, session: aiohttp.ClientSession) -> Dict:
        url = f"{self.BASE_URL}?contract={self.symbol}"
        price_url = f"{self.PRICE_URL}{self.symbol}"
        try:
            async with session.get(price_url) as response:
                response.raise_for_status()
                data = await response.json()
            if 'funding_rate_indicative' in data:
                return {
                    "ex": "Gate",
                    "symbol": self.symbol,
                    # "fundingRate": 0.3
                    "fundingRate": str(float(data['funding_rate_indicative']) * 100),
                    "price": data['index_price']
                }
            else:
                return {
                    "ex": "Gate",
                    "symbol": self.symbol,
                    "fundingRate": "Not supported",
                    "price": "Not supported"
                    # "fundingRate": 0.3
                }
        except aiohttp.ClientError as e:
            return {
                "ex": "Gate",
                "symbol": self.symbol,
                "fundingRate": "Not supported",
                "price": "Not supported"
                # "fundingRate": 0.3
            }


def load_data(filename: str) -> List[str]:
    with open(filename, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


async def main():
    symbols = load_data("coins.txt")
    proxies = load_data("proxies.txt")

    batch_size = 20
    tasks = []
    sessions = []

    for i, symbol in enumerate(symbols):
        proxy_index = (i // batch_size) % len(proxies)
        proxy = proxies[proxy_index]
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        connector = ProxyConnector.from_url(proxy) if proxy else aiohttp.TCPConnector()
        session = aiohttp.ClientSession()
        sessions.append(session)

        fetcher = GateFundingRateFetcher(symbol, proxy)
        tasks.append(fetcher.fetch_funding_rate(session))

    results = await asyncio.gather(*tasks)

    for session in sessions:
        await session.close()

    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
#
