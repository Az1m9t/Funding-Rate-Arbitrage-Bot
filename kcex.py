import aiohttp
import asyncio
from aiohttp_socks import ProxyConnector
from typing import List, Dict, Optional
from decimal import Decimal

class KcexFundingRateFetcher:
    BASE_URL = "https://www.kcex.io/fapi/v1/contract/funding_rate"
    PRICE_URL = "https://www.kcex.io/fapi/v1/contract/deals"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
    }

    def __init__(self, symbol: str, proxy: Optional[str] = None):
        self.symbol = symbol
        self.proxy = proxy

    async def fetch_history_funding(self, token, session: aiohttp.ClientSession):
        token = token.replace('USDT', '_USDT')
        history_url = f'https://www.kcex.io/fapi/v1/contract/funding_rate/history?page_num=1&page_size=15&symbol={token}'

        async with session.get(history_url, headers=self.headers) as response:
            response.raise_for_status()
            data = await response.json()
            result = {}
            for i in range(0, 4):
                result[Decimal(data['data']['resultList'][i]['fundingRate']).normalize() * 100] = data['data']['resultList'][i]['settleTime']
            return result


    async def fetch_funding_rate(self, session: aiohttp.ClientSession) -> Dict:
        url = f"{self.BASE_URL}/{self.symbol}"
        price_url = f"{self.PRICE_URL}/{self.symbol}"
        try:
            async with session.get(url, headers=self.headers) as response:
                response.raise_for_status()
                data = await response.json()
            async with session.get(price_url, headers=self.headers) as response:
                response.raise_for_status()
                data_price = await response.json()
            if not('message' in data_price) and ('data' in data_price):
                if len(data_price['data']) > 0:
                    pass
                else:
                    self.symbol = self.symbol.replace('_USDT', 'NEW_USDT')
                    price_url = f"{self.PRICE_URL}/{self.symbol}"
                    async with session.get(price_url) as response:
                        response.raise_for_status()
                        data_price = await response.json()
            else:
                return {
                    "ex": "kcex",
                    "symbol": self.symbol,
                    "fundingRate": "Not supported",
                    "price": "Not supported"
                    # "fundingRate": 0.3
                }
            try:
                if 'data' in data and 'p' in data_price['data'][0]:
                    funding_rate = Decimal(f"{data['data']['fundingRate']}")
                    return {
                        "ex": "kcex",
                        "symbol": data['data']['symbol'],
                        "fundingRate": str(funding_rate.normalize() * 100),
                        "price": data_price['data'][0]['p']
                    }
                else:
                    return {
                        "ex": "kcex",
                        "symbol": self.symbol,
                        "fundingRate": "Not supported",
                        "price": "Not supported"
                        # "fundingRate": 0.3
                    }
            except Exception as e:
                return {
                    "ex": "kcex",
                    "symbol": self.symbol,
                    "fundingRate": "Not supported",
                    "price": "Not supported"
                    # "fundingRate": 0.3
                }
        except aiohttp.ClientError as e:
            return {
                "ex": "kcex",
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

        fetcher = KcexFundingRateFetcher(symbol, proxy)
        tasks.append(fetcher.fetch_funding_rate(session))

    results = await asyncio.gather(*tasks)

    for session in sessions:
        await session.close()

    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
#
