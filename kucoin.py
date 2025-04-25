import aiohttp
import asyncio
from aiohttp_socks import ProxyConnector
from typing import List, Dict, Optional
from decimal import Decimal
import time
from datetime import datetime, timedelta

class KucoinFundingRateFetcher:
    BASE_URL = "https://api-futures.kucoin.com/api/v1/contracts/active"

    def __init__(self, symbol):
        self.symbol = symbol

    async def fetch_history_funding(self, token, session: aiohttp.ClientSession):
        now = datetime.now()
        to_time = datetime(now.year, now.month, now.day, 23, 59, 59)
        from_time = to_time - timedelta(days=2)
        from_timestamp = int(time.mktime(from_time.timetuple())) * 1000
        to_timestamp = int(time.mktime(to_time.timetuple())) * 1000

        token = token.replace('_USDT', 'USDT')
        history_url = f'https://api-futures.kucoin.com/api/v1/contract/funding-rates?symbol={token}M&from={from_timestamp}&to={to_timestamp}'

        try:
            async with session.get(history_url) as response:
                response.raise_for_status()
                data = await response.json()
                result = {}
                for i in range(0, 4):
                    result[Decimal(data['data'][i]['fundingRate']).normalize() * 100] = data['data'][i]['timepoint']
                return result
        except Exception as e:
            pass

    async def fetch_funding_rate(self, session: aiohttp.ClientSession) -> List:
        result_list = []
        async with session.get(self.BASE_URL) as response:
            response.raise_for_status()
            data = await response.json()
            # print(data)
            for i in range(len(data['data'])):
                if data['data'][i]['fundingFeeRate'] == None:
                    continue
                symbol = data['data'][i]['symbol']
                symbol = symbol.replace('USDTM', 'USDT')
                coin = {
                    "ex": "kucoin",
                    "symbol": symbol,
                    "fundingRate": str(Decimal(data['data'][i]['fundingFeeRate']).normalize() * 100),
                    # "fundingRate": '3.0',
                    "price": str(data['data'][i]['indexPrice'])
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

    session = aiohttp.ClientSession()
    sessions.append(session)
    for symb in symbols:
        symb = symb.replace('_USDT', 'USDT')
        fetcher = KucoinFundingRateFetcher(symbols)

        tasks.append(fetcher.fetch_history_funding(symb, session))
    tasks.append(fetcher.fetch_funding_rate(session))
    results = await asyncio.gather(*tasks)

    for session in sessions:
        await session.close()

    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())

