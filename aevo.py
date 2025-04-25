import aiohttp
import asyncio
from aiohttp_socks import ProxyConnector
from typing import List, Dict, Optional
from decimal import Decimal

class AevoFundingRateFetcher:
    BASE_URL = "https://api.aevo.xyz/funding?instrument_name="
    PRICE_URL = "https://api.aevo.xyz/statistics?asset="

    def __init__(self, symbol: str, proxy: Optional[str] = None):
        self.symbol = symbol
        self.proxy = proxy

    async def fetch_history_funding(self, token, session: aiohttp.ClientSession):
        token = token.replace('_USDT', '-PERP')
        history_url = f'https://api.aevo.xyz/funding-history?instrument_name={token}&limit=4'
        async with session.get(history_url) as response:
            response.raise_for_status()
            data = await response.text()
            result = {}
            try:
                for i in range(0, 4):
                    result[Decimal(data['funding_history'][i][2]).normalize() * 100] = data['funding_history'][i][1]
                return result
            except Exception as e:
                pass

    async def fetch_funding_rate(self, session: aiohttp.ClientSession) -> Dict:
        token = self.symbol.replace('_USDT', '-PERP')
        url = f"{self.BASE_URL}{token}"
        token = token.replace('-PERP', '')
        price_url = f"{self.PRICE_URL}{token}&instrument_type=PERPETUAL"
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
            async with session.get(price_url) as response:
                response.raise_for_status()
                data_price = await response.json()
            try:
                if 'funding_rate' in data:
                    funding_rate = Decimal(f"{data['funding_rate']}")
                    return {
                        "ex": "aevo",
                        "symbol": self.symbol,
                        "fundingRate": str(funding_rate.normalize() * 100),
                        "price": data_price['mark_price']
                    }
                else:
                    return {
                        "ex": "aevo",
                        "symbol": self.symbol,
                        "fundingRate": "Not supported",
                        "price": "Not supported"
                        # "fundingRate": 0.3
                    }
            except Exception as e:
                return {
                    "ex": "aevo",
                    "symbol": self.symbol,
                    "fundingRate": "Not supported",
                    "price": "Not supported"
                    # "fundingRate": 0.3
                }
        except aiohttp.ClientError as e:
            return {
                "ex": "aevo",
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

    if not symbols:
        print("No symbols found in coins.txt")
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

        # connector = ProxyConnector.from_url(proxy) if proxy else aiohttp.TCPConnector()
        session = aiohttp.ClientSession()
        sessions.append(session)

        fetcher = AevoFundingRateFetcher(symbol, proxy)
        tasks.append(fetcher.fetch_funding_rate(session))
        tasks.append(fetcher.fetch_history_funding(symbol, session))

    results = await asyncio.gather(*tasks)

    for session in sessions:
        await session.close()

    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
#
