import aiohttp
import asyncio
from aiohttp_socks import ProxyConnector
from typing import List, Dict, Optional
from decimal import Decimal

class OkxFundingRateFetcher:
    BASE_URL = "https://www.okx.com/api/v5/public/funding-rate?instId="
    PRICE_URL = "https://www.okx.com/api/v5/public/mark-price?instType=SWAP&instId="
    def __init__(self, symbol: str, proxy: Optional[str] = None):
        symbol = symbol.replace('_', '-')
        self.symbol = symbol
        self.proxy = proxy

    async def fetch_history_funding(self, token, session: aiohttp.ClientSession):
        token = token.replace('USDT', '-USDT')
        token = token.replace('_USDT', '-USDT')
        history_url = f"https://www.okx.com/api/v5/public/funding-rate-history?instId={token}-SWAP&limit=4"
        async with session.get(history_url) as response:
            response.raise_for_status()
            data = await response.json()
            result = {}
            if len(data['data'])>3:
                for i in range(0, 4):
                    fund_rate = data['data'][i]['fundingRate']
                    result[Decimal(fund_rate).normalize() * 100] = data['data'][i]['fundingTime']
                return result

    async def fetch_funding_rate(self, session: aiohttp.ClientSession) -> Dict:
        url = f"{self.BASE_URL}{self.symbol}-SWAP"
        price_url = f"{self.PRICE_URL}{self.symbol}-SWAP"
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
            async with session.get(price_url) as response:
                response.raise_for_status()
                data_price = await response.json()

            if len(data_price['data'])>0:

                funding_rate = Decimal(f"{data['data'][0]['fundingRate']}")
                return {
                    "ex": "okx",
                    "symbol": self.symbol,
                    "fundingRate": str(funding_rate.normalize()*100),
                    # "fundingRate": '3.0',
                    "price": data_price['data'][0]['markPx']
                }
            else:
                return {
                    "ex": "okx",
                    "symbol": self.symbol,
                    "fundingRate": "Not supported",
                    "price": "Not supported"
                    # "fundingRate": 0.3
                }
        except aiohttp.ClientError as e:
            return {
                "ex": "okx",
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

        connector = ProxyConnector.from_url(proxy) if proxy else aiohttp.TCPConnector()
        session = aiohttp.ClientSession(connector=connector)
        sessions.append(session)
        fetcher = OkxFundingRateFetcher(symbol, proxy)
        tasks.append(fetcher.fetch_funding_rate(session))

    results = await asyncio.gather(*tasks)

    for session in sessions:
        await session.close()

    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
