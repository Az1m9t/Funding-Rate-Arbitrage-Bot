import aiohttp
import asyncio
from aiohttp_socks import ProxyConnector
from typing import List, Dict, Optional
from decimal import Decimal
import time
from datetime import datetime, timedelta

class HyperFundingRateFetcher:
    BASE_URL = "https://api.hyperliquid.xyz/info"
    def __init__(self, symbol):
        self.symbol = symbol

    async def fetch_history_funding(self, token, session: aiohttp.ClientSession):
        token = token.replace('_USDT', '')
        token = token.replace('USDT', '')
        # Определение временных меток
        now = datetime.now()
        to_time = datetime(now.year, now.month, now.day, 23, 59, 59)
        from_time = to_time - timedelta(days=2)
        # print(from_time)

        # Конвертируем в UNIX timestamp
        from_timestamp = int(time.mktime(from_time.timetuple()))

        headers = {
            'Content-Type': 'application/json'
        }
        data = {
            'type': 'fundingHistory',
            'coin': token,
            'startTime': from_timestamp * 1000
        }
        try:
            async with session.post(self.BASE_URL, headers=headers, json=data) as response:
                response.raise_for_status()
                data = await response.json()
                result = {}
                for i in range(len(data) - 1, len(data) - 5, -1):
                    result[Decimal(data[i]['fundingRate']).normalize() * 100] = data[i]['time']
                return result
        except Exception as e:
            pass

    async def fetch_funding_rate(self, session: aiohttp.ClientSession) -> List:
        result_list = []
        headers = {
            'Content-Type': 'application/json'
        }
        data = {
            'type': 'metaAndAssetCtxs'
        }
        async with session.post(self.BASE_URL, headers=headers, json=data) as response:
            response.raise_for_status()
            data = await response.json()
            for i in range(len(data[0]['universe'])):
                coin = {
                    "ex": "hyperliquid",
                    "symbol": data[0]['universe'][i]['name']+'USDT',
                    "fundingRate": str(Decimal(data[1][i]['funding']).normalize() * 100),
                    # "fundingRate": '3.0',
                    "price": str(data[1][i]['markPx'])
                }
                result_list.append(coin)
        return result_list



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

    # for i in range(1):
    session = aiohttp.ClientSession()
    sessions.append(session)
    for symb in symbols:
        symb = symb.replace('_USDT', '')
        fetcher = HyperFundingRateFetcher(symbols)
        # tasks.append(fetcher.fetch_funding_rate(session))
        tasks.append(fetcher.fetch_history_funding(symb, session))

    results = await asyncio.gather(*tasks)

    for session in sessions:
        await session.close()

    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
#
